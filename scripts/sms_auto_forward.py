#!/usr/bin/env python3
"""
Automated SMS forwarding script for cron jobs.

This script:
1. Reads SMS messages from a JSON file (updated via browser console)
2. Forwards new messages to Discord
3. Marks messages as forwarded to avoid duplicates
4. Provides instructions for browser console SMS retrieval

For production use with cron jobs.
"""
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from src.modem_sms.discord_forwarder import DiscordForwarder

# Setup logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "sms_auto_forward.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SMSForwarder:
    """Handles automated SMS forwarding with state tracking."""
    
    def __init__(self, state_file: Path, discord_config: dict):
        self.state_file = state_file
        self.discord_config = discord_config
        self.forwarded_ids = self._load_state()
        
        # Initialize Discord forwarder
        if discord_config.get('webhook'):
            self.discord = DiscordForwarder(webhook_url=discord_config['webhook'])
        elif discord_config.get('bot_token') and discord_config.get('channel_id'):
            self.discord = DiscordForwarder(
                bot_token=discord_config['bot_token'],
                channel_id=discord_config['channel_id']
            )
        else:
            raise ValueError("Discord configuration required (webhook or bot_token+channel_id)")
    
    def _load_state(self) -> set:
        """Load the set of already-forwarded message IDs."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('forwarded_ids', []))
            except Exception as e:
                logger.error(f"Error loading state file: {e}")
                return set()
        return set()
    
    def _save_state(self):
        """Save the set of forwarded message IDs."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    'forwarded_ids': list(self.forwarded_ids),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state file: {e}")
    
    def _filter_and_consolidate_messages(self, messages: list) -> list:
        """
        Consolidate ALL messages from the same sender into summaries.
        
        Returns filtered list of messages.
        """
        # Sort messages by index first (chronological order)
        sorted_messages = sorted(messages, key=lambda m: int(m.get('index', 0)))
        
        # Group ALL messages by sender (not just consecutive)
        from collections import defaultdict
        sender_groups = defaultdict(list)
        
        for msg in sorted_messages:
            sender = msg.get('from', 'Unknown')
            sender_groups[sender].append(msg)
        
        # Convert groups to summaries, maintaining chronological order by first message
        consolidated = []
        for sender in sorted(sender_groups.keys(), key=lambda s: int(sender_groups[s][0].get('index', 0))):
            group = sender_groups[sender]
            consolidated.append(self._create_summary_or_single(group))
        
        return consolidated
    
    def _create_summary_or_single(self, messages: list) -> dict:
        """
        Create a summary message if there are multiple messages, otherwise return the single message.
        """
        if len(messages) == 1:
            return messages[0]
        
        # Multiple messages from same sender - create summary
        sender = messages[0].get('from', 'Unknown')
        count = len(messages)
        first_time = messages[0].get('receivedTime', 'Unknown')
        last_time = messages[-1].get('receivedTime', 'Unknown')
        
        # Extract message indices for tracking
        indices = [m.get('index') for m in messages]
        
        # Create summary content with all message contents
        if sender == '222177':
            # Special handling for system messages - just show count
            content = f"🔕 {count} system detection messages (filtered)"
        else:
            # For other senders, show all message contents with timestamps
            content = f"📞 {count} messages from {sender}\n\n"
            
            for i, msg in enumerate(messages, 1):
                msg_time = msg.get('receivedTime', 'Unknown')
                msg_content = msg.get('content', '')
                content += f"[{msg_time}]\n{msg_content}\n\n"
        
        summary_msg = {
            'index': f"summary_{sender}_{indices[0]}_{indices[-1]}",
            'from': f"{sender} ({count} messages)",
            'content': content.strip(),
            'receivedTime': last_time,
            'unread': '0',
            '_filtered_ids': indices  # Track all IDs for deletion
        }
        
        logger.info(f"Consolidated {count} messages from {sender} into summary")
        return summary_msg
    
    def process_messages(self, messages: list) -> dict:
        """
        Process messages: filter, sort, forward new ones and track state.
        
        Returns dict with statistics.
        """
        # Filter and consolidate messages by sender (already sorted chronologically)
        filtered_messages = self._filter_and_consolidate_messages(messages)
        
        stats = {
            'total': len(messages),
            'new': 0,
            'forwarded': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for msg in filtered_messages:
            msg_id = msg.get('index')
            
            if not msg_id:
                logger.warning(f"Message missing index: {msg}")
                continue
            
            # Skip already forwarded messages
            if msg_id in self.forwarded_ids:
                stats['skipped'] += 1
                logger.debug(f"Skipping already forwarded message {msg_id}")
                continue
            
            stats['new'] += 1
            
            # Forward to Discord
            if self.discord.send_sms_to_discord(msg):
                stats['forwarded'] += 1
                self.forwarded_ids.add(msg_id)
                
                # Also mark filtered 222177 messages as forwarded
                if '_filtered_ids' in msg:
                    for filtered_id in msg['_filtered_ids']:
                        self.forwarded_ids.add(filtered_id)
                
                logger.info(f"✅ Forwarded message {msg_id} from {msg.get('from', 'Unknown')}")
            else:
                stats['failed'] += 1
                logger.error(f"❌ Failed to forward message {msg_id}")
        
        # Save state after processing
        if stats['forwarded'] > 0:
            self._save_state()
        
        return stats


def print_browser_instructions():
    """Print instructions for updating the messages JSON file."""
    print("\n" + "="*70)
    print("📱 SMS AUTO-FORWARD - Browser Console Instructions")
    print("="*70)
    print("""
To update SMS messages for forwarding:

1. Open browser and navigate to: http://192.168.7.1/
2. Login to the modem
3. Open Developer Tools (F12) -> Console tab
4. Execute this JavaScript:

   $.act(ACT_SET, LTE_SMS_RECVMSGBOX, null, null, ["PageNumber=0"]);
   $.exe();
   var smsInboxPagelist = $.act(ACT_GL, LTE_SMS_RECVMSGENTRY, null, null, 
       ["index", "from", "content", "receivedTime", "unread"]);
   $.exe();
   console.log(JSON.stringify(smsInboxPagelist, null, 2));

5. Copy the JSON output
6. Save it to: scripts/data/current_messages.json

7. This script will automatically:
   - Forward new messages to Discord
   - Track which messages have been forwarded
   - Skip duplicates on subsequent runs
""")
    print("="*70 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Automated SMS forwarding for cron jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--messages-file', 
                        default='data/current_messages.json',
                        help='JSON file with SMS messages from browser console')
    parser.add_argument('--state-file',
                        default='data/forwarded_state.json',
                        help='State file to track forwarded messages')
    parser.add_argument('--webhook', 
                        default=os.environ.get('DISCORD_WEBHOOK'),
                        help='Discord webhook URL')
    parser.add_argument('--bot-token', 
                        default=os.environ.get('DISCORD_BOT_TOKEN'),
                        help='Discord bot token')
    parser.add_argument('--channel-id', 
                        default=os.environ.get('DISCORD_CHANNEL_ID'),
                        help='Discord channel ID')
    parser.add_argument('--show-instructions', 
                        action='store_true',
                        help='Show browser console instructions and exit')
    parser.add_argument('--reset-state',
                        action='store_true',
                        help='Reset forwarded state (will re-forward all messages)')
    
    args = parser.parse_args()
    
    # Show instructions if requested
    if args.show_instructions:
        print_browser_instructions()
        return 0
    
    # Resolve paths relative to script directory
    script_dir = Path(__file__).parent
    messages_file = script_dir / args.messages_file
    state_file = script_dir / args.state_file
    
    # Reset state if requested
    if args.reset_state:
        if state_file.exists():
            state_file.unlink()
            logger.info("State file reset - all messages will be re-forwarded")
        return 0
    
    # Check if messages file exists
    if not messages_file.exists():
        logger.error(f"Messages file not found: {messages_file}")
        logger.info("Run with --show-instructions to see how to create it")
        print_browser_instructions()
        return 1
    
    # Validate Discord configuration
    discord_config = {
        'webhook': args.webhook,
        'bot_token': args.bot_token,
        'channel_id': args.channel_id
    }
    
    if not discord_config['webhook'] and not (discord_config['bot_token'] and discord_config['channel_id']):
        logger.error("Discord configuration required!")
        logger.error("Set DISCORD_WEBHOOK or (DISCORD_BOT_TOKEN + DISCORD_CHANNEL_ID)")
        return 1
    
    # Load messages
    try:
        with open(messages_file, 'r') as f:
            messages = json.load(f)
        
        if not isinstance(messages, list):
            logger.error("Messages file must contain a JSON array")
            return 1
        
        logger.info(f"Loaded {len(messages)} messages from {messages_file}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in messages file: {e}")
        return 1
    except Exception as e:
        logger.error(f"Error reading messages file: {e}")
        return 1
    
    # Process messages
    try:
        forwarder = SMSForwarder(state_file, discord_config)
        stats = forwarder.process_messages(messages)
        
        # Log summary
        logger.info("="*50)
        logger.info("📊 Processing Summary:")
        logger.info(f"  Total messages: {stats['total']}")
        logger.info(f"  New messages: {stats['new']}")
        logger.info(f"  Forwarded: {stats['forwarded']}")
        logger.info(f"  Failed: {stats['failed']}")
        logger.info(f"  Skipped (already forwarded): {stats['skipped']}")
        logger.info("="*50)
        
        # Send summary to Discord if there were new messages
        if stats['new'] > 0:
            forwarder.discord.send_batch_summary(
                stats['total'], 
                stats['forwarded'], 
                stats['failed']
            )
        
        return 0 if stats['failed'] == 0 else 1
        
    except Exception as e:
        logger.error(f"Error processing messages: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
