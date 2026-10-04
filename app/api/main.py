"""Local-only API for synthetic banking reviews and their audit records."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
from threading import BoundedSemaphore
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.audit.customer_review import AuditedReviewError, run_customer_review
from app.audit.review import ReviewAuditStore
from app.graph.review_explanation import serialize
from app.api.auth import AuthStore, COOKIE, SESSION_SECONDS, can_access


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str = Field(pattern=r"^C[0-9]{3}$", min_length=4, max_length=4)
    mode: Literal["deterministic", "deepseek"] = "deterministic"
    paid_consent: StrictBool = False


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=1, max_length=256)


class ReviewResponse(BaseModel):
    request_id: UUID
    status: Literal["succeeded", "partial_success"]
    report: dict


class AuditResponse(BaseModel):
    request_id: UUID
    customer_id: str
    mode: Literal["deterministic", "deepseek"]
    status: Literal["started", "succeeded", "partial_success", "failed"]
    created_at: datetime
    finished_at: datetime | None
    elapsed_ms: int | None
    sql_execution_status: str
    error_code: str | None
    metadata: dict
    policy_refs: list[dict]
    report: dict | None


def json_safe(value):
    # FastAPI's generic Decimal conversion can lose precision; use the existing serializer.
    return json.loads(json.dumps(value, default=serialize, ensure_ascii=False))


def create_app(review_runner=None, audit_store=None, auth_store=None):
    runner = review_runner or run_customer_review
    store = audit_store or ReviewAuditStore()
    auth = auth_store or AuthStore()
    review_slots = BoundedSemaphore(2)
    api = FastAPI(title="Banking Risk Copilot", version="0.1.0")
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    static = Path(__file__).resolve().parents[1] / "web/static"
    api.mount("/assets", StaticFiles(directory=static), name="assets")

    @api.get("/", include_in_schema=False)
    def workbench():
        return FileResponse(static / "index.html")

    @api.middleware("http")
    async def local_browser_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if (origin and origin != str(request.base_url).rstrip("/")) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(status_code=403, content={"detail": {"code": "cross_origin_not_allowed"}})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        return response

    @api.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Do not echo unexpected request bodies (which could contain pasted credentials).
        return JSONResponse(status_code=422, content={"detail": {"code": "invalid_request"}})

    @api.get("/health")
    def health():
        root = Path(__file__).resolve().parents[2]
        return {"status": "ok", "scope": "process_liveness_only", "app":"banking-risk-copilot",
                "instance":hashlib.sha256(str(root).encode()).hexdigest()[:16]}

    @api.get("/ready")
    def readiness():
        from app.sql.database import connect
        try:
            with connect() as connection:
                if not connection.execute("SELECT 1 FROM policy_retrieval_state WHERE singleton").fetchone():
                    raise ValueError("Missing corpus")
            with connect("audit") as connection:
                connection.execute("SELECT request_id FROM audit_logs LIMIT 1")
            with auth.connect() as connection:
                if not connection.execute("SELECT 1 FROM users WHERE active=1 AND role='admin' LIMIT 1").fetchone():
                    raise ValueError("Missing accounts")
        except Exception:
            raise HTTPException(503, detail={"code":"runtime_dependencies_unavailable"}) from None
        return {"status":"ready", "scope":"database_read_access_policy_index_and_accounts", "provider":"not_checked_optional"}

    def identity(request: Request):
        try:
            user = auth.identity(request.cookies.get(COOKIE))
        except Exception:
            raise HTTPException(503, detail={"code": "authentication_unavailable"}) from None
        if user is None:
            raise HTTPException(401, detail={"code": "login_required"})
        return user

    @api.post("/auth/login")
    def login(body: LoginRequest, request: Request, response: Response):
        try:
            token, error = auth.login(body.username, body.password, request.client.host if request.client else "local")
        except Exception:
            raise HTTPException(503, detail={"code": "authentication_unavailable"}) from None
        if error:
            raise HTTPException(429 if error == "login_throttled" else 401, detail={"code": error})
        old = request.cookies.get(COOKIE)
        if old:
            auth.logout(old)
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite="strict", secure=request.url.scheme == "https", path="/")
        return {"status": "signed_in"}

    @api.get("/auth/me")
    def me(user=Depends(identity)):
        return user

    @api.post("/auth/logout")
    def logout(request: Request, response: Response, user=Depends(identity)):
        auth.logout(request.cookies[COOKIE])
        response.delete_cookie(COOKIE, path="/")
        return {"status": "signed_out"}

    @api.post("/reviews", response_model=ReviewResponse, status_code=201)
    def create_review(body: ReviewRequest, request: Request, user=Depends(identity)):
        if not can_access(user, body.customer_id):
            raise HTTPException(403, detail={"code": "customer_access_denied"})
        if body.mode == "deepseek" and not body.paid_consent:
            raise HTTPException(422, detail={"code": "paid_consent_required"})
        if not review_slots.acquire(blocking=False):
            raise HTTPException(status_code=429, detail={"code": "review_busy"}, headers={"Retry-After": "5"})
        try:
            report = runner(body.customer_id, body.mode, actor={"username": user["username"], "role": user["role"]})
        except AuditedReviewError as error:
            status = {"customer_not_found": 404, "review_capacity_exceeded": 422,
                      "database_error": 503, "audit_start_unconfirmed": 503,
                      "audit_completion_unconfirmed": 503,
                      "invalid_request_or_configuration": 503}.get(error.code, 500)
            raise HTTPException(status_code=status, detail={"code": error.code, "request_id": error.request_id}) from None
        except Exception:
            raise HTTPException(status_code=500, detail={"code": "internal_error"}) from None
        finally:
            review_slots.release()
        if not can_access(identity(request), body.customer_id):
            raise HTTPException(403, detail={"code": "customer_access_denied"})
        return {"request_id": report["request_id"], "status": report["audit"]["status"], "report": json_safe(report)}

    @api.get("/reviews/{request_id}", response_model=AuditResponse)
    def read_review(request_id: UUID, user=Depends(identity)):
        try:
            row = store.read(str(request_id))
        except Exception:
            raise HTTPException(status_code=503, detail={"code": "audit_read_unavailable", "request_id": str(request_id)}) from None
        if row is None or not can_access(user, row["customer_id"]):
            raise HTTPException(status_code=404, detail={"code": "review_not_found", "request_id": str(request_id)})
        return json_safe(dict(request_id=row["request_id"], customer_id=row["customer_id"],
                              mode=row["review_mode"], status=row["review_status"],
                              created_at=row["created_at"], finished_at=row["finished_at"],
                              elapsed_ms=row["elapsed_ms"], sql_execution_status=row["sql_execution_status"],
                              error_code=row["error_message"], metadata=row["review_metadata"],
                              policy_refs=row["retrieved_policy_refs"], report=row["final_answer"]))

    return api


app = create_app()
