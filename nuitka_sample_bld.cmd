@ECHO OFF
ECHO ************************************************************************
ECHO Build the pykob package and the 'Sample' command-line utility application
REM * USE WITH Python3.11
REM
ECHO.
ECHO ********************************************************
ECHO ** Remove existing 'pykob' package
ECHO ********************************************************
IF exist bin\pykob.build DEL /s/q bin\pykob.build
IF exist bin\pykob.* DEL /q bin\pykob.*
ECHO.
ECHO ********************************************************
ECHO ** Remove existing 'Sample' build and dist
ECHO ********************************************************
IF exist bin\Sample.build DEL /s/q bin\Sample.build
IF exist bin\Sample.dist DEL /s/q bin\Sample.dist
ECHO.
ECHO ********************************************************
ECHO ** Build the 'pykob' package binary
ECHO ********************************************************
python /Users/aesil/code/Nuitka-factory/Nuitka/bin/nuitka --module src.py/pykob --include-package=pykob --include-module=ctypes --include-module=socket --output-dir=bin --enable-console --force-stdout-spec=exe.out.txt --force-stderr-spec=exe.err.txt --debug --python-flag=-v
IF exist bin\pykob.cp311-win_amd64.pyd GOTO NEXT
ECHO.
ECHO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ECHO 'pykob' package binary not found.
GOTO END
:NEXT
ECHO.
ECHO.
ECHO ********************************************************
ECHO ** Build the 'Sample' command-line application binary
ECHO ********************************************************
REM
COPY bin\pykob.cp311-win_amd64.pyd src.py\pykob.pyd
COPY bin\*.pyi src.py
REM
python /Users/aesil/code/Nuitka-factory/Nuitka/bin/nuitka --nofollow-import-to=pykob --standalone --include-data-dir=src.py/pykob/data=pykob/data --include-data-dir=src.py/pykob/resources=pykob/resources --output-dir=bin --enable-console --force-stdout-spec=exe.out.txt --force-stderr-spec=exe.err.txt --debug --python-flag=-v src.py/Sample.py
REM
REM ** Copy pykob package binary into Sample.dist for execution
COPY src.py\pykob.py* bin\Sample.dist
:END
