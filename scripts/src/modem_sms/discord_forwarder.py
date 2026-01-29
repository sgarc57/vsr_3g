import logging
from typing import Dict, Optional
import requests
import time
import json

logger = logging.getLogger(__name__)


class DiscordForwarder:
    """
    Forwards SMS messages to a Discord channel via webhook or bot token.
    """
    
    def __init__(self, webhook_url: str = None, bot_token: str = None, channel_id: str = None):
        """
        Initialize Discord forwarder.
        
        Args:
            webhook_url: Discord webhook URL for the target channel (webhook mode)
            bot_token: Discord bot token (bot mode, requires channel_id)
            channel_id: Discord channel ID (required for bot mode)
        """
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.use_bot = bool(bot_token and channel_id)
        
        if self.use_bot:
            logger.info(f"Discord forwarder initialized with bot token for channel: {channel_id}")
            self.headers = {
                "Authorization": f"Bot {bot_token}",
                "Content-Type": "application/json"
            }
        elif webhook_url:
            logger.info(f"Discord forwarder initialized with webhook: {webhook_url[:50]}...")
            self.headers = {"Content-Type": "application/json"}
        else:
            raise ValueError("Either webhook_url or (bot_token + channel_id) must be provided")
    
    def send_sms_to_discord(self, sms_message: Dict, max_retries: int = 3) -> bool:
        """
        Send an SMS message to Discord with rate limit handling.
        
        Args:
            sms_message: Dict with keys: from, content, receivedTime, index
            max_retries: Maximum number of retry attempts for rate limits
            
        Returns:
            True if successfully sent, False otherwise
        """
        try:
            # Extract message details
            from_number = sms_message.get('from', 'Unknown')
            content = sms_message.get('content', '')
            received_time = sms_message.get('receivedTime', 'Unknown')
            index = sms_message.get('index', 'N/A')
            
            logger.info(f"Forwarding SMS #{index} from {from_number} to Discord")
            
            # Format Discord message with embed
            discord_payload = {
                "embeds": [{
                    "title": "📱 New SMS Message",
                    "color": 3447003,  # Blue color
                    "fields": [
                        {
                            "name": "From",
                            "value": from_number,
                            "inline": True
                        },
                        {
                            "name": "Received",
                            "value": received_time,
                            "inline": True
                        },
                        {
                            "name": "Message",
                            "value": content[:1024] if content else "(empty)",  # Discord field limit
                            "inline": False
                        }
                    ],
                    "footer": {
                        "text": f"SMS Index: {index}"
                    }
                }]
            }
            
            # Send to Discord with retry logic for rate limits
            if self.use_bot:
                url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages"
            else:
                url = self.webhook_url
            
            for attempt in range(max_retries):
                response = requests.post(
                    url,
                    json=discord_payload,
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code in (200, 204):
                    logger.info(f"Successfully forwarded SMS #{index} to Discord")
                    return True
                elif response.status_code == 429:
                    # Rate limited - parse retry_after and wait
                    try:
                        rate_limit_data = response.json()
                        retry_after = rate_limit_data.get('retry_after', 1.0)
                        logger.warning(f"Rate limited. Waiting {retry_after}s before retry (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_after)
                        continue
                    except:
                        logger.warning(f"Rate limited but couldn't parse retry_after. Waiting 1s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(1.0)
                        continue
                else:
                    logger.error(f"Discord API failed with status {response.status_code}: {response.text}")
                    return False
            
            logger.error(f"Failed to forward SMS #{index} after {max_retries} retries")
            return False
                
        except Exception as e:
            logger.error(f"Error forwarding SMS to Discord: {e}", exc_info=True)
            return False
    
    def send_batch_summary(self, total_messages: int, forwarded: int, failed: int) -> bool:
        """
        Send a summary message to Discord after batch processing.
        
        Args:
            total_messages: Total number of messages processed
            forwarded: Number successfully forwarded
            failed: Number that failed to forward
            
        Returns:
            True if successfully sent, False otherwise
        """
        try:
            logger.info(f"Sending batch summary to Discord: {forwarded}/{total_messages} forwarded")
            
            color = 3066993 if failed == 0 else 15158332  # Green if all success, red if any failures
            
            discord_payload = {
                "embeds": [{
                    "title": "📊 SMS Forwarding Summary",
                    "color": color,
                    "fields": [
                        {
                            "name": "Total Messages",
                            "value": str(total_messages),
                            "inline": True
                        },
                        {
                            "name": "Forwarded",
                            "value": str(forwarded),
                            "inline": True
                        },
                        {
                            "name": "Failed",
                            "value": str(failed),
                            "inline": True
                        }
                    ]
                }]
            }
            
            # Send to Discord (webhook or bot API)
            if self.use_bot:
                url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages"
            else:
                url = self.webhook_url
            
            response = requests.post(
                url,
                json=discord_payload,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code in (200, 204):
                logger.info("Successfully sent batch summary to Discord")
                return True
            else:
                logger.error(f"Discord API failed for summary: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending batch summary to Discord: {e}", exc_info=True)
            return False
