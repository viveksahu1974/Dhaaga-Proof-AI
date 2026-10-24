@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
echo.
echo ===================================================
echo            DHAAGAPROOF AI - LOCAL DEMO
 echo ===================================================
echo.
where py >nul 2>nul
if not errorlevel 1 goto USING_PY
where python >nul 2>nul
if not errorlevel 1 goto USING_PYTHON
echo Python not found. Install Python 3.11+ and add it to PATH.
goto END
:USING_PY
py -3 app.py
goto END
:USING_PYTHON
python app.py
:END
echo.
echo If the server stopped with an error, read the message above.
pause
