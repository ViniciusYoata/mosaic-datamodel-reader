#!/usr/bin/env python3
"""
Automated environment setup script for Mosaic Data Model Reader Skill.

Performs:
  1. Validates Python version (>= 3.10).
  2. Creates local virtual environment (.venv) if missing.
  3. Upgrades pip and installs packages from requirements.txt.
  4. Downloads Playwright Chromium browser binaries.
  5. Initializes local cache directories (.temp and .temp/cache).
"""

import os
import subprocess
import sys
import venv

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_DIR = os.path.join(SKILL_DIR, ".venv")
REQ_FILE = os.path.join(SKILL_DIR, "requirements.txt")
TEMP_DIR = os.path.join(SKILL_DIR, ".temp")
CACHE_DIR = os.path.join(TEMP_DIR, "cache")

is_win = sys.platform.startswith("win")
VENV_PYTHON = os.path.join(VENV_DIR, "Scripts" if is_win else "bin", "python.exe" if is_win else "python3")
VENV_PIP = os.path.join(VENV_DIR, "Scripts" if is_win else "bin", "pip.exe" if is_win else "pip3")
VENV_PLAYWRIGHT = os.path.join(VENV_DIR, "Scripts" if is_win else "bin", "playwright.exe" if is_win else "playwright")


def log(msg, emoji="🔹"):
    print(f"{emoji} {msg}", flush=True)


def check_python_version():
    if sys.version_info < (3, 10):
        print(f"❌ Python 3.10 or higher is required. Found: {sys.version}", file=sys.stderr)
        sys.exit(1)
    log(f"Python version: {sys.version.split()[0]} [OK]")


def setup_venv():
    if not os.path.exists(VENV_PYTHON):
        log(f"Creating virtual environment in: {VENV_DIR}...")
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(VENV_DIR)
        log("Virtual environment created [OK]", "✅")
    else:
        log("Virtual environment already exists [OK]", "✅")


def install_requirements():
    if not os.path.exists(REQ_FILE):
        log(f"requirements.txt not found at {REQ_FILE}, skipping pip install.", "⚠️")
        return

    log("Installing dependencies from requirements.txt...")
    cmd = [VENV_PYTHON, "-m", "pip", "install", "--upgrade", "pip"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

    cmd_reqs = [VENV_PYTHON, "-m", "pip", "install", "-r", REQ_FILE]
    res = subprocess.run(cmd_reqs, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Failed to install dependencies:\n{res.stderr}", file=sys.stderr)
        sys.exit(1)
    log("Python dependencies installed successfully [OK]", "✅")


def install_playwright_browsers():
    log("Installing Playwright Chromium browser...")
    cmd = [VENV_PLAYWRIGHT, "install", "chromium"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        # Fallback via python -m playwright
        cmd_fallback = [VENV_PYTHON, "-m", "playwright", "install", "chromium"]
        res_fb = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if res_fb.returncode != 0:
            print(f"❌ Failed to install Chromium browser:\n{res_fb.stderr}", file=sys.stderr)
            sys.exit(1)
    log("Playwright Chromium browser installed [OK]", "✅")


def setup_temp_dirs():
    os.makedirs(CACHE_DIR, exist_ok=True)
    log(f"Cache directories verified at {TEMP_DIR} [OK]", "✅")


def main():
    print("=" * 60)
    print("🚀 Initializing Mosaic Data Model Reader Environment")
    print("=" * 60)
    check_python_version()
    setup_venv()
    install_requirements()
    install_playwright_browsers()
    setup_temp_dirs()
    print("=" * 60)
    print("🎉 Skill environment is fully prepared and ready to use!")
    print(f"   Interpreter: {VENV_PYTHON}")
    print("=" * 60)


if __name__ == "__main__":
    main()
