#!/usr/bin/env python3

import logging

logging.basicConfig(level=logging.DEBUG)

import xmlrpc.client
import requests
import sys
import sqlite3
import socket
import os

from json import dumps, loads
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QFontDatabase
from datetime import datetime
from sqlite3 import Error
from pathlib import Path
from shutil import copyfile
from xmlrpc.client import ServerProxy, Error


def relpath(filename):
    try:
        base_path = sys._MEIPASS  # pylint: disable=no-member
    except:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)


def load_fonts_from_dir(directory):
    families = set()
    for fi in QDir(directory).entryInfoList(["*.ttf", "*.woff", "*.woff2"]):
        _id = QFontDatabase.addApplicationFont(fi.absoluteFilePath())
        families |= set(QFontDatabase.applicationFontFamilies(_id))
    return families


class qsoEdit(QtCore.QObject):
    """
    Custom qt event signal used when qso edited or deleted.
    """

    lineChanged = QtCore.pyqtSignal()


class MainWindow(QtWidgets.QMainWindow):

    database = "SST.db"
    server = False
    mycall = ""
    myexchange = ""
    userigctl = True
    flrig = False
    rigonline = False
    useqrz = False
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
        "qrzurl": "https://xmldata.qrz.com/xml/",
        "useqrz": 0,
        "userigcontrol": 0,
        "rigcontrolip": "localhost",
        "rigcontrolport": "12345",
        "usehamdb": 0,
    }
    fkeys = dict()
    keyerserver = "http://localhost:8000"

    def __init__(self, *args, **kwargs):
        logging.debug(f"MainWindow: __init__")
        super().__init__(*args, **kwargs)
        uic.loadUi(self.relpath("main.ui"), self)
        self.listWidget.itemDoubleClicked.connect(self.qsoclicked)
        self.mycallEntry.textEdited.connect(self.changemycall)
        self.myexchangeEntry.textEdited.connect(self.changemyexchange)
        self.callsign_entry.textEdited.connect(self.calltest)
        self.callsign_entry.returnPressed.connect(self.log_contact)
        self.callsign_entry.editingFinished.connect(self.dupCheck)
        self.exchange_entry.textEdited.connect(self.exchangetest)
        self.exchange_entry.returnPressed.connect(self.log_contact)
        self.radio_icon.setPixmap(QtGui.QPixmap(self.relpath("icon/radio_grey.png")))
        self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
        self.genLogButton.clicked.connect(self.generateLogs)
        self.band_selector.activated.connect(self.changeband)
        self.settings_gear.clicked.connect(self.settingspressed)
        self.radiochecktimer = QtCore.QTimer()
        self.radiochecktimer.timeout.connect(self.Radio)
        self.radiochecktimer.start(1000)
        self.changeband()
        self.readpreferences()
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
        logging.debug(f"MainWindow: settingspressed")
        settingsdialog = Settings()
        settingsdialog.setup()
        settingsdialog.exec()
        self.readpreferences()

    def relpath(self, filename):
        """
        If the program is packaged with pyinstaller, this is needed since all files will be in a temp folder during execution.
        """
        try:
            base_path = sys._MEIPASS  # pylint: disable=no-member
        except:
            base_path = os.path.abspath(".")
        logging.debug(f"MainWindow: relpath: {base_path}{filename}")
        return os.path.join(base_path, filename)

    def readCWmacros(self):
        """
        Reads in the CW macros, firsts it checks to see if the file exists. If it does not,
        and this has been packaged with pyinstaller it will copy the default file from the
        temp directory this is running from... In theory.
        """

        if (
            getattr(sys, "frozen", False)
            and hasattr(sys, "_MEIPASS")
            and not Path("./cwmacros.txt").exists()
        ):
            logging.debug("readCWmacros: copying default macro file.")
            copyfile(relpath("cwmacros.txt"), "./cwmacros.txt")
        with open("./cwmacros.txt", "r") as f:
            for line in f:
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

    def has_internet(self):
        """
        Connect to a main DNS server to check connectivity.
        Returns True/False
        """
        try:
            socket.create_connection(("1.1.1.1", 53))
            logging.debug(f"MainWindow: has_internet - True")
            return True
        except OSError as e:
            logging.debug(f"MainWindow: has_internet: {e}")
        return False

    def getband(self, freq):
        """
        Convert a (float) frequency into a (string) band.
        Returns a (string) band.
        Returns a "0" if frequency is out of band.
        """
        logging.debug(f"MainWindow: getband: {freq}")
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

    def setband(self, theband):
        self.band_selector.setCurrentIndex(self.band_selector.findText(theband))
        self.changeband()

    def pollRadio(self):
        """
        Poll rigctld to get band.
        """
        if self.flrig:
            try:
                newfreq = self.server.rig.get_vfo()
                self.radio_icon.setPixmap(
                    QtGui.QPixmap(self.relpath("icon/radio_green.png"))
                )
                if newfreq != self.oldfreq:
                    self.oldfreq = newfreq
                    self.setband(str(self.getband(newfreq)))
            except socket.error as e:
                self.radio_icon.setPixmap(
                    QtGui.QPixmap(self.relpath("icon/radio_red.png"))
                )
                logging.warning(f"pollRadio: flrig: {e}")
            return
        if self.rigonline:
            # try:
            self.rigctrlsocket.settimeout(0.5)
            self.rigctrlsocket.send(b"f")
            newfreq = self.rigctrlsocket.recv(1024).decode().strip()
            self.radio_icon.setPixmap(
                QtGui.QPixmap(self.relpath("icon/radio_green.png"))
            )
            self.rigctrlsocket.shutdown(socket.SHUT_RDWR)
            self.rigctrlsocket.close()
            if newfreq != self.oldfreq:
                self.oldfreq = newfreq
                self.setband(str(self.getband(newfreq)))
        # except:
        # self.rigonline = False
        # logging.warning("pollRadio: Rig Offline.")

    def checkRadio(self):
        """
        Checks to see if rigctld daemon is running.
        """
        if not (self.flrig or self.userigctl):
            self.radio_icon.setPixmap(
                QtGui.QPixmap(self.relpath("icon/radio_grey.png"))
            )
        if self.userigctl:
            self.rigctrlsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.rigctrlsocket.settimeout(0.1)
            self.rigonline = True
            try:
                logging.debug(
                    f"checkRadio: {self.settings_dict['rigcontrolip']} {self.settings_dict['rigcontrolport']}"
                )
                self.rigctrlsocket.connect(
                    (
                        self.settings_dict["rigcontrolip"],
                        int(self.settings_dict["rigcontrolport"]),
                    )
                )
            except:
                self.rigonline = False
                logging.debug("checkRadio: Rig Offline.")
                self.radio_icon.setPixmap(
                    QtGui.QPixmap(self.relpath("icon/radio_red.png"))
                )
        else:
            self.rigonline = False

    def Radio(self):
        """
        Check for connection to rigctld. if it's there, poll it for radio status.
        """
        self.checkRadio()
        self.pollRadio()

    def processMacro(self, macro):
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
        if event.key() == Qt.Key_Escape:
            self.clearinputs()
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

    def sendcw(self, texttosend):
        with ServerProxy(self.keyerserver) as proxy:
            try:
                proxy.k1elsendstring(texttosend)
            except Error as e:
                logging.debug(f"{self.keyerserver}, xmlrpc error: {e}")
            except ConnectionRefusedError:
                logging.debug(f"{self.keyerserver}, xmlrpc Connection Refused")

    def sendf1(self):
        self.sendcw(self.processMacro(self.F1.toolTip()))

    def sendf2(self):
        self.sendcw(self.processMacro(self.F2.toolTip()))

    def sendf3(self):
        self.sendcw(self.processMacro(self.F3.toolTip()))

    def sendf4(self):
        self.sendcw(self.processMacro(self.F4.toolTip()))

    def sendf5(self):
        self.sendcw(self.processMacro(self.F5.toolTip()))

    def sendf6(self):
        self.sendcw(self.processMacro(self.F6.toolTip()))

    def sendf7(self):
        self.sendcw(self.processMacro(self.F7.toolTip()))

    def sendf8(self):
        self.sendcw(self.processMacro(self.F8.toolTip()))

    def sendf9(self):
        self.sendcw(self.processMacro(self.F9.toolTip()))

    def sendf10(self):
        self.sendcw(self.processMacro(self.F10.toolTip()))

    def sendf11(self):
        self.sendcw(self.processMacro(self.F11.toolTip()))

    def sendf12(self):
        self.sendcw(self.processMacro(self.F12.toolTip()))

    def clearinputs(self):
        self.dupe_indicator.setText("")
        self.callsign_entry.clear()
        self.exchange_entry.clear()
        self.callsign_entry.setFocus()

    def updateTime(self):
        """
        Update local and UTC time on screen.
        """
        utcnow = datetime.utcnow().isoformat(" ")[5:19].replace("-", "/")
        self.utctime.setText(utcnow)

    def flash(self):
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

    def changemycall(self):
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

    def changemyexchange(self):
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

    def calltest(self):
        """
        Cleans callsign of spaces and strips non alphanumeric or '/' characters.
        """
        text = self.callsign_entry.text()
        if len(text):
            if text[-1] == " ":
                self.callsign_entry.setText(text.strip())
                self.exchange_entry.setFocus()
            else:
                cleaned = "".join(
                    ch for ch in text if ch.isalnum() or ch == "/"
                ).upper()
                self.callsign_entry.setText(cleaned)

    def exchangetest(self):
        """
        Cleans exchange, strips non alpha or space characters.
        """
        text = self.exchange_entry.text()
        if len(text):
            cleaned = "".join(ch for ch in text if ch.isalpha() or ch == " ").upper()
            self.exchange_entry.setText(cleaned)

    def dupCheck(self):
        acall = self.callsign_entry.text()
        dupetext = ""
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute(
                    f"select callsign, name, sandpdx, band from contacts where callsign like '{acall}' order by band"
                )
                log = c.fetchall()
        except Error as e:
            logging.critical(f"dupCheck: {e}")
            return
        for x in log:
            hiscall, hisname, sandpdx, hisband = x
            if len(self.exchange_entry.text()) == 0:
                self.exchange_entry.setText(f"{hisname} {sandpdx}")
            if hisband == self.band:
                self.flash()
                dupetext = " DUP!!!"
                self.dupe_indicator.setText(dupetext)

    def create_DB(self):
        """create a database and table if it does not exist"""
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                sql_table = """ CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, callsign text NOT NULL, name text NOT NULL, sandpdx text NOT NULL, date_time text NOT NULL, frequency text NOT NULL, band text NOT NULL, grid text NOT NULL, opname text NOT NULL); """
                c.execute(sql_table)
        except Error as e:
            logging.critical(f"create_DB: {e}")

    def readpreferences(self):
        try:
            home = os.path.expanduser("~")
            if os.path.exists(home + "/.k1usnsst.json"):
                f = open(home + "/.k1usnsst.json", "rt")
                self.settings_dict = loads(f.read())
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
                f = open(home + "/.k1usnsst.json", "wt")
                f.write(dumps(self.settings_dict))
        except Error as e:
            logging.critical(f"readpreferences: {e}")
        self.qrzauth()

    def writepreferences(self):
        home = os.path.expanduser("~")
        with open(home + "/.k1usnsst.json", "wt") as f:
            f.write(dumps(self.settings_dict))

    def log_contact(self):
        if len(self.callsign_entry.text()) == 0 or len(self.exchange_entry.text()) == 0:
            return
        grid, opname = self.qrzlookup(self.callsign_entry.text())
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
                logging.debug(f"log_contact: {sql}\n{contact}")
                cur = conn.cursor()
                cur.execute(sql, contact)
                conn.commit()
        except Error as e:
            logging.critical(f"Log Contact: {e}")
        self.logwindow()
        self.clearinputs()

    def logwindow(self):
        self.listWidget.clear()
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select * from contacts order by date_time desc")
                log = c.fetchall()
        except Error as e:
            logging.critical(f"logwindow: {e}")
        for x in log:
            logid, hiscall, hisname, sandpdx, datetime, frequency, band, _, _ = x
            logline = f"{str(logid).rjust(3,'0')} {hiscall.ljust(11)} {hisname.ljust(12)} {sandpdx} {datetime} {str(band).rjust(3)}"
            self.listWidget.addItem(logline)
        self.calcscore()

    def qsoclicked(self):
        """
        Gets the line of the log clicked on, and passes that line to the edit dialog.
        """
        item = self.listWidget.currentItem()
        linetopass = item.text()
        dialog = editQSODialog(self)
        dialog.setup(linetopass, self.database)
        dialog.change.lineChanged.connect(self.qsoedited)
        dialog.open()

    def qsoedited(self):
        """
        Perform functions after QSO edited or deleted.
        """
        self.logwindow()

    def qrzauth(self):
        """
        Get QRZ session key.
        """
        logging.debug(f"qrzauth:")
        if self.settings_dict["useqrz"] and self.has_internet():
            try:
                payload = {
                    "username": self.settings_dict["qrzusername"],
                    "password": self.settings_dict["qrzpassword"],
                }
                r = requests.get(
                    self.settings_dict["qrzurl"], params=payload, timeout=1.0
                )
                if r.status_code == 200 and r.text.find("<Key>") > 0:
                    self.qrzsession = r.text[
                        r.text.find("<Key>") + 5 : r.text.find("</Key>")
                    ]
                    self.QRZ_icon.setStyleSheet("color: rgb(128, 128, 0);")
                    logging.info("QRZ: Obtained session key.")
                else:
                    self.qrzsession = False
                    self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
                if r.status_code == 200 and r.text.find("<Error>") > 0:
                    errorText = r.text[
                        r.text.find("<Error>") + 7 : r.text.find("</Error>")
                    ]
                    self.dupe_indicator.setText("QRZ Error: " + errorText)
                    logging.warning(f"QRZ Error: {errorText}")
            except requests.exceptions.RequestException as e:
                self.dupe_indicator.setText(f"QRZ:{e}")
                logging.warning(f"QRZ Error: {e}")
        else:
            self.QRZ_icon.setStyleSheet("color: rgb(26, 26, 26);")
            self.qrzsession = False

    def qrzlookup(self, call):
        logging.debug(f"qrzlookup: {call}")
        grid = False
        name = False
        internet_good = self.has_internet()
        try:
            if self.qrzsession and self.settings_dict["useqrz"] and internet_good:
                payload = {"s": self.qrzsession, "callsign": call}
                logging.debug(
                    f"qrzlookup: sending: {self.settings_dict['qrzurl']} params = {payload}"
                )
                r = requests.get(
                    self.settings_dict["qrzurl"], params=payload, timeout=3.0
                )
                if not r.text.find("<Key>"):  # key expired get a new one
                    logging.debug(f"qrzlookup: keyexpired.")
                    self.qrzauth()
                    if self.qrzsession:
                        logging.debug(f"qrzlookup: Resending")
                        payload = {"s": self.qrzsession, "callsign": call}
                        r = requests.get(
                            self.settings_dict["qrzurl"], params=payload, timeout=3.0
                        )
                grid, name = self.parseLookup(r)
                logging.debug(f"qrzlookup: {grid} {name}")
            elif internet_good and self.settings_dict["usehamdb"]:
                logging.debug(f"qrzlookup: using hamdb")
                r = requests.get(
                    f"http://api.hamdb.org/v1/{call}/xml/k1usnsstlogger", timeout=5.0
                )
                grid, name = self.parseLookup(r)
                logging.debug(f"qrzlookup: {grid} {name}")
        except:
            logging.warn("Lookup Failed")
        if grid == "NOT_FOUND":
            grid = False
        if name == "NOT_FOUND":
            name = False
        return grid, name

    def parseLookup(self, r):
        grid = False
        name = False
        try:
            if r.status_code == 200:
                if r.text.find("<Error>") > 0:
                    errorText = r.text[
                        r.text.find("<Error>") + 7 : r.text.find("</Error>")
                    ]
                    logging.warn(f"parselookup: QRZ/HamDB Error: {errorText}")
                    self.dupe_indicator.setText(f"\nQRZ/HamDB Error: {errorText}\n")
                if r.text.find("<grid>") > 0:
                    grid = r.text[r.text.find("<grid>") + 6 : r.text.find("</grid>")]
                if r.text.find("<fname>") > 0:
                    name = r.text[r.text.find("<fname>") + 7 : r.text.find("</fname>")]
                if r.text.find("<name>") > 0:
                    if not name:
                        name = r.text[
                            r.text.find("<name>") + 6 : r.text.find("</name>")
                        ]
                    else:
                        name += (
                            " "
                            + r.text[r.text.find("<name>") + 6 : r.text.find("</name>")]
                        )
        except:
            self.dupe_indicator.setText(f"Lookup Failed...\n")
        return grid, name

    def adif(self):
        logname = "SST.adi"
        logging.info(f"Saving ADIF to: {logname}\n")
        try:
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("select * from contacts order by date_time ASC")
                log = c.fetchall()
        except Error as e:
            logging.critical(f"adif: {e}")
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
        logging.debug("calcscore()")
        total_qso = 0
        total_mults = 0
        total_score = 0
        with open("SST_Statistics.txt", "w", encoding="ascii") as f:
            print(f"", file=f)
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
                    logging.debug(f"score: band:{band} q:{qso} s&p:{sandp} dx:{dx}")
            except Error as e:
                logging.critical(f"calcscore: {e}")
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
        except Error as e:
            logging.critical(f"getbands: {e}")
            return []
        if x:
            for count in x:
                bandlist.append(count[0])
            return bandlist
        return []

    def generateLogs(self):
        self.calcscore()
        self.adif()


