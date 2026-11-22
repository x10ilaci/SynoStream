param([switch]$Offline)
$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$arguments = @('-p', $project, 'testReleaseUnitTest', 'lintRelease', 'assembleRelease', '--no-watch-fs', '--max-workers=2', '--console=plain')
if ($Offline) { $arguments += '--offline' }
& "$project/gradlew.bat" @arguments
if ($LASTEXITCODE -ne 0) { throw 'A release build vagy a tesztek sikertelenek.' }
$gradleText = Get-Content -LiteralPath "$project/app/build.gradle" -Raw
$releaseVersion = [regex]::Match($gradleText, "versionName '([^']+)'").Groups[1].Value
$releaseCode = [regex]::Match($gradleText, 'versionCode ([0-9]+)').Groups[1].Value
$apk = "$project/app/build/outputs/apk/release/app-release.apk"
py -3.13 "$project/verify_release.py" $apk --version $releaseVersion --version-code $releaseCode
if ($LASTEXITCODE -ne 0) { throw 'Az APK nem felel meg a terjesztési ellenőrzésnek; nem publikálható.' }
Write-Output "Ellenőrzött release APK: $apk"
