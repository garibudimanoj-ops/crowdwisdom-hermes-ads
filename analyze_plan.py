import json

with open('outputs/visual_prompts/full_cinematography_plan.json') as f:
    plan = json.load(f)

print("=== CINEMATOGRAPHY PLAN SCENES ===")
for scene in plan['scenes']:
    sid = scene['scene_id']
    print("Scene %d: %ss-%ss (%ss)" % (sid, scene['start_seconds'], scene['end_seconds'], scene['duration_seconds']))
    print("  Creative goal: %s" % scene['creative_goal'][:80])
    for i, shot in enumerate(scene['shots']):
        shot_id = chr(65 + i)
        print("    Shot %s: %s - %s" % (shot_id, shot['shot_type'], shot['subject']))
        print("      %s..." % shot['visual_description'][:100])
        print("      Camera: %s, Motion: %s" % (shot['camera'], shot['camera_motion']))
        print("      Lighting: %s, Mood: %s" % (shot['lighting'], shot['mood']))
        print("      Footage queries: %s" % shot.get('footage_queries', []))
    print()

print("=== EXISTING ASSETS ===")
import os
for root, dirs, files in os.walk('outputs/assets'):
    for f in files:
        path = os.path.join(root, f)
        print("  %s (%d bytes)" % (path, os.path.getsize(path)))

print("=== NEW ASSET DIRECTORIES ===")
for root, dirs, files in os.walk('assets'):
    for d in sorted(dirs):
        print("  %s" % os.path.join(root, d))