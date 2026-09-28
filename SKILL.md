---
name: mosaic-datamodel-reader
description: Reads, summarizes, analyzes, and enhances a Strategy/MicroStrategy Mosaic Data Model via REST API or MSTrio SDK, featuring untouched/working local caching, versioning/rollback, numbered selection menus, interactive enhancement workflows, and automated environment initialization (/mosaic-datamodel-reader init). Use ALWAYS whenever the user mentions "Mosaic", "Mosaic Studio", "Strategy/MicroStrategy data model", "dataModels API", a "mosaic id" / "dataModelId", asks to init/setup the skill, or asks to read, summarize, analyze, review, or suggest improvements to a Strategy One data model.
---

# Mosaic Data Model Reader & Enhancer (Strategy REST API / MSTrio SDK)

> 🚨 **SCOPE RESTRICTION:**
> This skill is **strictly focused on the data modeling layer of the Mosaic Data Model**.
> **DO NOT execute and summarily decline** any administrative or infrastructure management requests (users, permissions, licenses, iServer configuration, schedules, etc.).

---

## 🛠️ Automated Skill Initialization (`/mosaic-datamodel-reader init`)

Whenever the user invokes `/mosaic-datamodel-reader init` (or asks to "initialize", "setup", or "prepare" the skill environment), OR whenever the assistant detects that `.venv` or Playwright Chromium is not yet configured:
1. **Execute the automated initialization script:**
   ```bash
   # From the skill directory:
   python3 scripts/init_env.py
   # Or via root wrapper:
   ./init.sh
   ```
2. The script automatically:
   - Validates Python 3.10+
   - Creates the local virtual environment `.venv` if missing
   - Installs/updates dependencies from `requirements.txt`
   - Downloads Playwright Chromium binaries (`playwright install chromium`)
   - Prepares `.temp/cache/` directories
3. **Acknowledge and confirm readiness** to the user in their spoken language once complete.

---

## 🌐 Multilingual Interaction & User Language Mirroring (CRITICAL RULE)

> 🗣️ **LANGUAGE ADAPTATION DIRECTIVE:**
> Although this skill definition, documentation, and underlying scripts are standardized in **English**, the assistant **MUST ALWAYS detect and conduct all interactions in the language spoken by the user** (e.g., Brazilian Portuguese, English, Spanish, French, etc.).
> - If the user initiates or communicates in Portuguese, all conversational messages, numbered selection menus, enhancement options, confirmation prompts, and analysis summaries **MUST be presented in Portuguese**.
> - If the user communicates in English, respond in English.
> - If the user communicates in any other language, dynamically mirror their language across all user-facing interactions.
> - Always respect workspace language constraints (such as `sempre responda em PTBR`) with highest precedence.

---

## ⚡ Connection Optimization & Token Economy Rules

1. **Persistent Session:** Always attempt to reuse the existing session in `.temp/session.json` before prompting for a new login. The background keepalive daemon (`session_keepalive.py`) automatically maintains the token active.
2. **Single Batch Request:** Fetch the complete data model in a single execution and store it under `.temp/cache/<model_id>/`.
3. **Local Cache First:** All subsequent analyses MUST read `.temp/cache/<model_id>/working_copy.json` — avoiding repeated API calls.
4. **Concise Responses:** Provide clear, actionable suggestions to conserve context window tokens.

---

## 🔢 Numbered Selection Rule (UX)

Always list projects and models with ordinal numbers. Accept **number**, **name**, or **GUID**:

```
Available projects:
[1] Greenfield_CeA  (id: 9627E...)
[2] MicroStrategy Tutorial  (id: B7CA9...)

Which project would you like to access?
```

Wait for user response before fetching models. **DO NOT list models before the user selects a project.**

---

## 💾 Local Cache Structure (hidden `.temp` directory inside the skill)

```
.temp/
├── session.json              ← active token + cookies + base_url
├── keepalive.pid             ← keepalive daemon PID
├── projects.json             ← cached project list
├── models.json               ← models of selected project
└── cache/
    └── <data_model_id>/
        ├── original_v1.json  ← untouched original snapshot
        ├── working_copy.json ← local working draft
        └── history/          ← pre-publish backups for rollback
```

---

## 🔑 Sequential Authentication and Selection Flow

### Step 1 — Authenticate and list projects (opens browser once)
```bash
.venv/bin/python3 scripts/quick_session.py --base-url "<url>" --list-projects
```
- If `.temp/session.json` contains a valid unexpired token, **DO NOT open the browser** — reuse existing session.
- The browser displays `resources/login_success.html` after capturing the token and closes automatically after 4 seconds.
- A keepalive background daemon is spawned to keep the session alive.

### Step 2 — List models for chosen project (no new login required)
```bash
.venv/bin/python3 scripts/quick_session.py --base-url "<url>" --project-id "<project_id>"
```

### Step 3 — Download complete model in batch (no new login required)
```bash
.venv/bin/python3 scripts/quick_session.py --base-url "<url>" \
    --project-id "<project_id>" --data-model-id "<model_id>"
```

---

