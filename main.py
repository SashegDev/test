import minecraft_launcher_lib
import subprocess
import os
import shutil
from datetime import datetime
import sys
import logging
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QThread, pyqtSignal
import requests
import json

with open("log.log","w+") as log:
    log.flush()

logging.basicConfig(
    level=logging.NOTSET,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='log.log',
    filemode='a'
)

class RequestThread(QThread):
    finished = pyqtSignal(int, str)
    error = pyqtSignal(str)

    def __init__(self, nickname, password):
        super(RequestThread, self).__init__()
        self.nickname = nickname
        self.password = password

    def run(self):
        try:
            url = 'http://yourserver.com/login'
            data = {'nickname': self.nickname, 'password': self.password}
            response = requests.post(url, data=data)
            self.finished.emit(response.status_code, response.text)
            logging.info(f"Login attempt with nickname: {self.nickname}, status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.error.emit(str(e))
            logging.error(f"Login error with nickname: {self.nickname}, error: {str(e)}")

def fetch_user_status(nickname):
    url = 'https://raw.githubusercontent.com/SashegDev/test/main/database.json'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = json.loads(response.text)
        for user in data:
            if user['nickname'] == nickname:
                return user['status'], user['role']
        return None, None
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch user status: {str(e)}")
        return None, None

class Ui(QtWidgets.QMainWindow):
    def __init__(self, debug_mode):
        super(Ui, self).__init__()
        self.debug_mode = debug_mode

        self.login_ui_path = 'login.ui'
        self.launcher_ui_path = 'launcher.ui'
        
        uic.loadUi(self.login_ui_path, self)
        
        self.nickname_input = self.findChild(QtWidgets.QLineEdit, 'lineEdit')
        self.password_input = self.findChild(QtWidgets.QLineEdit, 'lineEdit_2')
        self.login_button = self.findChild(QtWidgets.QPushButton, 'pushButton')
        
        self.login_button.clicked.connect(self.on_login_clicked)
        
        self.show()

    def on_login_clicked(self):
        self.login_button.setEnabled(False)
        self.nickname_input.setEnabled(False)
        self.password_input.setEnabled(False)
        nickname = self.nickname_input.text()
        password = self.password_input.text()
        logging.info(f"Login button clicked with nickname: {nickname}")
        
        if self.debug_mode:
            logging.info("Debug mode enabled, skipping login request")
            self.handle_response(200, "Debug mode")
        else:
            self.request_thread = RequestThread(nickname, password)
            self.request_thread.finished.connect(self.handle_response)
            self.request_thread.error.connect(self.show_error_message)
            self.request_thread.start()



    def on_play_clicked(self):
        logging.info("Play button clicked")

        ram_slider = self.launcher_ui.findChild(QtWidgets.QSlider, 'slider_ram')
        width_input = self.launcher_ui.findChild(QtWidgets.QLineEdit, 'lineEdit_width')
        height_input = self.launcher_ui.findChild(QtWidgets.QLineEdit, 'lineEdit_height')
        username_label = self.launcher_ui.findChild(QtWidgets.QLabel, 'nickname')

        if not all([ram_slider, width_input, height_input, username_label]):
            logging.error("One or more UI elements not found")
            return

        username = username_label.text()
        width = width_input.text()
        height = height_input.text()
        ram = ram_slider.value()

        mc_options = {
            'username': username,
            'uuid': '',
            'token': '',
            "customResolution": True,
            "resolutionWidth": width,
            "resolutionHeight": height,
            "jvmArguments": [f"-Xms{ram}M", f"-Xmx{ram}M"],
        }

        logging.info(f"Minecraft options: {mc_options}")

        try:
            minecraft_launcher_lib.fabric.install_fabric("1.20.1", ".bglauncher")
            subprocess.call(minecraft_launcher_lib.command.get_minecraft_command(version="1.20.1", minecraft_directory=".bglauncher", options=mc_options))
        except Exception as e:
            logging.error(f"Error launching Minecraft: {str(e)}")



    

    def handle_response(self, status_code, response_text):
        self.enable_inputs()
        if status_code == 200:
            nickname = self.nickname_input.text()
            status, role = fetch_user_status(nickname)
            if status == 'Active':
                self.open_launcher_ui(nickname, role)
            elif status == 'InActive':
                self.show_inactive_message()
            else:
                self.show_error_message("User not found or invalid status")
        else:
            self.show_error_message(response_text)

    def show_error_message(self, error_text):
        self.enable_inputs()
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setText("Login Error")
        msg.setInformativeText(f"An error occurred during login: {error_text}")
        msg.setWindowTitle("Error")
        msg.exec_()

    def show_inactive_message(self):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setText("Account Inactive")
        msg.setInformativeText("This account is inactive and requires activation.")
        msg.setWindowTitle("Inactive Account")
        msg.exec_()
        self.close()
        self.__init__(self.debug_mode)

    def enable_inputs(self):
        self.login_button.setEnabled(True)
        self.nickname_input.setEnabled(True)
        self.password_input.setEnabled(True)

    def open_launcher_ui(self, nickname, role):
        self.close()
        self.launcher_ui = QtWidgets.QMainWindow()
        
        uic.loadUi(self.launcher_ui_path, self.launcher_ui)
        
        nickname_label = self.launcher_ui.findChild(QtWidgets.QLabel, 'nickname')
        if nickname_label is not None:
            nickname_label.setText(nickname)
        
        status_label = self.launcher_ui.findChild(QtWidgets.QLabel, 'userStatus')
        if status_label is not None:
            status_label.setText(role)
    
        play_button = self.launcher_ui.findChild(QtWidgets.QPushButton, 'pushButton_play')
        if play_button is not None:
            play_button.clicked.connect(self.on_play_clicked)
        
        self.launcher_ui.show()


    @staticmethod
    def copy_log_file():
        project_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(project_dir, 'logs')

        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        current_date = datetime.now().strftime('%Y-%m-%d')
        log_file_name = f'{current_date}.log'
        log_file_path = os.path.join(logs_dir, log_file_name)

        if os.path.exists(log_file_path):
            counter = 1
            while True:
                new_log_file_name = f'{current_date}_{counter}.log'
                new_log_file_path = os.path.join(logs_dir, new_log_file_name)
                if not os.path.exists(new_log_file_path):
                    log_file_path = new_log_file_path
                    break
                counter += 1

        shutil.copy('log.log', log_file_path)
        logging.info(f"Log file copied to {log_file_path}")

if __name__ == "__main__":
    debug_mode = False
    if len(sys.argv) > 1 and sys.argv[1] == "--bruh_debug":
        debug_mode = True
        logging.info("Debug mode enabled")

    app = QtWidgets.QApplication(sys.argv)
    window = Ui(debug_mode)
    app.exec_()
    
    Ui.copy_log_file()
