param(
    [string]$WorkspaceRoot = "D:\MimicKitNative",
    [string]$CondaEnvName = "mimickit-isaaclab-win",
    [string]$CondaPrefix = "",
    [string]$RootName = "case_white_knight_mesh_native_20260312_224041",
    [string]$CaseName = "view_motion_humanoid_sword_shield_args.txt",
    [int]$Frames = 60,
    [int]$FrameStride = 10,
    [string]$Device = "cuda:0"
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
$renderScript = Join-Path $mimicKitDir "tools\ue_bridge\build_mimickit_render_sequences.py"

if ([string]::IsNullOrWhiteSpace($CondaPrefix)) {
    $CondaPrefix = Join-Path $workspaceRoot "conda\$CondaEnvName"
}
$CondaPrefix = [System.IO.Path]::GetFullPath($CondaPrefix)

$condaBat = Resolve-Conda
$activateBat = Resolve-ActivateBat -CondaBat $condaBat

$cmd = @(
    "call `"$activateBat`" `"$CondaPrefix`"",
    "set MIMICKIT_SKIP_XVFB=1",
    "set MIMICKIT_VIEWER_HEADLESS=0",
    "call `"$isaacLabDir\isaaclab.bat`" -p `"$renderScript`"",
    "--train-root `"$mimicKitDir\output\train`"",
    "--img-root `"$mimicKitDir\output\img`"",
    "--roots $RootName",
    "--cases $CaseName",
    "--frames $Frames",
    "--frame-stride $FrameStride",
    "--device $Device",
    "--num-envs 1",
    "--force"
) 

$fullCmd = ($cmd -join " && ")
Write-Host $fullCmd -ForegroundColor DarkGray
cmd.exe /c $fullCmd
if ($LASTEXITCODE -ne 0) {
    throw "White-knight render sequence run failed."
}
