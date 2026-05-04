"""
2FA (Two-Factor Authentication) Handler for Roblox.
Supports TOTP (Time-based One-Time Password) and backup codes.

Features:
- TOTP code generation from secret keys
- Backup code validation
- 2FA account file management
"""
import os
import sys
import time
import hmac
import hashlib
import base64
import struct
from typing import Optional, Dict, List, Tuple
from pathlib import Path

# Try to import pyotp for TOTP
try:
    import pyotp
    HAS_PYOTP = True
except ImportError:
    HAS_PYOTP = False
    print("[!] Install pyotp for TOTP support: pip install pyotp")


class TwoFAHandler:
    """
    Handles 2FA authentication for Roblox accounts.
    """
    
    # File paths
    TWOFA_ACCOUNTS_FILE = Path("2fa_accounts.txt")
    TWOFA_SECRETS_FILE = Path("2fa_secrets.txt")  # More secure storage
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.accounts_2fa = {}  # username -> {secret, backup_codes}
        self._load_2fa_accounts()
    
    def log(self, msg: str):
        if self.debug:
            print(f"[2FA] {msg}")
    
    def _load_2fa_accounts(self):
        """Load 2FA accounts from files."""
        
        # Load from 2fa_accounts.txt (format: username:secret:backup_codes)
        if self.TWOFA_ACCOUNTS_FILE.exists():
            try:
                with open(self.TWOFA_ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        parts = line.split(':')
                        if len(parts) >= 2:
                            username = parts[0].lower()
                            secret = parts[1]
                            backup_codes = parts[2].split(',') if len(parts) > 2 else []
                            
                            self.accounts_2fa[username] = {
                                'secret': secret,
                                'backup_codes': backup_codes
                            }
                            
                self.log(f"Loaded {len(self.accounts_2fa)} 2FA accounts")
            except Exception as e:
                self.log(f"Error loading 2FA accounts: {e}")
        
        # Also load from 2fa_secrets.txt (format: username secret backup_codes)
        if self.TWOFA_SECRETS_FILE.exists():
            try:
                with open(self.TWOFA_SECRETS_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        parts = line.split()
                        if len(parts) >= 2:
                            username = parts[0].lower()
                            secret = parts[1]
                            backup_codes = parts[2].split(',') if len(parts) > 2 else []
                            
                            if username not in self.accounts_2fa:
                                self.accounts_2fa[username] = {
                                    'secret': secret,
                                    'backup_codes': backup_codes
                                }
            except Exception as e:
                self.log(f"Error loading 2FA secrets: {e}")
    
    def has_2fa(self, username: str) -> bool:
        """Check if account has 2FA enabled."""
        return username.lower() in self.accounts_2fa
    
    def get_totp_code(self, username: str) -> Optional[str]:
        """Generate TOTP code for account."""
        
        username = username.lower()
        
        if username not in self.accounts_2fa:
            return None
        
        secret = self.accounts_2fa[username].get('secret')
        if not secret:
            return None
        
        try:
            if HAS_PYOTP:
                # Use pyotp library
                totp = pyotp.TOTP(secret)
                code = totp.now()
                self.log(f"Generated TOTP code for {username}: {code}")
                return code
            else:
                # Manual TOTP implementation
                code = self._generate_totp_manual(secret)
                self.log(f"Generated TOTP code (manual) for {username}: {code}")
                return code
                
        except Exception as e:
            self.log(f"Error generating TOTP: {e}")
            return None
    
    def _generate_totp_manual(self, secret: str) -> Optional[str]:
        """Manual TOTP implementation without pyotp."""
        
        try:
            # Remove spaces and convert to uppercase
            secret = secret.upper().replace(' ', '')
            
            # Decode base32 secret
            secret_bytes = base64.b32decode(secret, casefold=True)
            
            # Get current time interval (30 second window)
            time_interval = int(time.time() // 30)
            
            # Pack time as big-endian 64-bit integer
            time_bytes = struct.pack('>Q', time_interval)
            
            # Calculate HMAC-SHA1
            hmac_result = hmac.new(secret_bytes, time_bytes, hashlib.sha1).digest()
            
            # Get offset from last nibble
            offset = hmac_result[-1] & 0x0F
            
            # Get 4 bytes starting at offset
            code_bytes = hmac_result[offset:offset + 4]
            
            # Convert to integer (masking sign bit)
            code_int = struct.unpack('>I', code_bytes)[0] & 0x7FFFFFFF
            
            # Get last 6 digits
            code = str(code_int % 1000000).zfill(6)
            
            return code
            
        except Exception as e:
            self.log(f"Manual TOTP error: {e}")
            return None
    
    def get_backup_code(self, username: str) -> Optional[str]:
        """Get a backup code for account."""
        
        username = username.lower()
        
        if username not in self.accounts_2fa:
            return None
        
        backup_codes = self.accounts_2fa[username].get('backup_codes', [])
        
        if backup_codes:
            # Return first unused backup code
            return backup_codes[0]
        
        return None
    
    def use_backup_code(self, username: str, code: str) -> bool:
        """Mark a backup code as used."""
        
        username = username.lower()
        
        if username not in self.accounts_2fa:
            return False
        
        backup_codes = self.accounts_2fa[username].get('backup_codes', [])
        
        if code in backup_codes:
            backup_codes.remove(code)
            self._save_2fa_accounts()
            return True
        
        return False
    
    def _save_2fa_accounts(self):
        """Save 2FA accounts to file."""
        
        try:
            lines = []
            lines.append("# 2FA Accounts File")
            lines.append("# Format: username:secret:backup_code1,backup_code2,...")
            lines.append("# Example: myuser:JBSWY3DPEHPK3PXP:123456,789012")
            lines.append("")
            
            for username, data in self.accounts_2fa.items():
                backup_codes = ','.join(data.get('backup_codes', []))
                line = f"{username}:{data['secret']}:{backup_codes}"
                lines.append(line)
            
            with open(self.TWOFA_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
                
            self.log("Saved 2FA accounts")
            
        except Exception as e:
            self.log(f"Error saving 2FA accounts: {e}")
    
    def add_account(self, username: str, secret: str, backup_codes: List[str] = None):
        """Add a 2FA account."""
        
        username = username.lower()
        
        self.accounts_2fa[username] = {
            'secret': secret,
            'backup_codes': backup_codes or []
        }
        
        self._save_2fa_accounts()
        self.log(f"Added 2FA account: {username}")
    
    def remove_account(self, username: str):
        """Remove a 2FA account."""
        
        username = username.lower()
        
        if username in self.accounts_2fa:
            del self.accounts_2fa[username]
            self._save_2fa_accounts()
            self.log(f"Removed 2FA account: {username}")


def create_2fa_template():
    """Create template 2FA accounts file."""
    
    template = """# 2FA Accounts File for Roblox Checker
# ==========================================
# 
# Format: username:secret_key:backup_codes
#
# - username: Roblox username (case-insensitive)
# - secret_key: TOTP secret key (from authenticator app setup)
# - backup_codes: Comma-separated list of backup codes (optional)
#
# Examples:
#
# Single account with just TOTP:
# myusername:JBSWY3DPEHPK3PXP
#
# Account with TOTP and backup codes:
# myusername:JBSWY3DPEHPK3PXP:123456,789012,345678
#
# Account with only backup codes (no TOTP secret):
# myusername::123456,789012
#
# How to get your TOTP secret:
# 1. Go to Roblox Settings -> Security
# 2. Enable 2-Step Verification
# 3. Choose "Authenticator App"
# 4. When shown the QR code, look for the "manual entry" option
# 5. The secret key is shown there (usually 16-32 characters)
#
# IMPORTANT: Keep this file secure! Anyone with these secrets
# can generate 2FA codes for your accounts.
#
"""
    
    with open('2fa_accounts.txt', 'w', encoding='utf-8') as f:
        f.write(template)
    
    print("[+] Created 2fa_accounts.txt template")
    print("[+] Edit the file and add your 2FA accounts")


# Global instance
_2fa_handler = None


def get_2fa_handler(debug: bool = False) -> TwoFAHandler:
    """Get or create global 2FA handler instance."""
    global _2fa_handler
    if _2fa_handler is None:
        _2fa_handler = TwoFAHandler(debug=debug)
    return _2fa_handler


if __name__ == "__main__":
    print("=" * 50)
    print("2FA Handler for Roblox Checker")
    print("=" * 50)
    
    # Create template file
    create_2fa_template()
    
    # Test the handler
    handler = TwoFAHandler(debug=True)
    
    # Test manual TOTP (using a test secret)
    print("\n[TEST] Manual TOTP implementation:")
    test_secret = "JBSWY3DPEHPK3PXP"  # Known test secret
    code = handler._generate_totp_manual(test_secret)
    print(f"Test code: {code}")
    
    if HAS_PYOTP:
        print("\n[TEST] Using pyotp library:")
        totp = pyotp.TOTP(test_secret)
        print(f"Test code: {totp.now()}")