# Harmony Music Player - Windows Build Script (PowerShell)
# Creates executable and installer

param(
    [switch]$Installer,
    [switch]$Zip,
    [switch]$Clean = $true,
    [switch]$Debug
)

$ErrorActionPreference = "Stop"

$APP_NAME = "Harmony"
$APP_VERSION = "1.0.0"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$DIST_DIR = Join-Path $SCRIPT_DIR "dist"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  $APP_NAME v$APP_VERSION - Windows Build" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion"
} catch {
    Write-Host "Error: Python is required" -ForegroundColor Red
    exit 1
}

# Check mpv DLL availability for mpv backend
$mpvDllInPath = $null
foreach ($pathDir in $env:PATH.Split(';')) {
    if (-not [string]::IsNullOrWhiteSpace($pathDir)) {
        $candidate = Join-Path $pathDir "mpv-2.dll"
        if (Test-Path $candidate) {
            $mpvDllInPath = $candidate
            break
        }
    }
}
if (-not $mpvDllInPath) {
    Write-Host "Warning: mpv-2.dll not found in PATH" -ForegroundColor Yellow
    Write-Host "mpv backend may not work in packaged app. Install mpv (e.g. scoop install mpv)." -ForegroundColor Yellow
} else {
    Write-Host "Found mpv DLL: $mpvDllInPath" -ForegroundColor Green
}

# Install PyInstaller if needed
try {
    python -c "import PyInstaller" 2>$null
} catch {
    Write-Host "Installing PyInstaller..."
    pip install pyinstaller
}

# Clean previous builds
if ($Clean) {
    Write-Host "Cleaning previous builds..."
    $buildDir = Join-Path $SCRIPT_DIR "build"
    if (Test-Path $buildDir) {
        Remove-Item -Recurse -Force $buildDir
    }
    if (Test-Path $DIST_DIR) {
        Remove-Item -Recurse -Force $DIST_DIR
    }
}

# Build executable
Write-Host ""
Write-Host "Building executable..."

$buildArgs = @("build.py", "windows")
if (-not $Clean) {
    $buildArgs += "--no-clean"
}
if ($Debug) {
    $buildArgs += "--debug"
}

& python $buildArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Build failed" -ForegroundColor Red
    exit 1
}

$exePath = Join-Path $DIST_DIR "$APP_NAME.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "Error: Executable not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Build completed: $exePath" -ForegroundColor Green

# Create installer
if ($Installer) {
    Write-Host ""
    Write-Host "Creating installer..." -ForegroundColor Yellow

    # Check for Inno Setup
    $isccPath = Get-Command iscc -ErrorAction SilentlyContinue
    if (-not $isccPath) {
        # Try common installation paths
        $innoPaths = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
        )
        foreach ($path in $innoPaths) {
            if (Test-Path $path) {
                $isccPath = $path
                break
            }
        }
    }

    if (-not $isccPath) {
        Write-Host "Inno Setup not found. Skipping installer creation." -ForegroundColor Yellow
        Write-Host "Install from: https://jrsoftware.org/isdl.php"
    } else {
        # Create Inno Setup script
        $issContent = @"
[Setup]
AppName=$APP_NAME
AppVersion=$APP_VERSION
AppPublisher=Harmony Player
AppPublisherURL=https://github.com/harmonyplayer/harmony
DefaultDirName={autopf}\$APP_NAME
DefaultGroupName=$APP_NAME
OutputDir=$DIST_DIR
OutputBaseFilename=$APP_NAME-$APP_VERSION-setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\$APP_NAME.exe
UninstallDisplayName=$APP_NAME
SetupIconFile=$SCRIPT_DIR\icons\icon.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "$DIST_DIR\$APP_NAME.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "$SCRIPT_DIR\translations\*"; DestDir: "{app}\translations"; Flags: ignoreversion recursesubdirs
Source: "$DIST_DIR\mpv-2.dll"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "$DIST_DIR\libmpv-2.dll"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\$APP_NAME"; Filename: "{app}\$APP_NAME.exe"
Name: "{group}\Uninstall $APP_NAME"; Filename: "{uninstallexe}"
Name: "{autodesktop}\$APP_NAME"; Filename: "{app}\$APP_NAME.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Run]
Filename: "{app}\$APP_NAME.exe"; Description: "{cm:LaunchProgram,$APP_NAME}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\$APP_NAME"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"
"@

        $issPath = Join-Path $SCRIPT_DIR "installer.iss"
        $issContent | Out-File -FilePath $issPath -Encoding ASCII

        # Build installer
        & $isccPath $issPath

        if ($LASTEXITCODE -eq 0) {
            Write-Host "Installer created: $DIST_DIR\$APP_NAME-$APP_VERSION-setup.exe" -ForegroundColor Green
        }

        # Clean up ISS file
        Remove-Item $issPath -ErrorAction SilentlyContinue
    }
}

