# Mosaic Data Model Reader & Enhancer

> **An agentic skill for inspecting, analyzing, optimizing, and publishing Strategy One / MicroStrategy Mosaic Data Models (`EMMA Cube`).**

This skill equips AI assistants (like Antigravity) with full lifecycle capabilities over Mosaic Data Models using the Strategy REST API and MSTrio Python SDK. It features interactive browser-based authentication (supporting SSO, SAML, and MFA), persistent session keepalive, single-request batch caching, granular changeset publishing, and safe automated rollbacks.

---

## 📦 Installation (Adding this Skill to your Project or Workspace)

You can install this skill directly from GitHub into any Antigravity workspace or globally across all your projects.

### Option A: Install in Current Project / Workspace (Recommended)
From the root of your target project:
```bash
# Ensure the skills directory exists
mkdir -p .agent/skills

# Clone the repository directly into your project's skills
git clone https://github.com/ViniciusYoata/mosaic-datamodel-reader.git .agent/skills/mosaic-datamodel-reader

# (Optional alternative) If your project uses Git, you can add it as a submodule:
# git submodule add https://github.com/ViniciusYoata/mosaic-datamodel-reader.git .agent/skills/mosaic-datamodel-reader
```

### Option B: Install Globally (Available across ALL your Antigravity Workspaces)
To make this skill available everywhere in your Antigravity environment without reinstalling per repository:
```bash
mkdir -p ~/.gemini/config/skills
git clone https://github.com/ViniciusYoata/mosaic-datamodel-reader.git ~/.gemini/config/skills/mosaic-datamodel-reader
```

---

## 🚀 Quick Start Guide

### 1. Automated Environment Setup (Recommended)

You can initialize the entire environment in **one single command** directly from chat or terminal:

#### ⚡ Option 1: Via Antigravity Chat (Easiest)
Just type in the prompt:
```
/mosaic-datamodel-reader init
```
The assistant will automatically create `.venv`, install `requirements.txt`, download Playwright Chromium, and confirm readiness.

#### ⚡ Option 2: Via Terminal Script
Run the automated initialization script from the skill directory:
```bash
cd .agent/skills/mosaic-datamodel-reader  # or ~/.gemini/config/skills/mosaic-datamodel-reader
./init.sh
```

---

<details>
<summary><b>🔧 Option 3: Manual Step-by-Step Setup (Alternative)</b></summary>

If you prefer to configure the environment manually:

```bash
cd .agent/skills/mosaic-datamodel-reader  # or ~/.gemini/config/skills/mosaic-datamodel-reader

# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Chromium browser for Playwright authentication
playwright install chromium
```
</details>

---

### 2. How to Trigger & Use the Skill in Antigravity

You can trigger the skill naturally in chat by mentioning Mosaic or Strategy data models. The assistant automatically mirrors your language (Portuguese, English, etc.):

#### Example Prompts:
* 🇧🇷 *"Quero analisar o modelo de dados Mosaic do projeto Greenfield"*
* 🇧🇷 *"Liste os projetos disponíveis no Strategy e mostre os modelos Mosaic"*
* 🇺🇸 *"Please inspect the Mosaic Data Model for sales in our project"*
* 🇺🇸 *"Help me add derived metrics and reorganize folders in my Mosaic model"*

---

### 3. Step-by-Step Interaction Flow

```
┌──────────────────────────┐
│ 1. Browser Login (1x)    │ ──► Captures token & cookies via Playwright
└─────────────┬────────────┘
              ▼
┌──────────────────────────┐
│ 2. Background Keepalive  │ ──► Silent daemon pings /api/auth/keepAlive every 2m
└─────────────┬────────────┘
              ▼
┌──────────────────────────┐
│ 3. Numbered Selection    │ ──► Lists projects and models: [1], [2], [3]
└─────────────┬────────────┘
              ▼
┌──────────────────────────┐
│ 4. Single Batch Download │ ──► Saves untouched original & working draft to local cache
└─────────────┬────────────┘
              ▼
┌──────────────────────────┐
│ 5. Local Modeling & Edit │ ──► Analyzes & edits working_copy.json without API overhead
└─────────────┬────────────┘
              ▼
┌──────────────────────────┐
│ 6. Granular Publish      │ ──► Commits changes in small Changesets (~30 ops/commit)
└──────────────────────────┘
```

