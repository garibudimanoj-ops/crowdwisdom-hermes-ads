$ErrorActionPreference = "Stop"
$json = Get-Content "C:\AI Projects\crowdwisdom-hermes-ads\outputs\video_production\shot_list.json" -Raw | ConvertFrom-Json
$shots = $json.shot_list
Write-Output "Total shots: $($shots.Count)"

$scenes = @{1 = "0,8"; 2 = "8,18"; 3 = "18,28"; 4 = "28,38"; 5 = "38,45" }
$errors = @()

foreach ($s in $shots) {
    $sid = $s.scene_id
    $parts = $scenes[$sid].Split(",")
    $scene_start = [double]$parts[0]
    $scene_end = [double]$parts[1]
    if (-not ($scene_start -le $s.start_seconds -and $s.start_seconds -lt $scene_end)) {
        $errors += "$($s.shot_id): start $($s.start_seconds) outside scene $sid"
    }
    if (-not ($scene_start -lt $s.end_seconds -and $s.end_seconds -le $scene_end)) {
        $errors += "$($s.shot_id): end $($s.end_seconds) outside scene $sid"
    }
}

for ($i = 0; $i -lt ($shots.Count - 1); $i++) {
    if ($shots[$i].end_seconds -ne $shots[$i + 1].start_seconds) {
        $errors += "Gap/overlap between $($shots[$i].shot_id) and $($shots[$i + 1].shot_id)"
    }
}

if ($shots[0].start_seconds -ne 0) { $errors += "First shot does not start at 0" }
if ($shots[-1].end_seconds -ne 45) { $errors += "Last shot does not end at 45" }

$scene_ids = $shots | ForEach-Object { $_.scene_id } | Sort-Object -Unique
Write-Output "Scene IDs present: $($scene_ids -join ',')"

if ($errors.Count -eq 0) {
    Write-Output "VALIDATION PASSED"
} else {
    Write-Output "VALIDATION FAILED ($($errors.Count) errors):"
    $errors | ForEach-Object { Write-Output "  $_" }
}

Write-Output "Timeline starts: $($shots[0].start_seconds)"
Write-Output "Timeline ends: $($shots[-1].end_seconds)"