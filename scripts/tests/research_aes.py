import base64
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# Target data from HAR for password "admin"
# target = "ob+A2K3Ax6zwCtZsD1Vc1w=="

def brute_force_aes():
    target_b64 = "ob+A2K3Ax6zwCtZsD1Vc1w=="
    target_bytes = base64.b64decode(target_b64)
    password = "admin"
    username = "admin"
    
    # Based on tpEncrypt.js:
    # genKey uses (new Date).getTime() + "" + 1e9*Math.random()
    # This means the key and IV are random strings of 16 characters!
    # However, for the HAR to be reproducible, they might be fixed in some contexts
    # or the user might have been lucky.
    # But wait, if they are random, how does the router know them?
    # The 'sign' parameter is the RSA-encrypted (AES_key + AES_iv + hash + seq).
    # That's how the router gets the key!
    
    # So for the HAR:
    # sign = RSA_encrypt("key=K&iv=I&h=H&s=S")
    
    print("Since AES key/IV are random (from Date/Math.random), we cannot match 'data'")
    print("without the specific key/iv used in that HAR session.")
    print("However, we can implement the random generation logic from tpEncrypt.js.")

if __name__ == "__main__":
    brute_force_aes()
