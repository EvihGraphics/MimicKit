param(
    [string]$WorkspaceRoot = "D:\MimicKitNative",
    [string]$CondaEnvName = "mimickit-isaaclab-win",
    [string]$CondaPrefix = "",
    [string]$Device = "cuda:0",
    [string]$MotionFile = "",
    [switch]$DatasetMode = $false
)

$ErrorActionPreference = "Stop"

function Resolve-Conda {
    $candidates = @(
        "C:\ProgramData\anaconda3\condabin\conda.bat",
        "C:\ProgramData\anaconda3\Scripts\conda.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    $condaCmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($condaCmd) {
        return $condaCmd.Source
    }
    throw "Conda was not found."
}

function Resolve-ActivateBat {
    param([string]$CondaBat)

    $condaDir = Split-Path -Parent $CondaBat
    $anacondaRoot = Split-Path -Parent $condaDir
    $activateBat = Join-Path $anacondaRoot "Scripts\activate.bat"
    if (Test-Path $activateBat) {
        return $activateBat
    }
    throw "activate.bat was not found for $CondaBat"
}

$workspaceRoot = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$mimicKitDir = Join-Path $workspaceRoot "workspace\MimicKit"
$isaacLabDir = Join-Path $workspaceRoot "workspace\IsaacLab_full"
$runPy = Join-Path $mimicKitDir "mimickit\run.py"
$argFile = Join-Path $mimicKitDir "args\view_motion_humanoid_sword_shield_args.txt"

if ([string]::IsNullOrWhiteSpace($CondaPrefix)) {
    $CondaPrefix = Join-Path $workspaceRoot "conda\$CondaEnvName"
}
$CondaPrefix = [System.IO.Path]::GetFullPath($CondaPrefix)

if ($DatasetMode) {
    $envConfig = Join-Path $mimicKitDir "data\envs\view_motion_humanoid_sword_shield_dataset_mesh_env.yaml"
}
else {
    $envConfig = Join-Path $mimicKitDir "data\envs\view_motion_humanoid_sword_shield_mesh_env.yaml"
}

$engineConfig = Join-Path $mimicKitDir "data\engines\isaac_lab_engine.yaml"
$condaBat = Resolve-Conda
$activateBat = Resolve-ActivateBat -CondaBat $condaBat

$extraArgs = @()
if ($MotionFile -ne "") {
    $extraArgs += "--motion_file"
    $extraArgs += "`"$MotionFile`""
}

$cmd = @(
    "call `"$activateBat`" `"$CondaPrefix`"",
    "set MIMICKIT_SKIP_XVFB=1",
    "set MIMICKIT_VIEWER_HEADLESS=0",
    "call `"$isaacLabDir\isaaclab.bat`" -p `"$runPy`"",
    "--arg_file `"$argFile`"",
    "--engine_config `"$engineConfig`"",
    "--env_config `"$envConfig`"",
    "--mode test",
    "--visualize true",
    "--num_envs 1",
    "--test_episodes 1",
    "--devices $Device"
) + $extraArgs

$fullCmd = ($cmd -join " && ")
Write-Host $fullCmd -ForegroundColor DarkGray
cmd.exe /c $fullCmd
if ($LASTEXITCODE -ne 0) {
    throw "White-knight view_motion run failed."
}
