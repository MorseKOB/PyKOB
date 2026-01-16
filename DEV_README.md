# Development Environment Setup

This file is not intended as any type of tutorial on development, and is therefore
fairly terse.

## Python

PyKOB is currently targeted to Python 3.11. When running the applications, a newer
version can probably be used, but for now we are sticking with 3.11 for development
in order to support the older machines that a number of the users have.

Install a Python 3.11 on the dev machine in order to create the virtual environment
used for development (see the next section).

## Virtual Environment

Use the **requirments.txt** to create a virtual Python environment

### Windows

``` shell
python3 -m venv .venv
.venv/Scripts/activate.bat
```

### Mac

``` shell
python3 -m venv .venv
source .venv/bin/activate
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

