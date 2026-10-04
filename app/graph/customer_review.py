"""Deterministic SQL + policy evidence workflow; never a misconduct verdict."""

from datetime import timedelta
from decimal import Decimal
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from openai import APIError
from pydantic import ValidationError

from app.rag.retrieval import PolicyRetriever
from app.sql.review import load_customer_evidence
from app.graph.review_explanation import DEMO_AML_THRESHOLD, ExplanationValidationError, ReviewExplanation, explanation_messages, review_payload, validate_explanation
from app.rag.providers import call_metadata
from app.graph.generation_diagnostics import parsing_diagnostic, schema_diagnostic


class ReviewState(TypedDict, total=False):
    customer_id: str
    evidence: dict
    candidates: list
    policies: list
    report: dict
    explanation: ReviewExplanation | None
    generation_error: str | None
    generation_diagnostic: dict | None
    model_call: dict


def find_candidates(transactions):
    candidates = []
    for incoming in transactions:
        if incoming["direction"] != "inbound":
            continue
        for outgoing in transactions:
            if outgoing["direction"] != "outbound" or outgoing["account_id"] != incoming["account_id"]:
                continue
            elapsed = outgoing["transaction_time"] - incoming["transaction_time"]
            ratio = outgoing["amount"] / incoming["amount"]
            if timedelta(0) < elapsed <= timedelta(hours=24) and Decimal("0.9") <= ratio <= Decimal("1.1"):
                candidates.append(dict(incoming_transaction_id=incoming["transaction_id"],
                                       outgoing_transaction_id=outgoing["transaction_id"],
                                       elapsed_minutes=int(elapsed.total_seconds() / 60),
                                       amount_ratio=str(ratio)))
    return candidates


