import json
import os

manifest_path = r"C:\AI Projects\crowdwisdom-hermes-ads\outputs\assets\asset_manifest.json"

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Update generated_at
from datetime import datetime
manifest['generated_at'] = datetime.utcnow().isoformat() + 'Z'

# Update asset_006 for Scene 5 Pexels video
scene_5_asset = {
    "asset_id": "asset_006",
    "scene_id": 5,
    "asset_type": "video",
    "source": "Pexels",
    "source_url": "https://www.pexels.com/video/focused-man-doing-paperwork-9464299/",
    "local_path": "assets/scenes/scene_05/primary.mp4",
    "duration": 29.4,
    "license": "Pexels License",
    "provenance": "Downloaded from Pexels: Focused man doing paperwork",
    "why_selected": "Calm, professional businessman working at desk - fits resolved/confident ending"
}
# Update or add the asset
asset_found = False
for i, asset in enumerate(manifest['assets']):
    if asset['asset_id'] == 'asset_006':
        manifest['assets'][i] = scene_5_asset
        asset_found = True
        break
if not asset_found:
    manifest['assets'].append(scene_5_asset)

# Update scene_mapping for Scene 5
for scene_map in manifest['scene_mapping']:
    if scene_map['scene_id'] == 5:
        scene_map['primary_asset'] = 'asset_006'
        scene_map['secondary_assets'] = []
        scene_map['fallback_asset'] = None
        scene_map['missing_asset'] = False
        break

# Update acquisition_metadata for Scene 5 to mark as satisfied
for acq in manifest['acquisition_metadata']:
    if acq['scene_id'] == 5:
        acq['required_visuals'] = [
            "CrowdWisdom logo and tagline",
            "dark background with faint trader silhouette", 
            "static wide shot logo fade in",
            "businessman working calmly at desk"
        ]
        acq['footage_queries'] = ["focused man doing paperwork desk"]  # Query that acquired the Pexels asset
        acq['duration_required'] = 7.0
        acq['tone'] = "calm, resolved, confident"
        acq['asset_status'] = "acquired_via_pexels_9464299"
        acq['real_footage_required'] = False
        acq['product_ui_required'] = True  # Logo/tagline will be added in Remotion
        acq['motion_graphics_required'] = True  # Logo fade in, tagline slide up
        break

# Update acquisition_metadata for Scenes 2-4 to reflect hybrid approach
# Scene 2: trader hands + monitors (real footage) + CrowdWisdom panel (UI) + motion graphics (chaos->order)
for acq in manifest['acquisition_metadata']:
    if acq['scene_id'] == 2:
        acq['required_visuals'] = [
            "trader's hand moving to toggle switch",
            "slow pull back from close-up on hands to wide desk shot",
            "left chaotic monitor flood and right organized CrowdWisdom panel",
            "push-in on CrowdWisdom panel"
        ]
        acq['footage_queries'] = [
            "trader hand toggle desk monitor",
            "split screen chaos order comparison",
            "CrowdWisdom panel interface"
        ]
        acq['duration_required'] = 10.0
        acq['tone'] = "transition from chaos to order"
        acq['real_footage_required'] = True  # Trader hands, monitors, workspace
        acq['product_ui_required'] = True   # CrowdWisdom panel UI
        acq['motion_graphics_required'] = True  # Chaos to ordered information transition
        break

# Scene 3: analyst environment (real footage) + conviction/consensus/recency meters (UI) + converging signals (motion graphics)
for acq in manifest['acquisition_metadata']:
    if acq['scene_id'] == 3:
        acq['required_visuals'] = [
            "CrowdWisdom research panel with conviction, consensus, recency meters",
            "static close-up panel with slow tilt upward",
            "converging signal lines"
        ]
        acq['footage_queries'] = [
            "CrowdWisdom research panel",
            "data scoring meters animation",
            "signal lines converging visualization"
        ]
        acq['duration_required'] = 10.0
        acq['tone'] = "building, rhythmic"
        acq['real_footage_required'] = True   # Analyst/data environment
        acq['product_ui_required'] = True    # Conviction/consensus/recency meters UI
        acq['motion_graphics_required'] = True # Signals converging animation
        break

# Scene 4: focused professional (real footage) + structured research card (UI) + card animation (motion graphics)
for acq in manifest['acquisition_metadata']:
    if acq['scene_id'] == 4:
        acq['required_visuals'] = [
            "research card UI elements animating in",
            "slow push-in on research card",
            "shallow depth of field blurring background"
        ]
        acq['footage_queries'] = [
            "research card UI interface",
            "structured data card",
            "analysis results panel"
        ]
        acq['duration_required'] = 10.0
        acq['tone'] = "focused, confident"
        acq['real_footage_required'] = True   # Focused trader/analyst in workspace
        acq['product_ui_required'] = True    # Structured research card UI
        acq['motion_graphics_required'] = True # Cards appearing / slow push-in animation
        break

# Write updated manifest
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)

print("Manifest updated successfully")