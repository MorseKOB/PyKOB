:: Set MKOB configuration options

@ECHO OFF
set port=com3
set /p port=Serial port (COM3): 
set interface=loop
set /p interface=Interface type (LOOP^|key_sounder): 
set audio=on
set /p audio=Audio (ON^|off): 
set sounder=on
set /p sounder=Sounder (ON^|off): 
py ../Configure.py -p %port% -I %interface% -a %audio% -A %sounder%
pause
