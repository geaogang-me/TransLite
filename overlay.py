# translite_full_cursor_position.py
# 将悬浮翻译按钮与翻译弹窗的位置与鼠标箭头一致（使用 QCursor.pos()）
# 保留原有功能：悬浮按钮、翻译弹窗、自适应高度、托盘菜单与服务器选择
# 不包含测试/演示代码（可直接集成到你的项目中）

# type: ignore[attr-defined]
import sys
from typing import Optional, List, Tuple

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, pyqtProperty, QPoint
from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QVBoxLayout,
    QTextEdit,
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QLabel,
)
from PyQt5.QtGui import (
    QPainter,
    QPen,
    QColor,
    QIcon,
    QPixmap,
    QTextOption,
    QFont,
    QFontMetrics,
    QCursor,
)


class LoadingSpinner(QLabel):
    """旋转加载动画组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setStyleSheet("background: transparent;")

        # 旋转角度属性
        self._rotation = 0.0

        # 创建旋转动画
        self.animation = QPropertyAnimation(self, b"rotation")
        self.animation.setDuration(1000)  # 1秒一圈
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(360.0)
        self.animation.setLoopCount(-1)  # 无限循环

        # 启动动画
        self.animation.start()

    @pyqtProperty(float)
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        self._rotation = value
        self.update()  # 触发重绘

    def paintEvent(self, event):
        """绘制旋转的加载图标"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 设置旋转中心
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._rotation)

        # 绘制圆形内部的黑色背景
        painter.setBrush(QColor(0, 0, 0, 250))  # 黑色半透明背景
        painter.setPen(Qt.NoPen)  # 无边框
        painter.drawEllipse(-12, -12, 24, 24)  # 绘制黑色圆形背景

        # 绘制旋转的圆圈边框
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        painter.setBrush(Qt.NoBrush)  # 不填充，只有边框
        painter.drawEllipse(-12, -12, 24, 24)

        # 绘制旋转点
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(8, -2, 4, 4)

    def stop_animation(self):
        """停止动画"""
        if self.animation:
            self.animation.stop()


class OverlayButton(QWidget):
    """
    悬浮翻译按钮。
    位置与鼠标箭头对齐（使用 QCursor.pos()），若 parent 给定则把全局坐标转换为 parent 局部坐标。
    点击时会发出 translateRequested(text, screen_x, screen_y)，传递按钮的全局锚点（屏幕坐标）。
    """
    translateRequested = pyqtSignal(str, int, int)  # text, screen_x, screen_y

    def __init__(self, parent=None) -> None:
        # Qt.Tool + Frameless 让它看起来像悬浮工具小窗，但 parent 仍可指定
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._text = ""
        self._auto_hide = QTimer(self)
        self._auto_hide.setInterval(2000)
        self._auto_hide.setSingleShot(True)
        self._auto_hide.timeout.connect(self.hide)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.button = QPushButton("译", self)
        self.button.setFixedSize(28, 28)
        self.button.setStyleSheet(
            """
            QPushButton {
                border-radius: 14px;
                background: black;
                color: white;
                font-weight: bold;
                font-family: Microsoft YaHei;
            }
            """
        )
        self.button.clicked.connect(self._on_click)
        layout.addWidget(self.button)

        # 记录最后一次显示时按钮的全局锚点（屏幕坐标）
        self._last_global_anchor = QPoint(0, 0)

    def _on_click(self) -> None:
        """
        发出翻译请求信号，携带按钮的全局坐标（按钮中心的屏幕坐标），
        这样 popup 可以精确地以按钮为锚点定位。
        """
        # 使用按钮的中心作为锚点（更自然的对齐），若需要左上角对齐可改为 QPoint(0,0)
        try:
            btn_center = self.button.mapToGlobal(self.button.rect().center())
        except Exception:
            btn_center = QCursor.pos()

        g_x, g_y = btn_center.x(), btn_center.y()
        self.hide()
        self.translateRequested.emit(self._text, g_x, g_y)

    def show_near(self, x: int, y: int, text: str) -> None:
        """
        显示悬浮按钮并把其位置向鼠标箭头右下偏移一个鼠标箭头的空间。
        如果存在 parent，则把全局坐标转换为 parent 局部坐标再移动。
        并记录按钮的全局锚点（屏幕坐标）。
        """
        self._text = text
        cursor_pt = QCursor.pos()
        # 向右下偏移一个鼠标箭头的空间（通常约 像素）
        offset_x = 8  # 鼠标箭头右偏移
        offset_y = 8  # 鼠标箭头下偏移
        if self.parent() is not None:
            local_pt = self.parent().mapFromGlobal(cursor_pt)
            self.move(local_pt.x() + offset_x, local_pt.y() + offset_y)
        else:
            # 顶级窗口 move 使用屏幕坐标
            self.move(cursor_pt.x() + offset_x, cursor_pt.y() + offset_y)

        # 记录按钮当前的全局锚点（使用按钮中心）
        try:
            self._last_global_anchor = self.button.mapToGlobal(self.button.rect().center())
        except Exception:
            self._last_global_anchor = QCursor.pos()

        self.show()
        self._auto_hide.start()

    def enterEvent(self, a0):  # type: ignore[override]
        self._auto_hide.stop()
        return super().enterEvent(a0)

    def leaveEvent(self, a0):  # type: ignore[override]
        self._auto_hide.start()
        return super().leaveEvent(a0)


