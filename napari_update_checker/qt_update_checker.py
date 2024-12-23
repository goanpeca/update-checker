import os
import sys
from contextlib import suppress
from datetime import date
from typing import Optional

import packaging.version
from napari import __version__
from napari._qt.qthreading import create_worker
from napari.utils.misc import running_as_constructor_app
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt import ensure_main_thread

from napari_update_checker.utils import (
    get_latest_version,
    is_version_installed,
)

ON_BUNDLE = running_as_constructor_app()
IGNORE_DAYS = 21
IGNORE_FILE = "napari-update-ignore.txt"


class UpdateChecker(QWidget):

    FIRST_TIME = False
    URL_PACKAGE = "https://napari.org/dev/tutorials/fundamentals/installation.html#install-as-python-package-recommended"
    URL_BUNDLE = "https://napari.org/dev/tutorials/fundamentals/installation.html#install-as-a-bundled-app"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._current_version = packaging.version.parse(__version__)
        self._is_dev = '.dev' in __version__
        self._latest_version = None
        self._worker = None
        self._base_folder = sys.prefix
        self._snoozed = False

        self.label = QLabel("Checking for updates...<br>")
        self.check_updates_button = QPushButton("Check for updates")
        self.check_updates_button.clicked.connect(self._check)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.check_updates_button)
        self.setLayout(layout)

        self._timer = QTimer()
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.check)
        self._timer.setSingleShot(True)
        self._timer.start()

    def _check(self):
        self.label.setText("Checking for updates...\n")
        self._timer.start()

    def _check_time(self):
        if os.path.exists(os.path.join(self._base_folder, IGNORE_FILE)):
            with (
                open(
                    os.path.join(self._base_folder, IGNORE_FILE),
                    encoding="utf-8",
                ) as f_p,
                suppress(ValueError),
            ):
                old_date = date.fromisoformat(f_p.read())
                self._snoozed = (date.today() - old_date).days < IGNORE_DAYS
                if (date.today() - old_date).days < IGNORE_DAYS:
                    return True

            os.remove(os.path.join(self._base_folder, IGNORE_FILE))

        return False

    def check(self):
        self._check_time()
        self._worker = create_worker(get_latest_version)
        self._worker.returned.connect(self.show_version_info)
        self._worker.start()

    @ensure_main_thread
    def show_version_info(
        self, latest_version: Optional[packaging.version.Version] = None
    ):
        my_version = self._current_version
        remote_version = latest_version

        if self._is_dev:
            msg = (
                f"You using napari in development mode.<br><br>"
                f"Installed version: {my_version}<br>"
                f"Current released version: {remote_version}<br><br>"
            )
            self.label.setText(msg)
        else:
            if remote_version > my_version and not is_version_installed(
                str(remote_version)
            ):
                url = self.URL_BUNDLE if ON_BUNDLE else self.URL_PACKAGE
                msg = (
                    f"You use outdated version of napari.<br><br>"
                    f"Installed version: {my_version}<br>"
                    f"Current version: {remote_version}<br><br>"
                    "For more information on how to update <br>"
                    f'visit the <a href="{url}">online documentation</a><br><br>'
                )
                self.label.setText(msg)
                if not self._snoozed:
                    message = QMessageBox(
                        QMessageBox.Icon.Information,
                        "New release",
                        msg,
                        QMessageBox.StandardButton.Ok
                        | QMessageBox.StandardButton.Ignore,
                    )
                    if message.exec_() == QMessageBox.StandardButton.Ignore:  # type: ignore
                        os.makedirs(self._base_folder, exist_ok=True)
                        with open(
                            os.path.join(self._base_folder, IGNORE_FILE),
                            "w",
                            encoding="utf-8",
                        ) as f_p:
                            f_p.write(date.today().isoformat())
            else:
                msg = (
                    f"You are using the latest version of napari!<br><br>"
                    f"Installed version: {my_version}<br><br>"
                )
                self.label.setText(msg)


if __name__ == '__main__':
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    checker = UpdateChecker()
    sys.exit(app.exec_())  # type: ignore
