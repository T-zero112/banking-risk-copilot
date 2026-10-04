"""Browser checks of local UI. Model states are mocked; no paid requests."""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    output = ROOT / "data/ui-qa"
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="Asia/Singapore")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.base_url)
        credentials = (ROOT / "data/auth/bootstrap-credentials.txt").read_text(encoding="utf-8")
        accounts = dict(line.split(": ", 1) for line in credentials.splitlines() if ": " in line)
        expect(page.locator("#login-panel")).to_be_visible()
        for width in (390, 768, 1440):
            page.set_viewport_size({"width":width,"height":900})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / ("login.png" if width == 1440 else f"login-{width}.png")), full_page=True)
        page.locator("#username").fill("admin")
        page.locator("#password").fill(accounts["admin"])
        page.locator("#login-form button").click()
        expect(page.locator("#workspace")).to_be_visible()
        expect(page.locator(".brand svg")).to_be_visible()
        assert page.locator("#empty").is_visible()
        assert page.locator("#paid-notice").is_hidden()
        page.screenshot(path=str(output / "desktop-empty.png"), full_page=True)
        with page.expect_response(lambda r: r.url.endswith("/reviews") and r.request.method == "POST") as request:
            page.locator("#run").click()
        response = request.value.json()
        assert response["status"] == "succeeded"
        expect(page.locator("#run")).to_be_enabled()
        expect(page.locator("#result")).to_be_visible()
        assert page.locator("#report-title").inner_text() == "客户 C003"
        assert page.locator("#request-id").inner_text() == response["request_id"]
        assert page.locator("#panel-overview").inner_text().find("KYC 待复核") >= 0
        page.screenshot(path=str(output / "desktop-overview.png"), full_page=True)
        page.locator('[data-view="transactions"]').click()
        assert page.locator("#tx-T00038").is_visible()
        page.screenshot(path=str(output / "desktop-transactions.png"), full_page=True)
        page.locator('[data-view="policies"]').click()
        page.locator(".policy summary").first.click()
        assert page.locator(".excerpt").first.is_visible()
        page.screenshot(path=str(output / "desktop-policy.png"), full_page=True)
        page.locator('[data-view="audit"]').click()
        assert page.locator("#panel-audit").inner_text().find("审查完成") >= 0
        page.locator('[data-view="overview"]').click()
        with page.expect_download() as downloaded:
            page.locator("#download").click()
        assert downloaded.value.suggested_filename.endswith(".json")
        for width in (390, 768, 1440):
            page.set_viewport_size({"width":width,"height":900})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Horizontal overflow at {width}"
            page.screenshot(path=str(output / f"overview-{width}.png"), full_page=True)

        # Intercept every POST in model tests; these never reach the server/provider.
        partial = deepcopy(response)
        partial["status"] = "partial_success"
        partial["report"]["mode"] = "deepseek_review"
        partial["report"]["ai_generation"] = {"status":"failed", "error_code":"model_api_failed"}
        partial["report"]["audit"]["status"] = "partial_success"
        page.route("**/reviews", lambda route: route.fulfill(status=201, json=partial))
        page.locator('input[value="deepseek"]').check()
        assert page.locator("#paid-notice").is_visible()
        page.locator("#run").click()
        assert page.locator("#notification").inner_text().find("确认") >= 0
        page.locator("#consent").check()
        page.locator("#run").click()
        expect(page.locator("#run")).to_be_enabled()
        assert page.locator("#outcome").inner_text() == "AI 生成失败"
        assert not page.locator("#consent").is_checked()

        partial["status"] = "succeeded"
        partial["report"]["audit"]["status"] = "succeeded"
        partial["report"]["ai_generation"] = {"status":"succeeded"}
        partial["report"]["ai_explanation"] = {
            "observations":[{"kind":"fact","text":"浏览器测试说明：KYC 已过期。 <img src=x onerror=alert(1)>",
                             "fact_refs":["kyc_status"],"transaction_refs":["T00038"]}],
            "policy_context":[{"text":"浏览器测试：现金条件未确认，仅背景参考。","policy_citations":[1]}],
            "suggested_checks":["浏览器测试：人工核实客户资料。"],
        }
        page.locator("#consent").check()
        page.locator("#run").click()
        expect(page.locator("#run")).to_be_enabled()
        assert "DeepSeek 审查说明" in page.locator("#panel-overview").inner_text()
        assert page.locator("#panel-overview img").count() == 0
        page.locator('[data-transaction="T00038"]').click()
        assert page.locator("#panel-transactions").is_visible()
        page.locator('[data-view="overview"]').click()
        page.locator('[data-citation="1"]').last.click()
        assert page.locator("#policy-1 details").get_attribute("open") is not None

        page.unroute("**/reviews")
        pending = []
        page.route("**/reviews", lambda route: pending.append(route))
        page.locator('input[value="deterministic"]').check()
        page.locator("#run").click()
        expect(page.locator("#run")).to_be_disabled()
        page.evaluate("document.querySelector('#review-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
        assert len(pending) == 1, "Duplicate submission while busy"
        pending[0].fulfill(status=201, json=response)
        expect(page.locator("#run")).to_be_enabled()
        page.unroute("**/reviews")
        page.locator('input[value="deterministic"]').check()
        page.locator("#customer").fill("C999")
        page.locator("#run").click()
        expect(page.locator("#run")).to_be_enabled()
        assert page.locator("#notification").inner_text().find("不存在") >= 0
        assert page.locator("#outcome").inner_text() == "审查失败"
        assert page.locator("#panel-audit").is_visible()
        other = context.request.post(args.base_url + "/reviews", data={"customer_id":"C004"})
        assert other.status == 201
        other_id = other.json()["request_id"]
        actual_audit = context.request.get(args.base_url + "/reviews/" + other_id).json()
        assert actual_audit["metadata"]["actor"] == {"username":"admin", "role":"admin"}
        page.screenshot(path=str(output / "failed-review.png"), full_page=True)
        page.locator("#logout").click()
        expect(page.locator("#login-panel")).to_be_visible()
        assert not page.locator("#workspace").is_visible()
        assert page.locator("#panel-overview").inner_text() == ""
        page.locator("#username").fill("reviewer")
        page.locator("#password").fill(accounts["reviewer"])
        page.locator("#login-form button").click()
        expect(page.locator("#workspace")).to_be_visible()
        assert page.locator("#history-list [data-request]").count() == 0
        denied = context.request.post(args.base_url + "/reviews", data={"customer_id":"C004"})
        assert denied.status == 403
        assert context.request.get(args.base_url + "/reviews/" + response["request_id"]).status == 200
        denied_audit = context.request.get(args.base_url + "/reviews/" + other_id)
        assert denied_audit.status == 404 and "report" not in denied_audit.json()
        page.locator("#customer").fill("C004")
        page.locator("#run").click()
        expect(page.locator("#run")).to_be_enabled()
        assert "访问权限" in page.locator("#notification").inner_text()
        page.locator("#logout").click()
        expect(page.locator("#login-panel")).to_be_visible()
        assert context.request.get(args.base_url + "/reviews/" + response["request_id"]).status == 401
        assert not errors, errors
        browser.close()
    print("PASS login/logout, actor audit, customer-scoped review/history access, download, three viewports, mocked AI/XSS safety and no paid calls")
    print(f"Screenshots: {output}; no paid model requests")


if __name__ == "__main__":
    main()
