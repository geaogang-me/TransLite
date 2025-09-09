# type: ignore[attr-defined]
from contextlib import contextmanager
from PyQt5.QtCore import QObject, QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QGuiApplication

from pynput import keyboard


class SelectionDetector(QObject):
    selectionReady = pyqtSignal(str, int, int)
    _tryCaptureSignal = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        # 连接信号和槽，确保在主线程中执行Qt操作
        self._tryCaptureSignal.connect(self._try_capture)

        # 键盘监听 - F2键支持
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            daemon=True,  # 设置为守护线程
            suppress=False  # 不阻止其他程序接收键盘事件
        )
        try:
            self._keyboard_listener.start()
        except Exception as e:
            print(f"键盘监听器启动失败: {e}")
            
        self._last_text: str = ""
        self._last_pos = (0, 0)
        self._kb = keyboard.Controller()


    # ---------- 键盘按键（F2）触发捕获 ----------
    def _on_key_press(self, key):
        try:
            if key == keyboard.Key.f2:
                # 获取当前鼠标位置作为弹出按钮的位置
                from pynput import mouse
                mouse_position = mouse.Controller().position
                self._last_pos = (mouse_position[0], mouse_position[1])
                # 尝试捕获当前选中的文本（在主线程）
                self._tryCaptureSignal.emit()
        except AttributeError:
            pass

    def _try_capture(self) -> None:
        app = QApplication.instance() or QGuiApplication.instance()
        if app is None:
            return
        clipboard = app.clipboard()
        original = clipboard.text()
        try:
            with self._pressed_ctrl():
                self._kb.press('c')
                self._kb.release('c')
        except Exception:
            pass
        QTimer.singleShot(120, lambda: self._read_and_restore_clipboard(original))

    def _read_and_restore_clipboard(self, original_text: str) -> None:
        app = QApplication.instance() or QGuiApplication.instance()
        if app is None:
            return
        clipboard = app.clipboard()
        captured = clipboard.text()
        # 恢复原始剪贴板内容
        clipboard.setText(original_text)

        text = (captured or "").strip()
        if not text:
            return
        # 允许重复翻译同一段文本，不再跳过与上次相同的内容
        self._last_text = text
        x, y = self._last_pos
        self.selectionReady.emit(text, x, y)

    @contextmanager
    def _pressed_ctrl(self):
        self._kb.press(keyboard.Key.ctrl)
        try:
            yield
        finally:
            self._kb.release(keyboard.Key.ctrl)

    def cleanup(self):
        """清理资源，停止键盘监听器"""
        try:
            if hasattr(self, '_keyboard_listener') and self._keyboard_listener:
                self._keyboard_listener.stop()
        except Exception as e:
            print(f"停止键盘监听器失败: {e}")
