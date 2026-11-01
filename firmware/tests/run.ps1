param([string]$Compiler = "", [string]$ArduinoJsonPath = "", [string]$Output = "")
$ErrorActionPreference = "Stop"
$firmwareRoot = Split-Path $PSScriptRoot -Parent
if (-not $Compiler) {
    $Compiler = (Get-Command g++ -ErrorAction SilentlyContinue).Source
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler)) { throw "Provide a host g++ compiler using -Compiler, or add g++ to PATH." }
if (-not $Output) {
    $Output = Join-Path $firmwareRoot "build/native-tests.exe"
}
New-Item -ItemType Directory -Force (Split-Path $Output -Parent) | Out-Null
if (-not $ArduinoJsonPath) {
    $ArduinoJsonPath = Join-Path $env:USERPROFILE "Documents/Arduino/libraries/ArduinoJson"
}
$jsonInclude = Join-Path $ArduinoJsonPath "src"
if (-not (Test-Path -LiteralPath (Join-Path $jsonInclude "ArduinoJson.h"))) {
    throw "Provide the installed ArduinoJson library folder using -ArduinoJsonPath (see Arduino IDE sketchbook location)."
}
$oldPath = $env:PATH
try {
    $env:PATH = (Split-Path $Compiler -Parent) + ";" + $env:PATH
    & $Compiler -std=c++14 -static -Wall -Wextra -I (Join-Path $firmwareRoot "SmartGarden") -I $jsonInclude (Join-Path $PSScriptRoot "test_runtime.cpp") -o $Output
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Output
    exit $LASTEXITCODE
} finally {
    $env:PATH = $oldPath
}
