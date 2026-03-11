@echo off
REM Harmony Music Player - Windows Build Script
REM Creates executable and installer

setlocal enabledelayedexpansion

set APP_NAME=Harmony
set APP_VERSION=1.0.0
set SCRIPT_DIR=%~dp0
set DIST_DIR=%SCRIPT_DIR%dist

echo ==========================================
echo   %APP_NAME% v%APP_VERSION% - Windows Build
echo ==========================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is required
    exit /b 1
)

REM Install PyInstaller if needed
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
echo Cleaning previous builds...
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

REM Build executable
echo.
echo Building executable...
python build.py windows

REM Check if build succeeded
if not exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo Error: Build failed
    exit /b 1
)

echo.
echo Build completed: %DIST_DIR%\%APP_NAME%.exe

REM Create installer (requires Inno Setup)
:create_installer
if "%1"=="--installer" (
    echo.
    echo Creating installer...

    REM Check for Inno Setup
    where iscc >nul 2>&1
    if errorlevel 1 (
        echo Inno Setup not found. Skipping installer creation.
        echo Install from: https://jrsoftware.org/isdl.php
        exit /b 0
    )

    REM Create Inno Setup script
    call :create_inno_script

    REM Build installer
    iscc "%SCRIPT_DIR%installer.iss"

    echo Installer created: %DIST_DIR%\%APP_NAME%-%APP_VERSION%-setup.exe
)

REM Create portable ZIP
if "%1"=="--zip" (
    echo.
    echo Creating portable ZIP...

    REM Check for 7zip
    where 7z >nul 2>&1
    if errorlevel 1 (
        echo 7-Zip not found. Skipping ZIP creation.
        echo Install from: https://www.7-zip.org/
        exit /b 0
    )

    REM Create portable directory
    set PORTABLE_DIR=%DIST_DIR%\%APP_NAME%-portable
    mkdir "%PORTABLE_DIR%"

    REM Copy executable
    copy "%DIST_DIR%\%APP_NAME%.exe" "%PORTABLE_DIR%\"

    REM Create README
    echo %APP_NAME% v%APP_VERSION% > "%PORTABLE_DIR%\README.txt"
    echo. >> "%PORTABLE_DIR%\README.txt"
    echo This is a portable version. No installation required. >> "%PORTABLE_DIR%\README.txt"
    echo Just run %APP_NAME%.exe >> "%PORTABLE_DIR%\README.txt"

    REM Create ZIP
    7z a -tzip "%DIST_DIR%\%APP_NAME%-%APP_VERSION%-portable.zip" "%PORTABLE_DIR%\*"

    echo Portable ZIP created: %DIST_DIR%\%APP_NAME%-%APP_VERSION%-portable.zip
)

echo.
echo Build complete!
echo Executable: %DIST_DIR%\%APP_NAME%.exe
echo.
echo To create additional packages:
echo   %~nx0 --installer  # Create installer with Inno Setup
echo   %~nx0 --zip        # Create portable ZIP with 7-Zip

exit /b 0

:create_inno_script
REM Create Inno Setup script
set ISS_FILE=%SCRIPT_DIR%installer.iss

echo [Setup] > "%ISS_FILE%"
echo AppName=%APP_NAME% >> "%ISS_FILE%"
echo AppVersion=%APP_VERSION% >> "%ISS_FILE%"
echo AppPublisher=Harmony Player >> "%ISS_FILE%"
echo AppPublisherURL=https://github.com/harmonyplayer/harmony >> "%ISS_FILE%"
echo DefaultDirName={autopf}\%APP_NAME% >> "%ISS_FILE%"
echo DefaultGroupName=%APP_NAME% >> "%ISS_FILE%"
echo OutputDir=%DIST_DIR% >> "%ISS_FILE%"
echo OutputBaseFilename=%APP_NAME%-%APP_VERSION%-setup >> "%ISS_FILE%"
echo SetupIconFile=%SCRIPT_DIR%icons\icon.ico >> "%ISS_FILE%"
echo Compression=lzma >> "%ISS_FILE%"
echo SolidCompression=yes >> "%ISS_FILE%"
echo PrivilegesRequired=lowest >> "%ISS_FILE%"
echo PrivilegesRequiredOverridesAllowed=dialog >> "%ISS_FILE%"
echo UninstallDisplayIcon={app}\%APP_NAME%.exe >> "%ISS_FILE%"
echo UninstallDisplayName=%APP_NAME% >> "%ISS_FILE%"
echo. >> "%ISS_FILE%"
echo [Files] >> "%ISS_FILE%"
echo Source: "%DIST_DIR%\%APP_NAME%.exe"; DestDir: "{app}"; Flags: ignoreversion >> "%ISS_FILE%"
echo. >> "%ISS_FILE%"
echo [Icons] >> "%ISS_FILE%"
echo Name: "{group}\%APP_NAME%"; Filename: "{app}\%APP_NAME%.exe" >> "%ISS_FILE%"
echo Name: "{group}\Uninstall %APP_NAME%"; Filename: "{uninstallexe}" >> "%ISS_FILE%"
echo Name: "{autodesktop}\%APP_NAME%"; Filename: "{app}\%APP_NAME%.exe"; Tasks: desktopicon >> "%ISS_FILE%"
echo. >> "%ISS_FILE%"
echo [Tasks] >> "%ISS_FILE%"
echo Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}" >> "%ISS_FILE%"
echo. >> "%ISS_FILE%"
echo [Run] >> "%ISS_FILE%"
echo Filename: "{app}\%APP_NAME%.exe"; Description: "{cm:LaunchProgram,%APP_NAME%}"; Flags: nowait postinstall skipifsilent >> "%ISS_FILE%"

exit /b 0
