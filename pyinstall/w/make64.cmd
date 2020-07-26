@echo off

echo Make the Windows 64 bit bundle

rem Set environment variables for the Python interpreter and target folder.
set _MAKE_DIR_=%~dp0
set _PYTHON_EXE_=%PYTHON64%
set _BUILD_DIR_=%_MAKE_DIR_%buildW64
set _DIST_DIR_=%_MAKE_DIR_%distW64
set _PKG_NAME_=MKOB-W64

call make_common.cmd