class editQSODialog(QtWidgets.QDialog):

    theitem = ""
    database = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("dialog.ui"), self)
        self.deleteButton.clicked.connect(self.delete_contact)
        self.buttonBox.accepted.connect(self.saveChanges)
        self.change = qsoEdit()

    def setup(self, linetopass, thedatabase):
        logging.debug(f"editQSODialog.setup: {linetopass} : {linetopass.split()}")
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

    def saveChanges(self):
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"update contacts set callsign = '{self.editCallsign.text().upper()}', name = '{self.editExchange.text().upper().split()[0]}', sandpdx = '{self.editExchange.text().upper().split()[1]}', date_time = '{self.editDateTime.text()}', band = '{self.editBand.currentText()}'  where id={self.theitem}"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except Error as e:
            logging.critical(f"editQSODialog.saveChanges: {e}")
        self.change.lineChanged.emit()

    def delete_contact(self):
        try:
            with sqlite3.connect(self.database) as conn:
                sql = f"delete from contacts where id={self.theitem}"
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
        except Error as e:
            logging.critical(f"editQSODialog.delete_contact: {e}")
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
        self.buttonBox.accepted.connect(self.saveChanges)

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
        except Error as e:
            logging.critical(f"Settings.setup: {e}")

    def relpath(self, filename):
        try:
            base_path = sys._MEIPASS  # pylint: disable=no-member
        except:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def saveChanges(self):
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
        except Error as e:
            logging.critical(f"Settings.saveChanges: {e}")


app = QtWidgets.QApplication(sys.argv)
app.setStyle("Fusion")
font_dir = relpath("font")
families = load_fonts_from_dir(os.fspath(font_dir))
logging.info(families)
window = MainWindow()
window.show()
window.create_DB()
window.readpreferences()
window.readCWmacros()
window.qrzauth()
window.logwindow()
window.callsign_entry.setFocus()
timer = QtCore.QTimer()
timer.timeout.connect(window.updateTime)
timer.start(1000)
sys.exit(app.exec())
