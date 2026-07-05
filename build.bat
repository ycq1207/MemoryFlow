@echo off
echo ========================================
echo  MemoryFlow Build Script
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

echo [1/3] Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist MemoryFlow.spec del MemoryFlow.spec

echo [2/3] Building single exe...
pyinstaller --onefile --noconsole --name MemoryFlow --clean --add-data "poems/*.json;poems" main.py

if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo [3/3] Copying exe...
copy dist\MemoryFlow.exe MemoryFlow.exe

echo.
echo ========================================
echo  Build complete!
echo ========================================
echo  Output: MemoryFlow.exe
echo ========================================
pause
