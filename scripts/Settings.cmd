:: Set MKOB configuration options

@ECHO OFF
set port=None
set /p port=Serial port: 
set interface=loop
set /p interface=Interface type [LOOP/key_sounder]: 
set audio=on
set /p audio=Audio [ON/off]: 
set sounder=on
set /p audio=Sounder [ON/off]: 
py ../Configure.py -p %port% -I %interface% -a %audio% -A %sounder%
pause
