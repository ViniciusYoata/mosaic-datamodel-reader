"""
Keepalive daemon for MicroStrategy session.

Calls /api/auth/keepAlive every 2 minutes to keep the token active
while Antigravity is in use.

Usage:
  .venv/bin/python3 scripts/session_keepalive.py --session-file .temp/session.json &
"""

import argparse
import json
import os
import signal
import sys
import time
import requests


def parse_args():
    p = argparse.ArgumentParser(description="MicroStrategy session keepalive daemon")
    p.add_argument("--session-file", default=".temp/session.json", help="Path to session JSON file")
    p.add_argument("--interval", type=int, default=120, help="Interval in seconds (default: 120)")
    return p.parse_args()


def keepalive(base_url, token, cookies):
    s = requests.Session()
    s.cookies.update(cookies or {})
    headers = {"X-MSTR-AuthToken": token, "Accept": "application/json"}
    url = base_url.rstrip("/") + "/api/auth/keepAlive"
    resp = s.put(url, headers=headers, verify=True, timeout=15)
    return resp.status_code in (200, 204)


def main():
    args = parse_args()

    # Write own PID for external process management
    pid_file = os.path.join(os.path.dirname(args.session_file), "keepalive.pid")
    os.makedirs(os.path.dirname(args.session_file), exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    def on_exit(sig, frame):
        try:
            os.remove(pid_file)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_exit)
    signal.signal(signal.SIGINT, on_exit)

    print(f"[Keepalive] Started (PID {os.getpid()}) — interval: {args.interval}s", flush=True)

    while True:
        time.sleep(args.interval)
        if not os.path.exists(args.session_file):
            print("[Keepalive] Session file not found. Terminating.", flush=True)
            break
        try:
            with open(args.session_file, "r", encoding="utf-8") as f:
                sess = json.load(f)
            base_url = sess.get("base_url", "")
            token    = sess.get("auth_token", "")
            cookies  = sess.get("cookies", {})
            if not token:
                print("[Keepalive] Token missing. Terminating.", flush=True)
                break
            ok = keepalive(base_url, token, cookies)
            status = "OK" if ok else "FAILED"
            print(f"[Keepalive] {time.strftime('%H:%M:%S')} — keepAlive: {status}", flush=True)
            if not ok:
                print("[Keepalive] Session expired. Terminating daemon.", flush=True)
                break
        except Exception as e:
            print(f"[Keepalive] Error: {e}", flush=True)

    try:
        os.remove(pid_file)
    except Exception:
        pass


if __name__ == "__main__":
    main()
