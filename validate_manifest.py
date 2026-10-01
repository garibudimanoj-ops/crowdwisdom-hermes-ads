#!/usr/bin/env python3
"""Validate outputs/assets/asset_manifest.json against the cinematography plan."""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(BASE_DIR, "outputs", "assets", "asset_manifest.json")
PLAN_PATH = os.path.join(BASE_DIR, "outputs", "visual_prompts", "full_cinematography_plan.json")

errors = []


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    manifest = load_json(MANIFEST_PATH)
    plan = load_json(PLAN_PATH)

    # --- 1. Top-level structure ---
    for key in ("version", "project", "generated_at", "source_plan", "assets", "scene_mapping"):
        if key not in manifest:
            errors.append("Missing top-level key: %s" % key)

    # --- 2. Assets array ---
    assets = manifest.get("assets", [])
    asset_ids = set()
    for a in assets:
        aid = a.get("asset_id")
        if not aid:
            errors.append("Asset missing asset_id")
            continue
        if aid in asset_ids:
            errors.append("Duplicate asset_id: %s" % aid)
        asset_ids.add(aid)

        # Required fields for non-missing assets
        if not a.get("missing"):
            for field in ("asset_type", "source", "local_path", "duration", "license", "provenance", "why_selected"):
                if not a.get(field):
                    errors.append("Asset %s missing field: %s" % (aid, field))

        # Scene id must be int 1-5
        sid = a.get("scene_id")
        if not isinstance(sid, int) or not (1 <= sid <= 5):
            errors.append("Asset %s has invalid scene_id: %r" % (aid, sid))

        # Local path validation (skip missing assets)
        local_path = a.get("local_path")
        if a.get("missing"):
            continue
        if not local_path:
            errors.append("Asset %s has no local_path and is not marked missing" % aid)
            continue
        full_path = os.path.join(BASE_DIR, local_path)
        if not os.path.exists(full_path):
            errors.append("Broken path: %s" % local_path)

    # --- 3. Scene mapping ---
    scene_mapping = manifest.get("scene_mapping", [])
    mapped_scene_ids = set()
    for m in scene_mapping:
        sid = m.get("scene_id")
        if not isinstance(sid, int) or not (1 <= sid <= 5):
            errors.append("Scene mapping has invalid scene_id: %r" % sid)
            continue
        mapped_scene_ids.add(sid)

        primary = m.get("primary_asset")
        if primary and primary not in asset_ids:
            errors.append("Scene %s primary_asset %s not in assets" % (sid, primary))
        for sec in m.get("secondary_assets", []):
            if sec not in asset_ids:
                errors.append("Scene %s secondary_asset %s not in assets" % (sid, sec))
        fb = m.get("fallback_asset")
        if fb and fb not in asset_ids:
            errors.append("Scene %s fallback_asset %s not in assets" % (sid, fb))

    # All 5 scenes must be mapped
    for i in range(1, 6):
        if i not in mapped_scene_ids:
            errors.append("Scene %d missing from scene_mapping" % i)

    # --- 4. Acquisition metadata ---
    ac = manifest.get("acquisition_metadata", [])
    missing_scene_ids = {
        m["scene_id"] for m in scene_mapping if m.get("missing_asset") is True
    }
    acq_scene_ids = {a["scene_id"] for a in ac}
    missing_acq = missing_scene_ids - acq_scene_ids
    if missing_acq:
        errors.append(
            "Missing acquisition metadata for scenes: %s" % sorted(missing_acq)
        )

    # Acquisition metadata fields
    for a in ac:
        sid = a.get("scene_id")
        if not isinstance(sid, int) or not (1 <= sid <= 5):
            errors.append("Acquisition metadata invalid scene_id: %r" % sid)
        for field in ("required_visuals", "footage_queries", "duration_required", "tone"):
            if not a.get(field):
                errors.append("Acquisition metadata for scene %s missing field: %s" % (sid, field))

    # --- 5. Plan consistency ---
    plan_scenes = plan.get("scenes", [])
    if len(plan_scenes) != 5:
        errors.append("Cinematography plan has %d scenes, expected 5" % len(plan_scenes))

    # --- 6. Scene directory existence (informational only) ---
    for i in range(1, 6):
        scene_dir = os.path.join(BASE_DIR, "assets", "scenes", "scene_%02d" % i)
        if not os.path.isdir(scene_dir):
            errors.append("Scene directory missing: assets/scenes/scene_%02d" % i)

    # --- Report ---
    if errors:
        print("Asset manifest: FAIL")
        for e in errors:
            print("  - %s" % e)
        sys.exit(1)

    print("Asset manifest: PASS")


if __name__ == "__main__":
    main()