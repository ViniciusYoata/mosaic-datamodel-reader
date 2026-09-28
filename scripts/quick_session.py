"""
Browser Auth + Batch API in sequential flow with persistent session.

Execution modes:
  1) Authenticate and list projects:
     .venv/bin/python3 scripts/quick_session.py --base-url "https://host/Library" --list-projects

  2) List models in a project (reuses active session):
     .venv/bin/python3 scripts/quick_session.py --base-url "https://host/Library" --project-id <id>

  3) Download full model in batch (reuses active session):
     .venv/bin/python3 scripts/quick_session.py --base-url "https://host/Library" \\
         --project-id <id> --data-model-id <id>
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import requests
from urllib.parse import urljoin

# ── Base paths ────────────────────────────────────────────────────────────────
SKILL_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR    = os.path.join(SKILL_DIR, ".temp")
SESSION_FILE = os.path.join(TEMP_DIR, "session.json")
SUCCESS_HTML = os.path.join(SKILL_DIR, "resources", "login_success.html")
VENV_PYTHON  = os.path.join(SKILL_DIR, ".venv", "bin", "python3")


def api_url(base_url, path):
    return urljoin(base_url.rstrip("/") + "/", "api/" + path.lstrip("/"))


def save_session(base_url, token, cookies):
    os.makedirs(TEMP_DIR, exist_ok=True)
    data = {"base_url": base_url, "auth_token": token, "cookies": cookies}
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def make_session(token, cookies):
    s = requests.Session()
    s.cookies.update(cookies or {})
    return s, {"X-MSTR-AuthToken": token, "Accept": "application/json"}


def start_keepalive():
    pid_file = os.path.join(TEMP_DIR, "keepalive.pid")
    # Avoid duplicate keepalive daemons
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # Check if process exists
            return  # Already running
        except (ProcessLookupError, ValueError):
            pass
    keepalive_script = os.path.join(SKILL_DIR, "scripts", "session_keepalive.py")
    subprocess.Popen(
        [VENV_PYTHON, keepalive_script, "--session-file", SESSION_FILE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print("[Session] Keepalive daemon started in background.")


# ── Browser Auth ─────────────────────────────────────────────────────────────

def open_browser_and_capture(base_url, session_data, done_event):
    from playwright.sync_api import sync_playwright

    library_url = base_url.rstrip("/") + "/app"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        def grab_token(token):
            if token and not session_data.get("auth_token"):
                session_data["auth_token"] = token
                session_data["cookies"] = {c["name"]: c["value"] for c in context.cookies()}
                print(f"\n[Auth] Token captured: {token[:15]}...", flush=True)

        page.on("response", lambda r: grab_token(r.headers.get("x-mstr-authtoken")))
        page.on("request",  lambda r: grab_token(r.headers.get("x-mstr-authtoken")))

        try:
            page.goto(library_url)
        except Exception as e:
            print(f"Notice while navigating to URL: {e}", flush=True)

        print(f"Browser opened at: {library_url}", flush=True)
        print("Please log in and wait for the page to load...", flush=True)

        start = time.time()
        while time.time() - start < 300:
            if session_data.get("auth_token"):
                break
            try:
                tk = page.evaluate(
                    "() => sessionStorage.getItem('X-MSTR-AuthToken') || localStorage.getItem('X-MSTR-AuthToken')"
                )
                if tk:
                    grab_token(tk)
            except Exception:
                pass
            time.sleep(1)

        if session_data.get("auth_token"):
            # Redirect to local success page and close after 4s
            try:
                page.goto(f"file://{SUCCESS_HTML}")
                time.sleep(4)
            except Exception:
                pass

        browser.close()
        done_event.set()


# ── API Helpers ───────────────────────────────────────────────────────────────

MOSAIC_SUBTYPES = {776, 779, 781}


def fetch_projects(base_url, token, cookies):
    s, h = make_session(token, cookies)
    resp = s.get(api_url(base_url, "projects"), headers=h, verify=True, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_models(base_url, token, cookies, project_id):
    s, h = make_session(token, cookies)
    h["X-MSTR-ProjectID"] = project_id
    found = {}

    for stype in [3, 776]:
        try:
            params = {"name": "", "pattern": 4, "type": stype,
                      "getAncestors": "false", "limit": -1, "certifiedStatus": "ALL"}
            r = s.get(api_url(base_url, "searches/results"), headers=h, params=params, timeout=30)
            if r.ok:
                for item in r.json().get("result", []):
                    if item.get("subtype") in MOSAIC_SUBTYPES:
                        found[item["id"]] = item
        except Exception:
            pass

    # Fallback: endpoint /model/dataModels
    try:
        r2 = s.get(api_url(base_url, "model/dataModels"), headers=h, timeout=30)
        if r2.ok:
            for item in r2.json().get("dataModels", []):
                obj_id = item.get("information", {}).get("objectId") or item.get("id")
                name   = item.get("information", {}).get("name") or item.get("name", "")
                if obj_id:
                    found[obj_id] = {"id": obj_id, "name": name, "subtype": 776}
    except Exception:
        pass

    return list(found.values())


def fetch_full_model(base_url, token, cookies, project_id, model_id):
    s, h = make_session(token, cookies)
    h["X-MSTR-ProjectID"] = project_id

    def get(path):
        r = s.get(api_url(base_url, path), headers=h, params={"offset": 0, "limit": -1}, timeout=60)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def get_list(path, key):
        data = get(path)
        return (data or {}).get(key, [])

    print(f"\nDownloading complete model (id: {model_id})...")
    model      = get(f"model/dataModels/{model_id}")
    tables     = get_list(f"model/dataModels/{model_id}/tables",      "tables")
    attributes = get_list(f"model/dataModels/{model_id}/attributes",  "attributes")
    fact_mets  = get_list(f"model/dataModels/{model_id}/factMetrics", "factMetrics")
    metrics    = get_list(f"model/dataModels/{model_id}/metrics",      "metrics")
    hierarchy  = get(f"model/dataModels/{model_id}/hierarchy")

    raw = {
        "model": model, "tables": tables, "attributes": attributes,
        "factMetrics": fact_mets, "metrics": metrics, "hierarchy": hierarchy,
    }

    # Save to .temp/cache/<model_id>/
    cache_dir = os.path.join(TEMP_DIR, "cache", model_id)
    os.makedirs(os.path.join(cache_dir, "history"), exist_ok=True)

    orig_path = os.path.join(cache_dir, "original_v1.json")
    work_path = os.path.join(cache_dir, "working_copy.json")

    if not os.path.exists(orig_path):
        with open(orig_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
        print(f"  Original snapshot saved: {orig_path}")

    with open(work_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)

    print(f"  Tables: {len(tables)} | Attributes: {len(attributes)} | "
          f"Fact Metrics: {len(fact_mets)} | Derived Metrics: {len(metrics)}")
    print(f"  Cache Directory: {cache_dir}")
    return raw, cache_dir


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Browser Auth + Batch API — Mosaic Skill")
    p.add_argument("--base-url",      required=True, help="Base Library URL (e.g., https://host/MicroStrategyLibrary)")
    p.add_argument("--list-projects", action="store_true", help="Authenticate and list available projects")
    p.add_argument("--project-id",    default=None, help="Strategy Project GUID")
    p.add_argument("--data-model-id", default=None, help="Mosaic Data Model GUID")
    return p.parse_args()


def authenticate(base_url):
    """Opens browser, captures token, persists session, and starts keepalive daemon."""
    session_data = {}
    done_event   = threading.Event()

    t = threading.Thread(
        target=open_browser_and_capture,
        args=(base_url, session_data, done_event),
        daemon=True,
    )
    t.start()

    print("Waiting for login in the browser...")
    for _ in range(300):
        if session_data.get("auth_token"):
            break
        time.sleep(1)

    if not session_data.get("auth_token"):
        print("[ERROR] Token was not captured within the timeout period.", file=sys.stderr)
        sys.exit(1)

    token   = session_data["auth_token"]
    cookies = session_data.get("cookies", {})

    save_session(base_url, token, cookies)
    print("[Session] Session saved to .temp/session.json")

    start_keepalive()
    done_event.wait(timeout=10)
    return token, cookies


def main():
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    if base_url.endswith("/app"):
        base_url = base_url[:-4]

    # Try reusing existing session
    sess = load_session()
    token   = sess["auth_token"] if sess else None
    cookies = sess.get("cookies", {}) if sess else {}

    # ── MODE 1: Authenticate + list projects ──────────────────────────────
    if args.list_projects:
        if not token:
            token, cookies = authenticate(base_url)

        print("\nFetching projects...")
        try:
            projects = fetch_projects(base_url, token, cookies)
        except Exception as e:
            print(f"[ERROR] Failed to list projects: {e}")
            # Session may have expired — re-authenticate
            token, cookies = authenticate(base_url)
            projects = fetch_projects(base_url, token, cookies)

        print(f"\n{len(projects)} project(s) found:\n")
        for i, p in enumerate(projects, 1):
            print(f"  [{i}] {p.get('name')}  (id: {p.get('id')})")

        # Save project list to cache
        with open(os.path.join(TEMP_DIR, "projects.json"), "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2, ensure_ascii=False)
        return

    # ── MODE 2: List models in a project ─────────────────────────────────
    if args.project_id and not args.data_model_id:
        if not token:
            token, cookies = authenticate(base_url)

        print(f"\nSearching Mosaic models in project: {args.project_id}...")
        try:
            models = fetch_models(base_url, token, cookies, args.project_id)
        except Exception as e:
            print(f"[ERROR] Failed to list models: {e}")
            token, cookies = authenticate(base_url)
            models = fetch_models(base_url, token, cookies, args.project_id)

        if not models:
            print("No Mosaic Data Models found in this project.")
            return

        print(f"\n{len(models)} model(s) found:\n")
        for i, m in enumerate(models, 1):
            print(f"  [{i}] {m.get('name')}  (id: {m.get('id')})")

        # Save list to temporary cache
        with open(os.path.join(TEMP_DIR, "models.json"), "w", encoding="utf-8") as f:
            json.dump({"project_id": args.project_id, "models": models}, f, indent=2, ensure_ascii=False)
        return

    # ── MODE 3: Download complete model ──────────────────────────────────
    if args.project_id and args.data_model_id:
        if not token:
            token, cookies = authenticate(base_url)

        try:
            raw, cache_dir = fetch_full_model(base_url, token, cookies, args.project_id, args.data_model_id)
        except Exception as e:
            print(f"[ERROR] Failed to download model: {e}")
            token, cookies = authenticate(base_url)
            raw, cache_dir = fetch_full_model(base_url, token, cookies, args.project_id, args.data_model_id)

        info = (raw.get("model") or {}).get("information", {})
        print(f"\nModel '{info.get('name', args.data_model_id)}' loaded successfully.")
        return

    print("Please specify --list-projects, --project-id, or --project-id with --data-model-id", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
