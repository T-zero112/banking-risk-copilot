"""Free review evaluation and bounded opt-in live DeepSeek smoke tests."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
import sys
import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.audit.customer_review import AuditedReviewError, run_customer_review
from app.evaluation.reviews import review_probes, retriever_for
from app.graph.customer_review import build_review_graph
from app.graph.review_explanation import ExplanationValidationError, serialize, validate_explanation, ReviewExplanation, review_payload

OUTPUT = ROOT / "data/evaluations"
PRICING_URL = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=serialize), encoding="utf-8")


def fake_answer(customer="C003"):
    return dict(customer_id=customer, observations=[dict(kind="fact", text="KYC 待核实。", fact_refs=["kyc_status"], transaction_refs=[])],
                policy_context=[], suggested_checks=["人工核实客户资料。"], human_review_required=True)


def free_suite():
    entries = []
    for customer in ("C003", "C004"):
        report = run_customer_review(customer)
        checks = review_probes(report)
        entries.append(dict(id=customer, request_id=report["request_id"], checks=checks, report=report))
    base = entries[0]["report"]
    for kind in ("model_failure", "bad_citation", "bad_transaction", "empty_policy", "numeric_failure", "threshold_suggestion_failure"):
        class Generator:
            def invoke(self, messages):
                if kind == "model_failure":
                    raise ValueError("Simulated parse failure")
                answer = fake_answer()
                if kind == "bad_citation":
                    answer["policy_context"] = [dict(text="引用", policy_citations=[999], applicability="context_only_cash_condition_not_established")]
                if kind == "bad_transaction":
                    answer["observations"][0]["transaction_refs"] = ["T99999"]
                if kind == "numeric_failure":
                    answer["observations"][0].update(text="AML评分为99。", fact_refs=["aml_risk_score"])
                if kind == "threshold_suggestion_failure":
                    answer["suggested_checks"] = ["确认AML评分85（演示阈值）的构成。"]
                return answer
        graph = lambda **kwargs: build_review_graph(**kwargs, generator=Generator(), retriever=retriever_for("empty_policy" if kind == "empty_policy" else "default"))
        report = run_customer_review("C003", "deepseek", graph_factory=graph)
        expected = "succeeded" if kind == "empty_policy" else "partial_success"
        checks = dict(expected_status=report["audit"]["status"] == expected,
                      facts_preserved=report["facts"] == base["facts"], **review_probes(report))
        entries.append(dict(id=kind, request_id=report["request_id"], checks=checks, report=report))
    for kind, kwargs in (("unknown_customer", {}), ("database_failure", {"graph_factory":lambda **_: build_review_graph(loader=lambda _: (_ for _ in ()).throw(psycopg.OperationalError("Simulated database unavailable")))})):
        try:
            run_customer_review("C999" if kind == "unknown_customer" else "C003", **kwargs)
        except AuditedReviewError as error:
            entries.append(dict(id=kind, request_id=error.request_id, checks={"failure_logged":True}, error_code=error.code))
        else:
            entries.append(dict(id=kind, checks={"failure_logged":False}))
    # Preserve the historical counterexample as a local regression check.
    numeric_attack = fake_answer()
    numeric_attack["observations"][0].update(text="AML评分为99。", fact_refs=["aml_risk_score"])
    try:
        validate_explanation(ReviewExplanation.model_validate(numeric_attack), review_payload(base))
    except ExplanationValidationError as error:
        rejected = error.diagnostic["code"] == "numeric_fact_mismatch"
    else:
        rejected = False
    entries.append(dict(id="numeric_prose_regression", checks={"wrong_score_rejected": rejected}))
    gap = dict(id="unlabelled_numeric_prose", note="Only explicit numeric labels are checked; arbitrary prose remains unverified.")
    passed = all(all(e["checks"].values()) for e in entries)
    result = dict(phase="free", passed=passed, created_at=datetime.now(timezone.utc).isoformat(),
                  cases=entries, known_gaps=[gap], paid_api_calls=0,
                  scope="Fixed-fixture contracts and injected failures; no live prompt-injection resistance claim")
    save(OUTPUT / "free-results.json", result)
    print(f"Free suite: {len(entries)} cases; passed={passed}; 0 paid calls; numeric regression checked")
    return passed


def price_range(usage):
    if not usage.get("usage_available"):
        return None
    hit = usage.get("cache_hit_tokens") or 0
    miss = usage.get("cache_miss_tokens")
    miss = usage["input_tokens"] - hit if miss is None else miss
    # 2026-10-02 official CNY/M tokens. Range avoids assuming holiday/time-of-day billing.
    off_peak = (hit * .02 + miss * 1 + usage["output_tokens"] * 4) / 1_000_000
    return dict(off_peak_cny=off_peak, peak_cny=off_peak * 2,
                method="Provider counters times official list price, not account debit", pricing_url=PRICING_URL)


def live_suite(limit, continue_unattempted=False, selected_cases=None):
    free = json.loads((OUTPUT / "free-results.json").read_text(encoding="utf-8"))
    if not free["passed"]:
        raise ValueError("Free suite must pass before live calls")
    cases = json.loads((ROOT / "evals/review_cases.json").read_text())["live_cases"]
    if selected_cases:
        known = {case["id"] for case in cases}
        if not set(selected_cases) <= known:
            raise ValueError("Unknown evaluation case")
        cases = [case for case in cases if case["id"] in selected_cases]
    cases = cases[:limit]
    results = dict(phase="live", created_at=datetime.now(timezone.utc).isoformat(), api_attempt_limit=limit,
                   pricing_verified_date="2026-10-02", cases=[], human_review_status="pending")
    if continue_unattempted:
        results = json.loads((OUTPUT / "live-results.json").read_text(encoding="utf-8"))
        results["api_attempt_limit"] = limit
    attempted = {case["id"] for case in results["cases"]}
    snapshot = OUTPUT / ("live-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    save(snapshot, results)
    for case in cases:
        if case["id"] in attempted:
            continue
        started = perf_counter()
        factory = lambda **kwargs: build_review_graph(**kwargs, retriever=retriever_for(case["scenario"]))
        try:
            report = run_customer_review(case["customer_id"], "deepseek", graph_factory=factory)
            usage = report.get("ai_generation", {}).get("model_call", {})
            checks = dict(review_probes(report), generation_accepted=report.get("ai_generation", {}).get("status") == "succeeded")
            item = dict(case, request_id=report["request_id"], report=report, checks=checks,
                        usage=usage, cost_estimate=price_range(usage), elapsed_ms=int((perf_counter()-started)*1000),
                        human_review={"status":"pending", "questions":case["review_questions"]})
        except AuditedReviewError as error:
            item = dict(case, request_id=error.request_id, error_code=error.code, human_review={"status":"pending"})
        results["cases"].append(item)
        save(snapshot, results)
        save(OUTPUT / "live-results.json", results)
        print(json.dumps({key:item.get(key) for key in ("id","request_id","usage","cost_estimate","checks")}, ensure_ascii=True))
        # Do not spend again after unknown usage or an API/audit failure.
        if not item.get("usage", {}).get("usage_available") or item.get("report", {}).get("ai_generation", {}).get("error_code") == "model_api_failed":
            print("Stopping batch: usage unavailable or API failed; no retry")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly authorize paid DeepSeek requests")
    parser.add_argument("--max-calls", type=int, choices=range(1,11), default=4)
    parser.add_argument("--continue-unattempted", action="store_true", help="Keep existing results and skip all attempted cases")
    parser.add_argument("--case", action="append", choices=("risk_candidate", "no_demo_rule", "missing_policy", "prompt_injection"), help="Select a scenario; repeat to select multiple")
    args = parser.parse_args()
    if args.live:
        live_suite(args.max_calls, args.continue_unattempted, args.case)
    elif not free_suite():
        raise SystemExit(1)
