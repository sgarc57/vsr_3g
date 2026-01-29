#!/usr/bin/env python3
"""
Generate JavaScript code to delete forwarded SMS messages.

This script reads the state file (which tracks forwarded messages) and generates
JavaScript code that can be executed in the browser console to delete those messages.
"""
import os
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_delete_script(forwarded_ids: list, output_file: Path):
    """Generate JavaScript code to delete messages by their IDs."""
    
    if not forwarded_ids:
        logger.info("No messages to delete")
        return
    
    # Generate JavaScript code
    js_code = """// Auto-generated script to delete forwarded SMS messages
// Execute this in the browser console at http://192.168.7.1/

(function() {
    console.log("Starting SMS deletion...");
    
    // Get all messages first
    $.act(ACT_SET, LTE_SMS_RECVMSGBOX, null, null, ["PageNumber=0"]);
    $.exe();
    
    var smsInboxPagelist = $.act(ACT_GL, LTE_SMS_RECVMSGENTRY, null, null, 
        ["index", "from", "content", "receivedTime", "unread"]);
    $.exe();
    
    // IDs to delete
    var idsToDelete = """ + json.dumps(forwarded_ids) + """;
    
    var deleted = 0;
    var failed = 0;
    
    // Delete each message
    smsInboxPagelist.forEach(function(msg) {
        if (idsToDelete.includes(msg.index)) {
            console.log("Deleting message " + msg.index + " from " + msg.from);
            
            // Delete the message using its __stack
            $.act(ACT_DEL, LTE_SMS_RECVMSGENTRY, msg.__stack, null);
            var result = $.exe();
            
            if (result === 0 || $.ret === 0) {
                deleted++;
                console.log("✅ Deleted message " + msg.index);
            } else {
                failed++;
                console.error("❌ Failed to delete message " + msg.index);
            }
        }
    });
    
    console.log("\\n📊 Deletion Summary:");
    console.log("  Deleted: " + deleted);
    console.log("  Failed: " + failed);
    console.log("\\n✅ Deletion complete!");
    
    // Reload the page to see updated inbox
    if (deleted > 0) {
        console.log("Reloading page in 2 seconds...");
        setTimeout(function() { location.reload(); }, 2000);
    }
})();
"""
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write(js_code)
    
    logger.info(f"Generated deletion script for {len(forwarded_ids)} messages")
    logger.info(f"Script saved to: {output_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate JavaScript to delete forwarded SMS messages"
    )
    
    parser.add_argument('--state-file',
                        required=True,
                        help='State file with forwarded message IDs')
    parser.add_argument('--output',
                        required=True,
                        help='Output file for JavaScript code')
    
    args = parser.parse_args()
    
    # Resolve paths
    state_file = Path(args.state_file)
    output_file = Path(args.output)
    
    # Check if state file exists
    if not state_file.exists():
        logger.error(f"State file not found: {state_file}")
        return 1
    
    # Load state
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        forwarded_ids = state.get('forwarded_ids', [])
        
        if not forwarded_ids:
            logger.info("No forwarded messages to delete")
            return 0
        
        # Generate deletion script
        generate_delete_script(forwarded_ids, output_file)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
