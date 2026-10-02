@echo off
rem Sonic Pipe Dream Builder: builds the Windows version (proj\Packaged\Windows).
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw -3 native\builder.py & exit /b)
where pythonw >nul 2>nul && (start "" pythonw native\builder.py & exit /b)
echo Python 3 is needed: https://www.python.org/downloads/
pause
