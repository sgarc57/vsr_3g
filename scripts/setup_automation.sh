#!/bin/bash
#
# Setup script for fully automated SMS forwarding system
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "SMS Auto-Forward Setup (Fully Automated)"
echo "=========================================="
echo ""

# Check if Node.js is installed
echo "Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo ""
    echo "Please install Node.js first:"
    echo "  Ubuntu/Debian: sudo apt-get install nodejs npm"
    echo "  CentOS/RHEL: sudo yum install nodejs npm"
    echo "  Or download from: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "✅ Node.js installed: $NODE_VERSION"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed"
    exit 1
fi

NPM_VERSION=$(npm --version)
echo "✅ npm installed: $NPM_VERSION"
echo ""

# Install Puppeteer
echo "Installing Puppeteer dependencies..."
cd "$SCRIPT_DIR"

if [ ! -d "node_modules" ]; then
    npm install
    echo "✅ Puppeteer installed"
else
    echo "✅ Puppeteer already installed"
fi
echo ""

# Make scripts executable
echo "Making scripts executable..."
chmod +x sms_cron_job.sh
chmod +x sms_auto_forward.py
chmod +x generate_delete_script.py
chmod +x puppeteer_sms_retriever.js
echo "✅ Scripts are executable"
echo ""

# Check environment variables
echo "Checking environment variables..."
if [ -z "$DISCORD_BOT_TOKEN" ] && [ -z "$DISCORD_WEBHOOK" ]; then
    echo "⚠️  Discord credentials not set"
    echo ""
    echo "Please set one of the following:"
    echo "  export DISCORD_BOT_TOKEN=\"your_token\""
    echo "  export DISCORD_CHANNEL_ID=\"your_channel_id\""
    echo "  OR"
    echo "  export DISCORD_WEBHOOK=\"https://discord.com/api/webhooks/...\""
    echo ""
    echo "Add to ~/.bashrc to make permanent"
else
    echo "✅ Discord credentials configured"
fi
echo ""

# Check modem credentials
if [ -z "$ROUTER_PASS" ]; then
    echo "⚠️  Modem password not set (using default: admin)"
    echo "  To change: export ROUTER_PASS=\"your_password\""
else
    echo "✅ Modem password configured"
fi
echo ""

# Test Puppeteer script
echo "Testing Puppeteer SMS retrieval..."
TEST_OUTPUT="${SCRIPT_DIR}/data/test_retrieval.json"
if node "${SCRIPT_DIR}/puppeteer_sms_retriever.js" "$TEST_OUTPUT" "${SCRIPT_DIR}/data/forwarded_state.json" 2>&1 | grep -q "completed successfully"; then
    echo "✅ Puppeteer test successful"
    if [ -f "$TEST_OUTPUT" ]; then
        MESSAGE_COUNT=$(cat "$TEST_OUTPUT" | grep -o '"index"' | wc -l)
        echo "   Retrieved $MESSAGE_COUNT messages"
        rm "$TEST_OUTPUT"
    fi
else
    echo "⚠️  Puppeteer test had issues (check logs above)"
    echo "   This might be normal if there are no messages or login failed"
fi
echo ""

# Setup instructions
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Set Discord credentials (if not already set):"
echo "   echo 'export DISCORD_BOT_TOKEN=\"your_token\"' >> ~/.bashrc"
echo "   echo 'export DISCORD_CHANNEL_ID=\"your_channel_id\"' >> ~/.bashrc"
echo "   source ~/.bashrc"
echo ""
echo "2. Add to crontab for automatic execution every minute:"
echo "   crontab -e"
echo "   Add: * * * * * ${SCRIPT_DIR}/sms_cron_job.sh"
echo ""
echo "3. Test manually:"
echo "   ${SCRIPT_DIR}/sms_cron_job.sh"
echo ""
echo "4. Monitor logs:"
echo "   tail -f ${SCRIPT_DIR}/logs/*.log"
echo ""
echo "The system will now:"
echo "  ✅ Automatically retrieve SMS from modem (Puppeteer)"
echo "  ✅ Forward new messages to Discord"
echo "  ✅ Delete forwarded messages from modem"
echo "  ✅ Track state to prevent duplicates"
echo ""
echo "No manual intervention required!"
echo "=========================================="
