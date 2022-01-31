#!/usr/bin/env python3
"""
Logger for K1USN SST
"""

import logging
import xmlrpc.client
import sys
import sqlite3
import socket
import os

from json import dumps, loads
from datetime import datetime
from pathlib import Path
from shutil import copyfile
from xmlrpc.client import ServerProxy, Error
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFontDatabase
from bs4 import BeautifulSoup as bs
import requests


def relpath(filename: str):
    """
    Checks to see if program has been packaged with pyinstaller.
    If so base dir is in a temp folder.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = getattr(sys, "_MEIPASS")
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)


def load_fonts_from_dir(directory):
    """
    Well it loads fonts from a directory...
    """
    font_families = set()
    for _fi in QDir(directory).entryInfoList(["*.ttf", "*.woff", "*.woff2"]):
        _id = QFontDatabase.addApplicationFont(_fi.absoluteFilePath())
        font_families |= set(QFontDatabase.applicationFontFamilies(_id))
    return font_families


class QSOEdit(QtCore.QObject):
    """
    Custom qt event signal used when qso edited or deleted.
    """

    lineChanged = QtCore.pyqtSignal()


class QRZlookup:
    """
    Class manages QRZ lookups. Pass in a username and password at instantiation.
    """

    def __init__(self, username: str, password: str) -> None:
        self.session = False
        self.expiration = False
        self.error = (
            False  # "password incorrect", "session timeout", and "callsign not found".
        )
        self.username = username
        self.password = password
        self.qrzurl = "https://xmldata.qrz.com/xml/134/"
        self.message = False
        self.lastresult = False
        self.getsession()

    def getsession(self) -> None:
        """
        Get QRZ session key.
        Stores key in class variable 'session'
        Error messages returned by QRZ will be in class variable 'error'
        Other messages returned will be in class variable 'message'
        """
        logging.info("QRZlookup-getsession:")
        self.error = False
        self.message = False
        self.session = False
        try:
            payload = {"username": self.username, "password": self.password}
            query_result = requests.get(self.qrzurl, params=payload, timeout=10.0)
            root = bs(query_result.text, "html.parser")
            if root.session.find("key"):
                self.session = root.session.key.text
            if root.session.find("subexp"):
                self.expiration = root.session.subexp.text
            if root.session.find("error"):
                self.error = root.session.error.text
            if root.session.find("message"):
                self.message = root.session.message.text
            logging.info(
                "QRZlookup-getsession: key:%s error:%s message:%s",
                self.session,
                self.error,
                self.message,
            )
        except requests.exceptions.RequestException as exception:
            logging.info("QRZlookup-getsession: %s", exception)
            self.session = False
            self.error = f"{exception}"

    def lookup(self, call: str) -> tuple:
        """
        Lookup a call on QRZ
        """
        logging.info("QRZlookup-lookup: %s", call)
        grid = False
        name = False
        error_text = False
        nickname = False
        if self.session:
            payload = {"s": self.session, "callsign": call}
            query_result = requests.get(self.qrzurl, params=payload, timeout=3.0)
            root = bs(query_result.text, "html.parser")
            if not root.session.key:  # key expired get a new one
                logging.info("QRZlookup-lookup: no key, getting new one.")
                self.getsession()
                if self.session:
                    payload = {"s": self.session, "callsign": call}
                    query_result = requests.get(
                        self.qrzurl, params=payload, timeout=3.0
                    )
            grid, name, nickname, error_text = self.parse_lookup(query_result)
        return grid, name, nickname, error_text

    def parse_lookup(self, query_result):
        """
        Returns gridsquare and name for a callsign looked up by qrz or hamdb.
        Or False for both if none found or error.
        """
        logging.info("QRZlookup-parse_lookup:")
        grid = False
        name = False
        error_text = False
        nickname = False
        if query_result.status_code == 200:
            root = bs(query_result.text, "html.parser")
            if root.session.find("error"):
                error_text = root.session.error.text
                self.error = error_text
            if root.find("callsign"):
                if root.callsign.find("grid"):
                    grid = root.callsign.grid.text
                if root.callsign.find("fname"):
                    name = root.callsign.fname.text
                if root.find("name"):
                    if not name:
                        name = root.find("name").string
                    else:
                        name = f"{name} {root.find('name').string}"
                if root.callsign.find("nickname"):
                    nickname = root.callsign.nickname.text
        logging.info(
            "QRZlookup-parse_lookup: %s %s %s %s", grid, name, nickname, error_text
        )
        return grid, name, nickname, error_text


class MainWindow(QtWidgets.QMainWindow):
    """
    The main window
    """

    database = "SST.db"
    server = False
    mycall = ""
    myexchange = ""
    userigctl = True
    flrig = False
    rigonline = False
    useqrz = False
    qrz = False
    oldfreq = None
    band = None
    dfreq = {
        "160": "1830000",
        "80": "3530000",
        "60": "5340000",
        "40": "7030000",
        "20": "14030000",
        "15": "21030000",
        "10": "28030000",
        "6": "50030000",
        "2": "144030000",
        "222": "222030000",
        "432": "432030000",
    }
    settings_dict = {
        "mycallsign": "",
        "myexchange": "",
        "qrzusername": "w1aw",
        "qrzpassword": "secret",
        "qrzurl": "https://xmldata.qrz.com/xml/134",
        "useqrz": 0,
        "userigcontrol": 0,
        "rigcontrolip": "localhost",
        "rigcontrolport": "12345",
        "usehamdb": 0,
    }
    fkeys = {}
    keyerserver = "http://localhost:8000"
    pastcontacts = {}

    def __init__(self, *args, **kwargs):
        logging.info("MainWindow: __init__")
        super().__init__(*args, **kwargs)
        uic.loadUi(self.relpath("main.ui"), self)
        self.listWidget.itemDoubleClicked.connect(self.qsoclicked)
        self.mycallEntry.textEdited.connect(self.changemycall)
        self.myexchangeEntry.textEdited.connect(self.changemyexchange)
        self.callsign_entry.textEdited.connect(self.calltest)
        self.callsign_entry.returnPressed.connect(self.log_contact)
        self.callsign_entry.editingFinished.connect(self.dup_check)
        self.exchange_entry.textEdited.connect(self.exchangetest)
        self.exchange_entry.returnPressed.connect(self.log_contact)
        self.radio_grey = QtGui.QPixmap(self.relpath("icon/radio_grey.png"))
        self.radio_green = QtGui.QPixmap(self.relpath("icon/radio_green.png"))
        self.radio_red = QtGui.QPixmap(self.relpath("icon/radio_red.png"))
        self.radio_icon.setPixmap(self.radio_grey)
        self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
        self.genLogButton.clicked.connect(self.generate_logs)
        self.band_selector.activated.connect(self.changeband)
        self.settings_gear.clicked.connect(self.settingspressed)
        self.radiochecktimer = QtCore.QTimer()
        self.radiochecktimer.timeout.connect(self.Radio)
        self.radiochecktimer.start(1000)
        self.changeband()
        self.readpreferences()
        if self.settings_dict["useqrz"]:
            self.qrz = QRZlookup(
                self.settings_dict["qrzusername"], self.settings_dict["qrzpassword"]
            )
            if not self.qrz.session:
                self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
            else:
                self.QRZ_icon.setStyleSheet("color: rgb(128, 128, 0);")
        self.F1.clicked.connect(self.sendf1)
        self.F2.clicked.connect(self.sendf2)
        self.F3.clicked.connect(self.sendf3)
        self.F4.clicked.connect(self.sendf4)
        self.F5.clicked.connect(self.sendf5)
        self.F6.clicked.connect(self.sendf6)
        self.F7.clicked.connect(self.sendf7)
        self.F8.clicked.connect(self.sendf8)
        self.F9.clicked.connect(self.sendf9)
        self.F10.clicked.connect(self.sendf10)
        self.F11.clicked.connect(self.sendf11)
        self.F12.clicked.connect(self.sendf12)

    def settingspressed(self):
        """
        When the gear icon is clicked, this is called
        """
        logging.info("MainWindow: settingspressed")
        settingsdialog = Settings()
        settingsdialog.setup()
        settingsdialog.exec()
        self.readpreferences()

    def relpath(self, filename):
        """
        If the program is packaged with pyinstaller,
        this is needed since all files will be in a temp folder during execution.
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_path = getattr(sys, "_MEIPASS")
        else:
            base_path = os.path.abspath(".")
        logging.info("MainWindow: relpath: %s%s", base_path, filename)
        return os.path.join(base_path, filename)

    def read_cw_macros(self):
        """
        Reads in the CW macros, firsts it checks to see if the file exists. If it does not,
        and this has been packaged with pyinstaller it will copy the default file from the
        temp directory this is running from... In theory.
        """

        if (
            getattr(sys, "frozen", False)
            and hasattr(sys, "_MEIPASS")
            and not Path("./cwmacros_sst.txt").exists()
        ):
            logging.info("read_cw_macros: copying default macro file.")
            copyfile(relpath("cwmacros_sst.txt"), "./cwmacros_sst.txt")
        with open("./cwmacros_sst.txt", "r", encoding="utf-8") as cw_macros:
            for line in cw_macros:
                try:
                    fkey, buttonname, cwtext = line.split("|")
                    self.fkeys[fkey.strip()] = (buttonname.strip(), cwtext.strip())
                except ValueError:
                    break
        if "F1" in self.fkeys.keys():
            self.F1.setText(f"F1: {self.fkeys['F1'][0]}")
            self.F1.setToolTip(self.fkeys["F1"][1])
        if "F2" in self.fkeys.keys():
            self.F2.setText(f"F2: {self.fkeys['F2'][0]}")
            self.F2.setToolTip(self.fkeys["F2"][1])
        if "F3" in self.fkeys.keys():
            self.F3.setText(f"F3: {self.fkeys['F3'][0]}")
            self.F3.setToolTip(self.fkeys["F3"][1])
        if "F4" in self.fkeys.keys():
            self.F4.setText(f"F4: {self.fkeys['F4'][0]}")
            self.F4.setToolTip(self.fkeys["F4"][1])
        if "F5" in self.fkeys.keys():
            self.F5.setText(f"F5: {self.fkeys['F5'][0]}")
            self.F5.setToolTip(self.fkeys["F5"][1])
        if "F6" in self.fkeys.keys():
            self.F6.setText(f"F6: {self.fkeys['F6'][0]}")
            self.F6.setToolTip(self.fkeys["F6"][1])
        if "F7" in self.fkeys.keys():
            self.F7.setText(f"F7: {self.fkeys['F7'][0]}")
            self.F7.setToolTip(self.fkeys["F7"][1])
        if "F8" in self.fkeys.keys():
            self.F8.setText(f"F8: {self.fkeys['F8'][0]}")
            self.F8.setToolTip(self.fkeys["F8"][1])
        if "F9" in self.fkeys.keys():
            self.F9.setText(f"F9: {self.fkeys['F9'][0]}")
            self.F9.setToolTip(self.fkeys["F9"][1])
        if "F10" in self.fkeys.keys():
            self.F10.setText(f"F10: {self.fkeys['F10'][0]}")
            self.F10.setToolTip(self.fkeys["F10"][1])
        if "F11" in self.fkeys.keys():
            self.F11.setText(f"F11: {self.fkeys['F11'][0]}")
            self.F11.setToolTip(self.fkeys["F11"][1])
        if "F12" in self.fkeys.keys():
            self.F12.setText(f"F12: {self.fkeys['F12'][0]}")
            self.F12.setToolTip(self.fkeys["F12"][1])

    def readpastcontacts(self) -> None:
        """
        Reads in past exchange info from contacts that you have made.
        """
        try:
            home = os.path.expanduser("~")
            if os.path.exists(home + "/pastcontacts.json"):
                with open(
                    home + "/pastcontacts.json", "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.pastcontacts = loads(file_descriptor.read())
            else:
                with open(
                    home + "/pastcontacts.json", "wt", encoding="utf-8"
                ) as file_descriptor:
                    file_descriptor.write(dumps(self.pastcontacts))
        except IOError as exception:
            logging.critical("readpastcontacts: %s", exception)

    def savepastcontacts(self) -> None:
        """
        Saves contact call, name and state to a json file.
        """
        try:
            home = os.path.expanduser("~")
            with open(
                home + "/pastcontacts.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.pastcontacts))
        except IOError as exception:
            logging.critical("savepastcontacts: %s", exception)

    def has_internet(self):
        """
        Connect to a main DNS server to check connectivity.
        Returns True/False
        """
        try:
            socket.create_connection(("1.1.1.1", 53))
            logging.info("MainWindow: has_internet - True")
            return True
        except OSError as exception:
            logging.info("MainWindow: has_internet: %s", exception)
        return False

    def getband(self, freq: str) -> str:
        """
        Convert a (float) frequency into a (string) band.
        Returns a (string) band.
        Returns a "0" if frequency is out of band.
        """
        logging.info("MainWindow: getband: %s", freq)
        if freq.isnumeric():
            frequency = int(float(freq))
            if frequency > 1800000 and frequency < 2000000:
                return "160"
            if frequency > 3500000 and frequency < 4000000:
                return "80"
            if frequency > 5330000 and frequency < 5406000:
                return "60"
            if frequency > 7000000 and frequency < 7300000:
                return "40"
            if frequency > 10100000 and frequency < 10150000:
                return "30"
            if frequency > 14000000 and frequency < 14350000:
                return "20"
            if frequency > 18068000 and frequency < 18168000:
                return "17"
            if frequency > 21000000 and frequency < 21450000:
                return "15"
            if frequency > 24890000 and frequency < 24990000:
                return "12"
            if frequency > 28000000 and frequency < 29700000:
                return "10"
            if frequency > 50000000 and frequency < 54000000:
                return "6"
            if frequency > 144000000 and frequency < 148000000:
                return "2"
        else:
            return "0"

    def changeband(self):
        """
        Sets the internal band used for logging to the onscreen dropdown value.
        """
        self.band = self.band_selector.currentText()
        if not (self.rigonline or self.flrig):
            self.oldfreq = self.dfreq[self.band]

    def setband(self, theband: str) -> None:
        """
        It sets the band.
        """
        self.band_selector.setCurrentIndex(self.band_selector.findText(theband))
        self.changeband()

    def poll_radio(self) -> None:
        """
        Poll rigctld to get band.
        """
        if self.flrig:
            try:
                newfreq = self.server.rig.get_vfo()
                self.radio_icon.setPixmap(self.radio_green)
                if newfreq != self.oldfreq:
                    self.oldfreq = newfreq
                    self.setband(str(self.getband(newfreq)))
            except socket.error as exception:
                self.radio_icon.setPixmap(self.radio_red)
                logging.warning("poll_radio: flrig: %s", exception)
            return
        if self.rigonline:
            self.rigctrlsocket.settimeout(0.5)
            self.rigctrlsocket.send(b"f")
            newfreq = self.rigctrlsocket.recv(1024).decode().strip()
            self.radio_icon.setPixmap(self.radio_green)
            self.rigctrlsocket.shutdown(socket.SHUT_RDWR)
            self.rigctrlsocket.close()
            if newfreq != self.oldfreq:
                self.oldfreq = newfreq
                self.setband(str(self.getband(newfreq)))

    def check_radio(self) -> None:
        """
        Checks to see if rigctld daemon is running.
        """
        if not (self.flrig or self.userigctl):
            self.radio_icon.setPixmap(self.radio_grey)
        if self.userigctl:
            self.rigctrlsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.rigctrlsocket.settimeout(0.1)
            self.rigonline = True
            try:
                logging.info(
                    "check_radio: %s %s",
                    self.settings_dict["rigcontrolip"],
                    self.settings_dict["rigcontrolport"],
                )
                self.rigctrlsocket.connect(
                    (
                        self.settings_dict["rigcontrolip"],
                        int(self.settings_dict["rigcontrolport"]),
                    )
                )
            except socket.error:
                self.rigonline = False
                logging.info("check_radio: Rig Offline.")
                self.radio_icon.setPixmap(self.radio_red)
        else:
            self.rigonline = False

    def Radio(self):
        """
        Check for connection to rigctld. if it's there, poll it for radio status.
        """
        self.check_radio()
        self.poll_radio()

    def process_macro(self, macro):
        macro = macro.upper()
        macro = macro.replace("{MYEXCHANGE}", self.myexchangeEntry.text())
        macro = macro.replace("{MYCALL}", self.mycallEntry.text())
        myname, mystate = "", ""
        if len(self.myexchangeEntry.text().strip().split()) == 2:
            myname = self.myexchangeEntry.text().strip().split()[0]
            mystate = self.myexchangeEntry.text().strip().split()[1]
        macro = macro.replace("{MYNAME}", myname)
        macro = macro.replace("{MYSTATE}", mystate)
        macro = macro.replace("{HISCALL}", self.callsign_entry.text())
        hisname, hisstate = "", ""
        if len(self.exchange_entry.text().strip().split()) == 2:
            hisname = self.exchange_entry.text().strip().split()[0]
            hisstate = self.exchange_entry.text().strip().split()[1]
        macro = macro.replace("{HISNAME}", hisname)
        macro = macro.replace("{HISSTATE}", hisstate)
        return macro

    def keyPressEvent(self, event):
        """
        Process pressing TAB, ESC, F1-F12
        """
        if event.key() == Qt.Key_Escape:
            self.clearinputs()
        if event.key() == Qt.Key_Tab:
            if self.exchange_entry.hasFocus():
                logging.info("From exchange")
                self.callsign_entry.setFocus()
                self.callsign_entry.deselect()
                self.callsign_entry.end(False)
                return
            if self.callsign_entry.hasFocus():
                logging.info("From callsign")
                self.exchange_entry.setFocus()
                self.exchange_entry.deselect()
                self.exchange_entry.end(False)
                return
        if event.key() == Qt.Key_F1:
            self.sendf1()
        if event.key() == Qt.Key_F2:
            self.sendf2()
        if event.key() == Qt.Key_F3:
            self.sendf3()
        if event.key() == Qt.Key_F4:
            self.sendf4()
        if event.key() == Qt.Key_F5:
            self.sendf5()
        if event.key() == Qt.Key_F6:
            self.sendf6()
        if event.key() == Qt.Key_F7:
            self.sendf7()
        if event.key() == Qt.Key_F8:
            self.sendf8()
        if event.key() == Qt.Key_F9:
            self.sendf9()
        if event.key() == Qt.Key_F10:
            self.sendf10()
        if event.key() == Qt.Key_F11:
            self.sendf11()
        if event.key() == Qt.Key_F12:
            self.sendf12()

    def sendcw(self, texttosend: str) -> None:
        """
        Sends string to k1el keyer.
        """
        logging.info("sendcw: %s", texttosend)
        with ServerProxy(self.keyerserver) as proxy:
            try:
                proxy.k1elsendstring(texttosend)
            except Error as exception:
                logging.info("%s, xmlrpc error: %s", self.keyerserver, exception)
            except ConnectionRefusedError:
                logging.info("%s, xmlrpc Connection Refused", self.keyerserver)

    def sendf1(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F1.toolTip()))

    def sendf2(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F2.toolTip()))

    def sendf3(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F3.toolTip()))

    def sendf4(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F4.toolTip()))

    def sendf5(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F5.toolTip()))

    def sendf6(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F6.toolTip()))

    def sendf7(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F7.toolTip()))

    def sendf8(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F8.toolTip()))

    def sendf9(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F9.toolTip()))

    def sendf10(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F10.toolTip()))

    def sendf11(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F11.toolTip()))

    def sendf12(self) -> None:
        """
        Sends the contents of buttons tool tip
        to the k1el keyer.
        """
        self.sendcw(self.process_macro(self.F12.toolTip()))

    def clearinputs(self) -> None:
        """
        Clears input fields and sets focus to callsign field
        """
        self.dupe_indicator.setText("")
        if self.settings_dict["useqrz"]:
            if self.qrz.error:
                self.dupe_indicator.setText(self.qrz.error)
        self.callsign_entry.clear()
        self.exchange_entry.clear()
        self.callsign_entry.setFocus()

    def update_time(self) -> None:
        """
        Update local and UTC time on screen.
        """
        utcnow = datetime.utcnow().isoformat(" ")[5:19].replace("-", "/")
        self.utctime.setText(utcnow)

    def flash(self) -> None:
        """
        Flash the screen to give visual indication of a dupe.
        """
        self.setStyleSheet(
            "background-color: rgb(245, 121, 0);\ncolor: rgb(211, 215, 207);"
        )
        app.processEvents()
        self.setStyleSheet(
            "background-color: rgb(42, 42, 42);\ncolor: rgb(211, 215, 207);"
        )
        app.processEvents()

    def changemycall(self) -> None:
        text = self.mycallEntry.text()
        if len(text):
            if text[-1] == " ":
                self.mycallEntry.setText(text.strip())
            else:
                cleaned = "".join(
                    ch for ch in text if ch.isalnum() or ch == "/"
                ).upper()
                self.mycallEntry.setText(cleaned)
        self.settings_dict["mycallsign"] = self.mycallEntry.text()
        if self.settings_dict["mycallsign"] != "":
            self.mycallEntry.setStyleSheet("border: 1px solid green;")
        else:
            self.mycallEntry.setStyleSheet("border: 1px solid red;")
        self.writepreferences()

    def changemyexchange(self) -> None:
        text = self.myexchangeEntry.text()
        if len(text):
            cleaned = "".join(ch for ch in text if ch.isalpha() or ch == " ").upper()
            self.myexchangeEntry.setText(cleaned)
        self.settings_dict["myexchange"] = self.myexchangeEntry.text()
        if self.settings_dict["myexchange"] != "":
            self.myexchangeEntry.setStyleSheet("border: 1px solid green;")
        else:
            self.myexchangeEntry.setStyleSheet("border: 1px solid red;")
        self.writepreferences()

    def calltest(self) -> None:
        """
        Cleans callsign of spaces and strips non alphanumeric or '/' characters.
        """
        text = self.callsign_entry.text()
        if len(text):
            if text[-1] == " ":
                self.callsign_entry.setText(text.strip())
                self.exchange_entry.setFocus()
                self.exchange_entry.deselect()
            else:
                washere = self.callsign_entry.cursorPosition()
                cleaned = "".join(
                    ch for ch in text if ch.isalnum() or ch == "/"
                ).upper()
                self.callsign_entry.setText(cleaned)
                self.callsign_entry.setCursorPosition(washere)

    def exchangetest(self) -> None:
        """
        Cleans exchange, strips non alpha or space characters.
        """
        text = self.exchange_entry.text()
        if len(text):
            washere = self.exchange_entry.cursorPosition()
            cleaned = "".join(ch for ch in text if ch.isalpha() or ch == " ").upper()
            self.exchange_entry.setText(cleaned)
            self.exchange_entry.setCursorPosition(washere)

    def dup_check(self) -> None:
        """
        Check for duplicate
        """
        acall = self.callsign_entry.text()
        if len(self.exchange_entry.text()) == 0 and (acall in self.pastcontacts.keys()):
            self.exchange_entry.setText(self.pastcontacts[acall])
        dupetext = ""
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"select callsign, name, sandpdx, band from contacts where callsign like '{acall}' order by band"
                )
                log = cursor.fetchall()
        except sqlite3.Error as exception:
            logging.critical("dup_check: %s", exception)
            return
        for item in log:
            _, hisname, sandpdx, hisband = item
            if len(self.exchange_entry.text()) == 0:
                self.exchange_entry.setText(f"{hisname} {sandpdx}")
            if hisband == self.band:
                self.flash()
                dupetext = " DUP!!!"
                self.dupe_indicator.setText(dupetext)

    def create_db(self) -> None:
        """create a database and table if it does not exist"""
        try:
            with sqlite3.connect(self.database) as conn:
                cursor = conn.cursor()
                sql_table = """ CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, callsign text NOT NULL, name text NOT NULL, sandpdx text NOT NULL, date_time text NOT NULL, frequency text NOT NULL, band text NOT NULL, grid text NOT NULL, opname text NOT NULL); """
                cursor.execute(sql_table)
        except sqlite3.Error as exception:
            logging.critical("create_db: %s", exception)

    def readpreferences(self) -> None:
        """
        Reads preferences from json file.
        """
        logging.info("readpreferences:")
        try:
            home = os.path.expanduser("~")
            if os.path.exists(home + "/.k1usnsst.json"):
                with open(
                    home + "/.k1usnsst.json", "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.settings_dict = loads(file_descriptor.read())
                    self.mycallEntry.setText(self.settings_dict["mycallsign"])
                    self.myexchangeEntry.setText(self.settings_dict["myexchange"])
                    self.flrig = False
                    self.userigctl = False
                    if self.settings_dict["userigcontrol"] == 1:
                        self.flrig = False
                        self.userigctl = True
                    if self.settings_dict["userigcontrol"] == 2:
                        self.flrig = True
                        self.userigctl = False
                        self.server = xmlrpc.client.ServerProxy(
                            f"http://{self.settings_dict['rigcontrolip']}:{self.settings_dict['rigcontrolport']}"
                        )
            else:
                with open(
                    home + "/.k1usnsst.json", "wt", encoding="utf-8"
                ) as file_descriptor:
                    file_descriptor.write(dumps(self.settings_dict))
        except Error as exception:
            logging.critical("readpreferences: %s", exception)

    def writepreferences(self) -> None:
        """
        Write preferences to json file.
        """
        logging.info("writepreferences:")
        home = os.path.expanduser("~")
        with open(home + "/.k1usnsst.json", "wt", encoding="utf-8") as file_descriptor:
            file_descriptor.write(dumps(self.settings_dict))

    def log_contact(self) -> None:
        """
        Log Contact
        """
        logging.info("log_contact:")
        grid = False
        opname = False
        error = False
        if (
            len(self.callsign_entry.text()) == 0
            or len(self.exchange_entry.text().split()) < 2
        ):
            return
        self.pastcontacts[self.callsign_entry.text()] = self.exchange_entry.text()
        self.savepastcontacts()
        if self.settings_dict["useqrz"]:
            grid, opname, nickname, error = self.qrz.lookup(self.callsign_entry.text())
        if error:
            logging.info("log_contact: lookup error %s", error)
        if not grid:
            grid = ""
        if not opname:
            opname = ""
        contact = (
            self.callsign_entry.text(),
            self.exchange_entry.text().split()[0],
            self.exchange_entry.text().split()[1],
            self.oldfreq,
            self.band,
            grid,
            opname,
        )
        try:
            with sqlite3.connect(self.database) as conn:
                sql = "INSERT INTO contacts(callsign, name, sandpdx, date_time, frequency, band, grid, opname) VALUES(?,?,?,datetime('now'),?,?,?,?)"
                logging.info("log_contact: %s\n%s", sql, contact)
                cur = conn.cursor()
                cur.execute(sql, contact)
                conn.commit()
        except sqlite3.Error as exception:
            logging.critical("Log Contact: %s", exception)
        self.logwindow()
        self.clearinputs()

    def logwindow(self):
        logging.info("loqwindow:")
        self.listWidget.clear()
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select * from contacts order by date_time desc")
                log = c.fetchall()
        except sqlite3.Error as exception:
            logging.critical("logwindow: %s", exception)
        for x in log:
            logid, hiscall, hisname, sandpdx, datetime, frequency, band, _, _ = x
            logline = f"{str(logid).rjust(3,'0')} {hiscall.ljust(11)} {hisname.ljust(12)} {sandpdx} {datetime} {str(band).rjust(3)}"
            self.listWidget.addItem(logline)
        self.calcscore()

    def qsoclicked(self):
        """
        Gets the line of the log clicked on, and passes that line to the edit dialog.
        """
        logging.info("qsoclicked:")
        item = self.listWidget.currentItem()
        linetopass = item.text()
        dialog = edit_qso_dialog(self)
        dialog.setup(linetopass, self.database)
        dialog.change.lineChanged.connect(self.qsoedited)
        dialog.open()

    def qsoedited(self):
        """
        Perform functions after QSO edited or deleted.
        """
        self.logwindow()

    def adif(self):
        logname = "SST.adi"
        logging.info("Saving ADIF to: %s\n", logname)
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select * from contacts order by date_time ASC")
                log = c.fetchall()
        except sqlite3.Error as exception:
            logging.critical("adif: %s", exception)
            self.dupe_indicator.setText("Error!")
            return
        grid = False
        opname = False
        with open(logname, "w", encoding="ascii") as f:
            print("<ADIF_VER:5>2.2.0", end="\r\n", file=f)
            print("<EOH>", end="\r\n", file=f)
            mode = "CW"
            for x in log:
                (
                    _,
                    hiscall,
                    hisname,
                    sandpdx,
                    datetime,
                    frequency,
                    band,
                    grid,
                    opname,
                ) = x
                loggeddate = datetime[:10]
                loggedtime = datetime[11:13] + datetime[14:16]
                print(
                    f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>{''.join(loggeddate.split('-'))}",
                    end="\r\n",
                    file=f,
                )
                print(f"<TIME_ON:{len(loggedtime)}>{loggedtime}", end="\r\n", file=f)
                print(f"<CALL:{len(hiscall)}>{hiscall}", end="\r\n", file=f)
                print(f"<MODE:{len(mode)}>{mode}", end="\r\n", file=f)
                print(f"<BAND:{len(band + 'M')}>{band + 'M'}", end="\r\n", file=f)
                freq = str(int(frequency) / 1000000)
                print(f"<FREQ:{len(freq)}>{freq}", end="\r\n", file=f)
                print("<RST_SENT:3>599", end="\r\n", file=f)
                print("<RST_RCVD:3>599", end="\r\n", file=f)
                print(
                    f"<STX_STRING:{len(self.myexchangeEntry.text())}>{self.myexchangeEntry.text()}",
                    end="\r\n",
                    file=f,
                )
                hisexchange = f"{hisname} {sandpdx}"
                print(
                    f"<SRX_STRING:{len(hisexchange)}>{hisexchange}", end="\r\n", file=f
                )
                state = sandpdx
                if state:
                    print(f"<STATE:{len(state)}>{state}", end="\r\n", file=f)
                if len(grid) > 1:
                    print(f"<GRIDSQUARE:{len(grid)}>{grid}", end="\r\n", file=f)
                if len(opname) > 1:
                    print(f"<NAME:{len(opname)}>{opname}", end="\r\n", file=f)
                comment = "K1USN SST"
                print(f"<COMMENT:{len(comment)}>{comment}", end="\r\n", file=f)
                contest = "K1USN-SST"
                print(f"<CONTEST_ID:{len(contest)}>{contest}", end="\r\n", file=f)
                print("<EOR>", end="\r\n", file=f)
        self.dupe_indicator.setText(f"{logname} saved.")

    def calcscore(self):
        """
        determine the amount od QSO's, S/P per band, DX per band.
        """
        logging.info("calcscore()")
        total_qso = 0
        total_mults = 0
        total_score = 0
        with open("SST_Statistics.txt", "w", encoding="ascii") as f:
            print("", file=f)
        bandsworked = self.getbands()
        for band in bandsworked:
            try:
                with sqlite3.connect(self.database) as conn:
                    c = conn.cursor()
                    query = f"select count(*) from contacts where band='{band}'"
                    c.execute(query)
                    qso = c.fetchone()
                    query = f"select count(distinct sandpdx) from contacts where band='{band}' and sandpdx <> 'DX'"
                    c.execute(query)
                    sandp = c.fetchone()
                    query = f"select count(*) from contacts where band='{band}' and sandpdx = 'DX'"
                    c.execute(query)
                    dx = c.fetchone()
                    with open("SST_Statistics.txt", "a", encoding="ascii") as f:
                        print(
                            f"band:{band} QSOs:{qso[0]} state and province:{sandp[0]} dx:{dx[0]} mult:{sandp[0]+dx[0]}",
                            end="\r\n",
                            file=f,
                        )
                    logging.info(
                        "score: band:%s q:%s s&p:%s dx:%s", band, qso, sandp, dx
                    )
            except sqlite3.Error as exception:
                logging.critical("calcscore: %s", exception)
            total_qso += qso[0]
            total_mults += sandp[0] + dx[0]
            total_score = total_qso * total_mults
        self.Total_CW.setText(str(total_qso))
        self.Total_Mults.setText(str(total_mults))
        self.Total_Score.setText(str(total_score))
        with open("SST_Statistics.txt", "a", encoding="ascii") as f:
            print(f"Total QSO: {total_qso}", end="\r\n", file=f)
            print(f"Total Mults: {total_mults}", end="\r\n", file=f)
            print(f"Total Score: {total_score}", end="\r\n", file=f)

    def getbands(self):
        """
        Returns a list of bands worked, and an empty list if none worked.
        """
        bandlist = []
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select DISTINCT band from contacts")
                x = c.fetchall()
        except sqlite3.Error as exception:
            logging.critical("getbands: %s", exception)
            return []
        if x:
            for count in x:
                bandlist.append(count[0])
            return bandlist
        return []

    def generate_logs(self):
        self.calcscore()
        self.adif()


class edit_qso_dialog(QtWidgets.QDialog):

    theitem = ""
    database = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("dialog.ui"), self)
        self.deleteButton.clicked.connect(self.delete_contact)
        self.buttonBox.accepted.connect(self.save_changes)
        self.change = QSOEdit()

    def setup(self, linetopass, thedatabase):
        logging.info("edit_qso_dialog.setup: %s : %s", linetopass, linetopass.split())
        self.database = thedatabase
        (
            self.theitem,
            thecall,
            thename,
            thestate,
            thedate,
            thetime,
            theband,
        ) = linetopass.split()
        theexchange = f"{thename} {thestate}"
        self.editCallsign.setText(thecall)
        self.editExchange.setText(theexchange)
        self.editBand.setCurrentIndex(self.editBand.findText(theband))
        date_time = thedate + " " + thetime
        now = QtCore.QDateTime.fromString(date_time, "yyyy-MM-dd hh:mm:ss")
        self.editDateTime.setDateTime(now)

    def relpath(self, filename):
        try:
            base_path = sys._MEIPASS  # pylint: disable=no-member
        except:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def save_changes(self):
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"update contacts set callsign = '{self.editCallsign.text().upper()}', name = '{self.editExchange.text().upper().split()[0]}', sandpdx = '{self.editExchange.text().upper().split()[1]}', date_time = '{self.editDateTime.text()}', band = '{self.editBand.currentText()}'  where id={self.theitem}"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except sqlite3.Error as exception:
            logging.critical("edit_qso_dialog.save_changes: %s", exception)
        self.change.lineChanged.emit()

    def delete_contact(self):
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"delete from contacts where id={self.theitem}"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except sqlite3.Error as exception:
            logging.critical("edit_qso_dialog.delete_contact: %s", exception)
        self.change.lineChanged.emit()
        self.close()


