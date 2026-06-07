from playwright.sync_api import sync_playwright
import sys

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    errors = []
    def on_console(msg):
        print(f"[{msg.type}] {msg.text}", file=sys.stderr)
    def on_error(err):
        print(f"[PAGE_ERROR] {err}", file=sys.stderr)
        errors.append(str(err))
    
    page.on("console", on_console)
    page.on("pageerror", on_error)
    
    page.goto("https://shin488.github.io/lost-items/", wait_until="networkidle", timeout=60000)
    print("Page loaded, waiting 45s for app init...")
    page.wait_for_timeout(45000)
    
    splash = page.evaluate("document.getElementById('splash') ? 'visible' : 'removed'")
    body_text = page.evaluate("document.body.innerText.substring(0, 200)")
    print(f"Splash: {splash}")
    print(f"Errors: {errors}")
    print(f"Body: {body_text[:200]}")
    browser.close()
