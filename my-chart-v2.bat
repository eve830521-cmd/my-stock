@echo off
REM 1. Free port 8000 (ignore errors if not in use)
FOR /F "tokens=5" %%T IN ('netstat -a -n -o ^| findstr "0.0.0.0:8000" ') DO (
    TaskKill.exe /F /PID %%T > NUL 2>&1
)

REM 2. Start Backend Server in a new window using python -m to avoid path issues
start "MyStock Server" cmd /k "python -m uvicorn app:app --host 0.0.0.0 --port 8000"

REM 3. Wait for 3 seconds to let the server start completely
timeout /t 3 /nobreak > NUL

REM 4. Open default browser to the dashboard
start http://localhost:8000
