#!/usr/bin/env node
/**
 * Automated SMS Retrieval using Puppeteer
 * 
 * This script:
 * 1. Launches headless browser
 * 2. Logs into the TP-Link modem
 * 3. Executes JavaScript to retrieve SMS messages
 * 4. Saves messages to JSON file
 * 5. Optionally deletes forwarded messages
 */

const puppeteer = require('puppeteer');
const fs = require('fs').promises;
const path = require('path');

// Configuration from environment variables
// Parse arguments properly
const args = process.argv.slice(2);
const deleteFlag = args.includes('--delete');
const noHeadlessFlag = args.includes('--no-headless');
const fileArgs = args.filter(arg => !arg.startsWith('--'));

const config = {
    modemUrl: process.env.ROUTER_BASE || 'http://192.168.7.1/',
    modemActualUrl: process.env.ROUTER_ACTUAL || 'http://192.168.7.1/',
    modemPassword: process.env.ROUTER_PASS || 'admin',
    outputFile: fileArgs[0] || path.join(__dirname, 'data', 'current_messages.json'),
    deleteStateFile: fileArgs[1] || path.join(__dirname, 'data', 'forwarded_state.json'),
    deleteForwarded: deleteFlag,
    headless: !noHeadlessFlag,
    timeout: 30000
};

console.log(`[${new Date().toISOString()}] Starting SMS retrieval...`);
console.log(`Modem URL: ${config.modemUrl}`);
console.log(`Output file: ${config.outputFile}`);
console.log(`Headless mode: ${config.headless}`);

