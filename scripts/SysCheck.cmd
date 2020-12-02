:: Verify the system configuration.

@echo off
:: Check for Python Installation
py --version 2>NUL
if errorlevel 1 goto errorNoPython

:: Reaching here means Python is installed.
py ../SysCheck.py
goto end

:errorNoPython
echo.
echo Python is not available. Install Python 3 from http://python.org/downloads
echo Once Python 3 is installed run this again.

:end
pause
