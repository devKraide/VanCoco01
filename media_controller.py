from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path
from typing import Optional

import PySide6
import vlc

from config import WINDOW_NAME


PYSIDE6_PATHS = list(getattr(PySide6, "__path__", []))
if not PYSIDE6_PATHS:
    raise RuntimeError("Nao foi possivel localizar a instalacao do PySide6.")

QT_ROOT = Path(PYSIDE6_PATHS[0]).resolve() / "Qt"
QT_PLUGINS_DIR = QT_ROOT / "plugins"
QT_PLATFORMS_DIR = QT_PLUGINS_DIR / "platforms"

os.environ.setdefault("QT_PLUGIN_PATH", str(QT_PLUGINS_DIR))
os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(QT_PLATFORMS_DIR))
if platform.system() == "Darwin":
    os.environ.setdefault("QT_QPA_PLATFORM", "cocoa")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget


class PresentationWindow(QWidget):
    def __init__(self, controller: "MediaController") -> None:
        super().__init__()
        self._controller = controller
        self._video_surface = QWidget(self)
        self._configure_window()

    @property
    def video_surface(self) -> QWidget:
        return self._video_surface

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._controller.register_key(27)
            return

        text = event.text().lower()
        if text:
            self._controller.register_key(ord(text))

    def closeEvent(self, event) -> None:
        self._controller.request_close()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        self._video_surface.setGeometry(self.rect())
        super().resizeEvent(event)

    def _configure_window(self) -> None:
        self.setWindowTitle(WINDOW_NAME)
        self.setCursor(Qt.BlankCursor)
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("black"))
        self.setPalette(palette)

        self._video_surface.setAutoFillBackground(True)
        self._video_surface.setPalette(palette)
        self._video_surface.setAttribute(Qt.WA_NativeWindow, True)
        self._video_surface.hide()


class MediaController:
    def __init__(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.addLibraryPath(str(QT_PLUGINS_DIR))
        self._pressed_key: Optional[int] = None
        self._is_running = True
        self._video_finished = False
        self._mock_video_deadline: Optional[float] = None
        self._vlc_instance = vlc.Instance("--no-video-title-show")
        self._media_player: Optional[vlc.MediaPlayer] = None
        self._window = PresentationWindow(self)
        self._window.showFullScreen()

    def show_black_screen(self) -> None:
        self._window.video_surface.hide()
        self._window.showFullScreen()
        self._window.raise_()
        self._window.activateWindow()

    def start_video(self, video_path: Path) -> None:
        self.stop_video()
        if not video_path.exists():
            raise FileNotFoundError(f"Nao foi possivel abrir o video: {video_path}")

        self._video_finished = False
        self._mock_video_deadline = None
        media = self._vlc_instance.media_new(str(video_path))
        self._media_player = self._vlc_instance.media_player_new()
        self._media_player.set_media(media)
        self._window.video_surface.show()
        self._bind_player_to_window()
        self._attach_player_events()
        self._media_player.play()

    def start_mock_video(self, duration_seconds: float) -> None:
        self.stop_video()
        self._video_finished = False
        self._mock_video_deadline = time.monotonic() + duration_seconds
        self._window.video_surface.hide()

    def stop_video(self) -> None:
        if self._media_player is not None:
            self._media_player.stop()
            self._media_player.release()
            self._media_player = None
        self._mock_video_deadline = None
        self.show_black_screen()

    def close(self) -> None:
        self.stop_video()
        self._window.close()
        self._app.quit()

    def update_ui(self) -> None:
        self._app.processEvents()
        if self._mock_video_deadline is not None and time.monotonic() >= self._mock_video_deadline:
            self._mock_video_deadline = None
            self._video_finished = True

    def consume_key(self) -> Optional[int]:
        pressed_key = self._pressed_key
        self._pressed_key = None
        return pressed_key

    def should_close(self) -> bool:
        return not self._is_running

    def consume_video_finished(self) -> bool:
        if not self._video_finished:
            return False

        self._video_finished = False
        return True

    def register_key(self, key_code: int) -> None:
        self._pressed_key = key_code

    def request_close(self) -> None:
        self._is_running = False

    def _bind_player_to_window(self) -> None:
        if self._media_player is None:
            return

        video_surface_id = int(self._window.video_surface.winId())
        system_name = platform.system()

        if system_name == "Darwin":
            self._media_player.set_nsobject(video_surface_id)
            return

        if system_name == "Linux":
            self._media_player.set_xwindow(video_surface_id)
            self._media_player.video_set_mouse_input(False)
            self._media_player.video_set_key_input(False)
            return

        if system_name == "Windows":
            self._media_player.set_hwnd(video_surface_id)
            self._media_player.video_set_mouse_input(False)
            self._media_player.video_set_key_input(False)
            return

        raise RuntimeError(f"Sistema operacional nao suportado: {system_name}")

    def _attach_player_events(self) -> None:
        if self._media_player is None:
            return

        events = self._media_player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_video_finished)

    def _on_video_finished(self, _event) -> None:
        self._video_finished = True
