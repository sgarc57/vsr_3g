import argparse
import logging
import os
import sys
from typing import Optional

from src.modem_sms.auth import TPLinkModemAuth
from src.modem_sms.sms import TPLinkSMS
from src.modem_sms.discord_forwarder import DiscordForwarder


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def login_to_modem(base_url: str, password: str, username: str = "admin") -> Optional[TPLinkModemAuth]:
    """Login to the modem and return authenticated session."""
    logger = logging.getLogger(__name__)
    logger.info("Attempting to login to modem...")
    
    auth = TPLinkModemAuth(base_url=base_url, username=username, password=password)
    if auth.login():
        logger.info("✅ Successfully logged in to modem")
        return auth
    else:
        logger.error("❌ Login failed")
        return None


def cmd_list_sms(auth: TPLinkModemAuth, args):
    """List SMS messages."""
    logger = logging.getLogger(__name__)
    sms = TPLinkSMS(auth.session, auth.base_url)
    
    # Get inbox count
    inbox_info = sms.get_inbox_count()
    if inbox_info:
        print(f"\n📬 Inbox: {inbox_info['totalNumber']} total messages")
    
    # List messages
    messages = sms.list_messages(page=args.page)
    if messages:
        print(f"\n📨 Messages (Page {args.page}):")
        for msg in messages:
            status = "🔵 Unread" if msg.get('unread') == 1 else "✅ Read"
            print(f"\n{status} - From: {msg.get('from', 'Unknown')}")
            print(f"  Time: {msg.get('receivedTime', 'Unknown')}")
            print(f"  Message: {msg.get('content', '')[:100]}...")
    else:
        print("No messages found or error retrieving messages.")


def cmd_send_sms(auth: TPLinkModemAuth, args):
    """Send a new SMS message."""
    logger = logging.getLogger(__name__)
    sms = TPLinkSMS(auth.session, auth.base_url)
    
    print(f"\n📤 Sending SMS to {args.phone}...")
    success = sms.send_message(args.phone, args.message)
    
    if success:
        print("✅ Message sent successfully!")
    else:
        print("❌ Failed to send message.")
        sys.exit(1)


def cmd_forward_to_discord(auth: TPLinkModemAuth, args):
    """Forward all unread SMS messages to Discord."""
    logger = logging.getLogger(__name__)
    sms = TPLinkSMS(auth.session, auth.base_url)
    
    # Check if using webhook or bot token
    if args.bot_token and args.channel_id:
        discord = DiscordForwarder(bot_token=args.bot_token, channel_id=args.channel_id)
    elif args.webhook:
        discord = DiscordForwarder(webhook_url=args.webhook)
    else:
        logger.error("Either --webhook or (--bot-token + --channel-id) is required")
        logger.error("Or set DISCORD_WEBHOOK or (DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID) env vars")
        sys.exit(1)
    
    # Get all messages
    inbox_info = sms.get_inbox_count()
    if not inbox_info:
        print("❌ Could not retrieve inbox information.")
        sys.exit(1)
    
    total_messages = inbox_info['totalNumber']
    print(f"\n📬 Processing {total_messages} messages...")
    
    forwarded = 0
    failed = 0
    marked_read = 0
    deleted = 0
    
    # Process each page
    total_pages = (total_messages + inbox_info['amountPerPage'] - 1) // inbox_info['amountPerPage']
    
    for page in range(1, total_pages + 1):
        messages = sms.list_messages(page=page)
        if not messages:
            continue
        
        for msg in messages:
            # Forward to Discord
            if discord.send_sms_to_discord(msg):
                forwarded += 1
                
                # Mark as read if requested
                if args.mark_read and msg.get('__stack'):
                    if sms.mark_as_read(msg.get('index', 0), msg['__stack']):
                        marked_read += 1
                
                # Delete if requested
                if args.delete and msg.get('__stack'):
                    if sms.delete_message(msg.get('index', 0), msg['__stack']):
                        deleted += 1
            else:
                failed += 1
    
    # Send summary
    discord.send_batch_summary(total_messages, forwarded, failed)
    
    print(f"\n📊 Summary:")
    print(f"  Total messages: {total_messages}")
    print(f"  Forwarded to Discord: {forwarded}")
    print(f"  Failed: {failed}")
    if args.mark_read:
        print(f"  Marked as read: {marked_read}")
    if args.delete:
        print(f"  Deleted: {deleted}")


def main():
    parser = argparse.ArgumentParser(
        description="TP-Link 3G Modem SMS Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List SMS messages
  python modem_3g_commands.py list
  
  # Send an SMS
  python modem_3g_commands.py send --phone "+1234567890" --message "Hello!"
  
  # Forward all SMS to Discord and mark as read
  python modem_3g_commands.py forward --webhook "https://discord.com/api/webhooks/..." --mark-read
  
  # Forward to Discord and delete after forwarding
  python modem_3g_commands.py forward --webhook "https://discord.com/api/webhooks/..." --delete
"""
    )
    
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--base-url', default=os.environ.get('ROUTER_BASE', 'http://192.168.7.1/'),
                        help='Router base URL (default: ROUTER_BASE env or http://192.168.7.1/)')
    parser.add_argument('--password', default=os.environ.get('ROUTER_PASS', 'admin'),
                        help='Router password (default: ROUTER_PASS env or admin)')
    parser.add_argument('--username', default=os.environ.get('ROUTER_USER', 'admin'),
                        help='Router username (default: ROUTER_USER env or admin)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List SMS messages')
    list_parser.add_argument('--page', type=int, default=1, help='Page number to retrieve (default: 1)')
    
    # Send command
    send_parser = subparsers.add_parser('send', help='Send a new SMS message')
    send_parser.add_argument('--phone', required=True, help='Recipient phone number')
    send_parser.add_argument('--message', required=True, help='Message content')
    
    # Forward command
    forward_parser = subparsers.add_parser('forward', help='Forward SMS messages to Discord')
    forward_parser.add_argument('--webhook', default=os.environ.get('DISCORD_WEBHOOK'),
                                help='Discord webhook URL (default: DISCORD_WEBHOOK env)')
    forward_parser.add_argument('--bot-token', default=os.environ.get('DISCORD_BOT_TOKEN'),
                                help='Discord bot token (alternative to webhook, default: DISCORD_BOT_TOKEN env)')
    forward_parser.add_argument('--channel-id', default=os.environ.get('DISCORD_CHANNEL_ID'),
                                help='Discord channel ID (required with --bot-token, default: DISCORD_CHANNEL_ID env)')
    forward_parser.add_argument('--mark-read', action='store_true',
                                help='Mark messages as read after forwarding')
    forward_parser.add_argument('--delete', action='store_true',
                                help='Delete messages after successful forwarding')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Check if command was provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Login to modem
    auth = login_to_modem(args.base_url, args.password, args.username)
    if not auth:
        sys.exit(1)
    
    # Execute command
    try:
        if args.command == 'list':
            cmd_list_sms(auth, args)
        elif args.command == 'send':
            cmd_send_sms(auth, args)
        elif args.command == 'forward':
            cmd_forward_to_discord(auth, args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logging.getLogger(__name__).error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()