// Auto-generated script to delete forwarded SMS messages
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
    var idsToDelete = ["98", "99", "94", "97", "96", "95", "92", "93"];
    
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
    
    console.log("\n📊 Deletion Summary:");
    console.log("  Deleted: " + deleted);
    console.log("  Failed: " + failed);
    console.log("\n✅ Deletion complete!");
    
    // Reload the page to see updated inbox
    if (deleted > 0) {
        console.log("Reloading page in 2 seconds...");
        setTimeout(function() { location.reload(); }, 2000);
    }
})();
