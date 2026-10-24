param(
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$version = "1.54"
$appName = "SynoStream_$version"
$downloadsDir = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads"
$stageDir = Join-Path $env:TEMP ("SynoStream_release_" + [guid]::NewGuid().ToString("N"))
$binaryDir = Join-Path $stageDir "${appName}_Windows_x64"
$sourceStage = Join-Path $stageDir "source\$appName"
$pythonExe = $PythonExecutable

if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    $pythonExe = (& py -3.13 -c "import sys; print(sys.executable)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $pythonExe) {
        throw "Python 3.13 nem található. Telepítsd a Python 3.13-at, vagy add meg a -PythonExecutable útvonalat."
    }
}
$pythonExe = (Resolve-Path -LiteralPath $pythonExe).Path
if ((& $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim() -ne "3.13") {
    throw "A kiadás Python 3.13-mal készül. Megadott értelmező: $pythonExe"
}

$pythonRoot = Split-Path -Parent $pythonExe
$qtBin = Join-Path $pythonRoot "Lib\site-packages\PyQt6\Qt6\bin"
$safePath = @(
    (Join-Path $env:SystemRoot "System32"),
    $env:SystemRoot,
    (Join-Path $env:SystemRoot "System32\Wbem"),
    $PSHOME,
    $pythonRoot,
    $qtBin
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$originalPath = $env:PATH

$sourceFiles = @(
    ".gitignore", "BINARY_NOTICES.md", "build_windows.ps1", "LICENSE", "README.md",
    "requirements-build.txt", "requirements-dev.txt", "requirements.txt",
    "${appName}.py", "synostream_logic.py", "TESTING.md", "THIRD_PARTY_NOTICES.md"
)
$licensesDir = Join-Path $sourceDir "release_assets\licenses"
if (-not (Test-Path -LiteralPath $licensesDir -PathType Container)) {
    # The public source ZIP places the license directory at its root.
    $licensesDir = Join-Path $sourceDir "licenses"
}
if (-not (Test-Path -LiteralPath $licensesDir -PathType Container)) {
    throw "Hiányzik a licencmappa: release_assets\licenses vagy licenses"
}
$releaseFiles = @("BINARY_NOTICES.md", "LICENSE", "README.md")
$publishFiles = @(
    "${appName}.exe",
    "${appName}_Windows_x64.zip",
    "${appName}_Source.zip",
    "${appName}_SHA256.txt"
)

try {
    $env:PATH = $safePath -join ";"
    Set-Location -LiteralPath $sourceDir

    & $pythonExe -m pip install -r requirements.txt -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw "A buildfüggőségek telepítése nem sikerült." }

    & $pythonExe -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name $appName `
        --icon "assets\synostream.ico" `
        --add-data "LICENSE;." `
        --add-data "assets\synostream.ico;assets" `
        --add-data "assets\mpv\synostream_context.lua;assets\mpv" `
        "${appName}.py"
    if ($LASTEXITCODE -ne 0) { throw "A SynoStream EXE buildje nem sikerült." }

    New-Item -ItemType Directory -Path $binaryDir, $sourceStage -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $sourceDir "dist\${appName}.exe") -Destination $binaryDir
    foreach ($file in $releaseFiles) {
        Copy-Item -LiteralPath (Join-Path $sourceDir $file) -Destination $binaryDir
    }
    New-Item -ItemType Directory -Path (Join-Path $binaryDir "assets") -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $sourceDir "assets\synostream.ico") -Destination (Join-Path $binaryDir "assets") -Force
    Copy-Item -LiteralPath $licensesDir -Destination $binaryDir -Recurse -Force

    foreach ($file in $sourceFiles) {
        Copy-Item -LiteralPath (Join-Path $sourceDir $file) -Destination $sourceStage -Force
    }
    Copy-Item -LiteralPath (Join-Path $sourceDir "tests") -Destination $sourceStage -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $sourceDir "assets") -Destination $sourceStage -Recurse -Force
    Copy-Item -LiteralPath $licensesDir -Destination $sourceStage -Recurse -Force

    # A forráscsomag ne tartalmazzon helyi Python-gyorsítótárakat vagy fordított bytecode-ot.
    Get-ChildItem -LiteralPath $sourceStage -Directory -Filter "__pycache__" -Recurse |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $sourceStage -File -Recurse | Where-Object {
        $_.Extension -in @(".pyc", ".pyo")
    } | Remove-Item -Force

    $binaryZip = Join-Path $stageDir "${appName}_Windows_x64.zip"
    $sourceZip = Join-Path $stageDir "${appName}_Source.zip"
    Compress-Archive -Path $binaryDir -DestinationPath $binaryZip -CompressionLevel Optimal
    Compress-Archive -Path $sourceStage -DestinationPath $sourceZip -CompressionLevel Optimal
    Copy-Item -LiteralPath (Join-Path $binaryDir "${appName}.exe") -Destination $stageDir -Force

    $exeHash = (Get-FileHash -LiteralPath (Join-Path $binaryDir "${appName}.exe") -Algorithm SHA256).Hash.ToLowerInvariant()
    $binaryZipHash = (Get-FileHash -LiteralPath $binaryZip -Algorithm SHA256).Hash.ToLowerInvariant()
    $sourceZipHash = (Get-FileHash -LiteralPath $sourceZip -Algorithm SHA256).Hash.ToLowerInvariant()
    $hashLines = @(
        "$exeHash  ${appName}.exe",
        "$binaryZipHash  ${appName}_Windows_x64.zip",
        "$sourceZipHash  ${appName}_Source.zip"
    )
    Set-Content -LiteralPath (Join-Path $stageDir "${appName}_SHA256.txt") -Value $hashLines -Encoding ascii

    foreach ($name in $publishFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $stageDir $name))) {
            throw "Hiányzó kiadási fájl: $name"
        }
    }
    $publishDirectories = @(
        $downloadsDir,
        (Join-Path $downloadsDir "B")
    )
    foreach ($publishDirectory in $publishDirectories) {
        New-Item -ItemType Directory -Path $publishDirectory -Force | Out-Null
        foreach ($name in $publishFiles) {
            Copy-Item -LiteralPath (Join-Path $stageDir $name) -Destination (Join-Path $publishDirectory $name) -Force
        }
    }

    # Régi, verziózott kiadási fájlok törlése csak a sikeres build és csomagolás után.
    $oldReleasePattern = '^SynoStream_\d+\.\d+(?:_(?:Windows_x64|Source|SHA256))?\.(?:exe|zip|txt)$'
    $cleanupFailures = @()
    foreach ($publishDirectory in $publishDirectories) {
        $oldReleaseFiles = Get-ChildItem -LiteralPath $publishDirectory -File | Where-Object {
            $_.Name -match $oldReleasePattern -and $_.Name -notin $publishFiles
        }
        foreach ($oldFile in $oldReleaseFiles) {
            try {
                Remove-Item -LiteralPath $oldFile.FullName -Force -ErrorAction Stop
            }
            catch {
                $cleanupFailures += "$($oldFile.FullName): $($_.Exception.Message)"
            }
        }
    }

    Write-Output "Elkészült kiadási fájlok:"
    foreach ($publishDirectory in $publishDirectories) {
        $publishFiles | ForEach-Object { Get-Item -LiteralPath (Join-Path $publishDirectory $_) | Select-Object Name, Length, DirectoryName }
    }
    if ($cleanupFailures.Count -gt 0) {
        $cleanupDetails = $cleanupFailures -join [Environment]::NewLine
        Write-Warning "Néhány régi kiadási fájlt a Windows nem engedett törölni:`n$cleanupDetails"
    }
}
finally {
    $env:PATH = $originalPath
    if (Test-Path -LiteralPath $stageDir) { Remove-Item -LiteralPath $stageDir -Recurse -Force }
}
