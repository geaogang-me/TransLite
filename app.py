# type: ignore[attr-defined]
import sys
import os
import tempfile

# 修复PyQt5在打包后的路径问题
def fix_qt_plugin_path():
    """修复Qt插件路径问题，特别是在打包后的环境中"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        bundle_dir = sys._MEIPASS
        qt_plugins_path = os.path.join(bundle_dir, 'PyQt5', 'Qt', 'plugins')
        if os.path.exists(qt_plugins_path):
            os.environ['QT_PLUGIN_PATH'] = qt_plugins_path
        # 设置Qt平台插件路径
        platforms_path = os.path.join(bundle_dir, 'platforms')
        if os.path.exists(platforms_path):
            os.environ['QT_PLUGIN_PATH'] = os.path.dirname(platforms_path)

# 在导入PyQt5之前调用修复函数
fix_qt_plugin_path()

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QCoreApplication, QThread, pyqtSignal, QLockFile
from PyQt5.QtWidgets import QSystemTrayIcon

from selection import SelectionDetector
from overlay import OverlayButton, ResultPopup, create_tray
from translator import Translator

# 确保应用程序只有一个实例运行
def ensure_single_instance():
    # 创建一个锁文件
    lock_file_path = os.path.join(tempfile.gettempdir(), 'translite.lock')
    lock = QLockFile(lock_file_path)
    
    # 尝试锁定文件，如果失败，说明已有实例运行
    if not lock.tryLock(100):
        print("TransLite 已经在运行中，程序将退出。")
        sys.exit(0)
    
    return lock


class TranslationWorker(QThread):
	"""翻译工作线程"""
	translation_finished = pyqtSignal(str, int, int)  # 翻译完成信号
	
	def __init__(self, translator, text, x, y):
		super().__init__()
		self.translator = translator
		self.text = text
		self.x = x
		self.y = y
	
	def run(self):
		"""在线程中执行翻译"""
		result, _ = self.translator.translate_auto(self.text)
		self.translation_finished.emit(result, self.x, self.y)


def show_startup_notification(tray_icon):
	"""显示程序启动通知"""
	try:
		# 使用托盘通知显示启动信息
		tray_icon.showMessage(
			"🚀 TransLite 已启动！",
			"🔍 选中文本按 F2 键进行翻译\n⚙️ 右键托盘查看设置选项",
			QSystemTrayIcon.Information,
			5000  # 显示5秒
		)
	except Exception as e:
		print(f"显示启动通知失败: {e}")
		# 如果托盘通知失败，显示消息框作为备用
		from PyQt5.QtWidgets import QMessageBox
		msg_box = QMessageBox()
		msg_box.setIcon(QMessageBox.Information)
		msg_box.setWindowTitle("TransLite 已启动")
		msg_box.setText("🎉 翻译工具已成功启动！")
		msg_box.setInformativeText("• 按 F2 键选择文本进行翻译\n• 程序将在托盘区域运行")
		msg_box.setStandardButtons(QMessageBox.Ok)
		msg_box.exec_()


def cleanup_and_exit(app, selection=None, translation_worker=None, tray_icon=None, lock=None):
	"""统一的资源清理函数，确保所有组件在退出前被正确释放"""
	print("正在清理资源...")
	
	# 清理翻译工作线程
	if translation_worker:
		try:
			translation_worker.quit()
			translation_worker.wait(1000)  # 等待最多1秒
			translation_worker.deleteLater()
		except Exception as e:
			print(f"清理翻译线程失败: {e}")
	
	# 清理键盘监听器
	if selection:
		try:
			selection.cleanup()
		except Exception as e:
			print(f"清理键盘监听器失败: {e}")
	
	# 清理系统托盘
	if tray_icon:
		try:
			tray_icon.setVisible(False)
			tray_icon.deleteLater()
		except Exception as e:
			print(f"清理系统托盘失败: {e}")
	
	# 清理应用程序
	if app:
		try:
			app.quit()
		except Exception as e:
			print(f"清理应用程序失败: {e}")
	
	print("资源清理完成")


def main() -> int:
	# 确保应用程序只有一个实例运行
	lock = ensure_single_instance()
	
	QCoreApplication.setOrganizationName("TransLite")
	QCoreApplication.setApplicationName("TransLite")

	app = QApplication(sys.argv)
	app.setQuitOnLastWindowClosed(False)

	translator = Translator()
	overlay = OverlayButton()
	popup = ResultPopup()

	# 创建系统托盘图标并检查是否成功
	tray_icon = create_tray(app, translator)
	if not tray_icon:
		# 如果系统不支持托盘，至少显示一个消息提示
		from PyQt5.QtWidgets import QMessageBox
		QMessageBox.information(None, "TransLite", "程序已启动，请使用F2键选择文本进行翻译")
	else:
		# 显示启动通知
		show_startup_notification(tray_icon)

	selection = SelectionDetector()
	translation_worker = None  # 翻译工作线程

	def on_selection(text: str, x: int, y: int) -> None:
		overlay.show_near(x, y, text)

	def on_request_translate(text: str, x: int, y: int) -> None:
		# 显示加载状态
		popup.show_loading(x, y)
		
		# 创建并启动翻译线程
		global translation_worker
		translation_worker = TranslationWorker(translator, text, x, y)
		translation_worker.translation_finished.connect(on_translation_finished)
		translation_worker.start()

	def on_translation_finished(result: str, x: int, y: int) -> None:
		# 翻译完成，显示结果
		popup.show_text(result, x, y)
		# 清理工作线程
		global translation_worker
		if translation_worker:
			translation_worker.deleteLater()
			translation_worker = None

	selection.selectionReady.connect(on_selection)
	overlay.translateRequested.connect(on_request_translate)

	# 设置退出信号处理
	if tray_icon:
		tray_icon.activated.connect(lambda reason: None)  # 防止默认行为
	
	try:
		return app.exec_()
	finally:
		# 程序退出时自动清理资源
		cleanup_and_exit(app, selection, translation_worker, tray_icon, lock)


if __name__ == "__main__":
	sys.exit(main())

