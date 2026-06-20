# VLM Detection inference env (conda only; pip venv torch may fail on this PC)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$EnvName = "vlm_detection"
$Conda = "D:\anaconda\Scripts\conda.exe"
if (-not (Test-Path $Conda)) { $Conda = "conda" }

$exists = & $Conda env list | Select-String "^\s*$EnvName\s"
if (-not $exists) {
    Write-Host "Creating conda env: $EnvName ..."
    & $Conda create -n $EnvName python=3.10 -y
}

$line = & $Conda env list | Select-String "^\s*$EnvName\s"
$prefix = ($line.ToString() -split '\s+', 3)[1].Trim()
$Python = Join-Path $prefix "python.exe"

Write-Host "Installing PyTorch (conda) ..."
& $Conda install -n $EnvName pytorch torchvision cpuonly -c pytorch -y

Write-Host "Installing ultralytics + deps (pip) ..."
& $Python -m pip install --upgrade pip
& $Python -m pip install ultralytics huggingface_hub opencv-python-headless "numpy>=1.23.5,<2.0.0"

Write-Host "Verify ..."
& $Python -c "import torch; from ultralytics import YOLO; print('OK', torch.__version__)"

Write-Host ""
Write-Host "Done. Run:"
Write-Host "  conda activate $EnvName"
Write-Host "  python detect.py --source input --save-img --export-json"
