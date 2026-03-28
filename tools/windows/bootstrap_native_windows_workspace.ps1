param(
    [string]$WorkspaceRoot = "D:\MimicKitNative",
    [string]$CondaEnvName = "mimickit-isaaclab-win",
    [string]$CondaPrefix = "",
    [switch]$InstallIsaacSimPip = $true,
    [string]$IsaacSimVersion = "4.5.0",
    [string]$IsaacSimPipExtras = "all"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

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

    throw "Conda was not found. Install Anaconda/Miniconda for Windows first."
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

function Resolve-Mamba {
    $candidates = @(
        "C:\ProgramData\anaconda3\condabin\mamba.bat",
        "C:\ProgramData\anaconda3\Library\bin\mamba.exe",
        "C:\Users\PC\mambaforge\Scripts\mamba.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $mambaCmd = Get-Command mamba -ErrorAction SilentlyContinue
    if ($mambaCmd) {
        return $mambaCmd.Source
    }

    return $null
}

function Invoke-CondaBat {
    param(
        [string]$CondaBat,
        [string]$Arguments
    )
    $command = "`"$CondaBat`" $Arguments"
    Write-Host $command -ForegroundColor DarkGray
    cmd.exe /c $command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $command"
    }
}

function Invoke-CondaRun {
    param(
        [string]$CondaBat,
        [string]$Target,
        [switch]$UsePrefix,
        [string]$Command
    )
    if ($UsePrefix) {
        $args = "run -p `"$Target`" $Command"
    }
    else {
        $args = "run -n $Target $Command"
    }
    Invoke-CondaBat -CondaBat $CondaBat -Arguments $args
}

$workspaceRoot = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$workspaceDir = Join-Path $workspaceRoot "workspace"
$mimicKitDir = Join-Path $workspaceDir "MimicKit"
$isaacLabDir = Join-Path $workspaceDir "IsaacLab_full"
$runtimeDir = Join-Path $workspaceRoot "runtime"
$logDir = Join-Path $workspaceRoot "logs"
$condaRootDir = Join-Path $workspaceRoot "conda"
if ([string]::IsNullOrWhiteSpace($CondaPrefix)) {
    $CondaPrefix = Join-Path $condaRootDir $CondaEnvName
}
$CondaPrefix = [System.IO.Path]::GetFullPath($CondaPrefix)

Write-Step "Preparing directories"
New-Item -ItemType Directory -Force -Path $workspaceRoot, $workspaceDir, $runtimeDir, $logDir, $condaRootDir | Out-Null
$condaPkgsDir = Join-Path $condaRootDir "pkgs"
New-Item -ItemType Directory -Force -Path $condaPkgsDir | Out-Null
$transcriptPath = Join-Path $logDir "bootstrap_native_windows_workspace.log"
try {
    Start-Transcript -Path $transcriptPath -Append | Out-Null
}
catch {
    Write-Warning "Unable to start transcript at $transcriptPath"
}
Set-Location $workspaceRoot
$env:CONDA_PKGS_DIRS = $condaPkgsDir
$env:MAMBA_ROOT_PREFIX = $condaRootDir

if (-not (Test-Path (Join-Path $mimicKitDir "mimickit\run.py"))) {
    throw "MimicKit workspace is missing at $mimicKitDir"
}
if (-not (Test-Path (Join-Path $isaacLabDir "isaaclab.bat"))) {
    throw "IsaacLab_full workspace is missing at $isaacLabDir"
}

$condaBat = Resolve-Conda
$activateBat = Resolve-ActivateBat -CondaBat $condaBat
$mambaExe = Resolve-Mamba
$isaacSimRoot = Join-Path $runtimeDir "isaacsim-$IsaacSimVersion"

Write-Step "Ensuring conda environment at $CondaPrefix"
Invoke-CondaBat -CondaBat $condaBat -Arguments "env list"
$envExists = Test-Path (Join-Path $CondaPrefix "python.exe")
if (-not $envExists) {
    if ($mambaExe) {
        $createCmd = if ($mambaExe.EndsWith(".bat")) {
            "`"$mambaExe`" create -y -p `"$CondaPrefix`" python=3.10"
        } else {
            "`"$mambaExe`" create -y -p `"$CondaPrefix`" python=3.10"
        }
        Write-Host $createCmd -ForegroundColor DarkGray
        cmd.exe /c $createCmd
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create prefix environment with mamba."
        }
    }
    else {
        Invoke-CondaBat -CondaBat $condaBat -Arguments "create -y -p `"$CondaPrefix`" python=3.10"
    }
}

Write-Step "Upgrading bootstrap tooling"
Invoke-CondaRun -CondaBat $condaBat -Target $CondaPrefix -UsePrefix -Command "python -m pip install --upgrade pip setuptools wheel"

if ($InstallIsaacSimPip) {
    Write-Step "Installing Isaac Sim pip package $IsaacSimVersion"
    if ([string]::IsNullOrWhiteSpace($IsaacSimPipExtras)) {
        $isaacSimSpec = "isaacsim==$IsaacSimVersion"
    }
    else {
        $isaacSimSpec = "isaacsim[$IsaacSimPipExtras]==$IsaacSimVersion"
    }
    Invoke-CondaRun -CondaBat $condaBat -Target $CondaPrefix -UsePrefix -Command "python -m pip install `"$isaacSimSpec`" --extra-index-url https://pypi.nvidia.com"
}
elseif (-not (Test-Path $isaacSimRoot)) {
    throw "Binary Isaac Sim root was not found at $isaacSimRoot. Either extract Isaac Sim there or use -InstallIsaacSimPip."
}

if ((Test-Path $isaacSimRoot) -and (-not (Test-Path (Join-Path $isaacLabDir "_isaac_sim")))) {
    Write-Step "Creating _isaac_sim junction"
    cmd.exe /c "mklink /J `"$isaacLabDir\_isaac_sim`" `"$isaacSimRoot`""
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create _isaac_sim junction."
    }
}

