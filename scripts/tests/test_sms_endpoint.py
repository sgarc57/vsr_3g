#!/usr/bin/env python3
"""
Test script to replicate captured SMS API calls.
Use this to test different endpoint patterns based on browser DevTools captures.
"""
import os
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.modem_sms.auth import TPLinkModemAuth

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_endpoint(auth, method, endpoint, headers=None, data=None, params=None):
    """Test a specific endpoint with given parameters."""
    url = f"{auth.base_url.rstrip('/')}{endpoint}"
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {method} {url}")
    logger.info(f"{'='*60}")
    
    if headers:
        logger.info(f"Extra headers: {headers}")
    if data:
        logger.info(f"Data: {data}")
    if params:
        logger.info(f"Params: {params}")
    
    try:
        if method.upper() == 'GET':
            r = auth.session.get(url, headers=headers, params=params)
        elif method.upper() == 'POST':
            r = auth.session.post(url, headers=headers, data=data, params=params)
        else:
            logger.error(f"Unsupported method: {method}")
            return
        
        logger.info(f"Status: {r.status_code}")
        logger.info(f"Response headers: {dict(r.headers)}")
        logger.info(f"Response length: {len(r.text)}")
        logger.info(f"\nResponse body:")
        print(r.text)
        
        return r
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return None

def main():
    base_url = os.environ.get("ROUTER_BASE", "http://localhost:3080/")
    username = os.environ.get("ROUTER_USER", "admin")
    password = os.environ.get("ROUTER_PASS", "admin")
    
    auth = TPLinkModemAuth(base_url, username, password)
    
    if not auth.login():
        logger.error("Failed to login")
        return 1
    
    logger.info("✅ Successfully logged in")
    logger.info(f"JSESSIONID: {auth.jsessionid}")
    
    # Extract TokenID from getParm
    r = auth.session.get(f"{base_url}cgi/getParm")
    logger.info(f"\ngetParm response preview:")
    print(r.text[:500])
    
    # TODO: Add the captured endpoint calls here
    # Example:
    # test_endpoint(auth, 'POST', '/cgi/info', 
    #               headers={'TokenID': 'xxx', 'Content-Type': 'application/x-www-form-urlencoded'},
    #               data='PageNumber=1')
    
    logger.info("\n" + "="*60)
    logger.info("Add your captured API calls above this line")
    logger.info("="*60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
