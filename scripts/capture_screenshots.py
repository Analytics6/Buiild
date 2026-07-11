"""Capture screenshots of all Buiild Complaint RAG application views."""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:3000"
SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "screenshots"
VIEWPORT = {"width": 1440, "height": 900}
MOBILE_VIEWPORT = {"width": 390, "height": 844}


def wait_for_app(page, timeout_ms: int = 15000) -> None:
    page.wait_for_load_state("networkidle", timeout=timeout_ms)
    page.wait_for_timeout(800)


def clear_session(page) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.evaluate("() => localStorage.removeItem('complaint-token')")
    page.reload(wait_until="domcontentloaded")
    wait_for_app(page)


def login(page, email: str, password: str) -> None:
    clear_session(page)
    page.get_by_text("Customer Support Intelligence").wait_for(timeout=15000)
    form = page.locator("form")
    form.locator("input").nth(0).fill(email)
    form.locator('input[type="password"]').fill(password)
    form.get_by_role("button", name="Sign in").click()
    page.get_by_text("Support Operations Console").wait_for(timeout=20000)
    wait_for_app(page)


def click_nav(page, label: str) -> None:
    page.locator("aside").get_by_role("button", name=label).click()
    page.wait_for_timeout(600)


def screenshot(page, filename: str, full_page: bool = True) -> Path:
    path = SCREENSHOTS_DIR / filename
    page.screenshot(path=str(path), full_page=full_page)
    print(f"Saved {path}")
    return path


def capture_demo_user_views(page) -> list[dict]:
    captured = []

    login(page, "demo@support.ai", "demo123")
    click_nav(page, "Dashboard")
    screenshot(page, "02-dashboard.png")
    captured.append({"file": "02-dashboard.png", "view": "Dashboard", "user": "demo@support.ai"})

    click_nav(page, "Assistant")
    screenshot(page, "03-assistant-empty.png")
    captured.append({"file": "03-assistant-empty.png", "view": "AI Assistant (no active chat)", "user": "demo@support.ai"})

    click_nav(page, "Dashboard")
    page.locator("main").get_by_role("button", name="New review").click()
    page.wait_for_timeout(1000)
    screenshot(page, "04-assistant-new-review.png")
    captured.append({"file": "04-assistant-new-review.png", "view": "AI Assistant (new conversation)", "user": "demo@support.ai"})

    click_nav(page, "Reports")
    screenshot(page, "05-reports.png")
    captured.append({"file": "05-reports.png", "view": "Operational Reports", "user": "demo@support.ai"})

    click_nav(page, "Knowledge Base")
    screenshot(page, "06-knowledge-base.png")
    captured.append({"file": "06-knowledge-base.png", "view": "Knowledge Base & Intake", "user": "demo@support.ai"})

    click_nav(page, "Settings")
    screenshot(page, "07-settings-demo.png")
    captured.append({"file": "07-settings-demo.png", "view": "Settings (manager role)", "user": "demo@support.ai"})

    return captured


def capture_admin_settings(page) -> list[dict]:
    login(page, "admin@support.ai", "admin123")
    click_nav(page, "Settings")
    screenshot(page, "08-settings-admin.png")
    return [{"file": "08-settings-admin.png", "view": "Settings (admin role)", "user": "admin@support.ai"}]


def capture_mobile_dashboard(page) -> list[dict]:
    login(page, "demo@support.ai", "demo123")
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.wait_for_timeout(600)
    screenshot(page, "09-mobile-dashboard.png")
    page.set_viewport_size(VIEWPORT)
    return [{"file": "09-mobile-dashboard.png", "view": "Dashboard (mobile viewport)", "user": "demo@support.ai"}]


def main() -> None:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    skipped: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        try:
            clear_session(page)
            page.get_by_text("Customer Support Intelligence").wait_for(timeout=15000)
            screenshot(page, "01-login.png")
            results.append({"file": "01-login.png", "view": "Login (logged out)", "user": None})
        except Exception as exc:
            skipped.append({"view": "Login", "reason": str(exc)})

        try:
            results.extend(capture_demo_user_views(page))
        except Exception as exc:
            skipped.append({"view": "Demo user views", "reason": str(exc)})

        try:
            results.extend(capture_admin_settings(page))
        except Exception as exc:
            skipped.append({"view": "Admin settings", "reason": str(exc)})

        try:
            results.extend(capture_mobile_dashboard(page))
        except Exception as exc:
            skipped.append({"view": "Mobile dashboard", "reason": str(exc)})

        browser.close()

    manifest = {"captured": results, "skipped": skipped}
    manifest_path = SCREENSHOTS_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nCaptured {len(results)} screenshots, skipped {len(skipped)}")
    if skipped:
        for item in skipped:
            print(f"  SKIP {item['view']}: {item['reason']}")


if __name__ == "__main__":
    main()