## 💡 Interactive Enhancement Flows

After loading `working_copy.json` for the model, present the user with the following interactive enhancement options (translated to the user's spoken language):

1. **📊 [1] Enhance Metrics & Facts** — Derived temporal metrics (YoY, YTD, MTD), Ratios, Share %, custom formulas.
2. **🔗 [2] Enhance Relationships & Modeling** — Validate `keyForms`, referential integrity, attribute sufficiency for filtering.
3. **📁 [3] Organize & Structure the Model** — Logical folders, sub-folders, and naming conventions.
4. **⚡ [4] Performance & Governance Audit** — Partitioning, `sampling`, `dataServeMode`, and memory limits.

---

## 🔄 Backup, Publication & Rollback

### Create Pre-publish Backup:
```bash
.venv/bin/python3 scripts/model_cache_manager.py --model-id "<id>" --action backup --base-dir .temp/cache
```

### Publish Changes to Strategy ONE (Changeset Workflow):
> 🚨 **NEVER send a PUT/PATCH with the entire JSON payload to the root dataModel.** The Strategy ONE server ignores internal edits and returns a Changeset error.
> Always use the canonical granular sub-resource publication script:
```bash
.venv/bin/python3 scripts/publish_model.py <data_model_id> <project_id>
```

### Rollback:
```bash
.venv/bin/python3 scripts/model_cache_manager.py --model-id "<id>" --action rollback --base-dir .temp/cache
```

---

## 📌 Architecture Rules & API Lessons

### Changeset Rules (CRITICAL)

> 🚨 **Being inside a Changeset DOES NOT mean changes are committed to the model.**
> All changes only exist in the live model AFTER a commit returns HTTP status `201`. A Changeset with HTTP status `500` reverts **all** operations in that session, without exception.

1. **Verification ALWAYS outside Changeset:**
   - Every verification GET call must be executed **without** the `X-MSTR-MS-Changeset` header to inspect the server's committed state, not the draft changeset state.
   - `GET /api/model/dataModels/{id}/folders` **without** the changeset header = true persisted server state.

2. **Maximum Changeset Size:**
   - A Changeset containing too many operations (e.g., 79 PATCHes + 3 POSTs + 2 DELETEs) triggers a **500 timeout** during commit, rolling back everything.
   - **Rule:** Each Changeset must contain at most **~30 operations**. For larger batches, partition into multiple smaller Changesets with independent commits.

3. **Dependencies Between Changesets:**
   - Never reference a GUID generated by an uncommitted Changeset inside another Changeset.
   - If Changeset A fails (500), any GUID returned by a POST within it **does not exist** on the server. Changeset B relying on that pseudo-GUID will also fail.
   - **Rule:** Always commit and verify (outside the changeset) before using newly created GUIDs.

4. **Name Conflict when combining DELETE + CREATE in the same Changeset:**
   - `DELETE /model/dataModels/{id}/folders/{guid}` removes the internal model reference, but the **iServer catalog object** with that name may still linger.
   - Attempting `POST /model/dataModels/{id}/folders` with the same name in the same commit triggers `"An object with name X already exists in target folder"` (500).
   - **Solution:** First delete the catalog object via `DELETE /api/objects/{guid}?type=8` (outside changeset), then create the new folder via model API.

### Model Sub-folder Rules

5. **Correct Endpoint for Folders Visible in Mosaic Studio:**
   - `POST /api/model/dataModels/{model_id}/folders` → folders appear in Mosaic Studio ✅
   - `POST /api/folders` (Catalog API) → folders DO NOT appear in Mosaic Studio ❌

6. **Creating Sub-folders (Proper Payload):**
   ```json
   { "information": { "name": "Folder Name", "destinationFolderId": "<parent_folder_guid>" } }
   ```
   - For root model level folder: `"destinationFolderId": "<model schemaFolderId>"`
   - Store returned GUIDs IMMEDIATELY after confirmed commit.

7. **Remapping Attributes to Folders:**
   - Use `PATCH /model/dataModels/{id}/attributes/{attr_id}` with payload `{"information": {"destinationFolderId": "<new_guid>"}}`.
   - To ensure all attributes are captured, filter by current `destinationFolderId` (old folder GUID), NOT merely by `attributeLookupTable.name` (which might be incomplete).
   - Correct pattern: `if attr["information"].get("destinationFolderId") == "<old_guid>": remap`

### Attributes & Metrics Rules

8. **Updating Attributes (Avoiding `expression.tree` error):**
   - Use `PATCH /model/dataModels/{id}/attributes/{attr_id}` with minimal payload: `{"information": {"destinationFolderId": "<guid>"}}`.

9. **Updating Metrics (Avoiding `dimty` / `expression` error):**
   - Use `PUT /model/dataModels/{id}/metrics/{metric_id}` containing only `{"information": ..., "format": ...}` — never include `expression` or `dimty`.

10. **Synchronizing Hierarchies & Isolated Attributes:**
    - Every 1:N relationship inserted into `hierarchy.relationships` requires simultaneous removal of that attribute from `hierarchy.isolatedAttributes`.
