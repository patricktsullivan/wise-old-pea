@echo off
echo.
echo ========================================
echo    🎮 Wise Old Pea Bot Launcher 🎮
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://python.org
    echo.
    pause
    exit /b 1
)

echo ✅ Python found
python --version

REM Check if required files exist
if not exist "wise_old_pea.py" (
    echo ❌ Error: wise_old_pea.py not found
    echo Please ensure you're running this script from the bot directory
    echo.
    pause
    exit /b 1
)

if not exist "challenge_rules.json" (
    echo ❌ Error: challenge_rules.json not found
    echo This file is required for the bot to function
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo ❌ Error: .env file not found
    echo.
    echo Please create a .env file with your bot token:
    echo DISCORD_BOT_TOKEN=your_token_here
    echo.
    echo You can get a bot token from:
    echo https://discord.com/developers/applications
    echo.
    pause
    exit /b 1
)

echo ✅ Required files found

REM Check if dependencies are installed
echo.
echo 🔍 Checking dependencies...
python -c "import discord" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Discord.py not found, installing dependencies...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        echo.
        pause
        exit /b 1
    )
) else (
    echo ✅ Dependencies found
)

REM Check if directories exist, create if not
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo.
echo 🚀 Starting Wise Old Pea Bot...
echo.
echo ℹ️  Press Ctrl+C to stop the bot
echo ℹ️  Logs are saved to the logs/ directory
echo.

REM Start the bot
python wise_old_pea.py

REM If we get here, the bot has stopped
echo.
echo 🛑 Bot has stopped running
echo.
pause