async function loginToModem(page) {
    console.log('Setting up request interception for correct headers...');
    
    // Enable request interception to modify headers
    await page.setRequestInterception(true);
    
    page.on('request', (request) => {
        const headers = Object.assign({}, request.headers(), {
            'Referer': config.modemActualUrl,
            'Origin': config.modemActualUrl.replace(/\/$/, '')
        });
        
        request.continue({ headers });
    });
    
    console.log('Navigating to modem...');
    console.log(`  Connecting via: ${config.modemUrl}`);
    console.log(`  Headers set for: ${config.modemActualUrl}`);
    
    await page.goto(config.modemUrl, { waitUntil: 'networkidle2', timeout: config.timeout });
    
    // Wait for login page to load
    await page.waitForSelector('#pc-login-password', { timeout: 10000 });
    
    console.log('Logging in...');
    await page.type('#pc-login-password', config.modemPassword);
    await page.click('#pc-login-btn');
    
    // Wait for login to complete
    await page.waitForTimeout(2000);
    
    // Check for "only one login at a time" prompt and accept it
    console.log('Checking for login prompt...');
    try {
        // Wait a moment for the dialog to appear
        await page.waitForTimeout(500);
        
        // Check if the alert container is visible
        const hasPrompt = await page.evaluate(() => {
            const alertContainer = document.querySelector('#alert-container');
            return alertContainer && alertContainer.style.display !== 'none';
        });
        
        if (hasPrompt) {
            console.log('Found "only one login" prompt, clicking "Log In" button...');
            
            // Click the "Log In" button and wait for the dialog to close
            const clicked = await page.evaluate(() => {
                const loginButton = document.querySelector('#confirm-yes, .btn-msg-ok');
                if (loginButton) {
                    loginButton.click();
                    return true;
                }
                return false;
            });
            
            if (clicked) {
                console.log('✅ Clicked "Log In" button');
                
                // Wait for the alert dialog to disappear
                await page.waitForFunction(() => {
                    const alertContainer = document.querySelector('#alert-container');
                    return !alertContainer || alertContainer.style.display === 'none';
                }, { timeout: 5000 }).catch(() => {
                    console.log('⚠️  Alert dialog did not close');
                });
                
                // Wait for page to reload/settle after forcing login
                await page.waitForTimeout(4000);
                
                console.log('Waiting for main interface to load...');
            } else {
                console.log('⚠️  Could not find "Log In" button');
            }
        } else {
            console.log('No login prompt detected, continuing...');
        }
    } catch (e) {
        console.log('Note: Error checking for login prompt:', e.message);
    }
    
    // Wait for page to fully load after login
    await page.waitForTimeout(3000);
    
    // Debug: Check what's on the page
    const pageInfo = await page.evaluate(() => {
        return {
            url: window.location.href,
            title: document.title,
            hasDollar: typeof $ !== 'undefined',
            hasAct: typeof $ !== 'undefined' && typeof $.act === 'function',
            hasBody: !!document.body,
            bodyText: document.body ? document.body.innerText.substring(0, 200) : 'no body',
            hasMainDiv: !!document.querySelector('#pc-div'),
            hasLoginForm: !!document.querySelector('#pc-login-password')
        };
    });
    
    console.log('Page state after login:', JSON.stringify(pageInfo, null, 2));
    
    // Check if we're still on login page
    if (pageInfo.hasLoginForm || pageInfo.bodyText.toLowerCase().includes('forgot password')) {
        console.log('⚠️  Still on login page, attempting to reload...');
        await page.reload({ waitUntil: 'networkidle2' });
        await page.waitForTimeout(3000);
        
        // Check again
        const reloadedInfo = await page.evaluate(() => {
            return {
                hasAct: typeof $ !== 'undefined' && typeof $.act === 'function',
                bodyText: document.body ? document.body.innerText.substring(0, 100) : 'no body'
            };
        });
        
        if (!reloadedInfo.hasAct) {
            throw new Error('Login failed - still on login page after reload. Body: ' + reloadedInfo.bodyText);
        }
    }
    
    // Wait for JavaScript libraries to be available
    if (!pageInfo.hasAct) {
        console.log('JavaScript not loaded yet, waiting...');
        await page.waitForFunction(() => {
            return typeof $ !== 'undefined' && typeof $.act === 'function';
        }, { timeout: 15000 }).catch((err) => {
            console.log('⚠️  Timeout waiting for $.act');
            throw new Error('JavaScript libraries not loaded - login may have failed');
        });
    }
    
    console.log('✅ Login completed');
    
    // Navigate to SMS Inbox by clicking through the menu
    console.log('Navigating to SMS inbox page...');
    
    try {
        // Click the Advanced tab by ID
        const advancedClicked = await page.evaluate(() => {
            const advancedTab = document.querySelector('#advanced');
            if (advancedTab) {
                advancedTab.click();
                return true;
            }
            return false;
        });
        
        if (advancedClicked) {
            console.log('✅ Clicked Advanced tab');
            await page.waitForTimeout(1000);
        } else {
            console.log('⚠️  Could not find Advanced tab');
        }
        
        // Click the SMS button to expand the submenu
        const smsClicked = await page.evaluate(() => {
            const smsButton = document.querySelector('a[url="lteSmsInbox.htm"]#sms, a#sms, span#sms');
            if (smsButton) {
                // Click the parent link if it's just the icon
                const parentLink = smsButton.closest('a');
                if (parentLink) {
                    parentLink.click();
                    return true;
                }
                smsButton.click();
                return true;
            }
            // Try alternative selector
            const smsLink = Array.from(document.querySelectorAll('a')).find(a => 
                a.querySelector('#sms') || (a.textContent && a.textContent.trim() === 'SMS')
            );
            if (smsLink) {
                smsLink.click();
                return true;
            }
            return false;
        });
        
        if (smsClicked) {
            console.log('✅ Clicked SMS button');
            await page.waitForTimeout(1000);
        } else {
            console.log('⚠️  Could not find SMS button');
        }
        
        // Now click the Inbox link (which should now be visible)
        const clicked = await page.evaluate(() => {
            // Look for the Inbox link specifically
            const inboxLinks = Array.from(document.querySelectorAll('a'));
            const inboxLink = inboxLinks.find(a => {
                const text = a.textContent || '';
                const url = a.getAttribute('url');
                return url === 'lteSmsInbox.htm' && text.toLowerCase().includes('inbox');
            });
            
            if (inboxLink) {
                inboxLink.click();
                return true;
            }
            return false;
        });
        
        if (clicked) {
            console.log('✅ Clicked Inbox link');
            // Wait for the SMS inbox table to load
            await page.waitForTimeout(3000);
        } else {
            console.log('⚠️  Could not find Inbox link');
        }
    } catch (e) {
        console.log('⚠️  Error navigating to SMS:', e.message);
    }
}

