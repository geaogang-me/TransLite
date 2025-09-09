# type: ignore[attr-defined]
import json
import re
import typing as t
from urllib.parse import quote_plus
import time
import os
import sys

import requests


_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


class Translator:
	def __init__(self, libre_url: str = "https://libretranslate.de/translate", timeout_sec: float = 8.0, config_file: t.Optional[str] = None):
		# 加载配置文件
		self.config = self._load_config(config_file)
		
		self.libre_url = libre_url
		self.timeout_sec = self.config.get('timeout_seconds', timeout_sec)
		# 国内可访问的LibreTranslate镜像服务器列表
		self.backup_libre_urls = self.config.get('libre_servers', [
			"https://translate.fedilab.app/translate",
			"https://translate.argosopentech.com/translate",
			"https://translate.astian.org/translate",
			"https://libretranslate.pussthcat.org/translate",
			"https://translate.mentality.rip/translate",
			"https://libretranslate.eownerdead.dedyn.io/translate",
		])[1:]  # 去掉第一个（主服务器）
		
		# 请求头，模拟浏览器
		user_agent = self.config.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
		self.headers = {
			'User-Agent': user_agent,
			'Accept': 'application/json, text/plain, */*',
			'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
			'Content-Type': 'application/json'
		}
		
		self.enable_google_fallback = self.config.get('enable_google_fallback', True)
		self.debug_output = self.config.get('enable_debug_output', False)
		
		# 翻译模式：'auto' 或 'manual_X' (X为服务器索引)
		self._preferred_mode = 'auto'

	def _load_config(self, config_file: t.Optional[str] = None) -> dict:
		"""加载配置文件"""
		if config_file is None:
			# 处理打包后的路径问题
			if getattr(sys, 'frozen', False):
				# 打包后的exe文件
				base_path = sys._MEIPASS
			else:
				# 开发环境
				base_path = os.path.dirname(__file__)
			config_file = os.path.join(base_path, 'translator_config.json')
		
		try:
			if os.path.exists(config_file):
				with open(config_file, 'r', encoding='utf-8') as f:
					return json.load(f)
			else:
				print(f"配置文件不存在: {config_file}")
		except Exception as e:
			print(f"加载配置文件失败: {e}")
		
		# 返回默认配置
		return self._get_default_config()

	def _get_default_config(self) -> dict:
		"""获取默认配置，用于打包后无法读取配置文件的情况"""
		return {
			'timeout_seconds': 8.0,
			'libre_servers': [
				"https://libretranslate.de/translate",
				"https://translate.fedilab.app/translate",
				"https://translate.argosopentech.com/translate",
				"https://translate.astian.org/translate",
				"https://libretranslate.pussthcat.org/translate",
				"https://translate.mentality.rip/translate",
				"https://libretranslate.eownerdead.dedyn.io/translate"
			],
			'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
			'enable_google_fallback': True,
			'enable_debug_output': False
		}

	def _debug_print(self, message: str):
		"""调试输出"""
		if self.debug_output:
			print(message)

	@staticmethod
	def _contains_chinese(text: str) -> bool:
		return bool(_CHINESE_RE.search(text))

	def _try_libre_translate(self, text: str, source: str, target: str, url: str) -> t.Optional[str]:
		"""尝试使用LibreTranslate服务翻译"""
		try:
			payload = {
				"q": text, 
				"source": source, 
				"target": target, 
				"format": "text"
			}
			# 尝试使用POST方式（传统LibreTranslate）
			resp = requests.post(url, data=payload, timeout=self.timeout_sec, headers=self.headers)
			if resp.ok:
				data = resp.json()
				if isinstance(data, dict) and "translatedText" in data:
					return data["translatedText"]
					
			# 如果POST失败，尝试JSON格式
			headers_json = self.headers.copy()
			headers_json['Content-Type'] = 'application/json'
			resp = requests.post(url, json=payload, timeout=self.timeout_sec, headers=headers_json)
			if resp.ok:
				data = resp.json()
				if isinstance(data, dict) and "translatedText" in data:
					return data["translatedText"]
		except Exception as e:
			self._debug_print(f"LibreTranslate错误 ({url}): {e}")
		return None

	def _try_google_translate(self, text: str, target: str) -> t.Optional[str]:
		"""尝试使用Google翻译服务"""
		if not self.enable_google_fallback:
			return None
			
		try:
			url = (
				"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl="
				+ target
				+ "&dt=t&q="
				+ quote_plus(text)
			)
			resp = requests.get(url, timeout=self.timeout_sec, headers=self.headers)
			if resp.ok:
				data = json.loads(resp.text)
				if data and isinstance(data, list) and data[0]:
					segments = [seg[0] for seg in data[0] if seg and seg[0]]
					return "".join(segments)
		except Exception as e:
			self._debug_print(f"Google翻译错误: {e}")
		return None

	def translate_auto(self, text: str) -> t.Tuple[str, str]:
		"""
		自动检测语言并翻译，支持手动指定服务器
		返回: (translated_text, service_used)
		"""
		source = "zh" if self._contains_chinese(text) else "en"
		target = "en" if source == "zh" else "zh"
		
		self._debug_print(f"开始翻译: {text[:50]}{'...' if len(text) > 50 else ''} ({source} -> {target})")
		self._debug_print(f"当前模式: {self._preferred_mode}")
		
		# 手动指定服务器模式
		if self._preferred_mode.startswith('manual_'):
			server_idx = int(self._preferred_mode.split('_')[1])
			all_servers = [self.libre_url] + self.backup_libre_urls
			
			if 0 <= server_idx < len(all_servers):
				selected_url = all_servers[server_idx]
				self._debug_print(f"使用指定服务器: {selected_url}")
				
				result = self._try_libre_translate(text, source, target, selected_url)
				if result:
					server_name = "主要LibreTranslate" if server_idx == 0 else f"备用服务器 {server_idx}"
					self._debug_print(f"翻译成功（{server_name}）: {result[:50]}{'...' if len(result) > 50 else ''}")
					return result, f"manual_libre_{server_idx}"
				else:
					self._debug_print(f"指定服务器失败，回退到智能模式")
					# 如果指定服务器失败，回退到智能模式
					# 但不修改 _preferred_mode，保持用户选择
		
		# 智能选择模式（默认或回退）
		# 策略1: 尝试主要的LibreTranslate服务器
		result = self._try_libre_translate(text, source, target, self.libre_url)
		if result:
			self._debug_print(f"翻译成功（主LibreTranslate）: {result[:50]}{'...' if len(result) > 50 else ''}")
			return result, "libre"
		
		# 策略2: 尝试备用的LibreTranslate服务器
		for i, backup_url in enumerate(self.backup_libre_urls):
			self._debug_print(f"尝试备用LibreTranslate服务器 {i+1}: {backup_url}")
			result = self._try_libre_translate(text, source, target, backup_url)
			if result:
				self._debug_print(f"翻译成功（备用LibreTranslate {i+1}）: {result[:50]}{'...' if len(result) > 50 else ''}")
				return result, f"libre_backup_{i+1}"
		
		# 策略3: 尝试Google翻译（国外网络可用）
		if self.enable_google_fallback:
			self._debug_print("尝试Google翻译...")
			result = self._try_google_translate(text, target)
			if result:
				self._debug_print(f"翻译成功（Google翻译）: {result[:50]}{'...' if len(result) > 50 else ''}")
				return result, "google"
		
		# 所有服务都失败
		self._debug_print("所有翻译服务都失败")
		return "(网络错误：翻译失败)", "none"
	
	def get_available_servers(self) -> t.List[t.Tuple[int, str, str]]:
		"""获取可用服务器列表，返回 (索引, 名称, URL) 的列表"""
		all_servers = [self.libre_url] + self.backup_libre_urls
		server_info = []
		
		for i, url in enumerate(all_servers):
			if i == 0:
				name = "主要LibreTranslate服务器"
			else:
				name = f"备用服务器 {i}"
			server_info.append((i, name, url))
		
		return server_info
	
	def set_preferred_mode(self, mode: str) -> None:
		"""设置首选模式：'auto' 或 'manual_X' (X为服务器索引)"""
		if mode == 'auto' or mode.startswith('manual_'):
			self._preferred_mode = mode
			self._debug_print(f"切换到模式: {mode}")
		else:
			raise ValueError(f"无效的模式: {mode}")
	
	def get_current_mode(self) -> str:
		"""获取当前模式"""
		return self._preferred_mode
	
	def test_server(self, server_index: int) -> bool:
		"""测试指定服务器是否可用"""
		all_servers = [self.libre_url] + self.backup_libre_urls
		if 0 <= server_index < len(all_servers):
			url = all_servers[server_index]
			test_text = "Hello"
			result = self._try_libre_translate(test_text, "en", "zh", url)
			return result is not None
		return False

