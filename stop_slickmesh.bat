@echo off
echo Stopping any running SlickMesh AI processes on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a
)
echo SlickMesh AI server stopped successfully.
