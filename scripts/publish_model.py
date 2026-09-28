#!/usr/bin/env python3
"""
Publish Module for Strategy Mosaic Data Models via REST API.

Implements a safe, granular sub-resource publishing workflow using
independent Changesets capped at ~30 operations per commit:
  - Phase 1: Deletion of removed attributes and tables
  - Phase 2: Updating attributes in chunks of up to 28 (with name, description, and destinationFolderId)
  - Phase 3: Updating metrics (if any)
  - Phase 4: Updating hierarchy tree and 1:N relationships
"""

import json
import os
import requests
import sys

def make_headers(token, project_id, changeset_id=None):
    h = {
        "X-MSTR-AuthToken": token,
        "X-MSTR-ProjectID": project_id,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if changeset_id:
        h["X-MSTR-MS-Changeset"] = changeset_id
    return h


class ChangesetRunner:
    def __init__(self, session, base_url, token, project_id, cookies):
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project_id = project_id
        self.cookies = cookies

    def run_changeset(self, phase_name, op_func):
        """Opens a changeset, executes operations, and commits."""
        url_cs = f"{self.base_url}/api/model/changesets"
        headers_base = make_headers(self.token, self.project_id)
        
        r_cs = self.session.post(url_cs, json={}, headers=headers_base, verify=True, timeout=30)
        r_cs.raise_for_status()
        cs_id = r_cs.json()["id"]
        headers_cs = make_headers(self.token, self.project_id, cs_id)
        
        print(f"\n[{phase_name}] Starting Changeset: {cs_id}")
        try:
            op_func(headers_cs)
            
            print(f"[{phase_name}] Committing changes...")
            url_commit = f"{self.base_url}/api/model/changesets/{cs_id}/commit"
            r_commit = self.session.post(url_commit, headers=headers_cs, verify=True, timeout=90)
            r_commit.raise_for_status()
            print(f"[{phase_name}] ✅ Commit confirmed successfully!")
        except Exception as e:
            print(f"[{phase_name}] ❌ Error during Changeset: {e}")
            try:
                self.session.delete(f"{self.base_url}/api/model/changesets/{cs_id}", headers=headers_cs, timeout=15)
                print(f"[{phase_name}] Changeset safely aborted.")
            except Exception:
                pass
            raise


def publish_model(base_url, token, cookies, project_id, model_id, working_copy_data, orig_data=None):
    session = requests.Session()
    session.cookies.update(cookies)
    runner = ChangesetRunner(session, base_url, token, project_id, cookies)
    
    print("==================================================================")
    print("=== STARTING PUBLISH TO STRATEGY ONE (CHANGESET WORKFLOW) ===")
    print(f"Model: {model_id} | Project: {project_id}")
    print("==================================================================")

    # ── PHASE 1: Deletion of removed objects (tables and attributes) ─────────
    if orig_data:
        wc_attr_ids = {a["information"]["objectId"] for a in working_copy_data.get("attributes", [])}
        orig_attr_ids = {a["information"]["objectId"]: a["information"]["name"] for a in orig_data.get("attributes", [])}
        deleted_attr_ids = [(oid, orig_attr_ids[oid]) for oid in orig_attr_ids if oid not in wc_attr_ids]

        wc_tbl_ids = {t["information"]["objectId"] for t in working_copy_data.get("tables", [])}
        orig_tbl_ids = {t["information"]["objectId"]: t["information"]["name"] for t in orig_data.get("tables", [])}
        deleted_tbl_ids = [(oid, orig_tbl_ids[oid]) for oid in orig_tbl_ids if oid not in wc_tbl_ids]

        if deleted_attr_ids or deleted_tbl_ids:
            def phase1_ops(h_cs):
                for oid, name in deleted_attr_ids:
                    print(f"  - Deleting attribute: {name} ({oid})")
                    r = session.delete(f"{base_url}/api/model/dataModels/{model_id}/attributes/{oid}", headers=h_cs, timeout=15)
                    if r.status_code not in [200, 204, 404]:
                        print(f"    Notice: status {r.status_code} while deleting attribute {name}: {r.text[:100]}")
                for oid, name in deleted_tbl_ids:
                    print(f"  - Deleting table: {name} ({oid})")
                    r = session.delete(f"{base_url}/api/model/dataModels/{model_id}/tables/{oid}", headers=h_cs, timeout=15)
                    if r.status_code not in [200, 204, 404]:
                        print(f"    Notice: status {r.status_code} while deleting table {name}: {r.text[:100]}")

            runner.run_changeset("Phase 1: Deletion of Removed Objects", phase1_ops)

    # ── PHASE 2: Updating Attributes in chunks up to 28 ───────────────────────
    attributes = working_copy_data.get("attributes", [])
    chunk_size = 28
    chunks = [attributes[i:i + chunk_size] for i in range(0, len(attributes), chunk_size)]
    print(f"\nUpdating {len(attributes)} attributes in {len(chunks)} batch(es)...")

    for idx, chunk in enumerate(chunks, 1):
        def make_chunk_op(c_items):
            def chunk_ops(h_cs):
                ok_count = 0
                for attr in c_items:
                    attr_id = attr["information"]["objectId"]
                    dest_folder = attr["information"].get("destinationFolderId")
                    patch_payload = {
                        "information": {
                            "name": attr["information"]["name"],
                            "description": attr["information"].get("description", ""),
                            "destinationFolderId": dest_folder
                        }
                    }
                    url_attr = f"{base_url}/api/model/dataModels/{model_id}/attributes/{attr_id}"
                    r_attr = session.patch(url_attr, json=patch_payload, headers=h_cs, verify=True, timeout=15)
                    if r_attr.status_code in [200, 204]:
                        ok_count += 1
                    else:
                        print(f"    Failed updating attribute {attr['information']['name']}: {r_attr.status_code} - {r_attr.text[:150]}")
                print(f"  Batch {idx}: {ok_count}/{len(c_items)} attributes updated via PATCH.")
            return chunk_ops

        runner.run_changeset(f"Phase 2.{idx}: Attribute Update (Batch {idx}/{len(chunks)})", make_chunk_op(chunk))

    # ── PHASE 3: Metrics (if present) ─────────────────────────────────────────
    metrics = working_copy_data.get("metrics", [])
    if metrics:
        def phase3_ops(h_cs):
            for metric in metrics:
                metric_id = metric["information"]["objectId"]
                url_met = f"{base_url}/api/model/dataModels/{model_id}/metrics/{metric_id}"
                put_payload = {
                    "information": metric["information"],
                    "format": metric.get("format", {})
                }
                session.put(url_met, json=put_payload, headers=h_cs, verify=True, timeout=15)
        runner.run_changeset("Phase 3: Metrics", phase3_ops)

    # ── PHASE 4: Hierarchy and 1:N Relationships ─────────────────────────────
    hierarchy = working_copy_data.get("hierarchy")
    if hierarchy:
        def phase4_ops(h_cs):
            print(f"  Sending {len(hierarchy.get('relationships', []))} 1:N relationships and "
                  f"{len(hierarchy.get('isolatedAttributes', []))} isolated attributes...")
            url_hier = f"{base_url}/api/model/dataModels/{model_id}/hierarchy"
            r_hier = session.put(url_hier, json=hierarchy, headers=h_cs, verify=True, timeout=45)
            r_hier.raise_for_status()

        runner.run_changeset("Phase 4: Hierarchy and 1:N Relationships", phase4_ops)

    print("\n" + "="*66)
    print("🚀 PUBLISH SUCCESSFULLY COMPLETED IN STRATEGY ONE!")
    print("="*66)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: publish_model.py <model_id> <project_id>")
        sys.exit(1)
    
    m_id = sys.argv[1]
    p_id = sys.argv[2]
    
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(skill_dir, ".temp")
    session_file = os.path.join(temp_dir, "session.json")
    with open(session_file, "r", encoding="utf-8") as f:
        sess = json.load(f)
    
    work_file = os.path.join(temp_dir, "cache", m_id, "working_copy.json")
    with open(work_file, "r", encoding="utf-8") as f:
        wc = json.load(f)
        
    orig_file = os.path.join(temp_dir, "cache", m_id, "original_v1.json")
    orig = None
    if os.path.exists(orig_file):
        with open(orig_file, "r", encoding="utf-8") as f:
            orig = json.load(f)
        
    publish_model(sess["base_url"], sess["auth_token"], sess.get("cookies", {}), p_id, m_id, wc, orig)