Write-Step "Installing Isaac Lab source packages"
Push-Location $isaacLabDir
try {
    $installCmd = "call `"$activateBat`" `"$CondaPrefix`" && call `"$isaacLabDir\isaaclab.bat`" --install none"
    Write-Host $installCmd -ForegroundColor DarkGray
    cmd.exe /c $installCmd
    if ($LASTEXITCODE -ne 0) {
        throw "isaaclab.bat --install none failed."
    }
}
finally {
    Pop-Location
}

Write-Step "Installing MimicKit Python requirements"
Invoke-CondaRun -CondaBat $condaBat -Target $CondaPrefix -UsePrefix -Command "python -m pip install -r `"$mimicKitDir\requirements.txt`""

$summaryPath = Join-Path $logDir "native_windows_workspace_summary.txt"
@(
    "WorkspaceRoot=$workspaceRoot"
    "CondaEnvName=$CondaEnvName"
    "CondaPrefix=$CondaPrefix"
    "CondaPkgsDir=$condaPkgsDir"
    "MimicKitDir=$mimicKitDir"
    "IsaacLabDir=$isaacLabDir"
    "RuntimeDir=$runtimeDir"
    "InstallIsaacSimPip=$InstallIsaacSimPip"
    "IsaacSimVersion=$IsaacSimVersion"
    "IsaacSimPipExtras=$IsaacSimPipExtras"
) | Set-Content -Encoding ASCII $summaryPath

Write-Step "Bootstrap complete"
Write-Host "Summary: $summaryPath" -ForegroundColor Green
Write-Host "Next step:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$mimicKitDir\tools\windows\run_white_knight_mesh_viewmotion.ps1`" -WorkspaceRoot `"$workspaceRoot`" -CondaEnvName `"$CondaEnvName`"" -ForegroundColor Green
try {
    Stop-Transcript | Out-Null
}
catch {
}
