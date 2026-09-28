"""
Script for interactive authentication via Web Browser (supporting SSO/MFA/SAML/Okta/Azure AD)
in MicroStrategy Library.

This script opens a real browser using Playwright, allows the user to log in via the web
interface, and automatically intercepts the 'X-MSTR-AuthToken' header, 'X-MSTR-ProjectID', and
session cookies, saving everything into a session JSON file (default: .mstr_session.json).

Requirements:
  pip install playwright
  playwright install chromium
"""

import argparse
import json
import os
import sys
import time
from urllib.parse import urlparse

def parse_args():
    p = argparse.ArgumentParser(description="Interactive authentication in Strategy via Web Browser")
    p.add_argument("--base-url", required=True, help="E.g., https://host/MicroStrategyLibrary")
    p.add_argument("--output-session", default=".mstr_session.json", help="Destination session file (JSON)")
    p.add_argument("--timeout", type=int, default=300, help="Timeout in seconds for the user to complete login (default: 300s)")
    return p.parse_args()


def main():
    args = parse_args()
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Install by running:\n  pip install playwright && playwright install chromium", file=sys.stderr)
        sys.exit(1)

    base_url = args.base_url.rstrip("/")
    library_app_url = f"{base_url}/app" if not base_url.endswith("/app") else base_url

    session_data = {
        "base_url": base_url,
        "auth_token": None,
        "cookies": {},
        "projects": []
    }

    print(f"\n[Browser Auth] Opening browser at: {library_app_url}")
    print("[Browser Auth] Please log in within the browser window (including SSO/MFA if enabled)...\n")

    with sync_playwright() as p:
        # Launch visible browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # Listener to intercept REST API requests/responses containing X-MSTR-AuthToken
        def handle_response(response):
            headers = response.headers
            token = headers.get("x-mstr-authtoken") or headers.get("X-MSTR-AuthToken")
            if token and not session_data["auth_token"]:
                print(f"\n[SUCCESS] Authentication token intercepted: {token[:15]}...")
                session_data["auth_token"] = token

        def handle_request(request):
            headers = request.headers
            token = headers.get("x-mstr-authtoken") or headers.get("X-MSTR-AuthToken")
            if token and not session_data["auth_token"]:
                print(f"\n[SUCCESS] Authentication token intercepted in request: {token[:15]}...")
                session_data["auth_token"] = token

        page.on("response", handle_response)
        page.on("request", handle_request)

        try:
            page.goto(library_app_url)
        except Exception as e:
            print(f"Error opening URL {library_app_url}: {e}", file=sys.stderr)

        start_time = time.time()
        print("Waiting for login to complete...")

        while time.time() - start_time < args.timeout:
            # 1. Check if token was intercepted via header
            if session_data["auth_token"]:
                break
            
            # 2. Try capturing token stored in page sessionStorage/localStorage
            try:
                token_js = page.evaluate("() => sessionStorage.getItem('X-MSTR-AuthToken') || localStorage.getItem('X-MSTR-AuthToken') || (window.mstrConfig && window.mstrConfig.authToken)")
                if token_js:
                    print(f"\n[SUCCESS] Token retrieved via Session/Local Storage: {token_js[:15]}...")
                    session_data["auth_token"] = token_js
                    break
            except Exception:
                pass

            # 3. Check if iServer/JSESSIONID cookies are present and attempt a verification probe
            try:
                cookies = context.cookies()
                has_jsession = any(c['name'] in ('JSESSIONID', 'iServer') for c in cookies)
                if has_jsession and not session_data["auth_token"]:
                    # Trigger a simple fetch to /api/projects to force header issuance
                    page.evaluate("fetch('../api/projects').then(r => console.log('Projects checked'))")
            except Exception:
                pass

            time.sleep(1)

        # Final cookie capture
        try:
            cookies = context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            session_data["cookies"] = cookie_dict
        except Exception:
            pass

        browser.close()

    if not session_data["auth_token"]:
        print("\n[ERROR] Unable to capture X-MSTR-AuthToken within the timeout period.", file=sys.stderr)
        sys.exit(1)

    output_path = os.path.abspath(args.output_session)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    print(f"\nSession saved successfully to: {output_path}")
    print("You can now run skill scripts pointing to this session file.")


if __name__ == "__main__":
    main()
