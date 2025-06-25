#!/bin/bash

echo ""
echo "========================================"
echo "   🎮 Wise Old Pea Bot Setup 🎮"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Make start script executable
if [ -f "start_bot.sh" ]; then
    chmod +x start_bot.sh
    print_success "Made start_bot.sh executable"
else
    print_error "start_bot.sh not found"
fi

# Create .env template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "DISCORD_BOT_TOKEN=your_bot_token_here" > .env
    print_success "Created .env template"
    echo ""
    print_warning "Please edit .env and add your Discord bot token!"
    echo "You can get a bot token from: https://discord.com/developers/applications"
else
    print_info ".env file already exists"
fi

# Create directories
mkdir -p data logs
print_success "Created data and logs directories"

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    print_info "Installing dependencies..."
    
    # Use python3 if available, otherwise python
    if command -v python3 &> /dev/null; then
        PIP_CMD="pip3"
    else
        PIP_CMD="pip"
    fi
    
    $PIP_CMD install -r requirements.txt
    if [ $? -eq 0 ]; then
        print_success "Dependencies installed"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi
else
    print_warning "requirements.txt not found"
fi

echo ""
print_success "Setup complete!"
echo ""
print_info "Next steps:"
echo "1. Edit .env file with your Discord bot token"
echo "2. Ensure challenge_rules.json is in this directory"
echo "3. Run ./start_bot.sh to start the bot"
echo ""
print_info "For Windows users: Use start_bot.bat instead"
echo ""