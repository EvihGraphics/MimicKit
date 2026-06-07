param(
    [string]$WorkspaceRoot = "D:\MimicKitNative",
    [string]$CondaEnvName = "D:\MimicKitNative\conda\mimickit-isaaclab-win",
    [string]$RootName = "tmp_white_knight_mesh_reference_20260602_bridge_smoke",
    [int]$Frames = 10,
    [int]$FrameStride = 5,
    [int]$Mp4Fps = 12,
    [string]$Device = "cuda:0",
    [ValidateSet("glb", "gltf")]
    [string]$AssetExportFormat = "glb",
    [switch]$ForceRoot = $false,
    [switch]$SkipAssetExport = $false
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

$workspaceRoot = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$mimicKitDir = Join-Path $workspaceRoot "workspace\MimicKit"
$builder = Join-Path $mimicKitDir "tools\ue_bridge\build_mimickit_mesh_reference.py"
if (!(Test-Path $builder)) {
    throw "MimicKit mesh reference builder was not found: $builder"
}
Set-Location $mimicKitDir

$condaBat = Resolve-Conda
$condaTargetArgs = @()
$innerPython = ""
if (Test-Path $CondaEnvName) {
    $condaPrefix = [System.IO.Path]::GetFullPath($CondaEnvName)
    $condaTargetArgs = @("run", "-p", $condaPrefix)
    $innerPython = Join-Path $condaPrefix "python.exe"
    if (!(Test-Path $innerPython)) {
        throw "Python executable was not found in conda prefix: $innerPython"
    }
}
else {
    $condaTargetArgs = @("run", "-n", $CondaEnvName)
}
$argsList = @()
$argsList += $condaTargetArgs
$argsList += @(
    "python", $builder,
    "--root-name", $RootName,
    "--frames", "$Frames",
    "--frame-stride", "$FrameStride",
    "--mp4-fps", "$Mp4Fps",
    "--device", $Device,
    "--num-envs", "1",
    "--asset-export-format", $AssetExportFormat
)
if ($innerPython -ne "") {
    $argsList += @(
        "--render-python", $innerPython,
        "--asset-export-python", $innerPython,
        "--package-export-python", $innerPython
    )
}
if ($ForceRoot) {
    $argsList += "--force-root"
}
if ($SkipAssetExport) {
    $argsList += "--skip-asset-export"
}

Write-Host "Running native Windows MimicKit mesh reference builder..." -ForegroundColor Cyan
Write-Host "`"$condaBat`" $($argsList -join ' ')" -ForegroundColor DarkGray
& $condaBat @argsList
if ($LASTEXITCODE -ne 0) {
    throw "Native Windows mesh reference builder failed with exit code $LASTEXITCODE."
}