class ResultPopup(QWidget):
    """
    翻译结果弹窗（顶级工具窗口）
    位置使用调用者传入的屏幕坐标（x,y）作为锚点，并夹紧屏幕边界。
    弹窗的定位策略可通过 offset_x/offset_y 调整（默认为与锚点中心对齐）。
    """

    def __init__(self) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 自动隐藏定时器
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)
        self.hide_duration = 3000  # 毫秒
        self.remaining_time = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # loading container（居中放置 spinner）
        self.loading_container = QWidget(self)
        loading_layout = QVBoxLayout(self.loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setAlignment(Qt.AlignCenter)
        self.loading_spinner = LoadingSpinner(self.loading_container)
        loading_layout.addWidget(self.loading_spinner)
        self.loading_container.setStyleSheet("QWidget { background: transparent; }")
        self.loading_container.setFixedSize(32, 32)
        self.loading_container.hide()

        # 文本框（固定宽度，高度自适应）
        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setFixedWidth(280)
        self.text.setWordWrapMode(QTextOption.WordWrap)
        self.text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text.setStyleSheet("QTextEdit { background: #202124; color: #e8eaed; border-radius: 8px; padding: 8px; }")

        layout.addWidget(self.loading_container)
        layout.addWidget(self.text)

        # 可调参数：最小/最大行数（以行为单位）
        self._min_lines = 1
        self._max_lines = 12

    def show_loading(self, x: int, y: int) -> None:
        """
        显示加载状态。位置使用传入的屏幕坐标 (x,y) 作为锚点（通常为按钮中心），
        offset_x/offset_y 可用于微调弹窗相对锚点的位置。
        """
        self.loading_container.show()
        self.text.hide()

        # 调整偏移量使加载动画中心与按钮中心对齐
        # 加载动画容器32x32，所以需要向左上偏移(16,16)让动画中心对齐按钮中心
        offset_x = -23  # 向左偏移，使动画中心对齐按钮中心
        offset_y = -23  # 向上偏移，使动画中心对齐按钮中心

        # 确保尺寸已计算
        self.adjustSize()
        self._move_within_screen(x, y, offset_x=offset_x, offset_y=offset_y)
        self.show()

    def show_text(self, content: str, x: int, y: int) -> None:
        """
        显示翻译文本，位置使用传入的屏幕坐标 (x,y) 作为锚点（通常为按钮中心）。
        """
        self.loading_container.hide()
        self.text.setPlainText(content)
        self.text.show()

        def adjust_and_place():
            self._adjust_text_height()
            self.adjustSize()

            # 调整偏移量使翻译结果中心与按钮中心对齐
            # 翻译结果框宽度280px，需要向左偏移140px使中心对齐按钮中心
            offset_x = 0  # 向左偏移，使结果框中心对齐按钮中心
            offset_y = 0   # 向上偏移一点，避免遮挡按钮
            self._move_within_screen(x, y, offset_x=offset_x, offset_y=offset_y)
            self.show()
            self.start_hide_timer()

        QTimer.singleShot(0, adjust_and_place)

    def start_hide_timer(self):
        self.remaining_time = self.hide_duration
        self.hide_timer.start(self.hide_duration)

    def pause_hide_timer(self):
        if self.hide_timer.isActive():
            self.remaining_time = self.hide_timer.remainingTime()
            self.hide_timer.stop()

    def resume_hide_timer(self):
        if self.remaining_time > 0:
            self.hide_timer.start(self.remaining_time)

    def enterEvent(self, a0):
        """鼠标进入暂停自动隐藏"""
        self.pause_hide_timer()
        return super().enterEvent(a0)

    def leaveEvent(self, a0):
        """鼠标离开恢复自动隐藏"""
        self.resume_hide_timer()
        return super().leaveEvent(a0)

    def _adjust_text_height(self):
        """
        根据文档计算内容高度，并受最小/最大行数限制。
        使用 self.text.viewport().width() 作为可用宽度（更准确）。
        """
        padding_v = 8 * 2  # 与 styleSheet padding: 8px 对应，上下各8
        padding_h = 8 * 2  # 左右各8

        doc = self.text.document()

        viewport_width = max(10, self.text.viewport().width())
        content_width = max(10, viewport_width - padding_h)

        doc.setTextWidth(content_width)
        content_height = doc.size().height()

        fm = QFontMetrics(self.text.font())
        line_height = fm.lineSpacing()

        min_h = int(line_height * max(1, self._min_lines) + padding_v)
        max_h = int(line_height * max(1, self._max_lines) + padding_v)
        desired_h = int(content_height + padding_v)
        final_h = max(min_h, min(desired_h, max_h))

        self.text.setFixedHeight(final_h)

    def _move_within_screen(self, base_x: int, base_y: int, offset_x: int = 0, offset_y: int = 0):
        """
        把窗口移动到 (base_x + offset_x, base_y + offset_y) 附近，并确保窗口整体
        在该坐标所属屏幕的 availableGeometry 内（避免跑出屏幕）。
        base_x/base_y 为屏幕坐标（QPoint 全局坐标）。
        """
        target_x = base_x + offset_x
        target_y = base_y + offset_y

        screen = QApplication.screenAt(QPoint(base_x, base_y))
        if screen is None:
            screen = QApplication.primaryScreen()
        geom = screen.availableGeometry()

        # 确保尺寸已计算
        self.adjustSize()
        w = self.width()
        h = self.height()

        new_x = max(geom.left(), min(target_x, geom.right() - w))
        new_y = max(geom.top(), min(target_y, geom.bottom() - h))

        self.move(new_x, new_y)


def create_tray(app: QApplication, translator=None) -> Optional[QSystemTrayIcon]:
    """
    创建系统托盘图标并附带翻译服务器选择菜单（如果提供 translator）。
    translator 需要实现：
      - get_current_mode() -> str
      - set_preferred_mode(mode: str)
      - get_available_servers() -> List[Tuple[int, str, str]] (idx, name, url)
      - test_server(idx: int) -> bool
    """
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(app)
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(50, 50, 50))
    painter.setPen(QPen(QColor(30, 30, 30), 2))
    painter.drawEllipse(2, 2, 28, 28)

    font = QFont("Microsoft YaHei")
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(0, 0, 32, 32, Qt.AlignCenter, "译")
    painter.end()

    tray.setIcon(QIcon(pixmap))
    tray.setToolTip("TransLite")

    menu = QMenu()

    if translator:
        server_menu = QMenu("🌐 选择翻译服务", menu)

        # 自动模式
        auto_action = server_menu.addAction("⚙️ 智能模式（推荐）")
        auto_action.setCheckable(True)
        try:
            auto_action.setChecked(translator.get_current_mode() == 'auto')
        except Exception:
            auto_action.setChecked(False)
        auto_action.triggered.connect(lambda checked=False: _set_translator_mode(translator, 'auto', tray))

        server_menu.addSeparator()

        # 获取可用服务器列表并构建菜单（注意捕获 idx）
        try:
            servers = translator.get_available_servers()
        except Exception:
            servers = []

        for idx, name, url in servers:
            server_action = server_menu.addAction(f"🔗 {name}")
            server_action.setCheckable(True)
            try:
                current_mode = translator.get_current_mode()
                is_selected = current_mode == f'manual_{idx}'
            except Exception:
                is_selected = False
            server_action.setChecked(is_selected)
            server_action.triggered.connect(
                lambda checked=False, server_idx=idx: _set_translator_mode(translator, f'manual_{server_idx}', tray)
            )

        menu.addMenu(server_menu)
        menu.addSeparator()

        # 测试当前服务器
        test_action = menu.addAction("🔍 测试当前服务器")
        test_action.triggered.connect(lambda: _test_current_server(translator, tray))

        menu.addSeparator()

    # 关于信息
    about_action = menu.addAction("ℹ️ 关于")
    about_action.triggered.connect(lambda: _show_about_dialog())

    # 退出
    quit_action = menu.addAction("❌ 退出")
    if quit_action:
        quit_action.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.setVisible(True)
    return tray


