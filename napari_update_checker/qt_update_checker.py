import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import date
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import packaging
import packaging.version
from napari import __version__
from napari._qt.qthreading import create_worker
from napari.utils.misc import running_as_constructor_app
from napari.utils.notifications import show_warning
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt import ensure_main_thread

ON_BUNDLE = running_as_constructor_app()
IGNORE_DAYS = 21
IGNORE_FILE = "ignore.txt"


@lru_cache
def github_tags():
    url = 'https://api.github.com/repos/napari/napari/tags'
    with urlopen(url) as r:
        data = json.load(r)

    versions = []
    for item in data:
        version = item.get('name', None)
        if version:
            if version.startswith('v'):
                version = version[1:]

            versions.append(version)

    return list(reversed(versions))


@lru_cache
def conda_forge_releases():
    url = 'https://api.anaconda.org/package/conda-forge/napari/'
    with urlopen(url) as r:
        data = json.load(r)
    versions = data.get('versions', [])
    return versions


def get_latest_version():
    """Check latest version between tags and conda forge."""
    try:
        with ThreadPoolExecutor() as executor:
            tags = executor.submit(github_tags)
            cf = executor.submit(conda_forge_releases)

        gh_tags = tags.result()
        cf_versions = cf.result()
    except (HTTPError, URLError):
        show_warning(
            'Plugin manager: There seems to be an issue with network connectivity. '
        )
        return

    latest_version = packaging.version.parse(cf_versions[-1])
    latest_tag = packaging.version.parse(gh_tags[-1])
    if latest_version > latest_tag:
        yield latest_version
    else:
        yield latest_tag


class UpdateChecker(QWidget):

    FIRST_TIME = False
    URL_PACKAGE = "https://napari.org/dev/tutorials/fundamentals/installation.html#install-as-python-package-recommended"
    URL_BUNDLE = "https://napari.org/dev/tutorials/fundamentals/installation.html#install-as-a-bundled-app"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._current_version = packaging.version.parse(__version__)
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
        # print(os.path.join(self._base_folder, IGNORE_FILE))
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
        self._worker.yielded.connect(self.show_version_info)
        self._worker.start()

    @ensure_main_thread
    def show_version_info(self, latest_version):
        my_version = self._current_version
        remote_version = latest_version
        if remote_version > my_version:
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
                if message.exec_() == QMessageBox.StandardButton.Ignore:
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
    sys.exit(app.exec_())
