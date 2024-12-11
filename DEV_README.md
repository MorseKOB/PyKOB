# Development Environment Setup

This file is not intended as any type of tutorial on development, and is therefore
fairly terse.

## Virtual Environment

Use the **requirments.txt** to create a virtual Python environment

``` shell
python3 -m venv .venv
.venv/Scripts/activate.bat
```

 OR

``` shell
python3 -m venv .venv
source .venv/Scripts/activate
```

Load the required modules into the virtual environment:

``` shell
(.venv)
pip install -r requirements.txt
```

## Nuitka

Nuitka (Commercial) is used to create the binary executables of the
Python applications.

It needs to be installed into the Python Virtual Environment created
in the previous step.

Use git to clone the Nuitka-Commercial repo. With the repo cloned, run:

``` shell
.venv\Scripts\python.exe <<Windows path to repo>>\Nuitka-commercial\setup.py install
```

## Makefile Environment

Set up the environment to run make.

### Windows


## Installer

Set up the environment to create an installer.

### Windows

The Windows installer uses Nullsoft Scriptable Install System (NSIS).
NSIS needs to be installed and be in the path.

