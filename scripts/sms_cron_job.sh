#!/bin/bash
#
# SMS Auto-Forward Cron Job Script (Fully Automated)
#
# This script is designed to run via cron every minute to:
# 1. Retrieve SMS messages from modem (automated via Puppeteer)
# 2. Forward new messages to Discord
# 3. Delete forwarded messages from modem
#
# Setup:
#   1. Install Node.js and Puppeteer: npm install puppeteer
#   2. Make executable: chmod +x scripts/sms_cron_job.sh
#   3. Add to crontab: * * * * * /home/sgarcia/vsr_3g/scripts/sms_cron_job.sh
#

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/venv/bin/python3"
NODE_BIN="node"
PUPPETEER_SCRIPT="${SCRIPT_DIR}/puppeteer_sms_retriever.js"
MESSAGES_FILE="${SCRIPT_DIR}/data/current_messages.json"
STATE_FILE="${SCRIPT_DIR}/data/forwarded_state.json"
LOG_FILE="${SCRIPT_DIR}/logs/cron.log"

# Create logs directory if it doesn't exist
mkdir -p "${SCRIPT_DIR}/logs"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Starting SMS auto-forward cron job (fully automated)"

# Step 1: Retrieve SMS messages from modem using Puppeteer
log "Step 1: Retrieving SMS messages from modem..."
if $NODE_BIN "$PUPPETEER_SCRIPT" "$MESSAGES_FILE" "$STATE_FILE" 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ SMS retrieval completed"
else
    log "❌ SMS retrieval failed"
    exit 1
fi

# Check if messages file was created
if [ ! -f "$MESSAGES_FILE" ]; then
    log "❌ Messages file not created: $MESSAGES_FILE"
    exit 1
fi

# Step 2: Forward new messages to Discord
log "Step 2: Forwarding new messages to Discord..."
if $VENV_PYTHON "${SCRIPT_DIR}/sms_auto_forward.py" \
    --messages-file "$MESSAGES_FILE" \
    --state-file "$STATE_FILE" 2>&1 | tee -a "$LOG_FILE"; then
    
    log "✅ Forwarding completed successfully"
else
    log "❌ Forwarding failed"
    exit 1
fi

# Step 3: Delete forwarded messages from modem
log "Step 3: Deleting forwarded messages from modem..."
if [ -f "$STATE_FILE" ]; then
    if $NODE_BIN "$PUPPETEER_SCRIPT" "$MESSAGES_FILE" "$STATE_FILE" --delete 2>&1 | tee -a "$LOG_FILE"; then
        log "✅ Messages deleted from modem"
    else
        log "⚠️  Deletion failed (messages will remain on modem)"
    fi
else
    log "⚠️  No state file found, skipping deletion"
fi

log "✅ Cron job completed - SMS retrieved, forwarded, and deleted"
log "=========================================="