def _show_about_dialog():
    """显示关于对话框"""
    from PyQt5.QtWidgets import QMessageBox
    about_text = """
TransLite - 轻量级中英互译工具
选中文本按下F2键点击‘译’进行翻译
右键托盘图标可选择翻译服务
""".strip()
    QMessageBox.information(None, "关于 TransLite", about_text)


def _set_translator_mode(translator, mode: str, tray_icon):
    """设置翻译器模式并更新托盘显示"""
    try:
        translator.set_preferred_mode(mode)
        mode_name = "智能模式" if mode == 'auto' else _get_server_name_by_mode(translator, mode)
        tray_icon.showMessage(
            "TransLite",
            f"已切换到: {mode_name}",
            QSystemTrayIcon.Information,
            2000
        )
    except Exception as e:
        print(f"设置翻译模式失败: {e}")


def _get_server_name_by_mode(translator, mode: str) -> str:
    """根据模式获取服务器名称"""
    if mode == 'auto':
        return "智能模式"

    if mode.startswith('manual_'):
        try:
            server_idx = int(mode.split('_')[1])
            servers = translator.get_available_servers()
            for idx, name, url in servers:
                if idx == server_idx:
                    return name
        except (IndexError, ValueError, Exception):
            pass

    return "未知服务器"


def _test_current_server(translator, tray_icon):
    """测试当前服务器可用性"""
    try:
        current_mode = translator.get_current_mode()

        if current_mode == 'auto':
            test_result = translator.test_server(0)
            message = "智能模式：主服务器" + ("可用" if test_result else "不可用")
        elif current_mode.startswith('manual_'):
            server_idx = int(current_mode.split('_')[1])
            server_name = _get_server_name_by_mode(translator, current_mode)
            test_result = translator.test_server(server_idx)
            message = f"{server_name}: " + ("可用" if test_result else "不可用")
        else:
            message = "无法测试当前模式"

        icon_type = QSystemTrayIcon.Information if test_result else QSystemTrayIcon.Warning
        tray_icon.showMessage(
            "TransLite - 服务器测试",
            message,
            icon_type,
            3000
        )

    except Exception as e:
        print(f"测试服务器失败: {e}")
        tray_icon.showMessage(
            "TransLite",
            "测试失败，请检查网络连接",
            QSystemTrayIcon.Critical,
            3000
        )