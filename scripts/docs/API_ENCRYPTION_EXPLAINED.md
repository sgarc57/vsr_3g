# Understanding the TP-Link Modem API Encryption

## The Problem: Why We Can't Just Call the API Directly

### What `$.act()` Actually Does

When you call `$.act()` in the browser console:
```javascript
$.act(ACT_GET, LTE_SMS_RECVMSGBOX, null, null, ["totalNumber", "amountPerPage"]);
$.exe();
```

**Behind the scenes, this happens:**

1. **JavaScript builds the request** - Collects parameters
2. **Encrypts the data** - Uses RSA + AES encryption with:
   - RSA public key from `/cgi/getParm` (changes per session)
   - AES key/IV generated randomly
   - Sequence number tracking
3. **POSTs to `/cgi_gdpr`** - Sends encrypted payload:
   ```
   sign=<RSA encrypted signature>
   data=<AES encrypted request data>
   ```
4. **Receives encrypted response** - Gets back encrypted data
5. **Decrypts the response** - Uses the same AES key to decrypt
6. **Returns JavaScript object** - Makes it look like a simple API call

### Why Python Can't Replicate This Easily

From your HAR file (`sms_forward_har.json`), we saw:

```json
{
  "method": "POST",
  "url": "http://192.168.7.1/cgi_gdpr",
  "postData": {
    "text": "sign=<long encrypted string>&data=<long encrypted string>"
  }
}
```

**The challenges:**

1. **Dynamic encryption keys** - RSA parameters change per session
2. **Sequence tracking** - Must track `seq` number correctly
3. **Complex encryption** - RSA (no padding) + AES-CBC + Base64
4. **Unknown request format** - Don't know what data to encrypt for SMS operations
5. **Response decryption** - Need to decrypt the response

### What We Tried

#### ❌ Attempt 1: Direct HTTP Calls
```python
# Tried calling /cgi/info directly
response = session.get(f"{base_url}cgi/info")
# Result: Empty or wrong format
```

#### ❌ Attempt 2: Replicate Encryption
```python
# Tried to encrypt like login does
data, sign = encrypt_data(r)
response = session.post(f"{base_url}cgi_gdpr", data=f"sign={sign}&data={data}")
# Result: Don't know what to encrypt for SMS operations
```

#### ✅ Solution: Use Browser's JavaScript Engine

Since the browser already has:
- The encryption/decryption logic loaded
- The session state
- The `$.act()` function ready to use

**We use Puppeteer to execute JavaScript in the browser context!**

## How Our Solution Works

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Cron Job (Every Minute)                                │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Puppeteer (Headless Browser)                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  1. Navigate to http://192.168.7.1/               │  │
│  │  2. Login with password                           │  │
│  │  3. Execute JavaScript:                           │  │
│  │     $.act(ACT_GET, LTE_SMS_RECVMSGENTRY, ...)     │  │
│  │     $.exe()                                       │  │
│  │  4. Get decrypted JavaScript object               │  │
│  │  5. Return as JSON                                │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Python Script                                          │
│  - Reads JSON from Puppeteer                           │
│  - Forwards new messages to Discord                    │
│  - Tracks state to prevent duplicates                  │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Puppeteer (Again)                                      │
│  - Deletes forwarded messages                          │
│  - Uses $.act(ACT_DEL, ...) with __stack               │
└─────────────────────────────────────────────────────────┘
```

### Why This Works

1. **Browser handles encryption** - We don't need to understand it
2. **Session management** - Browser maintains cookies and TokenID
3. **JavaScript execution** - `$.act()` works as designed
4. **No reverse engineering** - We use the modem's own code

### The Key Insight

```javascript
// In browser console - this works:
var messages = $.act(ACT_GL, LTE_SMS_RECVMSGENTRY, null, null, 
    ["index", "from", "content", "receivedTime", "unread"]);
$.exe();
console.log(messages); // Returns decrypted data!
```

```python
# In Python - this doesn't work:
response = requests.post(
    "http://192.168.7.1/cgi_gdpr",
    data="sign=???&data=???"  # What do we put here?
)
# We don't know how to construct the encrypted request
```

**Solution:** Let Puppeteer execute the JavaScript for us!

```javascript
// puppeteer_sms_retriever.js
const messages = await page.evaluate(() => {
    $.act(ACT_GL, LTE_SMS_RECVMSGENTRY, null, null, 
        ["index", "from", "content", "receivedTime", "unread"]);
    $.exe();
    return smsInboxPagelist; // Puppeteer extracts this
});
```

## What's Encrypted

### Login Request (from auth.py)
```
Plaintext: "admin\nadmin"
↓ AES-CBC encryption
Encrypted data: "base64_encoded_ciphertext"
↓ RSA signature
Sign: "key=xxx&iv=xxx&h=md5hash&s=seq"
↓ POST to /cgi_gdpr
```

### SMS Request (what $.act() does)
```
Plaintext: Unknown format (proprietary)
↓ Same encryption process
Encrypted data: "???"
↓ POST to /cgi_gdpr
Response: Encrypted SMS data
↓ Decryption in browser
JavaScript object with messages
```

## Why We Need Puppeteer

| Approach | Pros | Cons |
|----------|------|------|
| **Direct HTTP** | Fast, simple | Don't know encryption format |
| **Reverse engineer** | No browser needed | Very complex, time-consuming |
| **Puppeteer** | ✅ Works immediately<br>✅ Uses modem's code<br>✅ Handles all encryption | Requires Node.js<br>Slightly slower |

## The Encryption Details (For Reference)

From `lib/auth.py` and `lib/tplink_crypto.py`:

```python
# RSA parameters from /cgi/getParm
nn = "very_long_hex_modulus"
ee = "010001"  # Public exponent
seq = 123456   # Sequence number

# Generate random AES key/IV
aes_key = random_string(16)
aes_iv = random_string(16)

# Encrypt data with AES-CBC
plaintext = "username\npassword"
ciphertext = AES_CBC_encrypt(plaintext, aes_key, aes_iv)
data = base64_encode(ciphertext)

# Sign with RSA (no padding!)
sign_plaintext = f"key={aes_key}&iv={aes_iv}&h={md5_hash}&s={seq + len(data)}"
sign = RSA_encrypt_no_padding(sign_plaintext, rsa_key)

# POST to /cgi_gdpr
POST data: f"sign={sign}&data={data}"
```

**The problem:** We don't know what `plaintext` format to use for SMS operations!

## Summary

- ✅ **`$.act()` is NOT a limitation** - It's actually our solution!
- ✅ **Encryption is the limitation** - We can't easily replicate it in Python
- ✅ **Puppeteer solves this** - By using the browser's JavaScript engine
- ✅ **Fully automated** - No manual steps required

The system is now **100% automated** because Puppeteer handles the complex encryption/decryption by executing the modem's own JavaScript code in a headless browser.