async function retrieveSMS(page) {
    console.log('Retrieving SMS messages...');
    
    // Check what's available in the page context
    const context = await page.evaluate(() => {
        return {
            hasAct: typeof $ !== 'undefined' && typeof $.act === 'function',
            hasACT_SET: typeof ACT_SET !== 'undefined',
            hasACT_GL: typeof ACT_GL !== 'undefined',
            hasLTE_SMS_RECVMSGBOX: typeof LTE_SMS_RECVMSGBOX !== 'undefined',
            hasLTE_SMS_RECVMSGENTRY: typeof LTE_SMS_RECVMSGENTRY !== 'undefined',
            ACT_SET_val: typeof ACT_SET !== 'undefined' ? ACT_SET : null,
            ACT_GL_val: typeof ACT_GL !== 'undefined' ? ACT_GL : null
        };
    });
    
    console.log('SMS context:', JSON.stringify(context, null, 2));
    
    // Wait for SMS JavaScript to be available
    await page.waitForFunction(() => {
        return typeof $ !== 'undefined' && typeof $.act === 'function';
    }, { timeout: 10000 }).catch(() => {
        console.log('⚠️  $.act not available');
    });
    
    console.log('Executing SMS retrieval...');
    
    // Execute JavaScript to retrieve SMS messages
    // This uses the exact same approach as the browser console
    const messages = await page.evaluate(() => {
        return new Promise((resolve, reject) => {
            try {
                // Check if required functions exist
                if (typeof $ === 'undefined' || typeof $.act === 'undefined') {
                    reject(new Error('jQuery or $.act not available'));
                    return;
                }
                
                // Check if SMS constants are available
                if (typeof ACT_SET === 'undefined' || typeof ACT_GL === 'undefined' ||
                    typeof LTE_SMS_RECVMSGBOX === 'undefined' || typeof LTE_SMS_RECVMSGENTRY === 'undefined') {
                    reject(new Error('SMS constants not available'));
                    return;
                }
                
                // Use the exact browser console approach
                // Set page number to 0 (first page)
                $.act(ACT_SET, LTE_SMS_RECVMSGBOX, null, null, ["PageNumber=0"]);
                const setResult = $.exe();
                
                // Get message list
                var smsInboxPagelist = $.act(
                    ACT_GL, 
                    LTE_SMS_RECVMSGENTRY, 
                    null, 
                    null,
                    ["index", "from", "content", "receivedTime", "unread"]
                );
                const exeResult = $.exe();
                
                // Debug: log what we got
                console.log('Set result:', setResult);
                console.log('Exe result:', exeResult);
                console.log('$.ret:', typeof $.ret !== 'undefined' ? $.ret : 'undefined');
                console.log('smsInboxPagelist type:', typeof smsInboxPagelist);
                console.log('smsInboxPagelist length:', smsInboxPagelist ? smsInboxPagelist.length : 'null/undefined');
                console.log('smsInboxPagelist:', smsInboxPagelist);
                
                // Return the messages
                resolve({
                    messages: smsInboxPagelist || [],
                    setResult: setResult,
                    exeResult: exeResult,
                    ret: typeof $.ret !== 'undefined' ? $.ret : null
                });
            } catch (error) {
                reject(error);
            }
        });
    });
    
    console.log('API Response:', JSON.stringify(messages, null, 2));
    
    const messageList = messages.messages || [];
    console.log(`✅ Retrieved ${messageList.length} messages`);
    return messageList;
}

