$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$buildDeps = Join-Path $projectRoot ".build_deps"
New-Item -ItemType Directory -Force -Path $buildDeps | Out-Null

$env:PYTHONNOUSERSITE = "1"
$env:PYTHONPATH = $buildDeps
python -m pip install --upgrade --target $buildDeps -r requirements\build.txt
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install build dependencies (exit code $LASTEXITCODE)."
}

python tools\make_icons.py
if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate icons (exit code $LASTEXITCODE)."
}

python -m PyInstaller --noconfirm --clean packaging\Petpet-windows.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed (exit code $LASTEXITCODE)."
}

$outputPath = Join-Path $projectRoot "dist\Petpet.exe"
if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "Build completed without producing $outputPath."
}

Write-Output "Built: $outputPath"
