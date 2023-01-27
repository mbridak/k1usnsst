# K1USN SST Logger

[![License: GPL v3](https://img.shields.io/github/license/mbridak/Tuner)](https://opensource.org/licenses/MIT)  [![Python: 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)  [![Made With:PyQt5](https://img.shields.io/badge/Made%20with-PyQt5-red)](https://pypi.org/project/PyQt5/)  ![PyPI - Downloads](https://img.shields.io/pypi/dm/k1usnsst)

## What it is

This is a scratch my own itch project. It's just a simple, lightweight logger for the [K1USN](http://www.k1usn.com/sst.html) slow speed CW contest. I consider it now in a usable stable state. Feel free to use it and give me your comments.

![mainscreen](https://github.com/mbridak/k1usnsst/raw/master/pics/k1usnsst_main.png)

- [K1USN SST Logger](#k1usn-sst-logger)
  - [What it is](#what-it-is)
  - [Recent Changes](#recent-changes)
  - [Installing](#installing)
  - [Running](#running)
  - [Settings](#settings)
    - [QRZ / HamDB](#qrz--hamdb)
    - [CAT](#cat)
    - [Enabling CW Interface](#enabling-cw-interface)
  - [CW Macros](#cw-macros)
  - [When the event is over](#when-the-event-is-over)

## Recent Changes

- Interface is now resizable
- Repackaged for PyPi and it now pip installable

## Installing

In a terminal type:

```bash
pip install k1usnsst
```

## Running

In a terminal type:

```bash
k1usnsst
```

## Settings

### QRZ / HamDB

![settings screen](https://github.com/mbridak/k1usnsst/raw/master/pics/k1usnsst_settings.png)

If you wish to used QRZ to look up the full name and gridsquare for inclusion in your adif log, Click the gear icon in the lower right corner and enter your username and password for QRZ. Then place a check in the 'use QRZ' box.
If you don't subscribe to the QRZ service, you can place a check in the 'use HamDB' box.

### CAT

The program can monitor your radio for band changes with either `rigctld`, `FLRIG` or None. Fill in the hostname and port for your choice.

Common port numbers are 4532 for rigctld and 12345 for FLRIG.

If you don't have rigctld or FLRIG and your a Debian/Ubuntu based Linux user you can install it/them with:

`sudo apt install libhamlib-utils`

`sudo apt install flrig`

### Enabling CW Interface

In the setting screen, switch to the CW tab. Set the host that is running either cwdaemon or PyWinkeyer. Most likely `localhost`. Set the port that the service is listening on. cwdaemon defaults to 6789, Pywinkeyer defaults to 8000. And lastly click the bullet next to the service you will be using.

![CW settings screen](https://github.com/mbridak/k1usnsst/raw/master/pics/cwsettings.png)

## CW Macros

The program will check in the current working directory for a file called `cwmacros_sst.txt`. If it is not there it will create one. It will parse the file and configure the new row of 12 buttons along the bottom half of the window. The macros can be activated by either pressing the corresponding function key, or by directly clicking on the button. You can check the file to glean it's structure, but it's pretty straight forward. Each line has 3 sections separated by the pipe `|` character. Here's an example line.

`F3|Run TU|tu {HISNAME} 73 ee`

The first field is the function key to program. The second is the name of the button. And lastly the third is the text you would like to send.

A limited set substitution macros are offered.

`{MYCALL}`

`{HISCALL}`

`{MYNAME}`

`{HISNAME}`

`{MYSTATE}`

`{HISSTATE}`

`{MYEXCHANGE}` in case you're too lazy to type `{MYCALL} {MYSTATE}`

## When the event is over

Click the 'Generate Log' button in the lower right side of the screen.
Two files will be generated.

SST_Statistics.txt, which holds a breakdown of bands / QSOs / Mults, and a points total for the event.

SST.adi, an ADIF file you can use to merge into your main log if you so choose.

Before the next SST event you should delete the SST.db file to start fresh.