# SMS Auto-Forward Cron Job Setup Guide

This guide explains how to set up automated SMS forwarding that runs every minute via cron.

## Overview

The automated system works in two phases:

### Phase 1: Retrieve SMS (Browser Console - Manual)
Since the modem uses encrypted API, you need to manually retrieve SMS via browser console and save to a JSON file.

### Phase 2: Forward & Delete (Automated via Cron)
The cron job automatically:
1. Reads the JSON file with SMS messages
2. Forwards new messages to Discord
3. Tracks which messages were forwarded
4. Generates JavaScript to delete forwarded messages

## Quick Setup

### 1. Make Scripts Executable

```bash
cd /home/sgarcia/vsr_3g/scripts
chmod +x sms_cron_job.sh
chmod +x sms_auto_forward.py
chmod +x generate_delete_script.py
```

### 2. Set Environment Variables

Add to your `~/.bashrc` or `~/.profile`:

```bash
export DISCORD_BOT_TOKEN="your_bot_token_here"
export DISCORD_CHANNEL_ID="your_channel_id_here"
# OR use webhook:
# export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
```

Then reload:
```bash
source ~/.bashrc
```

### 3. Create Initial Messages File

Open browser, navigate to http://192.168.7.1/, login, then open Developer Tools (F12) -> Console:

```javascript
$.act(ACT_SET, LTE_SMS_RECVMSGBOX, null, null, ["PageNumber=0"]);
$.exe();
var smsInboxPagelist = $.act(ACT_GL, LTE_SMS_RECVMSGENTRY, null, null, 
    ["index", "from", "content", "receivedTime", "unread"]);
$.exe();
console.log(JSON.stringify(smsInboxPagelist, null, 2));
```

Copy the output and save to: `/home/sgarcia/vsr_3g/scripts/data/current_messages.json`

### 4. Test the Script Manually

```bash
cd /home/sgarcia/vsr_3g/scripts
./sms_cron_job.sh
```

Check the logs:
```bash
tail -f logs/cron.log
tail -f logs/sms_auto_forward.log
```

### 5. Add to Crontab

```bash
crontab -e
```

Add this line to run every minute:
```
* * * * * /home/sgarcia/vsr_3g/scripts/sms_cron_job.sh
```

## Workflow

### Every Minute (Automated)

1. **Cron runs** `sms_cron_job.sh`
2. **Script checks** if `data/current_messages.json` exists and is recent
3. **Forwards new messages** to Discord (skips already-forwarded ones)
4. **Generates deletion script** at `data/delete_messages.js`
5. **Logs everything** to `logs/cron.log` and `logs/sms_auto_forward.log`

### Periodically (Manual - Every Few Minutes)

1. **Update messages**: Run the browser console JavaScript and update `current_messages.json`
2. **Delete forwarded messages**: Execute the generated `data/delete_messages.js` in browser console

## File Structure

```
scripts/
├── data/
│   ├── current_messages.json      # SMS messages from browser (you update this)
│   ├── forwarded_state.json       # Tracks forwarded messages (auto-managed)
│   └── delete_messages.js         # Generated deletion script (auto-generated)
├── logs/
│   ├── cron.log                   # Cron job execution log
│   └── sms_auto_forward.log       # Detailed forwarding log
├── sms_cron_job.sh               # Main cron script
├── sms_auto_forward.py           # Forwarding logic
└── generate_delete_script.py     # Deletion script generator
```

## Manual Commands

### Show Browser Console Instructions
```bash
cd /home/sgarcia/vsr_3g/scripts
venv/bin/python3 sms_auto_forward.py --show-instructions
```

### Reset State (Re-forward All Messages)
```bash
venv/bin/python3 sms_auto_forward.py --reset-state
```

### Test Forwarding with Custom File
```bash
venv/bin/python3 sms_auto_forward.py --messages-file data/test_messages.json
```

### View Logs
```bash
# Cron execution log
tail -f logs/cron.log

# Detailed forwarding log
tail -f logs/sms_auto_forward.log

# Follow both
tail -f logs/*.log
```

## Automation Script for SMS Retrieval (Optional)

For fully automated SMS retrieval, you can create a browser automation script:

```bash
# Create a script that:
# 1. Opens browser with Selenium/Puppeteer
# 2. Logs into modem
# 3. Executes JavaScript to get messages
# 4. Saves to current_messages.json
# 5. Executes delete_messages.js if it exists
```

This would make the entire process fully automated.

## Troubleshooting

### Messages Not Forwarding

1. Check if `current_messages.json` exists and is valid JSON
2. Check logs: `tail -f logs/sms_auto_forward.log`
3. Verify Discord credentials are set
4. Test manually: `./sms_cron_job.sh`

### Duplicate Messages

The system tracks forwarded messages in `forwarded_state.json`. If you want to re-forward:
```bash
venv/bin/python3 sms_auto_forward.py --reset-state
```

### Cron Not Running

1. Check crontab: `crontab -l`
2. Check cron logs: `grep CRON /var/log/syslog`
3. Ensure script is executable: `chmod +x sms_cron_job.sh`
4. Use absolute paths in crontab

### Messages File Stale

The cron job warns if `current_messages.json` is older than 5 minutes. Update it via browser console.

## Production Recommendations

1. **Set up log rotation** to prevent logs from growing too large
2. **Monitor Discord rate limits** (max ~50 messages per minute)
3. **Update messages file regularly** (every 1-2 minutes via browser console)
4. **Backup state file** periodically to avoid re-forwarding on reset
5. **Set up alerts** if forwarding fails consistently

## Example Cron Schedule

```bash
# Run every minute
* * * * * /home/sgarcia/vsr_3g/scripts/sms_cron_job.sh

# Or run every 2 minutes
*/2 * * * * /home/sgarcia/vsr_3g/scripts/sms_cron_job.sh

# Run every minute during business hours only
* 9-17 * * 1-5 /home/sgarcia/vsr_3g/scripts/sms_cron_job.sh
```

## Security Notes

1. **Protect credentials**: Never commit Discord tokens to git
2. **Secure log files**: Logs may contain message content
3. **File permissions**: Ensure only your user can read state files
4. **Network security**: Consider VPN if accessing modem remotely

## Next Steps

After setup, the system will:
- ✅ Automatically forward new SMS to Discord every minute
- ✅ Track forwarded messages to avoid duplicates
- ✅ Generate deletion scripts for cleanup
- ✅ Log all activity for monitoring

You only need to:
- 🔄 Update `current_messages.json` periodically via browser console
- 🗑️ Execute generated `delete_messages.js` to clean up forwarded messages