---

## 📁 Repository & Directory Layout

```
mosaic-datamodel-reader/
├── SKILL.md                  # Main skill definition & agent instructions
├── README.md                 # This onboarding and quick reference guide
├── references/               # Technical references & guides
│   ├── api-reference.md      # Strategy REST API endpoints & Changeset rules
│   └── mstrio-guide.md       # MSTrio Python SDK reference & code examples
├── resources/                # Static assets & web templates
│   └── login_success.html    # Success landing page after browser login
├── scripts/                  # CLI and background Python tools
│   ├── quick_session.py      # Core CLI for authentication, listing, & fetching
│   ├── browser_auth.py       # Playwright browser automation for SSO/MFA
│   ├── session_keepalive.py  # Background token keepalive daemon
│   ├── fetch_model.py        # Alternative batch fetcher & markdown summarizer
│   ├── model_cache_manager.py# Local snapshot, backup, and rollback manager
│   ├── publish_model.py      # Granular Changeset publishing pipeline
│   └── mstrio_helper.py      # Official MSTrio SDK inspection helper
└── .temp/                    # Hidden local cache & active session state (git-ignored)
    ├── session.json          # Active session token, base URL, and cookies
    ├── keepalive.pid         # Background keepalive process ID
    └── cache/<model_id>/     # Untouched original snapshot & working copy
```

---

## 💡 Best Practices & Pro Tips

### ⚡ 1. Token Economy & Local Cache First
* All model inspections and edits should be made directly to `.temp/cache/<model_id>/working_copy.json`.
* Do not make repetitive GET requests to the Strategy server during analysis — the local working copy contains the complete model definition (tables, physical columns, attributes, forms, metrics, and hierarchies).

### 🔒 2. Single Browser Login (Persistent Session)
* Once authenticated, your session is saved to `.temp/session.json`.
* The background keepalive script (`session_keepalive.py`) pings the server every 120 seconds, preventing session expiration while you work.
* Subsequent runs will reuse the session automatically without opening the browser.

### 🧱 3. The 30-Operation Changeset Rule (CRITICAL)
* The Strategy Intelligence Server can trigger a `HTTP 500 timeout` if a single Changeset commit contains more than ~30 operations.
* Always use `scripts/publish_model.py`, which automatically chunks attribute and table changes into smaller, safe sequential batches.

### 🛡️ 4. Safe Pre-Publish Backups & Instant Rollback
* Before publishing modifications to the server, create a backup snapshot:
  ```bash
  .venv/bin/python3 scripts/model_cache_manager.py --model-id "<id>" --action backup --base-dir .temp/cache
  ```
* If a rollback is needed:
  ```bash
  .venv/bin/python3 scripts/model_cache_manager.py --model-id "<id>" --action rollback --base-dir .temp/cache
  ```

### 🌐 5. Multilingual Conversation
* Even though all code and skill files are in English, the assistant automatically adapts to your conversational language. You can speak freely in Portuguese, English, Spanish, etc.

---

## 🛠️ CLI Quick Reference

```bash
# 1. Authenticate & list available projects
.venv/bin/python3 scripts/quick_session.py --base-url "https://host/MicroStrategyLibrary" --list-projects

# 2. List Mosaic models inside a project
.venv/bin/python3 scripts/quick_session.py --base-url "https://host/MicroStrategyLibrary" --project-id "<PROJECT_GUID>"

# 3. Download and cache full model locally
.venv/bin/python3 scripts/quick_session.py --base-url "https://host/MicroStrategyLibrary" \
    --project-id "<PROJECT_GUID>" --data-model-id "<MODEL_GUID>"

# 4. Publish validated changes to Strategy ONE
.venv/bin/python3 scripts/publish_model.py <MODEL_GUID> <PROJECT_GUID>
```