async function deleteMessages(page, messageIds) {
    if (!messageIds || messageIds.length === 0) {
        console.log('No messages to delete');
        return { deleted: 0, failed: 0 };
    }
    
    console.log(`Deleting ${messageIds.length} forwarded messages...`);
    
    const result = await page.evaluate((idsToDelete) => {
        return new Promise((resolve) => {
            try {
                // Get all messages first
                $.act(window.ACT_SET, window.LTE_SMS_RECVMSGBOX, null, null, ["PageNumber=0"]);
                $.exe();
                
                var smsInboxPagelist = $.act(
                    window.ACT_GL,
                    window.LTE_SMS_RECVMSGENTRY,
                    null,
                    null,
                    ["index", "from", "content", "receivedTime", "unread"]
                );
                $.exe();
                
                let deleted = 0;
                let failed = 0;
                
                // Delete each message
                smsInboxPagelist.forEach((msg) => {
                    if (idsToDelete.includes(msg.index)) {
                        console.log(`Deleting message ${msg.index} from ${msg.from}`);
                        
                        $.act(window.ACT_DEL, window.LTE_SMS_RECVMSGENTRY, msg.__stack, null);
                        const result = $.exe();
                        
                        if (result === 0 || $.ret === 0) {
                            deleted++;
                        } else {
                            failed++;
                        }
                    }
                });
                
                resolve({ deleted, failed });
            } catch (error) {
                resolve({ deleted: 0, failed: idsToDelete.length, error: error.message });
            }
        });
    }, messageIds);
    
    console.log(`✅ Deleted: ${result.deleted}, Failed: ${result.failed}`);
    return result;
}

async function main() {
    let browser;
    
    try {
        // Launch browser
        console.log('Launching browser...');
        browser = await puppeteer.launch({
            headless: config.headless ? 'new' : false,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        });
        
        const page = await browser.newPage();
        
        // Set viewport
        await page.setViewport({ width: 1280, height: 800 });
        
        // Enable console logging from page
        page.on('console', msg => {
            if (msg.type() === 'error') {
                console.error(`[Browser Error] ${msg.text()}`);
            }
        });
        
        // Login to modem
        await loginToModem(page);
        
        // Retrieve SMS messages
        const messages = await retrieveSMS(page);
        
        // Save messages to file
        await fs.writeFile(
            config.outputFile,
            JSON.stringify(messages, null, 2),
            'utf8'
        );
        console.log(`✅ Saved ${messages.length} messages to ${config.outputFile}`);
        
        // Delete forwarded messages if requested
        if (config.deleteForwarded) {
            try {
                const stateData = await fs.readFile(config.deleteStateFile, 'utf8');
                const state = JSON.parse(stateData);
                const forwardedIds = state.forwarded_ids || [];
                
                if (forwardedIds.length > 0) {
                    const deleteResult = await deleteMessages(page, forwardedIds);
                    
                    // Clear the forwarded state after successful deletion
                    if (deleteResult.deleted > 0) {
                        await fs.writeFile(
                            config.deleteStateFile,
                            JSON.stringify({ forwarded_ids: [], last_updated: new Date().toISOString() }, null, 2),
                            'utf8'
                        );
                        console.log('✅ Cleared forwarded state after deletion');
                    }
                }
            } catch (error) {
                console.error(`⚠️  Could not delete forwarded messages: ${error.message}`);
            }
        }
        
        console.log('✅ SMS retrieval completed successfully');
        process.exit(0);
        
    } catch (error) {
        console.error(`❌ Error: ${error.message}`);
        console.error(error.stack);
        process.exit(1);
        
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

// Run the script
main();