class Settings(QtWidgets.QDialog):
    """
    Setup settings dialog. Reads and stores settings to an sqlite db.
    Call setup() with filename of db.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("settings.ui"), self)
        self.buttonBox.accepted.connect(self.save_changes)

    def setup(self):
        try:
            home = os.path.expanduser("~")
            with open(home + "/.k1usnsst.json", "rt") as f:
                self.settings_dict = loads(f.read())
                self.qrzname_field.setText(self.settings_dict["qrzusername"])
                self.qrzpass_field.setText(self.settings_dict["qrzpassword"])
                self.qrzurl_field.setText(self.settings_dict["qrzurl"])
                self.rigcontrolip_field.setText(self.settings_dict["rigcontrolip"])
                self.rigcontrolport_field.setText(self.settings_dict["rigcontrolport"])
                self.useqrz_checkBox.setChecked(bool(self.settings_dict["useqrz"]))
                if self.settings_dict["userigcontrol"] == 1:
                    self.radioButton_rigctld.setChecked(True)
                if self.settings_dict["userigcontrol"] == 2:
                    self.radioButton_flrig.setChecked(True)
                self.usehamdb_checkBox.setChecked(bool(self.settings_dict["usehamdb"]))
        except Error as exception:
            logging.critical("Settings.setup: %s", exception)

    def relpath(self, filename):
        try:
            base_path = sys._MEIPASS  # pylint: disable=no-member
        except:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def save_changes(self):
        try:
            self.settings_dict["userigcontrol"] = 0
            if self.radioButton_rigctld.isChecked():
                self.settings_dict["userigcontrol"] = 1
            if self.radioButton_flrig.isChecked():
                self.settings_dict["userigcontrol"] = 2
            self.settings_dict["qrzusername"] = self.qrzname_field.text()
            self.settings_dict["qrzpassword"] = self.qrzpass_field.text()
            self.settings_dict["qrzurl"] = self.qrzurl_field.text()
            self.settings_dict["rigcontrolip"] = self.rigcontrolip_field.text()
            self.settings_dict["rigcontrolport"] = self.rigcontrolport_field.text()
            self.settings_dict["useqrz"] = int(self.useqrz_checkBox.isChecked())
            self.settings_dict["usehamdb"] = int(self.usehamdb_checkBox.isChecked())
            logging.info(self.settings_dict)
            home = os.path.expanduser("~")
            with open(home + "/.k1usnsst.json", "wt") as f:
                f.write(dumps(self.settings_dict))
        except Error as exception:
            logging.critical("Settings.save_changes: %s", exception)


if __name__ == "__main__":
    if Path("./debug").exists():
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    font_dir = relpath("font")
    families = load_fonts_from_dir(os.fspath(font_dir))
    logging.info(families)
    window = MainWindow()
    window.show()
    window.create_db()
    window.readpreferences()
    window.readpastcontacts()
    window.read_cw_macros()
    window.logwindow()
    window.callsign_entry.setFocus()
    timer = QtCore.QTimer()
    timer.timeout.connect(window.update_time)
    timer.start(1000)
    sys.exit(app.exec())
