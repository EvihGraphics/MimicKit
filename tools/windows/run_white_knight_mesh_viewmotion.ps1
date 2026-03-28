param(
    [string]$WorkspaceRoot = "D:\MimicKitNative",
    [string]$CondaEnvName = "mimickit-isaaclab-win",
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

$workspaceRoot = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$mimicKitDir = Join-Path $workspaceRoot "workspace\MimicKit"
$runPy = Join-Path $mimicKitDir "mimickit\run.py"
$argFile = Join-Path $mimicKitDir "args\view_motion_humanoid_sword_shield_args.txt"

if ($DatasetMode) {
    $envConfig = Join-Path $mimicKitDir "data\envs\view_motion_humanoid_sword_shield_dataset_mesh_env.yaml"
}
else {
    $envConfig = Join-Path $mimicKitDir "data\envs\view_motion_humanoid_sword_shield_mesh_env.yaml"
}

$engineConfig = Join-Path $mimicKitDir "data\engines\isaac_lab_engine.yaml"
$condaBat = Resolve-Conda

$extraArgs = @()
if ($MotionFile -ne "") {
    $extraArgs += "--motion_file"
    $extraArgs += "`"$MotionFile`""
}

$cmd = @(
    "`"$condaBat`" run -n $CondaEnvName python `"$runPy`"",
    "--arg_file `"$argFile`"",
    "--engine_config `"$engineConfig`"",
    "--env_config `"$envConfig`"",
    "--mode test",
    "--visualize true",
    "--num_envs 1",
    "--test_episodes 1",
    "--devices $Device"
) + $extraArgs

$fullCmd = ($cmd -join " ")
Write-Host $fullCmd -ForegroundColor DarkGray
cmd.exe /c $fullCmd
if ($LASTEXITCODE -ne 0) {
    throw "White-knight view_motion run failed."
}
