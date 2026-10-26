param(
    [Parameter(Mandatory = $true)]
    [string]$SumatraPdfPath,
    [string]$Version = "0.1.0",
    [switch]$Unsigned
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
$versionSource = Get-Content -Raw -LiteralPath (Join-Path $root "src\ghmc_print_agent\__init__.py")
if ($versionSource -notmatch ('__version__\s*=\s*"' + [regex]::Escape($Version) + '"')) {
    throw "Update the agent package version to $Version before building this release."
}
$buildRoot = Join-Path $root "build\windows"
$distRoot = Join-Path $root "dist"
$venv = Join-Path $buildRoot ".venv"

if (-not (Test-Path -LiteralPath $SumatraPdfPath -PathType Leaf)) {
    throw "Provide the reviewed SumatraPDF executable with -SumatraPdfPath."
}
$sumatraSignature = Get-AuthenticodeSignature -LiteralPath $SumatraPdfPath
if ($sumatraSignature.Status -ne "Valid") {
    throw "SumatraPDF must have a valid Authenticode signature before it can be packaged."
}
if (-not $Unsigned) {
    if (-not $env:GHMC_SIGNING_CERT_THUMBPRINT) {
        throw "Set GHMC_SIGNING_CERT_THUMBPRINT to the approved code-signing certificate thumbprint, or use -Unsigned for local testing only."
    }
    $signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if (-not $signtool) { throw "Windows SDK signtool.exe is required to sign release binaries." }
}

New-Item -ItemType Directory -Force -Path $buildRoot, $distRoot | Out-Null
if (-not (Test-Path -LiteralPath $venv)) {
    py -3.12 -m venv $venv
}
$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not update the build environment." }
& $python -m pip install ".[build]" pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Could not install pinned agent build dependencies." }
& $python -m PyInstaller --noconfirm --clean --onefile --name GHMCPrintAgent `
    --collect-all keyring --icon (Join-Path $root "assets\ghmc.ico") `
    --version-file (Join-Path $root "packaging\version_info.txt") `
    (Join-Path $root "src\ghmc_print_agent\cli.py")
if (-not $Unsigned) {
    & $signtool.Source sign /sha1 $env:GHMC_SIGNING_CERT_THUMBPRINT /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 (Join-Path $distRoot "GHMCPrintAgent.exe")
    if ($LASTEXITCODE -ne 0) { throw "Signing the agent executable failed." }
}

$stage = Join-Path $buildRoot "stage"
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $distRoot "GHMCPrintAgent.exe") -Destination $stage
Copy-Item -LiteralPath $SumatraPdfPath -Destination (Join-Path $stage "SumatraPDF.exe")
Copy-Item -LiteralPath (Join-Path $root "packaging\start_agent.vbs") -Destination $stage
$env:GHMC_AGENT_STAGE = $stage
$env:GHMC_AGENT_VERSION = $Version

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) { throw "Inno Setup 6 (ISCC.exe) is required to build the installer." }
& $iscc.Source "/DAppVersion=$Version" (Join-Path $root "packaging\installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE." }

$installer = Join-Path $distRoot "GHMCPrintAgent-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $installer)) { throw "Expected installer was not produced: $installer" }
if (-not $Unsigned) {
    & $signtool.Source sign /sha1 $env:GHMC_SIGNING_CERT_THUMBPRINT /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $installer
    if ($LASTEXITCODE -ne 0) { throw "Signing the installer failed." }
}
if ($Unsigned) { Write-Warning "Built an UNSIGNED local-testing artifact. Do not publish it or configure it as a GHMC release." }
Get-FileHash -Algorithm SHA256 -LiteralPath $installer
