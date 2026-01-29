import logging
import re
from typing import List, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class TPLinkSMS:
    """
    Handles SMS operations for TP-Link modem.
    
    Based on analysis of lteSmsInbox.htm, lteSmsReadMsg.htm, and lteSmsNewMsg.htm:
    - Uses $.act() calls with ACT_GET, ACT_SET, ACT_GL, ACT_DEL constants
    - LTE_SMS_RECVMSGBOX: inbox message box operations
    - LTE_SMS_RECVMSGENTRY: individual inbox message operations
    - LTE_SMS_SENDNEWMSG: send new message operations
    """
    
    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        self.base_url = base_url.rstrip('/') + '/'
        self._ensure_token_id()
    
    def _ensure_token_id(self):
        """Extract and set TokenID header if not already present."""
        if 'TokenID' in self.session.headers:
            return
        
        try:
            response = self.session.get(f"{self.base_url}cgi/getParm")
            token_match = re.search(r'var\s+TokenID\s*=\s*["\']([^"\']+)["\']', response.text)
            if token_match:
                token_id = token_match.group(1)
                self.session.headers['TokenID'] = token_id
                logger.debug(f"Set TokenID header: {token_id}")
            else:
                logger.warning("Could not extract TokenID from getParm response")
        except Exception as e:
            logger.error(f"Error extracting TokenID: {e}")
        
    def get_inbox_count(self) -> Optional[Dict[str, int]]:
        """
        Get SMS inbox statistics.
        Returns dict with 'totalNumber' and 'amountPerPage' or None on error.
        """
        try:
            logger.info("Fetching SMS inbox count")
            # Based on lteSmsReadMsg.htm: $.act(ACT_GET,LTE_SMS_RECVMSGBOX,null,null,["totalNumber","amountPerPage"])
            response = self.session.get(
                f"{self.base_url}cgi/info",
                headers={"Content-Type": "text/plain"}
            )
            logger.debug(f"Inbox count response status: {response.status_code}")
            
            # Parse response for totalNumber
            total_match = re.search(r'var\s+totalNumber\s*=\s*(\d+)', response.text)
            amount_match = re.search(r'var\s+amountPerPage\s*=\s*(\d+)', response.text)
            
            if total_match:
                result = {
                    'totalNumber': int(total_match.group(1)),
                    'amountPerPage': int(amount_match.group(1)) if amount_match else 7
                }
                logger.info(f"Inbox count: {result['totalNumber']} messages")
                return result
            
            logger.warning("Could not parse inbox count from response")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching inbox count: {e}", exc_info=True)
            return None
    
    def list_messages(self, page: int = 1) -> Optional[List[Dict]]:
        """
        List SMS messages from inbox.
        
        IMPORTANT: This method requires manual JavaScript execution in the browser console.
        The TP-Link modem uses an encrypted /cgi_gdpr API that cannot be easily replicated.
        
        To retrieve messages:
        1. Open browser and navigate to http://192.168.7.1/
        2. Login to the modem
        3. Open Developer Tools (F12) -> Console tab
        4. Execute this JavaScript:
        
           $.act(ACT_SET, LTE_SMS_RECVMSGBOX, null, null, ["PageNumber=0"]);
           $.exe();
           var smsInboxPagelist = $.act(ACT_GL, LTE_SMS_RECVMSGENTRY, null, null, 
               ["index", "from", "content", "receivedTime", "unread"]);
           $.exe();
           copy(smsInboxPagelist);
           console.log("Messages copied to clipboard!");
        
        5. Paste the result and parse it as JSON
        
        Message format:
        {
            "__stack": "1,0,0,0,0,0",      # Required for mark-as-read/delete operations
            "index": "99",                  # Message index
            "from": "Sender",               # Sender phone number or name
            "content": "Message text",      # Message content
            "receivedTime": "2024-02-16 18:54:25",  # Timestamp
            "unread": "0"                   # 0=read, 1=unread
        }
        
        Returns list of message dicts or empty list if unavailable.
        """
        try:
            logger.info(f"Listing SMS messages (page {page})")
            logger.warning("SMS listing requires manual JavaScript execution in browser console")
            logger.warning("See method docstring for instructions")
            logger.warning("The modem uses encrypted /cgi_gdpr API that requires browser context")
            
            # Return empty list - user must use browser console method
            messages = []
            logger.info(f"Retrieved {len(messages)} messages (manual retrieval required)")
            return messages
            
        except Exception as e:
            logger.error(f"Error listing messages: {e}", exc_info=True)
            return None
    
    def mark_as_read(self, message_index: int, message_stack: str) -> bool:
        """
        Mark a message as read.
        
        Based on lteSmsReadMsg.htm:
        - $.act(ACT_SET,LTE_SMS_RECVMSGENTRY,smsBoxPageList[indexGlobal].__stack,null,["unread=0"])
        """
        try:
            logger.info(f"Marking message {message_index} as read")
            
            response = self.session.post(
                f"{self.base_url}cgi/info",
                data=f"unread=0&stack={message_stack}",
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            success = "$.ret=0" in response.text or response.status_code == 200
            if success:
                logger.info(f"Message {message_index} marked as read")
            else:
                logger.warning(f"Failed to mark message {message_index} as read: {response.text[:100]}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error marking message as read: {e}", exc_info=True)
            return False
    
    def delete_message(self, message_index: int, message_stack: str) -> bool:
        """
        Delete a message.
        
        Based on lteSmsNewMsg.htm:
        - $.act(ACT_DEL,LTE_SMS_DRAFTMSGENTRY,smsDraftboxPagelist[indexGlobal].__stack,null)
        """
        try:
            logger.info(f"Deleting message {message_index}")
            
            response = self.session.post(
                f"{self.base_url}cgi/info",
                data=f"action=delete&stack={message_stack}",
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            success = "$.ret=0" in response.text or response.status_code == 200
            if success:
                logger.info(f"Message {message_index} deleted")
            else:
                logger.warning(f"Failed to delete message {message_index}: {response.text[:100]}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting message: {e}", exc_info=True)
            return False
    
    def send_message(self, phone_number: str, content: str) -> bool:
        """
        Send a new SMS message.
        
        Based on lteSmsNewMsg.htm:
        - $.act(ACT_SET,LTE_SMS_SENDNEWMSG,null,null,["index=1","to="+e,"textContent="+n])
        - Then check: $.act(ACT_GET,LTE_SMS_SENDNEWMSG,null,null,["sendResult"])
        
        Args:
            phone_number: Recipient phone number
            content: Message content (max 765 chars based on HTML)
        """
        try:
            logger.info(f"Sending SMS to {phone_number}")
            
            # Escape special characters (based on doEscapeCharEncode in HTML)
            escaped_content = content.replace('\n', '\x12').replace('\r', '\x11')
            
            # Send message
            response = self.session.post(
                f"{self.base_url}cgi/info",
                data=f"index=1&to={phone_number}&textContent={escaped_content}",
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            logger.debug(f"Send message response status: {response.status_code}")
            
            # Check send result
            response = self.session.get(
                f"{self.base_url}cgi/info",
                params={"fields": "sendResult"},
                headers={"Content-Type": "text/plain"}
            )
            
            # sendResult: 1=success, 2=busy, 3=pending, other=fail
            send_result_match = re.search(r'sendResult["\s:=]+(\d+)', response.text)
            if send_result_match:
                result = int(send_result_match.group(1))
                if result == 1:
                    logger.info(f"SMS sent successfully to {phone_number}")
                    return True
                elif result == 2:
                    logger.warning(f"SMS send busy for {phone_number}")
                elif result == 3:
                    logger.info(f"SMS send pending for {phone_number}")
                else:
                    logger.warning(f"SMS send failed for {phone_number}, result: {result}")
            else:
                logger.warning(f"Could not parse send result: {response.text[:100]}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return False
