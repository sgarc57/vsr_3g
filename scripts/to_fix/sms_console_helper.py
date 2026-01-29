#!/usr/bin/env python3
"""
Helper script for working with SMS messages retrieved via browser console.
Since the TP-Link modem uses encrypted /cgi_gdpr API, the easiest way to
retrieve messages is through the browser console.

Usage:
    1. Run this script to get the JavaScript command
    2. Execute it in your browser console
    3. Paste the JSON output when prompted
    4. Script will parse and display/forward the messages
"""
import os
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(__file__))

from src.modem_sms.discord_forwarder import DiscordForwarder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_javascript_command():
    """Print the JavaScript command to execute in browser console."""
    print("\n" + "="*70)
    print("STEP 1: Execute this JavaScript in your browser console")
    print("="*70)
    print("""
// Navigate to http://192.168.7.1/ and login first
// Then open Developer Tools (F12) -> Console tab
// Paste and execute this:

$.act(ACT_SET, LTE_SMS_RECVMSGBOX, null, null, ["PageNumber=0"]);
$.exe();
var smsInboxPagelist = $.act(ACT_GL, LTE_SMS_RECVMSGENTRY, null, null, 
    ["index", "from", "content", "receivedTime", "unread"]);
$.exe();
copy(smsInboxPagelist);
console.log("✅ Messages copied to clipboard! Paste them in the terminal.");
""")
    print("="*70 + "\n")


def parse_messages(json_text: str):
    """Parse the JSON messages from browser console."""
    try:
        messages = json.loads(json_text)
        if not isinstance(messages, list):
            logger.error("Expected a list of messages")
            return None
        
        logger.info(f"Parsed {len(messages)} messages")
        return messages
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return None


def display_messages(messages):
    """Display messages in a readable format."""
    print("\n" + "="*70)
    print(f"📬 Found {len(messages)} SMS Messages")
    print("="*70 + "\n")
    
    for i, msg in enumerate(messages, 1):
        status = "🔵 UNREAD" if msg.get('unread') == '1' else "✅ Read"
        print(f"{status} - Message {i}/{len(messages)}")
        print(f"  From: {msg.get('from', 'Unknown')}")
        print(f"  Time: {msg.get('receivedTime', 'Unknown')}")
        print(f"  Index: {msg.get('index', 'Unknown')}")
        
        content = msg.get('content', '')
        if len(content) > 100:
            print(f"  Message: {content[:100]}...")
        else:
            print(f"  Message: {content}")
        print()


def forward_to_discord(messages, webhook_url=None, bot_token=None, channel_id=None):
    """Forward messages to Discord."""
    if webhook_url:
        discord = DiscordForwarder(webhook_url=webhook_url)
    elif bot_token and channel_id:
        discord = DiscordForwarder(bot_token=bot_token, channel_id=channel_id)
    else:
        logger.error("No Discord configuration provided")
        return
    
    forwarded = 0
    failed = 0
    
    for msg in messages:
        if discord.send_sms_to_discord(msg):
            forwarded += 1
        else:
            failed += 1
    
    discord.send_batch_summary(len(messages), forwarded, failed)
    
    print(f"\n📊 Discord Forward Summary:")
    print(f"  Total: {len(messages)}")
    print(f"  Forwarded: {forwarded}")
    print(f"  Failed: {failed}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Helper for SMS retrieval via browser console",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--forward', action='store_true',
                        help='Forward messages to Discord after parsing')
    parser.add_argument('--webhook', default=os.environ.get('DISCORD_WEBHOOK'),
                        help='Discord webhook URL')
    parser.add_argument('--bot-token', default=os.environ.get('DISCORD_BOT_TOKEN'),
                        help='Discord bot token')
    parser.add_argument('--channel-id', default=os.environ.get('DISCORD_CHANNEL_ID'),
                        help='Discord channel ID')
    parser.add_argument('--json-file',
                        help='Read messages from JSON file instead of stdin')
    
    args = parser.parse_args()
    
    # Print the JavaScript command
    print_javascript_command()
    
    # Get messages
    if args.json_file:
        logger.info(f"Reading messages from {args.json_file}")
        with open(args.json_file, 'r') as f:
            json_text = f.read()
    else:
        print("STEP 2: Paste the JSON output here (Ctrl+D when done):")
        print("-" * 70)
        json_text = sys.stdin.read()
    
    # Parse messages
    messages = parse_messages(json_text)
    if not messages:
        logger.error("No messages to process")
        return 1
    
    # Display messages
    display_messages(messages)
    
    # Forward to Discord if requested
    if args.forward:
        if args.webhook or (args.bot_token and args.channel_id):
            forward_to_discord(messages, args.webhook, args.bot_token, args.channel_id)
        else:
            logger.error("Discord forwarding requires --webhook or (--bot-token + --channel-id)")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
