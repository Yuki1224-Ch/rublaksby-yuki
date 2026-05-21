# auth_intent.py - HIGH ACCURACY VERSION
# Must use the SAME session for nonce and login!

from base64 import b64encode
from time import time
import json
import random

try:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("[!] Install cryptography: pip install cryptography")


class AuthIntent:
    # Chrome 131 headers
    DEFAULT_HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131", "Not_A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }

    @staticmethod
    def string_to_bytes(raw_string) -> bytes:
        return bytes(raw_string, 'utf-8')

    @staticmethod
    def export_public_key_as_spki(public_key) -> str:
        spki_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return b64encode(spki_bytes).decode('utf-8')

    @staticmethod
    def generate_signing_key_pair_unextractable() -> tuple:
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        public_key = private_key.public_key()
        return private_key, public_key

    @staticmethod
    def sign(private_key, data) -> str:
        signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
        return b64encode(signature).decode('utf-8')

    @staticmethod
    def get_auth_intent(session) -> str | None:
        """
        Get auth intent for Roblox login.
        Uses the SAME session that will be used for login.
        Returns the secureAuthenticationIntent JSON string or empty string if failed.
        """
        if not HAS_CRYPTO:
            return ""

        try:
            # Step 1: Visit homepage to get cookies (if not already done)
            print("[AUTH] Getting initial cookies...")
            try:
                session.get("https://www.roblox.com/", timeout=10)
            except:
                pass
            
            # Step 2: Update headers
            session.headers.update({
                **AuthIntent.DEFAULT_HEADERS,
                "Origin": "https://www.roblox.com",
                "Referer": "https://www.roblox.com/login",
            })
            
            # Step 3: Get server nonce using the SAME session
            print("[AUTH] Getting server nonce...")
            url = "https://apis.roblox.com/hba-service/v1/getServerNonce"
            
            resp = session.get(url, timeout=15)
            
            if resp.status_code != 200:
                print(f"[AUTH] ❌ Nonce failed: status {resp.status_code}")
                return ""
            
            nonce = resp.text.strip().strip('"')
            if len(nonce) < 10:
                print(f"[AUTH] ❌ Invalid nonce: {nonce}")
                return ""
            
            print(f"[AUTH] ✅ Got nonce: {nonce[:20]}...")
            
            # Step 4: Generate keys and sign
            private_key, public_key = AuthIntent.generate_signing_key_pair_unextractable()
            client_public_key = AuthIntent.export_public_key_as_spki(public_key)
            client_epoch_timestamp = str(int(time() * 1000))
            
            # Construct payload and sign
            payload = f"{client_public_key}|{client_epoch_timestamp}|{nonce}"
            sai_signature = AuthIntent.sign(private_key, AuthIntent.string_to_bytes(payload))
            
            # Return as JSON string
            sai = json.dumps({
                "clientPublicKey": client_public_key,
                "clientEpochTimestamp": client_epoch_timestamp,
                "serverNonce": nonce,
                "saiSignature": sai_signature
            })
            
            print(f"[AUTH] ✅ Auth intent generated")
            return sai

        except Exception as e:
            print(f"[AUTH] ❌ Failed: {e}")
            return ""

    @staticmethod
    def get_auth_intent_simple() -> str:
        """
        Simple method - creates its own session.
        Only use if you don't have a session object.
        """
        if not HAS_CRYPTO:
            return ""
        
        try:
            from curl_cffi import requests as cffi_requests
            
            session = cffi_requests.Session(impersonate="chrome131")
            session.headers.update(AuthIntent.DEFAULT_HEADERS)
            session.headers.update({
                "Origin": "https://www.roblox.com",
                "Referer": "https://www.roblox.com/login",
            })
            
            # Visit homepage
            session.get("https://www.roblox.com/", timeout=10)
            
            # Get nonce
            resp = session.get("https://apis.roblox.com/hba-service/v1/getServerNonce", timeout=15)
            
            if resp.status_code != 200:
                return ""
            
            nonce = resp.text.strip().strip('"')
            if len(nonce) < 10:
                return ""
            
            # Generate and sign
            private_key, public_key = AuthIntent.generate_signing_key_pair_unextractable()
            client_public_key = AuthIntent.export_public_key_as_spki(public_key)
            client_epoch_timestamp = str(int(time() * 1000))
            payload = f"{client_public_key}|{client_epoch_timestamp}|{nonce}"
            sai_signature = AuthIntent.sign(private_key, AuthIntent.string_to_bytes(payload))
            
            return json.dumps({
                "clientPublicKey": client_public_key,
                "clientEpochTimestamp": client_epoch_timestamp,
                "serverNonce": nonce,
                "saiSignature": sai_signature
            })
        
        except:
            return ""