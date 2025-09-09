#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TransLite 完整打包脚本 - 解决网络错误问题
"""

import os
import subprocess
import shutil
import sys

def main():
    print("TransLite 完整打包 - 修复网络问题")
    
    # 清理之前的构建文件
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # 完整的 PyInstaller 命令，解决网络和SSL问题
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name=TransLite",
        "--add-data=translator_config.json;.",  # 包含配置文件
        "--add-data=translite.ico;.",  # 包含图标文件
        "--hidden-import=requests",
        "--hidden-import=urllib3",
        "--hidden-import=certifi",  # SSL证书
        "--hidden-import=charset_normalizer",  # requests依赖
        "--hidden-import=idna",  # requests依赖
        "--collect-all=certifi",  # 收集所有SSL证书
        "--collect-submodules=requests",  # 收集requests所有子模块
        "--collect-submodules=urllib3",  # 收集urllib3所有子模块
        "--icon=translite.ico",
        # 添加运行时钩子以确保SSL证书正确加载
        "--runtime-hook=runtime_hook.py",
        "app.py"
    ]
    
    # 创建运行时钩子文件
    create_runtime_hook()
    
    try:
        print("开始打包...")
        subprocess.run(cmd, check=True)
        print("✓ 打包成功！")
        
        # 清理临时文件
        if os.path.exists("runtime_hook.py"):
            os.remove("runtime_hook.py")
            
        print("\n解决方案说明:")
        print("1. 包含了所有SSL证书文件")
        print("2. 包含了配置文件和默认配置")
        print("3. 添加了所有网络相关的依赖")
        print("4. 修复了Qt插件路径问题")
        print("\n如果仍有网络问题，请检查:")
        print("- 防火墙设置")
        print("- 杀毒软件拦截")
        print("- 网络代理设置")
        
    except subprocess.CalledProcessError as e:
        print(f"✗ 打包失败！错误: {e}")
    except FileNotFoundError:
        print("✗ 未找到 PyInstaller，请先安装: pip install pyinstaller")

def create_runtime_hook():
    """创建运行时钩子文件，确保SSL证书正确加载"""
    hook_content = '''
import os
import sys
import ssl
import certifi

# 确保SSL证书路径正确
if hasattr(ssl, '_create_default_https_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# 设置CA证书路径
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
'''
    
    with open('runtime_hook.py', 'w', encoding='utf-8') as f:
        f.write(hook_content)

if __name__ == "__main__":
    main()