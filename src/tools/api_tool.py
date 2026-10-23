"""API tools: IMAP Email reader & Secure Encrypted Credential Manager for JARVIS.

Consolidates:
- src/tools/email_tools.js
- src/tools/credential_tools.js
- src/utils/credentials.js
"""

import os
import sys
import json
import socket
import getpass
import hashlib
import imaplib
import email
from email.header import decode_header
from pathlib import Path
from typing import Dict, Any, List, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from config.settings import get_logger

logger = get_logger("APITools")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CREDENTIALS_FILE = BASE_DIR / ".jarvis-credentials.json"


# ==========================================
# Secure Local Encrypted Credential Manager
# ==========================================

class CredentialVault:
    """Manages encrypted user credentials stored locally using AES-256-CBC."""

    def __init__(self, filepath: Optional[Path] = None):
        self.file_path = filepath or CREDENTIALS_FILE
        self.master_key = self._generate_machine_key()
        self.credentials: Dict[str, Any] = {}
        self.load()

    def _generate_machine_key(self) -> bytes:
        """Derives a stable 32-byte key from local machine signature."""
        try:
            hostname = socket.gethostname()
            username = getpass.getuser()
            seed = f"{hostname}-{username}-jarvis-local-vault-2026"
            return hashlib.sha256(seed.encode("utf-8")).digest()
        except Exception:
            return hashlib.sha256(b"jarvis-default-fallback-key").digest()

    def _encrypt(self, plaintext: str) -> Optional[str]:
        try:
            iv = os.urandom(16)
            cipher = Cipher(algorithms.AES(self.master_key), modes.CBC(iv), backend=default_backend())
            encryptor = cipher.encryptor()

            data = plaintext.encode("utf-8")
            # PKCS7 padding
            pad_len = 16 - (len(data) % 16)
            padded_data = data + bytes([pad_len] * pad_len)

            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            return iv.hex() + ":" + ciphertext.hex()
        except Exception as e:
            logger.error(f"Encrypt failed: {e}")
            return None

    def _decrypt(self, encrypted_payload: str) -> Optional[str]:
        try:
            parts = encrypted_payload.strip().split(":")
            if len(parts) != 2:
                return None
            iv = bytes.fromhex(parts[0])
            ciphertext = bytes.fromhex(parts[1])

            cipher = Cipher(algorithms.AES(self.master_key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            pad_len = padded_plaintext[-1]
            return padded_plaintext[:-pad_len].decode("utf-8")
        except Exception as e:
            logger.error(f"Decrypt failed: {e}")
            return None

    def load(self) -> None:
        if not self.file_path.exists():
            self.credentials = {}
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            decrypted = self._decrypt(content)
            if decrypted:
                self.credentials = json.loads(decrypted)
                logger.debug(f"Loaded {len(self.credentials)} encrypted credentials.")
        except Exception as e:
            logger.error(f"Failed to load credentials vault: {e}")
            self.credentials = {}

    def save(self) -> None:
        try:
            raw_json = json.dumps(self.credentials, indent=2, ensure_ascii=False)
            encrypted = self._encrypt(raw_json)
            if encrypted:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(encrypted)
        except Exception as e:
            logger.error(f"Failed to save credentials vault: {e}")

    def set_credential(self, service: str, username: str, password: str, metadata: Optional[Dict] = None) -> None:
        self.credentials[service.lower()] = {
            "service": service,
            "username": username,
            "password": password,
            "metadata": metadata or {}
        }
        self.save()

    def get_credential(self, service: str) -> Optional[Dict[str, Any]]:
        return self.credentials.get(service.lower())

    def list_services(self) -> List[str]:
        return list(self.credentials.keys())

    def delete_credential(self, service: str) -> bool:
        key = service.lower()
        if key in self.credentials:
            del self.credentials[key]
            self.save()
            return True
        return False


vault = CredentialVault()


def save_credential(query: str) -> str:
    """Saves encrypted credentials. Format: 'service: password' or 'service: user|pass'."""
    clean = query.strip()
    if ":" in clean:
        service, rest = clean.split(":", 1)
        service = service.strip()
        rest = rest.strip()
        if "|" in rest:
            user, pwd = rest.split("|", 1)
            vault.set_credential(service, user.strip(), pwd.strip())
        else:
            vault.set_credential(service, service, rest)
        return f"🔐 Kredensial untuk `{service}` berhasil disimpan dengan enkripsi AES-256."

    return "❌ Format kredensial harus 'layanan: password' atau 'layanan: username|password'."


def get_credential(query: str) -> str:
    """Retrieves an encrypted credential by service name."""
    cred = vault.get_credential(query.strip())
    if not cred:
        return f"❌ Kredensial untuk layanan `{query}` tidak ditemukan."
    return f"🔑 **Kredensial `{cred['service']}`:**\n- Username: `{cred['username']}`\n- Password: `{cred['password']}`"


def list_credentials(query: str = "") -> str:
    """Lists saved credential service names without showing passwords."""
    services = vault.list_services()
    if not services:
        return "🔐 Belum ada kredensial yang tersimpan di brankas terenkripsi."
    items = "\n".join(f"- {s}" for s in services)
    return f"🔐 **Daftar Layanan Tersimpan:**\n{items}"


def delete_credential(query: str) -> bool:
    """Deletes an encrypted credential by service name."""
    return vault.delete_credential(query.strip())


# ==========================================
# Email Tools (IMAP / Mail Parser)
# ==========================================

def _decode_mime_words(raw: str) -> str:
    if not raw:
        return ""
    decoded_fragments = decode_header(raw)
    result = []
    for frag, enc in decoded_fragments:
        if isinstance(frag, bytes):
            result.append(frag.decode(enc or "utf-8", errors="ignore"))
        else:
            result.append(str(frag))
    return "".join(result)


def check_email(query: str = "", sender: Optional[str] = None, date: Optional[str] = None) -> str:
    """Checks emails via IMAP using saved credentials or returns mock/status if offline."""
    logger.info(f"Checking email (sender={sender}, date={date}, query={query})")

    cred = vault.get_credential("gmail") or vault.get_credential("email")
    if not cred:
        # User hasn't configured IMAP credentials yet
        return (
            "📧 **Pemeriksaan Kotak Masuk Email:**\n\n"
            "> Kredensial email belum dikonfigurasi di brankas lokal.\n\n"
            "Silakan simpan kredensial IMAP terlebih dahulu menggunakan format:\n"
            "`simpan password gmail: alamat@gmail.com|app_password_anda`"
        )

    try:
        imap_server = "imap.gmail.com"
        mail = imaplib.IMAP4_SSL(imap_server, timeout=10)
        mail.login(cred["username"], cred["password"])
        mail.select("INBOX")

        search_criteria = "ALL"
        if sender:
            search_criteria = f'(FROM "{sender}")'

        status, data = mail.search(None, search_criteria)
        mail_ids = data[0].split()

        if not mail_ids:
            return f"📧 Tidak ada email baru yang ditemukan{f' dari {sender}' if sender else ''}."

        latest_ids = mail_ids[-3:]  # Get top 3 latest
        output_parts = ["📬 **Email Terbaru di Kotak Masuk:**\n"]

        for mid in reversed(latest_ids):
            _, msg_data = mail.fetch(mid, "(RFC822)")
            if not msg_data or not isinstance(msg_data[0], tuple):
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email if isinstance(raw_email, bytes) else bytes(raw_email))

            msg_subject = _decode_mime_words(msg.get("Subject", "(Tanpa Subjek)"))
            msg_from = _decode_mime_words(msg.get("From", "(Tanpa Pengirim)"))
            msg_date = msg.get("Date", "")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body = payload.decode("utf-8", errors="ignore")
                        break
            else:
                payload = msg.get_payload(decode=True)
                if isinstance(payload, bytes):
                    body = payload.decode("utf-8", errors="ignore")

            snippet = (body[:250] + "...") if len(body) > 250 else body

            output_parts.append(
                f"- **Pengirim:** {msg_from}\n"
                f"- **Subjek:** {msg_subject}\n"
                f"- **Tanggal:** {msg_date}\n"
                f"> {snippet}\n"
            )

        mail.close()
        mail.logout()
        return "\n".join(output_parts)

    except Exception as e:
        logger.error(f"IMAP check error: {e}")
        return f"❌ Gagal memeriksa email: {str(e)}. Pastikan Anda menggunakan App Password Gmail."


def draft_email(query: str) -> str:
    """Prepares an email draft. Format: 'to@example.com | Subjek | Isi pesan'."""
    parts = [p.strip() for p in query.split("|")]
    if len(parts) < 3:
        return "❌ Format draf email harus: `penerima@email.com | Subjek | Isi pesan`."

    recipient, subject, body = parts[0], parts[1], parts[2]
    return (
        f"📝 **Draf Email Berhasil Disiapkan:**\n\n"
        f"- **Penerima:** `{recipient}`\n"
        f"- **Subjek:** {subject}\n"
        f"> {body}\n\n"
        f"Draf siap dikirimkan melalui persetujuan Anda."
    )


# ==========================================
# Tool Definitions for Registry
# ==========================================

TOOL_DEFINITIONS = [
    {
        "name": "save_credential",
        "description": "Menyimpan kata sandi / kredensial akun secara lokal dengan enkripsi AES-256.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Format: 'layanan: password' atau 'layanan: user|pass'"}}, "required": ["query"]},
        "handler": save_credential
    },
    {
        "name": "get_credential",
        "description": "Mengambil kredensial tersimpan berdasarkan nama layanan.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Nama layanan (contoh: gmail, facebook)"}}, "required": ["query"]},
        "handler": get_credential
    },
    {
        "name": "list_credentials",
        "description": "Melihat daftar layanan yang kredensialnya tersimpan di brankas terenkripsi.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Opsional"}}},
        "handler": list_credentials
    },
    {
        "name": "check_email",
        "description": "Mengecek dan membaca kotak masuk email pengguna via protokol IMAP.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Provider atau filter kueri"},
                "sender": {"type": "string", "description": "Nama atau email pengirim spesifik"},
                "date": {"type": "string", "description": "Tanggal spesifik (contoh: 14/8/2026)"}
            }
        },
        "handler": check_email
    },
    {
        "name": "draft_email",
        "description": "Menyiapkan draf email sebelum dikirimkan. Format: penerima | subjek | pesan.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Format: penerima | subjek | pesan"}}, "required": ["query"]},
        "handler": draft_email
    }
]
