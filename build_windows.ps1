param(
    [string]$PythonExecutable = "",
    [string]$OutputDirectory = "",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$version = (Get-Content -LiteralPath (Join-Path $sourceDir "release_version.txt") -Raw).Trim()
if ($version -notmatch '^[1-9]\d{0,3}\.\d{1,4}(?:\.\d{1,4})?$') { throw "Érvénytelen kiadási verzió." }
$appName = "SynoStream_$version"
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads\SynoStream v$version"
}
$outputDir = [IO.Path]::GetFullPath($OutputDirectory)
$protectedOriginal = [IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads\SynoStream v1.54")).TrimEnd('\')
if ($outputDir.TrimEnd('\').Equals($protectedOriginal, [StringComparison]::OrdinalIgnoreCase) -or
    $outputDir.StartsWith($protectedOriginal + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Az eredeti SynoStream v1.54 mappa és tartalma nem módosítható."
}
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

$verifiedVersion = & $pythonExe (Join-Path $sourceDir "release_tools.py") --check-source $sourceDir
if ($LASTEXITCODE -ne 0 -or $verifiedVersion.Trim() -ne $version) { throw "A forrás verzióellenőrzése sikertelen." }

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
    ".gitignore", "BINARY_NOTICES.md", "build_windows.ps1", "LICENSE", "README.md", "release_tools.py", "release_version.txt", "release_guard.py", "publish_release.py", "synostream_updates.py", "synostream_update_ui.py",
    "requirements-build.txt", "requirements-dev.txt", "requirements.txt",
    "${appName}.py", "synostream_logic.py", "synostream_nfo.py", "synostream_pairings.py", "synostream_nas.py", "synostream_mpv_install.py", "synostream_storage.py",
    "synostream_deletion.py", "synostream_delete_ui.py", "synostream_connections.py", "synostream_sources.py", "synostream_source_migration.py", "synostream_source_ui.py", "synostream_source_folders.py", "synostream_recommendations.py", "synostream_recommendation_ui.py", "synostream_library.py", "synostream_playback.py", "synostream_performance.py", "synostream_downloads.py", "synostream_download_ui.py", "synostream_torrent_selection.py", "synostream_file_selection_ui.py", "synostream_window_chrome.py", "synostream_window_identity.py", "CHANGELOG_$version.md", "JAVITASOK_ES_ELLENORZES.md", "KIVETELEK_ATVIZSGALASA.md", "TESTING.md", "THIRD_PARTY_NOTICES.md"
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
    "${appName}_SHA256.txt", "update.json"
)

try {
    $env:PATH = $safePath -join ";"
    Set-Location -LiteralPath $sourceDir

    if (-not $SkipDependencyInstall) {
        & $pythonExe -m pip install -r requirements.txt -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw "A buildfüggőségek telepítése nem sikerült." }
    }

    & $pythonExe -m PyInstaller --noconfirm --onefile --windowed `
        --name $appName `
        --icon "assets\synostream.ico" `
        --add-data "LICENSE;." `
        --add-data "assets\synostream.ico;assets" `
        --add-data "assets\tmdb.png;assets" `
        --add-data "assets\qt\qtbase_hu.qm;assets\qt" `
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

    $resolvedStage = [IO.Path]::GetFullPath($stageDir).TrimEnd('\') + '\'
    if (-not ([IO.Path]::GetFullPath($sourceStage).StartsWith($resolvedStage, [StringComparison]::OrdinalIgnoreCase))) {
        throw "A forráscsomag útvonala kívül esik a munkamappán."
    }
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

    & $pythonExe (Join-Path $sourceDir 'release_tools.py') $stageDir $version (Join-Path $sourceDir "CHANGELOG_$version.md")
    if ($LASTEXITCODE -ne 0) { throw "A frissítési leíró létrehozása nem sikerült." }

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
    $publishDirectories = @($outputDir)
    foreach ($publishDirectory in $publishDirectories) {
        New-Item -ItemType Directory -Path $publishDirectory -Force | Out-Null
        foreach ($name in $publishFiles) {
            Copy-Item -LiteralPath (Join-Path $stageDir $name) -Destination (Join-Path $publishDirectory $name) -Force
        }
    }

    Write-Output "Elkészült kiadási fájlok:"
    foreach ($publishDirectory in $publishDirectories) {
        $publishFiles | ForEach-Object { Get-Item -LiteralPath (Join-Path $publishDirectory $_) | Select-Object Name, Length, DirectoryName }
    }

}
finally {
    $env:PATH = $originalPath
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    $finalStage = [IO.Path]::GetFullPath($stageDir)
    if (-not $finalStage.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $finalStage) -notlike 'SynoStream_release_*') {
        throw "Érvénytelen build-munkamappa; takarítás megszakítva."
    }
    if (Test-Path -LiteralPath $finalStage) { Remove-Item -LiteralPath $finalStage -Recurse -Force }
}


