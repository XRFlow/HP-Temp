# SPDX-License-Identifier: GPL-3.0-or-later
# Build HPTemp for Windows: onedir app, Inno Setup EXE, WiX MSI, and portable zip.
param(
    [switch]$SkipDeps
)
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

trap {
    Write-Host "::error::$($_.Exception.Message)"
    break
}

function Test-RequireInstallers {
    return ($env:GITHUB_ACTIONS -eq "true") -or ($env:CI -eq "true")
}

function Find-ISCC {
    $dirs = @(
        $env:ProgramFiles,
        ${env:ProgramFiles(x86)},
        (Join-Path $env:LOCALAPPDATA "Programs")
    ) | Where-Object { $_ }
    $candidates = @()
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $cmd) {
        $cmd = Get-Command ISCC -ErrorAction SilentlyContinue
    }
    if ($cmd -and $cmd.Path) {
        $candidates += $cmd.Path
    }
    foreach ($dir in $dirs) {
        foreach ($ver in @("Inno Setup 6", "Inno Setup 7")) {
            $candidates += (Join-Path (Join-Path $dir $ver) "ISCC.exe")
        }
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Find-WiXBin {
    $cmd = Get-Command heat.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Path) {
        return (Split-Path $cmd.Path)
    }
    $dirs = @(
        ${env:ProgramFiles(x86)},
        $env:ProgramFiles
    ) | Where-Object { $_ }
    foreach ($dir in $dirs) {
        foreach ($ver in @("WiX Toolset v3.14", "WiX Toolset v3.11")) {
            $bin = Join-Path (Join-Path $dir $ver) "bin"
            if (Test-Path -LiteralPath (Join-Path $bin "heat.exe")) {
                return $bin
            }
        }
    }
    return $null
}

$Version = (python -c "import sys; sys.path.insert(0, r'src'); from hptemp import __version__; print(__version__)").Trim()
if (-not $Version) { throw "Could not read hptemp.__version__" }
Write-Host "Building HPTemp $Version"

if (-not $SkipDeps) {
    python -m pip install -q -r requirements.txt PyQt6-Charts pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "pip install failed with exit code $LASTEXITCODE" }
}

python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\hptemp.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$AppDir = Join-Path $Root "dist\HPTemp"
if (-not (Test-Path -LiteralPath (Join-Path $AppDir "HPTemp.exe"))) {
    throw "PyInstaller did not produce dist\HPTemp\HPTemp.exe"
}

$Inno = Find-ISCC
if ($Inno) {
    $SourceRoot = $Root.Replace("\", "/")
    Write-Host "Using Inno Setup compiler: $Inno"
    Write-Host "ISCC SourceRoot=$SourceRoot Version=$Version"
    $isccOut = New-Object System.Collections.Generic.List[string]
    & $Inno "/DMyAppVersion=$Version" "/DSourceRoot=$SourceRoot" packaging\hptemp.iss 2>&1 | ForEach-Object {
        $line = "$_"
        Write-Host $line
        [void]$isccOut.Add($line)
    }
    if ($LASTEXITCODE -ne 0) {
        $tail = ($isccOut | Select-Object -Last 20) -join " | "
        throw "Inno Setup failed with exit code $LASTEXITCODE : $tail"
    }
} elseif (Test-RequireInstallers) {
    throw "Inno Setup not found (looked on PATH and under Program Files / LocalAppData). Install from https://jrsoftware.org/isinfo.php"
} else {
    Write-Warning "Inno Setup not found; skipping EXE installer. Install from https://jrsoftware.org/isinfo.php"
}

$WixBin = Find-WiXBin
if ($WixBin) {
    Write-Host "Using WiX tools in: $WixBin"
    $env:PATH = "$WixBin;$env:PATH"
    New-Item -ItemType Directory -Force -Path build | Out-Null
    $Harvest = "build\harvested.wxs"
    & heat.exe dir $AppDir -cg AppFiles -gg -sfrag -srd -sreg -dr INSTALLFOLDER -var var.HarvestDir -out $Harvest
    if ($LASTEXITCODE -ne 0) { throw "WiX heat failed with exit code $LASTEXITCODE" }
    & candle.exe -nologo -arch x64 `
        "-dProductVersion=$Version" `
        "-dIconFile=$Root\packaging\hptemp.ico" `
        "-dHarvestDir=$AppDir" `
        "packaging\hptemp.wxs" $Harvest -o build\
    if ($LASTEXITCODE -ne 0) { throw "WiX candle failed with exit code $LASTEXITCODE" }
    $lightOut = New-Object System.Collections.Generic.List[string]
    & light.exe -nologo -sval -spdb -b $AppDir `
        "build\hptemp.wixobj" "build\harvested.wixobj" `
        -o "dist\HPTemp-$Version.msi" 2>&1 | ForEach-Object {
            $line = "$_"
            Write-Host $line
            [void]$lightOut.Add($line)
        }
    if ($LASTEXITCODE -ne 0) {
        $tail = ($lightOut | Select-Object -Last 20) -join " | "
        throw "WiX light failed with exit code $LASTEXITCODE : $tail"
    }
} elseif (Test-RequireInstallers) {
    throw "WiX Toolset v3 not found (need heat.exe / candle.exe / light.exe). Install the WiX v3 toolset to build the MSI."
} else {
    Write-Warning "WiX Toolset not found; skipping MSI. Install the WiX v3 toolset to build it locally."
}

$Zip = "dist\HPTemp-$Version-windows-portable.zip"
if (Test-Path -LiteralPath $Zip) { Remove-Item -LiteralPath $Zip }
Compress-Archive -Path $AppDir -DestinationPath $Zip
Write-Host "Wrote $Zip"

Write-Host "Windows outputs in dist\"
Get-ChildItem dist | Format-Table Name, Length