# Create portable ZIP
if ($Zip) {
    Write-Host ""
    Write-Host "Creating portable ZIP..." -ForegroundColor Yellow

    # Check for 7-Zip
    $7zipPath = Get-Command 7z -ErrorAction SilentlyContinue
    if (-not $7zipPath) {
        # Try common installation paths
        $zipPaths = @(
            "${env:ProgramFiles}\7-Zip\7z.exe",
            "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
        )
        foreach ($path in $zipPaths) {
            if (Test-Path $path) {
                $7zipPath = $path
                break
            }
        }
    }

    if (-not $7zipPath) {
        Write-Host "7-Zip not found. Using PowerShell compression..." -ForegroundColor Yellow

        # Create portable directory
        $portableDir = Join-Path $DIST_DIR "$APP_NAME-portable"
        New-Item -ItemType Directory -Force -Path $portableDir | Out-Null

        # Copy executable
        Copy-Item $exePath $portableDir

        # Copy translations
        $translationsDir = Join-Path $SCRIPT_DIR "translations"
        if (Test-Path $translationsDir) {
            $destTranslations = Join-Path $portableDir "translations"
            Copy-Item -Recurse $translationsDir $destTranslations
        }

        # Create README
        $readmeContent = @"
$APP_NAME v$APP_VERSION

This is a portable version. No installation required.
Just run $APP_NAME.exe

System Requirements:
- Windows 10 or later
- Visual C++ Redistributable 2015-2022

Features:
- Modern Spotify-like interface
- Multiple audio format support (MP3, FLAC, OGG, M4A, WAV, WMA)
- Playlist management
- Lyrics display with LRC support
- Album art fetching
- Cloud drive integration (Quark Drive)
- Global hotkeys
- Mini player mode
- Audio equalizer

For support, visit: https://github.com/harmonyplayer/harmony
"@
        $readmePath = Join-Path $portableDir "README.txt"
        $readmeContent | Out-File -FilePath $readmePath -Encoding UTF8

        # Create ZIP using PowerShell
        $zipPath = Join-Path $DIST_DIR "$APP_NAME-$APP_VERSION-portable.zip"
        Compress-Archive -Path "$portableDir\*" -DestinationPath $zipPath -Force

        # Clean up portable directory
        Remove-Item -Recurse -Force $portableDir

        Write-Host "Portable ZIP created: $zipPath" -ForegroundColor Green
    } else {
        # Create portable directory
        $portableDir = Join-Path $DIST_DIR "$APP_NAME-portable"
        New-Item -ItemType Directory -Force -Path $portableDir | Out-Null

        # Copy executable
        Copy-Item $exePath $portableDir

        # Copy translations
        $translationsDir = Join-Path $SCRIPT_DIR "translations"
        if (Test-Path $translationsDir) {
            $destTranslations = Join-Path $portableDir "translations"
            Copy-Item -Recurse $translationsDir $destTranslations
        }

        # Create ZIP
        $zipPath = Join-Path $DIST_DIR "$APP_NAME-$APP_VERSION-portable.zip"
        & $7zipPath a -tzip $zipPath "$portableDir\*"

        # Clean up
        Remove-Item -Recurse -Force $portableDir

        Write-Host "Portable ZIP created: $zipPath" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Executable: $exePath"
Write-Host ""
Write-Host "Additional options:" -ForegroundColor Yellow
Write-Host "  .\build_windows.ps1 -Installer  # Create installer with Inno Setup"
Write-Host "  .\build_windows.ps1 -Zip        # Create portable ZIP"
Write-Host "  .\build_windows.ps1 -Installer -Zip  # Create both"
