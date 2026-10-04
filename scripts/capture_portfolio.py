"""Capture real synthetic-data workbench views without provider calls."""

from pathlib import Path
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "docs/screenshots"
    output.mkdir(parents=True, exist_ok=True)
    credentials = (ROOT / "data/auth/bootstrap-credentials.txt").read_text(encoding="utf-8")
    accounts = dict(line.split(": ", 1) for line in credentials.splitlines() if ": " in line)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width":1440, "height":1000}, timezone_id="Asia/Singapore")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def forbid_paid(route):
            body = route.request.post_data_json or {}
            if body.get("mode") == "deepseek" or body.get("paid_consent") is True:
                raise RuntimeError("Paid request blocked by screenshot script")
            route.continue_()

        page.route("**/reviews", forbid_paid)
        page.goto("http://127.0.0.1:8000/")

        def login(user):
            page.locator("#username").fill(user)
            page.locator("#password").fill(accounts[user])
            page.locator("#login-form button").click()
            expect(page.locator("#workspace")).to_be_visible()

        def capture(name):
            expect(page.locator("#login-panel")).to_be_hidden()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            # Local request identifiers are not needed in public portfolio screenshots.
            page.screenshot(path=str(output / name), full_page=True,
                            mask=[page.locator("#request-id")], mask_color="#e5e7eb")

        login("admin")
        page.locator('input[value="deterministic"]').check()
        page.locator("#customer").fill("C003")
        page.locator("#run").click()
        expect(page.locator("#result")).to_be_visible()
        expect(page.locator("#run")).to_be_enabled()
        capture("01-c003-overview.png")
        page.locator('[data-view="transactions"]').click()
        capture("02-transactions.png")
        page.locator('[data-view="policies"]').click()
        # Keep full third-party policy excerpts collapsed in publication assets.
        capture("03-policy-evidence.png")
        page.locator("#customer").fill("C004")
        page.locator("#run").click()
        expect(page.locator("#report-title")).to_have_text("客户 C004")
        expect(page.locator("#run")).to_be_enabled()
        page.locator('[data-view="overview"]').click()
        capture("04-c004-no-rule.png")
        page.locator("#logout").click()
        expect(page.locator("#login-panel")).to_be_visible()
        login("reviewer")
        page.locator("#customer").fill("C004")
        page.locator("#run").click()
        expect(page.locator("#notification")).to_contain_text("访问权限")
        expect(page.locator("#run")).to_be_enabled()
        capture("05-access-denied.png")
        page.locator("#logout").click()
        assert not errors, errors
        context.close()
        browser.close()
    print("Captured 5 real workbench screenshots; synthetic data, deterministic mode, no provider calls")


if __name__ == "__main__":
    main()
