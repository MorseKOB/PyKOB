@echo off
rem called from `make64` or `make32`

echo Make the Windows bundle

echo Python: %_PYTHON_EXE_%
echo Build Folder: %_BUILD_DIR_%
echo Dist Folder: %_DIST_DIR_%

if exist %_BUILD_DIR_% rmdir /S /Q %_BUILD_DIR_%
if exist %_DIST_DIR_% rmdir /S /Q %_DIST_DIR_%

rem Run PyInstaller with a specific Python install to generate 
rem the appropriate bundle in the configured 'dist*' folder
echo Building Configure...
%_PYTHON_EXE_% -m PyInstaller --clean --noconfirm --workpath=%_BUILD_DIR_% --distpath=%_DIST_DIR_% Configure.spec
if errorlevel 1 (
    echo PyInstaller Failure on Configure: %errorlevel%
    GOTO ERROR_EXIT
)

rem %_PYTHON_EXE_% -m PyInstaller --distpath=%_DIST_DIR_% Sample.py
rem %_PYTHON_EXE_% -m PyInstaller --distpath=%_DIST_DIR_% Clock.py
echo Building MKOB...
%_PYTHON_EXE_% -m PyInstaller --clean --noconfirm --workpath=%_BUILD_DIR_% --distpath=%_DIST_DIR_% MKOB.spec
if errorlevel 1 (
    echo PyInstaller Failure: %errorlevel%
    GOTO ERROR_EXIT
)

echo Copy Configure.exe into the MKOB folder
@echo on
copy %_DIST_DIR_%\Configure\Configure.exe %_DIST_DIR_%\MKOB4\Configure.exe
@echo off

echo Create ZIP for %_PKG_NAME_%
echo  to %_DIST_DIR_%\%_PKG_NAME_%.zip
powershell Compress-Archive -CompressionLevel Optimal -Path %_DIST_DIR_%\MKOB4\* -DestinationPath %_DIST_DIR_%\%_PKG_NAME_%.zip
if errorlevel 1 (
    echo Powershell Compress-Archive Failure: %errorlevel%
    GOTO ERROR_EXIT
)

exit /b 0

:ERROR_EXIT
    rem if exist %_DIST_DIR_% rmdir /S /Q %_DIST_DIR_%
    exit /b %errorlevel%
