@echo off
echo 正在启动Windows设置界面应用...
echo.

echo 1. 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo 2. 安装依赖包...
pip install -r requirements.txt

echo 3. 初始化数据库...
python database.py

echo 4. 启动Flask应用...
echo.
echo 应用将在 http://127.0.0.1:5000 启动
echo 按 Ctrl+C 停止应用
echo.
python app.py

pause
