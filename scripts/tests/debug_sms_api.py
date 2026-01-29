#!/usr/bin/env python3
"""
Debug script to understand the SMS API responses from the TP-Link modem.
This will help us implement the proper parsing logic.
"""
import os
import sys
import logging
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.modem_sms.auth import TPLinkModemAuth

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    base_url = os.environ.get("ROUTER_BASE", "http://localhost:3080/")
    username = os.environ.get("ROUTER_USER", "admin")
    password = os.environ.get("ROUTER_PASS", "admin")
    
    auth = TPLinkModemAuth(base_url, username, password)
    
    if not auth.login():
        logger.error("Failed to login")
        return 1
    
    logger.info("✅ Successfully logged in")
    
    # Try to extract TokenID from getParm response
    logger.info("Fetching getParm to look for TokenID...")
    r = auth.session.get(f"{base_url}cgi/getParm")
    logger.info(f"getParm status: {r.status_code}")
    
    # Look for TokenID in response
    token_match = re.search(r'var\s+TokenID\s*=\s*["\']([^"\']+)["\']', r.text)
    if token_match:
        token_id = token_match.group(1)
        logger.info(f"Found TokenID: {token_id}")
        auth.session.headers['TokenID'] = token_id
    else:
        logger.warning("No TokenID found in getParm response")
    
    # Try different API endpoints
    endpoints_to_test = [
        ("/cgi/info", {}),
        ("/cgi", {}),
        ("/cgi/getParm", {}),
    ]
    
    for endpoint, params in endpoints_to_test:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing endpoint: {endpoint}")
        logger.info(f"{'='*60}")
        
        try:
            r = auth.session.get(f"{base_url.rstrip('/')}{endpoint}", params=params)
            logger.info(f"Status: {r.status_code}")
            logger.info(f"Headers: {dict(r.headers)}")
            logger.info(f"Response length: {len(r.text)}")
            logger.info(f"Response preview (first 500 chars):")
            print(r.text[:500])
            
            # Look for SMS-related variables
            if 'sms' in r.text.lower() or 'lte' in r.text.lower():
                logger.info("⚠️  Found SMS/LTE related content!")
                
        except Exception as e:
            logger.error(f"Error testing {endpoint}: {e}")
    
    # Try to access the SMS inbox HTML page directly
    logger.info(f"\n{'='*60}")
    logger.info("Fetching SMS inbox HTML page")
    logger.info(f"{'='*60}")
    
    try:
        r = auth.session.get(f"{base_url}main/lteSmsInbox.htm")
        logger.info(f"Status: {r.status_code}")
        logger.info(f"Response length: {len(r.text)}")
        if r.status_code == 200:
            logger.info("✅ Successfully fetched SMS inbox page")
    except Exception as e:
        logger.error(f"Error: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
