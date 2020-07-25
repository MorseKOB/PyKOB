@echo off

REM Call the 64 and 32 bit Make files to build the Win64 and Win32 bundles

echo Build Win64 and Win32 bundles
call make64
if errorlevel 1 (
    echo Make Failure: %errorlevel%
    GOTO ERROR_EXIT
)
call make32
if errorlevel 1 (
    echo Make Failure: %errorlevel%
    GOTO ERROR_EXIT
)

exit /b 0

:ERROR_EXIT
    exit /b %errorlevel%
