@echo off

echo Make the Windows 32 bit bundle

rem Set environment variables for the Python interpreter and target folder.
set _MAKE_DIR_=%~dp0
set _PYTHON_EXE_=%PYTHON32%
set _BUILD_DIR_=%_MAKE_DIR_%buildW32
set _DIST_DIR_=%_MAKE_DIR_%distW32
set _PKG_NAME_=MKOB-W32

call make_common.cmd
