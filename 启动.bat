@echo off
rem 双击启动 LLD 网络连接管理工具（自动激活虚拟环境并打开浏览器）
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
    echo [错误] 未找到虚拟环境，请先执行: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python init_db.py
rem 禁用 Streamlit 首次运行的邮箱订阅提示
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
streamlit run app.py
pause
