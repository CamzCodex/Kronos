param(
    [switch]$Full,
    [switch]$RequireAccelerator,
    [string]$Device = "auto"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    py -3.12 -m venv (Join-Path $ProjectRoot ".venv")
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e "${ProjectRoot}[dev,webui]"

$VerifyArguments = @((Join-Path $ProjectRoot "scripts\verify_local.py"), "--device", $Device)
if ($Full) {
    $VerifyArguments += "--full"
}
if ($RequireAccelerator) {
    $VerifyArguments += "--require-accelerator"
}

& $VenvPython @VerifyArguments
Write-Host "Kronos is installed and verified in $ProjectRoot\.venv"
