@echo off
rem called from `make64` or `make32`

echo Make the Windows bundle

rem pushd ..\..

echo Python: %_PYTHON_EXE_%
echo Dist Folder: %_DIST_DIR_%

if exist %_DIST_DIR_% rmdir /S /Q %_DIST_DIR_%

rem Run PyInstaller with a specific Python install to generate 
rem the appropriate bundle in the configured 'dist*' folder
%_PYTHON_EXE_% -m PyInstaller --workpath=%_BUILD_DIR_% --distpath=%_DIST_DIR_% Configure.spec
if errorlevel 1 (
    echo PyInstaller Failure on Configure: %errorlevel%
    GOTO ERROR_EXIT
)

rem %_PYTHON_EXE_% -m PyInstaller --distpath=%_DIST_DIR_% Sample.py
rem %_PYTHON_EXE_% -m PyInstaller --distpath=%_DIST_DIR_% Clock.py
%_PYTHON_EXE_% -m PyInstaller --workpath=%_BUILD_DIR_% --distpath=%_DIST_DIR_% MKOB.spec
if errorlevel 1 (
    echo PyInstaller Failure: %errorlevel%
    GOTO ERROR_EXIT
)

echo Create ZIP for %_PKG_NAME_%
echo  to %_DIST_DIR_%\%_PKG_NAME_%.zip
powershell Compress-Archive %_DIST_DIR_% %_DIST_DIR_%\%_PKG_NAME_%.zip
if errorlevel 1 (
    echo Powershell Compress-Archive Failure: %errorlevel%
    GOTO ERROR_EXIT
)

rem popd
exit /b 0

:ERROR_EXIT
    if exist %_DIST_DIR_% rmdir /S /Q %_DIST_DIR_%
    rem popd
    exit /b %errorlevel%
