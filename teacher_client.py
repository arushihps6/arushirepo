# teacher_client.py
import sys
import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QDialog, QLineEdit,
    QPushButton, QFormLayout, QMessageBox
)
from PySide6.QtGui import QFont

# --- Configuration ---
SERVER_URL = "http://192.168.1.37:8000"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MAX_PERIODS = 8  # Adjust if your school has more


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)

        form_layout = QFormLayout()
        form_layout.addRow("Username:", self.username_edit)
        form_layout.addRow("Password:", self.password_edit)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.attempt_login)
        # Allow pressing Enter to attempt login
        self.password_edit.returnPressed.connect(self.attempt_login)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.login_button)

        self.teacher_id = None
        self.teacher_name = None

    def attempt_login(self):
        username = self.username_edit.text()
        password = self.password_edit.text()

        if not username or not password:
            QMessageBox.warning(self, "Input Error", "Username and password cannot be empty.")
            return

        try:
            response = requests.post(f"{SERVER_URL}/login", json={"username": username, "password": password})
            if response.status_code == 200:
                data = response.json()
                self.teacher_id = data['teacher_id']
                self.teacher_name = data['teacher_name']
                self.accept()  # This closes the dialog with a success signal
            else:
                QMessageBox.critical(self, "Login Failed", "Invalid username or password.")
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Connection Error",
                                 "Could not connect to the timetable server. Please ensure the server is running and accessible.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")


class TimetableView(QMainWindow):
    def __init__(self, teacher_id, teacher_name):
        super().__init__()
        self.teacher_id = teacher_id
        self.setWindowTitle(f"Timetable for {teacher_name}")
        self.setMinimumSize(1000, 700)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        title = QLabel(f"Timetable for {teacher_name}")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        self.layout.addWidget(title)

        self.grid = QTableWidget()
        self.grid.setEditTriggers(QTableWidget.NoEditTriggers)
        self.layout.addWidget(self.grid)

        self.refresh_button = QPushButton("Refresh Timetable")
        self.refresh_button.clicked.connect(self.populate_grid)
        self.layout.addWidget(self.refresh_button)

        self.populate_grid()

    def populate_grid(self):
        self.grid.clear()
        self.grid.setRowCount(MAX_PERIODS)
        self.grid.setColumnCount(len(DAYS))
        self.grid.setHorizontalHeaderLabels(DAYS)
        self.grid.setVerticalHeaderLabels([f"Period {i + 1}" for i in range(MAX_PERIODS)])
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.grid.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        try:
            response = requests.get(f"{SERVER_URL}/timetable/{self.teacher_id}")
            if response.status_code == 200:
                schedule = response.json()
                for entry in schedule:
                    if entry['day'] in DAYS:
                        day_index = DAYS.index(entry['day'])
                        period_index = entry['period'] - 1
                        if 0 <= period_index < MAX_PERIODS:
                            item_text = f"{entry['subject_name']}\n({entry['section_name']})"
                            item = QTableWidgetItem(item_text)
                            item.setTextAlignment(Qt.AlignCenter)
                            self.grid.setItem(period_index, day_index, item)
            else:
                QMessageBox.warning(self, "Error",
                                    f"Could not fetch timetable from server. Status: {response.status_code}")
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "Connection Error", "Could not connect to the timetable server.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    login_dialog = LoginDialog()
    # The login_dialog.exec() call will block until the user successfully logs in or closes the window
    if login_dialog.exec() == QDialog.Accepted:
        # If login was successful, create and show the main window
        window = TimetableView(login_dialog.teacher_id, login_dialog.teacher_name)
        window.show()
        sys.exit(app.exec())
    # If the user closes the login dialog, the app simply exits