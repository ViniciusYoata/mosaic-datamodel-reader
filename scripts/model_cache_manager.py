"""
Local Cache and Versioning Manager for Mosaic Data Models.

Directory layout:
  .mosaic_cache/<data_model_id>/
     ├── original_v1.json         (untouched original snapshot fetched from API)
     ├── working_copy.json        (working draft manipulated locally)
     └── history/                 (backups generated prior to publishing to production)
           └── backup_YYYYMMDD_HHMMSS.json
"""

import argparse
import json
import os
import shutil
import sys
import time

CACHE_BASE_DIR = ".mosaic_cache"


def get_model_dir(model_id, base_dir=CACHE_BASE_DIR):
    return os.path.join(base_dir, model_id)


def init_cache(model_id, raw_model_data, base_dir=CACHE_BASE_DIR):
    """Initializes cache creating original_v1.json and working_copy.json if not present."""
    model_dir = get_model_dir(model_id, base_dir)
    os.makedirs(os.path.join(model_dir, "history"), exist_ok=True)

    orig_path = os.path.join(model_dir, "original_v1.json")
    work_path = os.path.join(model_dir, "working_copy.json")

    # Save original only if missing to preserve pristine origin snapshot
    if not os.path.exists(orig_path):
        with open(orig_path, "w", encoding="utf-8") as f:
            json.dump(raw_model_data, f, indent=2, ensure_ascii=False)
        print(f"[Cache] Original snapshot saved to: {orig_path}")

    # Create/update working copy
    with open(work_path, "w", encoding="utf-8") as f:
        json.dump(raw_model_data, f, indent=2, ensure_ascii=False)
    print(f"[Cache] Working draft (working_copy) ready at: {work_path}")
    return work_path


def create_backup(model_id, base_dir=CACHE_BASE_DIR):
    """Creates a backup copy of working_copy before publishing changes to API."""
    model_dir = get_model_dir(model_id, base_dir)
    work_path = os.path.join(model_dir, "working_copy.json")

    if not os.path.exists(work_path):
        raise FileNotFoundError(f"Working copy not found for model {model_id}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.json"
    backup_path = os.path.join(model_dir, "history", backup_filename)

    shutil.copy2(work_path, backup_path)
    print(f"[Cache Backup] Backup created prior to publishing: {backup_path}")
    return backup_path


def rollback(model_id, backup_file=None, base_dir=CACHE_BASE_DIR):
    """Restores working_copy from a specific historical backup or from the original version."""
    model_dir = get_model_dir(model_id, base_dir)
    work_path = os.path.join(model_dir, "working_copy.json")

    if backup_file:
        source_path = os.path.join(model_dir, "history", backup_file) if not os.path.isabs(backup_file) else backup_file
    else:
        source_path = os.path.join(model_dir, "original_v1.json")

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file for rollback not found: {source_path}")

    shutil.copy2(source_path, work_path)
    print(f"[Cache Rollback] Successfully rolled back: {source_path} -> {work_path}")
    return work_path


def list_backups(model_id, base_dir=CACHE_BASE_DIR):
    """Lists all available historical backups for a model."""
    model_dir = get_model_dir(model_id, base_dir)
    history_dir = os.path.join(model_dir, "history")
    if not os.path.exists(history_dir):
        return []
    files = sorted(os.listdir(history_dir), reverse=True)
    return [f for f in files if f.endswith(".json")]


def main():
    p = argparse.ArgumentParser(description="Local cache and versioning manager for Mosaic Data Models")
    p.add_argument("--model-id", required=True, help="Data Model GUID")
    p.add_argument("--action", choices=["init", "backup", "rollback", "list-backups"], required=True, help="Cache action to execute")
    p.add_argument("--backup-file", default=None, help="Backup filename to restore (if omitted in rollback, restores original_v1.json)")
    p.add_argument("--base-dir", default=CACHE_BASE_DIR, help="Base cache directory")

    args = p.parse_args()

    if args.action == "backup":
        create_backup(args.model_id, args.base_dir)
    elif args.action == "rollback":
        rollback(args.model_id, args.backup_file, args.base_dir)
    elif args.action == "list-backups":
        backups = list_backups(args.model_id, args.base_dir)
        print(f"\n{len(backups)} backup(s) available:\n")
        for i, b in enumerate(backups, 1):
            print(f"[{i}] {b}")


if __name__ == "__main__":
    main()
