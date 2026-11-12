"""Exercise the real UI on desktop/mobile; all inputs are synthetic. Requires a seeded running app."""

import argparse
import getpass
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def capture(page, **kwargs):
    expect(page.locator("#notice")).to_have_text("", timeout=9000)
    page.screenshot(**kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--screenshots", default="test-results/browser")
    parser.add_argument("--chromium", default=os.environ.get("CHROMIUM_EXECUTABLE"))
    args = parser.parse_args()
    password = os.environ.get("DEMO_PASSWORD") or getpass.getpass("Local engineer demo password: ")
    output = Path(args.screenshots)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=args.chromium)
        for name, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844)]:
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                is_mobile=name == "mobile",
                has_touch=name == "mobile",
                base_url=args.url,
                timezone_id=os.environ.get("DEMO_TIMEZONE", "UTC"),
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.url)
            expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
            capture(page, path=str(output / f"{name}-login.png"), full_page=True)
            page.get_by_label("Username", exact=True).fill("engineer")
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Sign in", exact=False).click()
            expect(page.get_by_role("heading", name="Make sense of the incident.")).to_be_visible()
            page.get_by_role("link", name="New incident", exact=False).click()
            page.get_by_label("Incident title").fill(f"Checkout database investigation · {name}")
            page.get_by_label("Log excerpt").fill(Path("fixtures/development/database.log").read_text())
            page.get_by_role("button", name="Investigate incident", exact=False).click()
            expect(page.get_by_role("heading", name="Investigation report", exact=True)).to_be_visible()
            expect(page.get_by_text("Deterministic baseline · rules + PostgreSQL retrieval")).to_be_visible()
            expect(page.get_by_text("L2", exact=True)).to_be_visible()
            page.get_by_role("button", name="DB-001", exact=False).first.click()
            expect(page.get_by_role("dialog")).to_be_visible()
            expect(page.locator("#source-body")).to_contain_text("approved inventory")
            capture(page, path=str(output / f"{name}-source.png"), full_page=True)
            page.keyboard.press("Escape")
            expect(page.get_by_role("dialog")).not_to_be_visible()
            page.get_by_label("Review note").fill(
                "Synthetic monitoring check: listener issue confirmed for this demonstration."
            )
            page.get_by_role("button", name="Accept", exact=True).click()
            expect(page.get_by_text("recommendation reviewed", exact=True)).to_be_visible()
            expect(page.locator(".meta-list").get_by_text("accepted", exact=True)).to_be_visible()
            capture(page, path=str(output / f"{name}-investigation.png"), full_page=True)
            page.get_by_role("link", name="Overview", exact=False).click()
            expect(page.get_by_role("heading", name="Incident history")).to_be_visible()
            expect(
                page.get_by_role("link", name=f"Checkout database investigation · {name}", exact=True).first
            ).to_be_visible()
            capture(page, path=str(output / f"{name}-dashboard.png"), full_page=True)
            page.get_by_role("link", name="Knowledge library", exact=False).click()
            expect(page.get_by_role("heading", name="Runbooks, with context.")).to_be_visible()
            expect(page.get_by_role("heading", name="Restricted database topology")).to_have_count(0)
            expect(page.get_by_role("button", name="Add runbook", exact=False)).to_have_count(0)
            capture(page, path=str(output / f"{name}-library.png"), full_page=True)
            denied = context.request.get("/api/admin/audit")
            assert denied.status == 403
            page.get_by_role("link", name="New incident", exact=False).click()
            page.get_by_label("Incident title").fill(f"Unknown signal · {name}")
            page.locator("input[type=file]").set_input_files("fixtures/development/unknown.log")
            page.get_by_role("button", name="Investigate incident", exact=False).click()
            expect(page.get_by_text("Unknown or conflicting signals; obtain more context.")).to_be_visible()
            expect(page.get_by_role("button", name="Accept", exact=True)).to_have_count(0)
            capture(page, path=str(output / f"{name}-insufficient.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                "Viewport overflow"
            )
            page.get_by_role("button", name="Sign out", exact=True).click()
            expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
            assert context.request.get("/api/auth/me").status == 401
            assert not errors, errors
            results.append(
                {
                    "viewport": name,
                    "width": width,
                    "height": height,
                    "checks": [
                        "login",
                        "paste submission",
                        "investigation and line number",
                        "source inspection",
                        "keyboard dialog dismissal",
                        "review and audit",
                        "persisted history",
                        "authorized library",
                        "permission denied",
                        "file upload",
                        "insufficient evidence",
                        "no horizontal overflow",
                        "logout",
                    ],
                    "passed": True,
                    "javascript_errors": errors,
                }
            )
            context.close()
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, base_url=args.url)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.get_by_label("Username", exact=True).fill("admin")
        page.get_by_label("Password", exact=True).fill(password)
        page.get_by_role("button", name="Sign in", exact=False).click()
        expect(page.get_by_role("heading", name="Make sense of the incident.")).to_be_visible()
        page.get_by_role("link", name="Knowledge library", exact=False).click()
        page.get_by_role("button", name="Add runbook", exact=False).click()
        key = "DEMO-" + secrets.token_hex(3).upper()
        form = page.locator("#document-form")
        form.get_by_label("Runbook key").fill(key)
        form.get_by_label("Title", exact=True).fill("Browser verification runbook " + key)
        form.get_by_label("Section", exact=True).fill("Synthetic demonstration")
        form.get_by_label("Guidance", exact=False).fill(
            "Inspect approved monitoring and record the synthetic observation for human review."
        )
        form.get_by_role("button", name="Save runbook").click()
        article = page.locator("article").filter(
            has=page.get_by_role("heading", name="Browser verification runbook " + key, exact=True)
        )
        expect(article).to_be_visible()
        article.get_by_role("button", name="Edit / archive").click()
        form.get_by_label("Available for retrieval").uncheck()
        form.get_by_role("button", name="Save runbook").click()
        expect(article.get_by_text("archived", exact=True)).to_be_visible()
        expect(article.get_by_text(key + " · v2", exact=True)).to_be_visible()
        page.get_by_role("button", name="Load recent audit records").click()
        expect(page.locator("#admin-audit")).to_contain_text("document updated")
        capture(page, path=str(output / "admin-library.png"), full_page=True)
        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
        assert not errors, errors
        results.append(
            {
                "viewport": "administrator desktop",
                "width": 1440,
                "height": 1000,
                "checks": [
                    "administrator login",
                    "create document",
                    "edit/archive document",
                    "version increment",
                    "administrative audit",
                    "logout",
                ],
                "passed": True,
                "javascript_errors": errors,
            }
        )
        context.close()
        browser.close()
    Path("test-results").mkdir(exist_ok=True)
    Path("test-results/browser.json").write_text(
        json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(), "results": results}, indent=2)
        + "\n"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
