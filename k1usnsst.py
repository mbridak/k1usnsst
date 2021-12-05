#!/usr/bin/env python3

import logging
logging.basicConfig(level=logging.INFO)

import requests
import sys
import sqlite3
import socket
import os

from json import dumps
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QDir
from PyQt5.QtGui import QFontDatabase
from datetime import datetime
from sqlite3 import Error
from pathlib import Path

def relpath(filename):
		try:
			base_path = sys._MEIPASS # pylint: disable=no-member
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
	mycall = ""
	myexchange =""
	userigctl = True
	useqrz = False
	oldfreq = None
	band = None

	def __init__(self, *args, **kwargs):
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
		self.radio_icon.setPixmap(QtGui.QPixmap(self.relpath('icon/radio_grey.png')))
		self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
		self.genLogButton.clicked.connect(self.generateLogs)
		self.band_selector.activated.connect(self.changeband)
		self.settings_gear.clicked.connect(self.settingspressed)
		self.radiochecktimer = QtCore.QTimer()
		self.radiochecktimer.timeout.connect(self.Radio)
		self.radiochecktimer.start(1000)
		self.changeband()

	def settingspressed(self):
		settingsdialog = Settings()
		settingsdialog.setup(self.database)
		settingsdialog.exec()
		self.readpreferences()

	def relpath(self, filename):
		"""
		If the program is packaged with pyinstaller, this is needed since all files will be in a temp folder during execution.
		"""
		try:
			base_path = sys._MEIPASS # pylint: disable=no-member
		except:
			base_path = os.path.abspath(".")
		return os.path.join(base_path, filename)

	def has_internet(self):
		"""
		Connect to a main DNS server to check connectivity.
		Returns True/False
		"""
		try:
			socket.create_connection(("1.1.1.1", 53))
			return True
		except OSError:
			pass
		return False

	def getband(self, freq):
		"""
		Convert a (float) frequency into a (string) band.
		Returns a (string) band.
		Returns a "0" if frequency is out of band.
		"""
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

	def setband(self, theband):
		self.band_selector.setCurrentIndex(self.band_selector.findText(theband))
		self.changeband()

	def pollRadio(self):
		"""
		Poll rigctld to get band.
		"""
		if self.rigonline:
			#try:
				self.rigctrlsocket.settimeout(0.5)
				self.rigctrlsocket.send(b'f')
				newfreq = self.rigctrlsocket.recv(1024).decode().strip()
				self.radio_icon.setPixmap(QtGui.QPixmap(self.relpath('icon/radio_green.png')))
				self.rigctrlsocket.shutdown(socket.SHUT_RDWR)
				self.rigctrlsocket.close()
				if newfreq != self.oldfreq:
					self.oldfreq = newfreq
					self.setband(str(self.getband(newfreq)))
			#except:
				#self.rigonline = False
				#logging.warning("pollRadio: Rig Offline.")

	def checkRadio(self):
		"""
		Checks to see if rigctld daemon is running.
		"""
		if self.userigctl:
			self.rigctrlsocket=socket.socket()
			self.rigctrlsocket.settimeout(0.1)
			self.rigonline = True
			try:
				logging.debug(f"checkRadio: {self.rigctrlhost} {self.rigctrlport}")
				self.rigctrlsocket.connect((self.rigctrlhost, int(self.rigctrlport)))
				self.radio_icon.setPixmap(QtGui.QPixmap(self.relpath('icon/radio_red.png')))
			except:
				self.rigonline = False
				logging.debug("checkRadio: Rig Offline.")
				self.radio_icon.setPixmap(QtGui.QPixmap(self.relpath('icon/radio_grey.png')))
		else:
			self.rigonline = False

	def Radio(self):
		"""
		Check for connection to rigctld. if it's there, poll it for radio status.
		"""
		self.checkRadio()
		self.pollRadio()

	def keyPressEvent(self, event):
		if(event.key() == 16777216): #ESC
			self.clearinputs()

	def clearinputs(self):
		self.dupe_indicator.setText("")
		self.callsign_entry.clear()
		self.exchange_entry.clear()
		self.callsign_entry.setFocus()

	def updateTime(self):
		"""
		Update local and UTC time on screen.
		"""
		utcnow = datetime.utcnow().isoformat(' ')[5:19].replace('-', '/')
		self.utctime.setText(utcnow)

	def flash(self):
		"""
		Flash the screen to give visual indication of a dupe.
		"""
		self.setStyleSheet("background-color: rgb(245, 121, 0);\ncolor: rgb(211, 215, 207);")
		app.processEvents()
		self.setStyleSheet("background-color: rgb(42, 42, 42);\ncolor: rgb(211, 215, 207);")
		app.processEvents()

	def changemycall(self):
		text = self.mycallEntry.text()
		if(len(text)):
			if text[-1] == " ":
				self.mycallEntry.setText(text.strip())
			else:
				cleaned = ''.join(ch for ch in text if ch.isalnum() or ch=='/').upper()
				self.mycallEntry.setText(cleaned)
		self.mycall = self.mycallEntry.text()
		if self.mycall !="":
			self.mycallEntry.setStyleSheet("border: 1px solid green;")
		else:
			self.mycallEntry.setStyleSheet("border: 1px solid red;")
		self.writepreferences()

	def changemyexchange(self): 
		text = self.myexchangeEntry.text()
		if(len(text)):
				cleaned = ''.join(ch for ch in text if ch.isalpha() or ch==" ").upper()
				self.myexchangeEntry.setText(cleaned)
		self.myexchange = self.myexchangeEntry.text()
		if self.myexchange !="":
			self.myexchangeEntry.setStyleSheet("border: 1px solid green;")
		else:
			self.myexchangeEntry.setStyleSheet("border: 1px solid red;")
		self.writepreferences()

	def calltest(self):
		"""
		Cleans callsign of spaces and strips non alphanumeric or '/' characters.
		"""
		text = self.callsign_entry.text()
		if(len(text)):
			if text[-1] == " ":
				self.callsign_entry.setText(text.strip())
				self.exchange_entry.setFocus()
			else:
				cleaned = ''.join(ch for ch in text if ch.isalnum() or ch=='/').upper()
				self.callsign_entry.setText(cleaned)

	def exchangetest(self):
		"""
		Cleans exchange, strips non alpha or space characters.
		"""
		text = self.exchange_entry.text()
		if(len(text)):
			cleaned = ''.join(ch for ch in text if ch.isalpha() or ch ==' ').upper()
			self.exchange_entry.setText(cleaned)

	def dupCheck(self):
		acall = self.callsign_entry.text()
		try:
			with sqlite3.connect(self.database) as conn:
				c = conn.cursor()
				c.execute(f"select callsign, name, sandpdx, band from contacts where callsign like '{acall}' order by band")
				log = c.fetchall()
		except Error as e:
			logging.critical(f"dupCheck: {e}")
			return
		for x in log:
			hiscall, hisname, sandpdx, hisband = x
			if len(self.exchange_entry.text()) == 0: self.exchange_entry.setText(f"{hisname} {sandpdx}")
			dupetext=""
			if hisband == self.band:
				self.flash()
				dupetext = " DUP!!!"
			self.dupe_indicator.setText(dupetext)

	def create_DB(self):
		""" create a database and table if it does not exist """
		try:
			with sqlite3.connect(self.database) as conn:
				c = conn.cursor()
				sql_table = """ CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, callsign text NOT NULL, name text NOT NULL, sandpdx text NOT NULL, date_time text NOT NULL, band text NOT NULL, grid text NOT NULL, opname text NOT NULL); """
				c.execute(sql_table)
				sql_table = """ CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY, mycallsign TEXT DEFAULT '', myexchange TEXT DEFAULT '', qrzusername TEXT DEFAULT 'w1aw', qrzpassword TEXT default 'secret', qrzurl TEXT DEFAULT 'https://xmldata.qrz.com/xml/', useqrz INTEGER DEFAULT 0, userigcontrol INTEGER DEFAULT 1, rigcontrolip TEXT DEFAULT '127.0.0.1', rigcontrolport TEXT DEFAULT '4532', usehamdb INTEGER DEFAULT 0); """
				c.execute(sql_table)
				conn.commit()
		except Error as e:
			logging.critical(f"create_DB: {e}")

	def readpreferences(self):
		try:
			with sqlite3.connect(self.database) as conn:
				c = conn.cursor()
				c.execute("select * from preferences where id = 1")
				pref = c.fetchall()
				if len(pref) > 0:
					for x in pref:
						_, self.mycall, self.myexchange, self.qrzname, self.qrzpass, self.qrzurl, self.useqrz, self.userigctl ,self.rigctrlhost, self.rigctrlport, self.usehamdb = x
						logging.debug(f"readpreferences: {x}")
						self.mycallEntry.setText(self.mycall)
						self.myexchangeEntry.setText(self.myexchange)
				else:
					sql = f"INSERT INTO preferences(id, mycallsign, myexchange) VALUES(1,'{self.mycall}','{self.myexchange}')"
					logging.debug(sql)
					c.execute(sql)
					conn.commit()
		except Error as e:
			logging.critical(f"readpreferences: {e}")
		self.qrzauth()

	def writepreferences(self):
		try:
			with sqlite3.connect(self.database) as conn:
				sql = f"UPDATE preferences SET mycallsign = '{self.mycall}', myexchange = '{self.myexchange}' WHERE id = 1"
				logging.debug(f"writepreferences: {sql}")
				cur = conn.cursor()
				cur.execute(sql)
				conn.commit()
		except Error as e:
			logging.critical(f"writepreferences: {e}")

	def log_contact(self):
		if(len(self.callsign_entry.text()) == 0 or len(self.exchange_entry.text()) == 0): return
		grid, opname = self.qrzlookup(self.callsign_entry.text())
		contact = (self.callsign_entry.text(), self.exchange_entry.text().split()[0], self.exchange_entry.text().split()[1], self.band, grid, opname)
		try:
			with sqlite3.connect(self.database) as conn:
				sql = "INSERT INTO contacts(callsign, name, sandpdx, date_time, band, grid, opname) VALUES(?,?,?,datetime('now'),?,?,?)"
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
			logid, hiscall, hisname, sandpdx, datetime, band, _, _ = x
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
		if self.useqrz and self.has_internet():
			try:
				payload = {'username':self.qrzname, 'password':self.qrzpass}
				r=requests.get(self.qrzurl,params=payload, timeout=1.0)
				if r.status_code == 200 and r.text.find('<Key>') > 0:
					self.qrzsession=r.text[r.text.find('<Key>')+5:r.text.find('</Key>')]
					self.QRZ_icon.setStyleSheet("color: rgb(128, 128, 0);")
					logging.info("QRZ: Obtained session key.")
				else:
					self.qrzsession = False
					self.QRZ_icon.setStyleSheet("color: rgb(136, 138, 133);")
				if r.status_code == 200 and r.text.find('<Error>') > 0:
					errorText = r.text[r.text.find('<Error>')+7:r.text.find('</Error>')]
					self.infobox.insertPlainText("\nQRZ Error: "+ errorText + "\n")
					logging.warning(f"QRZ Error: {errorText}")
			except requests.exceptions.RequestException as e:
				self.infobox.insertPlainText(f"****QRZ Error****\n{e}\n")
				logging.warning(f"QRZ Error: {e}")
		else:
			self.QRZ_icon.setStyleSheet("color: rgb(26, 26, 26);")
			self.qrzsession = False

	def qrzlookup(self, call):
		grid = False
		name = False
		internet_good = self.has_internet()
		try:
			if self.qrzsession and self.useqrz and internet_good:
				payload = {'s':self.qrzsession, 'callsign':call}
				r=requests.get(self.qrzurl,params=payload, timeout=3.0)
				if not r.text.find('<Key>'): #key expired get a new one
					self.qrzauth()
					if self.qrzsession:
						payload = {'s':self.qrzsession, 'callsign':call}
						r=requests.get(self.qrzurl,params=payload, timeout=3.0)
				grid, name = self.parseLookup(r)
			elif internet_good and self.usehamdb:
				r=requests.get(f"http://api.hamdb.org/v1/{call}/xml/k1usnsstlogger",timeout=5.0)
				grid, name = self.parseLookup(r)
		except:
			logging.warn("Lookup Failed")
		if grid == "NOT_FOUND": grid = False
		if name == "NOT_FOUND": name = False
		return grid, name

	def parseLookup(self,r):
		grid=False
		name=False
		try:
			if r.status_code == 200:
				if r.text.find('<Error>') > 0:
					errorText = r.text[r.text.find('<Error>')+7:r.text.find('</Error>')]
					self.infobox.insertPlainText(f"\nQRZ/HamDB Error: {errorText}\n")
				if r.text.find('<grid>') > 0:
					grid = r.text[r.text.find('<grid>')+6:r.text.find('</grid>')]
				if r.text.find('<fname>') > 0:
					name = r.text[r.text.find('<fname>')+7:r.text.find('</fname>')]
				if r.text.find('<name>') > 0:
					if not name:
						name = r.text[r.text.find('<name>')+6:r.text.find('</name>')]
					else:
						name += " " + r.text[r.text.find('<name>')+6:r.text.find('</name>')]
		except:
			self.infobox.insertPlainText(f"Lookup Failed...\n")
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
			return
		grid = False
		opname = False
		with open(logname, "w", encoding='ascii') as f:
			print("<ADIF_VER:5>2.2.0", end='\r\n', file=f)
			print("<EOH>", end='\r\n', file=f)
			mode = "CW"
			for x in log:
				_, hiscall, hisname, sandpdx, datetime, band, grid, opname = x
				loggeddate = datetime[:10]
				loggedtime = datetime[11:13] + datetime[14:16]
				print(f"<QSO_DATE:{len(''.join(loggeddate.split('-')))}:d>{''.join(loggeddate.split('-'))}", end='\r\n', file=f)
				print(f"<TIME_ON:{len(loggedtime)}>{loggedtime}", end='\r\n', file=f)
				print(f"<CALL:{len(hiscall)}>{hiscall}", end='\r\n', file=f)
				print(f"<MODE:{len(mode)}>{mode}", end='\r\n', file=f)
				print(f"<BAND:{len(band + 'M')}>{band + 'M'}", end='\r\n', file=f)
				try:
					print(f"<FREQ:{len(self.dfreq[band])}>{self.dfreq[band]}", end='\r\n', file=f)
				except:
					pass # This is bad form... I can't remember why this is in a try block
				print("<RST_SENT:3>599", end='\r\n', file=f)
				print("<RST_RCVD:3>599", end='\r\n', file=f)
				print(f"<STX_STRING:{len(self.myexchangeEntry.text())}>{self.myexchangeEntry.text()}", end='\r\n', file=f)
				hisexchange = f"{hisname} {sandpdx}"
				print(f"<SRX_STRING:{len(hisexchange)}>{hisexchange}", end='\r\n', file=f)
				state = sandpdx
				if state: print(f"<STATE:{len(state)}>{state}", end='\r\n', file=f)
				if len(grid) > 1: print(f"<GRIDSQUARE:{len(grid)}>{grid}", end='\r\n', file=f)
				if len(opname) > 1: print(f"<NAME:{len(opname)}>{opname}", end='\r\n', file=f)
				comment = "K1USN SST"
				print(f"<COMMENT:{len(comment)}>{comment}", end='\r\n', file=f)
				contest = "K1USN-SST"
				print(f"<CONTEST_ID:{len(contest)}>{contest}", end='\r\n', file=f)
				print("<EOR>", end='\r\n', file=f)

	def calcscore(self):
		"""
		determine the amount od QSO's, S/P per band, DX per band.
		"""
		total_qso = 0
		total_mults = 0
		total_score = 0

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
					logging.debug(f"score: band:{band} q:{qso} s&p:{sandp} dx:{dx}")
			except Error as e:
				logging.critical(f"calcscore: {e}")
			total_qso += qso[0]
			total_mults += (sandp[0]+dx[0])
			total_score = total_qso * total_mults
			self.Total_CW.setText(str(total_qso))
			self.Total_Mults.setText(str(total_mults))
			self.Total_Score.setText(str(total_score))

	def getbands(self):
		"""
		Returns a list of bands worked, and an empty list if none worked.
		"""
		bandlist=[]
		try:
			with sqlite3.connect(self.database) as conn:
				c = conn.cursor()
				c.execute("select DISTINCT band from contacts")
				x=c.fetchall()
		except Error as e:
			logging.critical(f"getbands: {e}")
			return []
		if x:
			for count in x:
				bandlist.append(count[0])
			return bandlist
		return []
		
	def generateLogs(self):
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
		self.theitem, thecall, thename, thestate, thedate, thetime, theband = linetopass.split()
		theexchange = f"{thename} {thestate}"
		self.editCallsign.setText(thecall)
		self.editExchange.setText(theexchange)
		self.editBand.setCurrentIndex(self.editBand.findText(theband))
		date_time = thedate+" "+thetime
		now = QtCore.QDateTime.fromString(date_time, 'yyyy-MM-dd hh:mm:ss')
		self.editDateTime.setDateTime(now)

	def relpath(self, filename):
		try:
			base_path = sys._MEIPASS # pylint: disable=no-member
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
 
	def setup(self, thedatabase):
		self.database = thedatabase
		try:
			with sqlite3.connect(self.database) as conn:
				c = conn.cursor()	
				c.execute("select * from preferences where id = 1")
				pref = c.fetchall()
			if len(pref) > 0:
				for x in pref:
					_, _, _, qrzname, qrzpass, qrzurl,  useqrz, userigcontrol, rigctrlhost, rigctrlport, usehamdb = x
					self.qrzname_field.setText(qrzname)
					self.qrzpass_field.setText(qrzpass)
					self.qrzurl_field.setText(qrzurl)
					self.rigcontrolip_field.setText(rigctrlhost)
					self.rigcontrolport_field.setText(rigctrlport)
					self.useqrz_checkBox.setChecked(bool(useqrz))
					self.userigcontrol_checkBox.setChecked(bool(userigcontrol))
					self.usehamdb_checkBox.setChecked(bool(usehamdb))
		except Error as e:
			logging.critical(f"Settings.setup: {e}")

	def relpath(self, filename):
		try:
			base_path = sys._MEIPASS # pylint: disable=no-member
		except:
			base_path = os.path.abspath(".")
		return os.path.join(base_path, filename)

	def saveChanges(self):
		try:
			with sqlite3.connect(self.database) as conn:
				sql = f"UPDATE preferences SET qrzusername = '{self.qrzname_field.text()}', qrzpassword = '{self.qrzpass_field.text()}', qrzurl = '{self.qrzurl_field.text()}', rigcontrolip = '{self.rigcontrolip_field.text()}', rigcontrolport = '{self.rigcontrolport_field.text()}', useqrz = '{int(self.useqrz_checkBox.isChecked())}',  userigcontrol = '{int(self.userigcontrol_checkBox.isChecked())}', usehamdb = '{int(self.usehamdb_checkBox.isChecked())}'  where id=1;"
				cur = conn.cursor()
				cur.execute(sql)
				conn.commit()
		except Error as e:
			logging.critical(f"Settings.saveChanges: {e}")

app = QtWidgets.QApplication(sys.argv)
app.setStyle('Fusion')
font_dir = relpath("font")
families = load_fonts_from_dir(os.fspath(font_dir))
logging.info(families)
window = MainWindow()
window.show()
window.create_DB()
window.readpreferences()
window.qrzauth()
window.logwindow()
window.callsign_entry.setFocus()
timer = QtCore.QTimer()
timer.timeout.connect(window.updateTime)
timer.start(1000)
app.exec()