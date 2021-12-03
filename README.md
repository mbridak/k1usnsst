# K1USN SST Logger

[![License: GPL v3](https://img.shields.io/github/license/mbridak/Tuner)](https://opensource.org/licenses/MIT)  [![Python: 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)  [![Made With:PyQt5](https://img.shields.io/badge/Made%20with-PyQt5-red)](https://pypi.org/project/PyQt5/)

## What it is
This is a scratch my own itch project. It's just a simple, lightweight logger for the [K1USN](http://www.k1usn.com/sst.html) slow speed CW contest. It's a work in progress, not complete as of yet.

![mainscreen](pics/k1usnsst_main.png "Main Screen")

## Running from source

Install Python 3, then two required libraries.

If you're the Ubuntu/Debian type you can:

`sudo apt install python3-pyqt5 python3-requests`

You can install libraries via pip:

`python3 -m pip3 install -r requirements.txt`

Just make k1usnsst.py executable and run it within the same folder, or type:

`python3 k1usnsst.py`

## Building a binary executable

I've included a .spec file in case you wished to create your own binary from the source. To use it, first install pyinstaller.

`python3 -m pip3 install pyinstaller`

Then build the binary.

`pyinstaller -F k1usnsst.spec`

Look in the newly created dist directory to find your binary.