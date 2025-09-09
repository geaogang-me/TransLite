# TransLite

轻量级英中互译悬浮工具：选中文本后显示"译"按钮，点击即翻译。

## 安装

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 运行

```bash
.venv\Scripts\python app.py
```

或使用启动脚本：
```bash
start.bat
```

## 打包

```bash
python build_fixed.py
```

## 使用方法

1. 鼠标选中文本后，会在附近显示"译"按钮
2. 点击按钮进行翻译
3. 或者按F2键翻译当前选中的文本
4. 右键系统托盘图标可选择翻译服务

## 特性

- 英中自动互译
- 悬浮按钮界面
- F2快捷键支持
- 系统托盘集成
- 多翻译服务器支持
- 智能服务器选择
- 国内网络优化

## 项目结构

- `app.py` - 主程序入口
- `translator.py` - 翻译核心逻辑
- `overlay.py` - 界面组件和系统托盘
- `selection.py` - 文本选择检测
- `translator_config.json` - 翻译服务配置
- `build_fixed.py` - 打包脚本
- `start.bat` - 启动脚本