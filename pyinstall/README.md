# Executable Packager Files for PyInstaller

This folder contains scripts and PyInstaller `spec` files to create 'frozen' application bundles 
for Windows 64 bit, Windows 32 bit, Mac OS X, and Linux.

The different bundles must be generated on the target platform (Windows 32 bit can be generated on 
a Windows 64 bit machine if a 32 bit Python environment is available).

See the PyInstaller documentation for details.

## Windows

Two `CMD` scripts create the Windows-64 and Windows-32 bundles and generate a zip archive.

The build machine must set two environment variables: 
* PYTHON64 = Path to the python.exe for the 64 bit installation
* PYTHON32 = Path to the python.exe for the 32 bit installation

The scripts must be executed from the project root directory - for example:
pyinstaller\w\make64
