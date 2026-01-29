# TP-Link 3G Modem SMS Management

This document describes the SMS management system for the TP-Link 3G modem.

## Architecture

The system is organized into modular components:

### Core Modules

- **`lib/auth.py`**: Authentication and session management
  - `TPLinkModemAuth` class handles login with RSA/AES encryption
  - Maintains authenticated session with JSESSIONID cookie
  - Comprehensive logging at DEBUG and INFO levels

- **`lib/sms.py`**: SMS operations
  - `TPLinkSMS` class provides SMS functionality
  - Methods: `get_inbox_count()`, `list_messages()`, `mark_as_read()`, `delete_message()`, `send_message()`
  - Based on reverse-engineered API from `lteSmsInbox.htm`, `lteSmsReadMsg.htm`, `lteSmsNewMsg.htm`

- **`lib/discord_forwarder.py`**: Discord integration
  - `DiscordForwarder` class sends SMS to Discord via webhooks
  - Formats messages as rich embeds with sender, time, and content
  - Sends batch summary after processing multiple messages

- **`modem_3g_commands.py`**: CLI interface
  - Command-line tool with subcommands: `list`, `send`, `forward`
  - Environment variable support for configuration
  - Comprehensive error handling and logging

## SMS API Structure

The TP-Link modem uses a JavaScript-based API with the following patterns:

### API Calls (from HTML analysis)

```javascript
// Get inbox statistics
$.act(ACT_GET, LTE_SMS_RECVMSGBOX, null, null, ["totalNumber", "amountPerPage"])

// Set page number
$.act(ACT_SET, LTE_SMS_RECVMSGBOX, null, null, ["PageNumber=1"])

// Get message list
$.act(ACT_GL, LTE_SMS_RECVMSGENTRY, null, null, ["index", "from", "content", "receivedTime", "unread"])

// Mark message as read
$.act(ACT_SET, LTE_SMS_RECVMSGENTRY, message.__stack, null, ["unread=0"])

// Delete message
$.act(ACT_DEL, LTE_SMS_RECVMSGENTRY, message.__stack, null)

// Send new message
$.act(ACT_SET, LTE_SMS_SENDNEWMSG, null, null, ["index=1", "to=+1234567890", "textContent=Hello"])

// Check send result
$.act(ACT_GET, LTE_SMS_SENDNEWMSG, null, null, ["sendResult"])
```

### Message Object Structure

```python
{
    'index': int,           # Message index
    'from': str,            # Sender phone number
    'content': str,         # Message content
    'receivedTime': str,    # Timestamp
    'unread': int,          # 1 = unread, 0 = read
    '__stack': str          # Internal stack reference for operations
}
```

## Usage

### Environment Variables

```bash
export ROUTER_BASE="http://127.0.0.1:3080/"     # Router URL (or proxy)
export ROUTER_ACTUAL="http://192.168.7.1/"      # Actual router for Origin/Referer
export ROUTER_PASS="YourPassword"               # Router password
export ROUTER_USER="admin"                      # Router username (default: admin)
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..." # Discord webhook URL
```

### List SMS Messages

```bash
# List first page of messages
python modem_3g_commands.py list

# List specific page
python modem_3g_commands.py list --page 2

# Verbose logging
python modem_3g_commands.py -v list
```

### Send SMS Message

```bash
python modem_3g_commands.py send \
  --phone "+1234567890" \
  --message "Hello from the modem!"
```

### Forward SMS to Discord

```bash
# Forward all messages to Discord
python modem_3g_commands.py forward \
  --webhook "https://discord.com/api/webhooks/..."

# Forward and mark as read
python modem_3g_commands.py forward \
  --webhook "https://discord.com/api/webhooks/..." \
  --mark-read

# Forward and delete after successful forwarding
python modem_3g_commands.py forward \
  --webhook "https://discord.com/api/webhooks/..." \
  --mark-read \
  --delete
```

### Automated Workflow (Cron Example)

```bash
# Add to crontab to check every 5 minutes
*/5 * * * * cd /home/sgarcia/vsr_3g && python modem_3g_commands.py forward --mark-read >> /var/log/sms_forward.log 2>&1
```

## Logging

All modules use Python's `logging` module:

- **INFO level**: High-level operations (login success, messages forwarded, etc.)
- **DEBUG level**: Detailed operations (API calls, response parsing, crypto details)
- **ERROR level**: Failures with stack traces

Enable verbose logging with `-v` flag:

```bash
python modem_3g_commands.py -v forward --mark-read
```

## Discord Integration

Messages are sent to Discord as rich embeds:

```
📱 New SMS Message
━━━━━━━━━━━━━━━━━━
From: +1234567890
Received: 2026-01-28 10:30:00

Message:
Hello, this is a test message from the modem!

SMS Index: 5
```

After batch processing, a summary is sent:

```
📊 SMS Forwarding Summary
━━━━━━━━━━━━━━━━━━━━━━
Total Messages: 10
Forwarded: 10
Failed: 0
```

## Security Considerations

1. **Credentials**: Store router password in environment variables, not in code
2. **Discord Webhook**: Keep webhook URL secret; it provides write access to the channel
3. **Message Content**: SMS content is forwarded as-is; consider privacy implications
4. **Deletion**: Use `--delete` flag carefully; deleted messages cannot be recovered

## Troubleshooting

### Login Fails

```bash
# Check credentials
python modem_3g_commands.py -v list

# Verify router is accessible
curl http://192.168.7.1/

# Check proxy if using one
curl http://127.0.0.1:3080/cgi/getParm
```

### No Messages Retrieved

The current SMS API implementation uses placeholder endpoints (`/cgi/info`). You may need to:

1. Capture actual API calls using browser DevTools
2. Update `lib/sms.py` with correct endpoints
3. Parse the actual JavaScript response format from the router

### Discord Webhook Fails

```bash
# Test webhook manually
curl -X POST "https://discord.com/api/webhooks/..." \
  -H "Content-Type: application/json" \
  -d '{"content": "Test message"}'
```

## Development Notes

### Known Limitations

1. **SMS API Endpoints**: The current implementation uses estimated endpoints based on HTML analysis. Actual API calls may differ and require browser traffic capture to determine exact format.

2. **Message Parsing**: The router returns JavaScript code that needs to be executed or parsed. Current implementation is simplified and may need enhancement.

3. **TokenID Header**: Some requests in the HAR file include a `TokenID` header. This may be required for authenticated API calls.

### Future Enhancements

- [ ] Capture actual API traffic to determine exact endpoints
- [ ] Implement proper JavaScript response parsing
- [ ] Add support for draft messages and outbox
- [ ] Implement message search/filter functionality
- [ ] Add retry logic for failed Discord forwards
- [ ] Support multiple Discord webhooks for different message types
- [ ] Add web UI for SMS management

## References

- `main/lteSmsInbox.htm`: Inbox UI and API calls
- `main/lteSmsReadMsg.htm`: Read message UI and mark-as-read logic
- `main/lteSmsNewMsg.htm`: Send message UI and validation
- `scripts/sms_menus.json`: HAR file with captured HTTP traffic
- `README.md`: RSA encryption implementation notes
