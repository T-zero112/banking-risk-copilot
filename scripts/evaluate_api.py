"""Exercise the running local HTTP API with synthetic data and no model calls."""

import argparse
from getpass import getpass
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--bootstrap-credentials", action="store_true", help="Use the ignored local temporary admin credential file")
    args = parser.parse_args()
    if args.bootstrap_credentials:
        lines = (Path(__file__).resolve().parents[1] / "data/auth/bootstrap-credentials.txt").read_text(encoding="utf-8").splitlines()
        password = dict(line.split(": ", 1) for line in lines if ": " in line)["admin"]
    else:
        password = getpass("Local admin password: ")
    with httpx.Client(base_url=args.base_url, timeout=90, trust_env=False) as client:
        response = client.get("/health")
        response.raise_for_status()
        assert response.json()["scope"] == "process_liveness_only"
        assert client.get("/docs").status_code == 200
        assert "/reviews" in client.get("/openapi.json").json()["paths"]
        assert client.post("/reviews", json={"customer_id":"C003"}).status_code == 401
        login = client.post("/auth/login", json={"username":"admin", "password":password})
        assert login.status_code == 200, "Admin login failed"
        response = client.post("/reviews", json={"customer_id": "C003"})
        assert response.status_code == 201, response.text
        created = response.json()
        assert created["status"] == "succeeded"
        assert created["report"]["facts"]["inbound_sgd"] == "18000.00"
        request_id = created["request_id"]
        saved = client.get(f"/reviews/{request_id}")
        assert saved.status_code == 200
        assert saved.json()["status"] == "succeeded"
        assert saved.json()["report"]["request_id"] == request_id
        assert saved.json()["report"]["facts"] == created["report"]["facts"]
        print(f"PASS HTTP C003 review and stored audit: {request_id}")
        response = client.post("/reviews", json={"customer_id": "C999"})
        assert response.status_code == 404, response.text
        error = response.json()["detail"]
        assert error["code"] == "customer_not_found"
        saved = client.get(f"/reviews/{error['request_id']}")
        assert saved.json()["status"] == "failed"
        print(f"PASS HTTP unknown customer and failed audit: {error['request_id']}")
        assert client.post("/reviews", json={"customer_id": "C003", "mode": "invalid"}).status_code == 422
        assert client.post("/auth/logout").status_code == 200
        assert client.get(f"/reviews/{request_id}").status_code == 401
    print("PASS HTTP liveness, docs, validation, review and persisted failure; no paid API calls")


if __name__ == "__main__":
    main()
