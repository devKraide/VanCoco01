from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path
from typing import Optional

import PySide6
import cv2
import vlc

from config import OPERATIONAL_OVERLAY_ENABLED, VISION_PREVIEW_OVERLAY, WINDOW_NAME


VLC_ARGS = (
    "--no-video-title-show",
    "--avcodec-hw=none",
    # ALSA avoids PipeWire/PulseAudio Bluetooth startup underruns on Ubuntu.
    "--aout=alsa",
)


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
elif platform.system() == "Linux":
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget


PREVIEW_WIDTH = 360
PREVIEW_HEIGHT = 200
PREVIEW_MARGIN = 14
OPERATIONAL_OVERLAY_WIDTH = 420
OPERATIONAL_OVERLAY_HEIGHT = 170


class PresentationWindow(QWidget):
    def __init__(self, controller: "MediaController") -> None:
        super().__init__()
        self._controller = controller
        self._video_surface = QWidget(self)
        self._preview_overlay = QLabel(self)
        self._operational_overlay = QLabel(self)
        self._configure_window()

    @property
    def video_surface(self) -> QWidget:
        return self._video_surface

    @property
    def preview_overlay(self) -> QLabel:
        return self._preview_overlay

    @property
    def operational_overlay(self) -> QLabel:
        return self._operational_overlay

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
        self._position_preview_overlay()
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
        self._video_surface.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        self._video_surface.show()

        self._preview_overlay.setGeometry(
            PREVIEW_MARGIN,
            PREVIEW_MARGIN,
            PREVIEW_WIDTH,
            PREVIEW_HEIGHT,
        )
        self._preview_overlay.setStyleSheet(
            "background-color: black; border: 2px solid rgba(255, 255, 255, 180);"
        )
        self._preview_overlay.setAlignment(Qt.AlignCenter)
        self._preview_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._preview_overlay.hide()

        self._operational_overlay.setGeometry(
            PREVIEW_MARGIN,
            PREVIEW_MARGIN + PREVIEW_HEIGHT + 12,
            OPERATIONAL_OVERLAY_WIDTH,
            OPERATIONAL_OVERLAY_HEIGHT,
        )
        self._operational_overlay.setStyleSheet(
            "background-color: rgba(0, 0, 0, 210);"
            "border: 1px solid rgba(255, 255, 255, 130);"
            "color: white;"
            "font-family: monospace;"
            "font-size: 18px;"
            "padding: 10px;"
        )
        self._operational_overlay.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._operational_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._operational_overlay.hide()

    def _position_preview_overlay(self) -> None:
        self._preview_overlay.setGeometry(
            PREVIEW_MARGIN,
            PREVIEW_MARGIN,
            PREVIEW_WIDTH,
            PREVIEW_HEIGHT,
        )
        self._operational_overlay.setGeometry(
            PREVIEW_MARGIN,
            PREVIEW_MARGIN + PREVIEW_HEIGHT + 12,
            OPERATIONAL_OVERLAY_WIDTH,
            OPERATIONAL_OVERLAY_HEIGHT,
        )


class MediaController:
    def __init__(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.addLibraryPath(str(QT_PLUGINS_DIR))
        self._pressed_key: Optional[int] = None
        self._is_running = True
        self._video_finished = False
        self._mock_video_deadline: Optional[float] = None
        self._vlc_instance = vlc.Instance(*VLC_ARGS)
        print("VLC_HW_DECODING_DISABLED")
        print("VLC_AUDIO_BACKEND=alsa")
        self._media_player: Optional[vlc.MediaPlayer] = self._vlc_instance.media_player_new()
        self._window = PresentationWindow(self)
        self._window.showFullScreen()
        self._window.video_surface.setGeometry(self._window.rect())
        self._window.video_surface.winId()
        self._app.processEvents()
        self._bind_player_to_window()
        self._attach_player_events()
        print("VLC_PLAYER_PERSISTENT_INIT")

    def show_black_screen(self) -> None:
        self._window.video_surface.show()
        self._window.video_surface.setGeometry(0, 0, 1, 1)
        self._window.preview_overlay.raise_()
        self._window.operational_overlay.raise_()
        self._window.showFullScreen()
        self._window.raise_()
        self._window.activateWindow()
        self._app.processEvents()

    def start_video(self, video_path: Path) -> None:
        self.hide_preview_overlay()
        self.hide_operational_overlay()
        self.stop_video()
        if not video_path.exists():
            raise FileNotFoundError(f"Nao foi possivel abrir o video: {video_path}")

        self._video_finished = False
        self._mock_video_deadline = None
        media = self._vlc_instance.media_new(str(video_path))
        print(f"VLC_MEDIA_SET={video_path}")
        self._media_player.set_media(media)
        self._window.video_surface.show()
        self._window.video_surface.setGeometry(self._window.rect())
        self._app.processEvents()
        print("VLC_PLAY_START")
        self._media_player.play()

    def show_preview_frame(self, frame) -> None:
        if not VISION_PREVIEW_OVERLAY or frame is None:
            return

        preview = cv2.resize(
            frame,
            (PREVIEW_WIDTH, PREVIEW_HEIGHT),
            interpolation=cv2.INTER_AREA,
        )
        rgb_preview = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_preview.shape
        bytes_per_line = channels * width
        image = QImage(
            rgb_preview.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888,
        )
        self._window.preview_overlay.setPixmap(QPixmap.fromImage(image.copy()))
        self._window.preview_overlay.show()
        self._window.preview_overlay.raise_()

    def hide_preview_overlay(self) -> None:
        if not VISION_PREVIEW_OVERLAY:
            return

        self._window.preview_overlay.hide()

    def show_operational_overlay(
        self,
        state: str,
        expected: str,
        raw: str,
        status: str,
        reason: str,
    ) -> None:
        if not OPERATIONAL_OVERLAY_ENABLED:
            return

        text = "\n".join(
            (
                f"STATE    {state}",
                f"EXPECTED {expected}",
                f"RAW      {raw}",
                f"STATUS   {status}",
                f"REASON   {reason}",
            )
        )
        self._window.operational_overlay.setText(text)
        self._window.operational_overlay.show()
        self._window.operational_overlay.raise_()

    def hide_operational_overlay(self) -> None:
        if not OPERATIONAL_OVERLAY_ENABLED:
            return

        self._window.operational_overlay.hide()

    def start_mock_video(self, duration_seconds: float) -> None:
        self.stop_video()
        self._video_finished = False
        self._mock_video_deadline = time.monotonic() + duration_seconds
        self._window.video_surface.show()
        self._window.video_surface.setGeometry(0, 0, 1, 1)

    def stop_video(self) -> None:
        if self._media_player is not None:
            self._media_player.stop()
            print("VLC_STOP_NO_RELEASE")
        self._mock_video_deadline = None
        self.show_black_screen()

    def close(self) -> None:
        self.stop_video()
        if self._media_player is not None:
            self._media_player.release()
            self._media_player = None
            print("VLC_PLAYER_RELEASE_ON_CLOSE")
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

        raise RuntimeError(f"Sistema operacional nao suportado: {system_name}")

    def _attach_player_events(self) -> None:
        if self._media_player is None:
            return

        events = self._media_player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_video_finished)

    def _on_video_finished(self, _event) -> None:
        self._video_finished = True
