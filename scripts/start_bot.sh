#!/bin/bash

echo ""
echo "========================================"
echo "   🎮 Wise Old Pea Bot Launcher 🎮"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ Error: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    print_error "Python is not installed or not in PATH"
    echo "Please install Python 3.8 or higher"
    echo "Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "macOS: brew install python3"
    echo "Or download from: https://python.org"
    echo ""
    exit 1
fi

# Use python3 if available, otherwise python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
else
    PYTHON_CMD="python"
    PIP_CMD="pip"
fi

print_success "Python found"
$PYTHON_CMD --version

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "Python 3.8 or higher is required (found: $PYTHON_VERSION)"
    exit 1
fi

# Check if required files exist
if [ ! -f "wise_old_pea.py" ]; then
    print_error "wise_old_pea.py not found"
    echo "Please ensure you're running this script from the bot directory"
    echo ""
    exit 1
fi

if [ ! -f "challenge_rules.json" ]; then
    print_error "challenge_rules.json not found"
    echo "This file is required for the bot to function"
    echo ""
    exit 1
fi

if [ ! -f ".env" ]; then
    print_error ".env file not found"
    echo ""
    echo "Please create a .env file with your bot token:"
    echo "DISCORD_BOT_TOKEN=your_token_here"
    echo ""
    echo "You can get a bot token from:"
    echo "https://discord.com/developers/applications"
    echo ""
    exit 1
fi

print_success "Required files found"

# Check if dependencies are installed
echo ""
print_info "Checking dependencies..."
if ! $PYTHON_CMD -c "import discord" &> /dev/null; then
    print_warning "Discord.py not found, installing dependencies..."
    echo ""
    $PIP_CMD install -r requirements.txt
    if [ $? -ne 0 ]; then
        print_error "Failed to install dependencies"
        echo ""
        exit 1
    fi
else
    print_success "Dependencies found"
fi

# Check if directories exist, create if not
[ ! -d "data" ] && mkdir data
[ ! -d "logs" ] && mkdir logs

echo ""
print_info "Starting Wise Old Pea Bot..."
echo ""
print_info "Press Ctrl+C to stop the bot"
print_info "Logs are saved to the logs/ directory"
echo ""

# Set up signal handling to gracefully shutdown
trap 'echo ""; print_info "Shutting down bot..."; exit 0' INT TERM

# Start the bot
$PYTHON_CMD wise_old_pea.py

# If we get here, the bot has stopped
echo ""
print_info "Bot has stopped running"
echo ""