def build_review_graph(loader=None, retriever=None, *, mode="deterministic", generator=None):
    if mode not in {"deterministic", "deepseek"}:
        raise ValueError("Unknown customer review mode")
    if mode == "deepseek" and generator is None:
        from app.rag.providers import deepseek_generator
        generator = deepseek_generator(ReviewExplanation, max_tokens=4096, include_raw=True)
    loader = loader or load_customer_evidence
    # Exact keyword evidence is kept as an inspectable baseline for this rule.
    retriever = retriever or PolicyRetriever(top_k=5, source_id="spf-bank-red-flags")

    def load(state):
        return {"evidence": loader(state["customer_id"])}

    def assess(state):
        return {"candidates": find_candidates(state["evidence"]["transactions"])}

    def retrieve(state):
        if not state["candidates"]:
            return {"policies": []}
        docs = retriever.invoke("matching payments credits")
        # Require the actual phrase, not just the existence of a search hit.
        docs = [d for d in docs if "matching of payments out with credits paid in by cash" in " ".join(d.page_content.lower().split())]
        return {"policies": docs}

    def report(state):
        evidence = state["evidence"]
        customer = evidence["customer"]
        transactions = evidence["transactions"]
        facts = dict(customer, transaction_count=len(transactions),
                     inbound_sgd=sum((t["amount"] for t in transactions if t["direction"] == "inbound"), Decimal(0)),
                     outbound_sgd=sum((t["amount"] for t in transactions if t["direction"] == "outbound"), Decimal(0)),
                     cross_border_count=sum(t["is_cross_border"] is True for t in transactions),
                     unknown_cross_border_count=sum(t["is_cross_border"] is None for t in transactions))
        signals = []
        if customer["kyc_status"] in {"incomplete", "expired"}:
            signals.append(dict(code="kyc_follow_up", reason="KYC 信息不完整或已过期，需要人工核实。", policy_citations=[]))
        if customer["aml_risk_score"] is not None and customer["aml_risk_score"] >= DEMO_AML_THRESHOLD:
            signals.append(dict(code="demo_high_aml_score", reason="演示数据中的 AML 评分达到 80；这是项目阈值，不是监管标准。", policy_citations=[]))
        if customer["unresolved_alert_count"]:
            signals.append(dict(code="existing_alert", reason="存在尚未解决的告警，需要核查；告警不代表违法。", policy_citations=[]))
        if state["candidates"]:
            signals.append(dict(code="matching_payment_candidate", reason="同账户存在短时间、金额接近的进出交易候选；不能据此确认资金关联或洗钱。",
                                policy_citations=list(range(1, len(state["policies"]) + 1)),
                                policy_support="context_only_cash_condition_not_established" if state["policies"] else "not_found",
                                applicability_note="检索条目明确涉及现金入账；本规则未确认现金条件，不能直接认定满足该条目。"))
        policies = [dict(citation_id=i, excerpt=d.page_content, **d.metadata)
                    for i, d in enumerate(state["policies"], 1)]
        policy_status = "available" if policies else "not_found" if state["candidates"] else "not_requested"
        policy_notice = {
            "available": "已检索到政策背景；现金入账条件尚未确认，不能直接认定适用。",
            "not_found": "本次政策检索未获得匹配证据，不能据此确认合规或风险程度。",
            "not_requested": "未发现交易配对候选，本流程未执行政策检索；不代表合规或低风险。",
        }[policy_status]
        result = dict(customer_id=state["customer_id"], mode="deterministic_review",
                      as_of=evidence["as_of"], window="[as_of - 30 days, as_of), SGD only",
                      facts=facts, transactions=transactions, candidate_pairs=state["candidates"],
                      review_signals=signals, policy_evidence=policies,
                      policy_evidence_status=policy_status, policy_evidence_notice=policy_notice,
                      disposition="manual_review_suggested" if signals else "no_demo_rule_triggered",
                      limitations=["仅分析模拟数据，不是洗钱认定或法律建议。",
                                   "KYC 是当前快照，风险评分和告警是演示数据；不是完整历史重建。",
                                   "24 小时及金额比 0.9–1.1 是演示规则；交易配对不证明资金来源。",
                                   "政策仅为已导入的 SPF 快照，不包含 MAS/FATF 全部要求。",
                                   "无规则触发不代表低风险；未分析非 SGD 交易或完整客户背景。"])
        return {"report": result}

    def generate(state):
        metadata = {"usage_available": False}
        try:
            output = generator.invoke(explanation_messages(review_payload(state["report"])))
            if isinstance(output, dict) and "raw" in output and "parsed" in output:
                metadata = call_metadata(output["raw"])
                if output.get("parsing_error") is not None or output["parsed"] is None:
                    return {"explanation": None, "generation_error": "invalid_model_output", "model_call": metadata,
                            "generation_diagnostic": parsing_diagnostic(output["raw"], output.get("parsing_error"))}
                output = output["parsed"]
            return {"explanation": ReviewExplanation.model_validate(output), "generation_error": None,
                    "generation_diagnostic": None, "model_call": metadata}
        except APIError:
            return {"explanation": None, "generation_error": "model_api_failed", "model_call": metadata,
                    "generation_diagnostic": {"stage":"provider", "code":"model_api_failed"}}
        except ValidationError as failure:
            return {"explanation": None, "generation_error": "invalid_model_output", "model_call": metadata,
                    "generation_diagnostic": schema_diagnostic(failure)}
        except ValueError as failure:
            return {"explanation": None, "generation_error": "invalid_model_output", "model_call": metadata,
                    "generation_diagnostic": parsing_diagnostic(error=failure)}

    def validate(state):
        result = dict(state["report"], mode="deepseek_review")
        error = state.get("generation_error")
        diagnostic = state.get("generation_diagnostic")
        if not error:
            try:
                explanation = validate_explanation(state["explanation"], review_payload(result))
                result["ai_explanation"] = explanation.model_dump()
                result["ai_explanation"]["policy_evidence_notice"] = result["policy_evidence_notice"]
            except ExplanationValidationError as failure:
                diagnostic = failure.diagnostic
                error = "inconsistent_numeric_facts" if diagnostic["code"] == "numeric_fact_mismatch" else "invalid_evidence_references"
        result["ai_generation"] = dict(provider="deepseek", status="failed" if error else "succeeded",
                                       error_code=error, validation_diagnostic=diagnostic,
                                       validation_scope="schema_reference_membership_and_explicit_numeric_labels_only",
                                       model_call=state.get("model_call", {"usage_available": False}))
        return {"report": result}

    graph = StateGraph(ReviewState)
    for name, node in (("load_sql", load), ("assess", assess), ("retrieve_policy", retrieve), ("compose", report)):
        graph.add_node(name, node)
    graph.add_edge(START, "load_sql")
    graph.add_edge("load_sql", "assess")
    graph.add_edge("assess", "retrieve_policy")
    graph.add_edge("retrieve_policy", "compose")
    if mode == "deepseek":
        graph.add_node("generate_explanation", generate)
        graph.add_node("validate_explanation", validate)
        graph.add_edge("compose", "generate_explanation")
        graph.add_edge("generate_explanation", "validate_explanation")
        graph.add_edge("validate_explanation", END)
    else:
        graph.add_edge("compose", END)
    return graph.compile()
