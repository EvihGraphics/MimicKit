param(
    [string]$WorkspaceRoot = "D:\MimicKitNative",
    [string]$CondaEnvName = "D:\MimicKitNative\conda\mimickit-isaaclab-win",
    [string]$SourceRoot = "",
    [string]$Stage = "long_train",
    [string]$RootName = "",
    [string]$Case = "",
    [int]$Frames = 300,
    [int]$FrameStride = 5,
    [int]$Mp4Fps = 12,
    [string]$Device = "cuda:0",
    [int]$NumEnvs = 1,
    [int]$Seed = 7,
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
$builder = Join-Path $mimicKitDir "tools\ue_bridge\build_mimickit_exact_mesh_reference.py"
if (!(Test-Path $builder)) {
    throw "MimicKit exact mesh reference builder was not found: $builder"
}
if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    throw "SourceRoot is required."
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
    "--source-root", $SourceRoot,
    "--stage", $Stage,
    "--frames", "$Frames",
    "--frame-stride", "$FrameStride",
    "--mp4-fps", "$Mp4Fps",
    "--device", $Device,
    "--num-envs", "$NumEnvs",
    "--seed", "$Seed"
)
if ($RootName -ne "") {
    $argsList += @("--root-name", $RootName)
}
if ($Case -ne "") {
    $argsList += @("--case", $Case)
}
if ($innerPython -ne "") {
    $argsList += @(
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

Write-Host "Running native Windows MimicKit exact mesh reference builder..." -ForegroundColor Cyan
Write-Host "`"$condaBat`" $($argsList -join ' ')" -ForegroundColor DarkGray
$env:MIMICKIT_SKIP_XVFB = "1"
$env:MIMICKIT_VIEWER_HEADLESS = "1"
& $condaBat @argsList
if ($LASTEXITCODE -ne 0) {
    throw "Native Windows exact mesh reference builder failed with exit code $LASTEXITCODE."
}
