import base64
import hashlib
import logging
import os
import random
import re
import time
from collections import OrderedDict
from typing import Any
from urllib.parse import urlencode

import requests
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad
from requests import Response

from . import tplink_crypto

logger = logging.getLogger(__name__)


class TPLinkModemAuth:
    def __init__(self, base_url="http://localhost:3080/", username="admin", password=""):
        self.base_url = base_url.rstrip('/') + '/'
        self.actual_router = os.environ.get("ROUTER_ACTUAL", "http://192.168.7.1/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.jsessionid = None
        self.rsa_bits = 512

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.actual_router.rstrip('/'),
            "Referer": self.actual_router,
            "Connection": "keep-alive",
        })
        self.session.cookies.set("loginErrorShow", "1")

    def _parse_js_var_string(self, text, var_name):
        m = re.search(rf"var\s+{re.escape(var_name)}\s*=\s*([^;]+);", text)
        if not m: return ""
        expr = m.group(1)
        parts = re.findall(r'"([0-9A-Fa-f]*)"', expr)
        return "".join(parts)

    def _parse_js_var_int(self, text, var_name):
        m = re.search(rf"var\s+{re.escape(var_name)}\s*=\s*\"?(\d+)\"?\s*;", text)
        return m.group(1) if m else "0"

    def _gen_random_string(self, length=16):
        ts = str(int(time.time() * 1000))
        rn = str(random.random() * 1000000000)
        return (ts + rn)[:length]

    def login(self):
        try:
            logger.info(f"Starting login to {self.base_url}")
            self.session.cookies.clear()
            self.session.cookies.set("loginErrorShow", "1")

            logger.debug(f"Fetching getParm from {self.base_url}cgi/getParm")
            r = self.session.get(f"{self.base_url}cgi/getParm")
            logger.debug(f"getParm response status: {r.status_code}")

            data, sign = self.encrypt_data(r)
            logger.debug(f"Encrypted data length: {len(data)}, sign length: {len(sign) if sign else 0}")

            params = OrderedDict([("data", data), ("sign", sign), ("Action", "1"), ("LoginStatus", "0")])
            login_url = f"{self.base_url}cgi/login?{urlencode(params)}"
            logger.debug(f"Posting login request to {login_url[:50]}...")
            r = self.session.post(login_url)
            logger.debug(f"Login response: {r.text[:100]}")

            if "$.ret=0" in r.text:
                self.jsessionid = self.session.cookies.get("JSESSIONID")
                logger.info(f"Login successful. JSESSIONID: {self.jsessionid}")
                return True
            else:
                logger.warning(f"Login failed. Response: {r.text}")
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
        return False

    def encrypt_data(self, r: Response) -> tuple[str, Any]:
        logger.debug("Parsing RSA parameters from getParm response")
        nn = self._parse_js_var_string(r.text, "nn")
        ee = self._parse_js_var_string(r.text, "ee")
        seq = self._parse_js_var_int(r.text, "seq")
        logger.debug(f"RSA modulus bits: {len(nn)*4}, exponent: {ee[:10]}..., seq: {seq}")

        rsa_key = RSA.construct((int(nn, 16), int(ee, 16)))

        aes_key = self._gen_random_string(16)
        aes_iv = self._gen_random_string(16)
        login_hash = hashlib.md5(f"{self.username}{self.password}".encode()).hexdigest()
        logger.debug(f"Generated AES key/IV, login hash: {login_hash}")

        login_plaintext = f"{self.username}\n{self.password}".encode("utf-8")
        aes_cipher = AES.new(aes_key.encode(), AES.MODE_CBC, aes_iv.encode())
        data = base64.b64encode(aes_cipher.encrypt(pad(login_plaintext, 16))).decode()

        sign_plaintext = f"key={aes_key}&iv={aes_iv}&h={login_hash}&s={int(seq) + len(data)}"
        logger.debug(f"Sign plaintext length: {len(sign_plaintext)}")
        sign = tplink_crypto.rsa_encrypt_nopadding(sign_plaintext, rsa_key, rsa_bits=self.rsa_bits)
        return data, sign

    def make_encrypted_call(self, operation: str, params: dict = None) -> Response:
        """
        Make an encrypted API call to /cgi_gdpr endpoint.
        
        Args:
            operation: The operation to perform (e.g., "LTE_SMS_RECVMSGBOX")
            params: Optional parameters for the operation
        
        Returns:
            Response object from the API call
        """
        try:
            # Get fresh RSA parameters
            r = self.session.get(f"{self.base_url}cgi/getParm")
            data, sign = self.encrypt_data(r)
            
            # Format the request body
            body = f"sign={sign}\r\ndata={data}\r\n"
            
            response = self.session.post(
                f"{self.base_url}cgi_gdpr",
                data=body,
                headers={"Content-Type": "text/plain"}
            )
            
            logger.debug(f"Encrypted call response: {response.status_code}")
            return response
            
        except Exception as e:
            logger.error(f"Error making encrypted call: {e}", exc_info=True)
            raise
