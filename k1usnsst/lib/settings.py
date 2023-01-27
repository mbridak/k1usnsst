"""
    Settings
"""

import logging
import os
import sys
from json import dumps, loads
from PyQt5 import QtWidgets, uic


class Settings(QtWidgets.QDialog):  # pylint: disable=c-extension-no-member
    """
    Setup settings dialog. Reads and stores settings to an sqlite db.
    Call setup() with filename of db.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(self.relpath("settings.ui"), self)
        self.buttonBox.accepted.connect(self.save_changes)
        self.settings_dict = None

    def setup(self):
        """
        Reads in existing settings.
        """
        try:
            home = os.path.expanduser("~")
            with open(
                home + "/.k1usnsst.json", "rt", encoding="utf-8"
            ) as file_descriptor:
                self.settings_dict = loads(file_descriptor.read())

                self.usehamdb_checkBox.setChecked(bool(self.settings_dict["usehamdb"]))
                self.useqrz_checkBox.setChecked(bool(self.settings_dict["useqrz"]))
                self.qrzname_field.setText(self.settings_dict["qrzusername"])
                self.qrzpass_field.setText(self.settings_dict["qrzpassword"])
                self.qrzurl_field.setText(self.settings_dict["qrzurl"])

                self.rigcontrolip_field.setText(self.settings_dict["rigcontrolip"])
                self.rigcontrolport_field.setText(self.settings_dict["rigcontrolport"])
                if self.settings_dict["userigcontrol"] == 1:
                    self.radioButton_rigctld.setChecked(True)
                if self.settings_dict["userigcontrol"] == 2:
                    self.radioButton_flrig.setChecked(True)

                self.cwip_field.setText(self.settings_dict["cwip"])
                self.cwport_field.setText(str(self.settings_dict["cwport"]))
                self.usecwdaemon_radioButton.setChecked(
                    bool(self.settings_dict["cwtype"] == 1)
                )
                self.usepywinkeyer_radioButton.setChecked(
                    bool(self.settings_dict["cwtype"] == 2)
                )
        except IOError as exception:
            logging.critical("%s", exception)

    @staticmethod
    def relpath(filename: str) -> str:
        """
        If the program is packaged with pyinstaller,
        this is needed since all files will be in a temp folder during execution.
        """
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_path = getattr(sys, "_MEIPASS")
        else:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, filename)

    def save_changes(self) -> None:
        """
        Saves settings to the settings file.
        """

        self.settings_dict["userigcontrol"] = 0
        if self.radioButton_rigctld.isChecked():
            self.settings_dict["userigcontrol"] = 1
        if self.radioButton_flrig.isChecked():
            self.settings_dict["userigcontrol"] = 2
        self.settings_dict["rigcontrolip"] = self.rigcontrolip_field.text()
        self.settings_dict["rigcontrolport"] = self.rigcontrolport_field.text()

        self.settings_dict["usehamdb"] = int(self.usehamdb_checkBox.isChecked())
        self.settings_dict["useqrz"] = int(self.useqrz_checkBox.isChecked())
        self.settings_dict["qrzusername"] = self.qrzname_field.text()
        self.settings_dict["qrzpassword"] = self.qrzpass_field.text()
        self.settings_dict["qrzurl"] = self.qrzurl_field.text()

        self.settings_dict["cwip"] = self.cwip_field.text()
        self.settings_dict["cwport"] = int(self.cwport_field.text())
        self.settings_dict["cwtype"] = 0
        if self.usecwdaemon_radioButton.isChecked():
            self.settings_dict["cwtype"] = 1
        if self.usepywinkeyer_radioButton.isChecked():
            self.settings_dict["cwtype"] = 2

        logging.info(self.settings_dict)
        try:
            home = os.path.expanduser("~")
            with open(
                home + "/.k1usnsst.json", "wt", encoding="utf-8"
            ) as file_descriptor:
                file_descriptor.write(dumps(self.settings_dict))
        except IOError as exception:
            logging.critical("%s", exception)
