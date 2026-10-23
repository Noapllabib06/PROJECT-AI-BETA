"""System control, File operations, and Git executor tools for JARVIS.

Consolidates:
- src/tools/system_control.js
- src/tools/file_tools.js
- src/tools/git_tools.js
"""

import os
import sys
import shutil
import ctypes
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import settings, get_logger

logger = get_logger("CodeExecutor")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ==========================================
# System Control Tools
# ==========================================

APP_SHORTCUTS = {
    "kalkulator": "calc",
    "calculator": "calc",
    "notepad": "notepad",
    "catatan": "notepad",
    "spotify": "spotify",
    "discord": "discord",
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "file explorer": "explorer",
    "explorer": "explorer",
    "terminal": "wt",
    "cmd": "cmd",
    "powershell": "powershell"
}


def open_app(query: str) -> str:
    """Launches desktop applications locally on Windows."""
    clean_query = query.lower().strip()
    cmd = APP_SHORTCUTS.get(clean_query, clean_query)

    logger.info(f"Opening desktop app: '{cmd}'")
    try:
        if sys.platform == "win32":
            os.system(f"start {cmd}")
        elif sys.platform == "darwin":
            os.system(f"open -a '{cmd}'")
        else:
            os.system(f"{cmd} &")
        return f"✅ Berhasil membuka aplikasi '{query}'."
    except Exception as e:
        logger.error(f"Failed to open app {query}: {e}")
        return f"❌ Gagal membuka aplikasi '{query}': {str(e)}"


def control_volume(query: str) -> str:
    """Adjusts master system audio volume on Windows using SendMessage keystrokes."""
    clean = query.lower()
    logger.info(f"Controlling audio volume: '{clean}'")

    if sys.platform != "win32":
        return "⚠️ Pengaturan volume saat ini hanya didukung di sistem Windows."

    VK_VOLUME_MUTE = 0xAD
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF

    user32 = ctypes.windll.user32

    def press_key(key_code: int, times: int = 1):
        for _ in range(times):
            user32.keybd_event(key_code, 0, 0, 0)
            user32.keybd_event(key_code, 0, 2, 0)

    if "mute" in clean or "bisu" in clean or "matikan suara" in clean:
        press_key(VK_VOLUME_MUTE)
        return "🔇 Volume berhasil di-mute / toggle mute."
    elif "turunkan" in clean or "kecilkan" in clean or "down" in clean:
        press_key(VK_VOLUME_DOWN, 5)
        return "🔉 Volume berhasil diturunkan 10%."
    elif "naikkan" in clean or "besarkan" in clean or "tambah" in clean or "up" in clean:
        press_key(VK_VOLUME_UP, 5)
        return "🔊 Volume berhasil dinaikkan 10%."
    else:
        press_key(VK_VOLUME_UP, 2)
        return "🔊 Status volume diperbarui."


def get_system_info(query: str = "") -> str:
    """Returns local operating system and hardware status."""
    import platform
    import psutil  # type: ignore
    uname = platform.uname()
    cpu_pct = psutil.cpu_percent(interval=0.1) if "psutil" in sys.modules else "N/A"
    ram = psutil.virtual_memory() if "psutil" in sys.modules else None
    ram_str = f"{ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB ({ram.percent}%)" if ram else "N/A"

    return (
        f"💻 **Informasi Sistem Host:**\n"
        f"- OS: {uname.system} {uname.release} (Build {uname.version})\n"
        f"- Arsitektur: {uname.machine}\n"
        f"- Processor: {uname.processor}\n"
        f"- Penggunaan CPU: {cpu_pct}%\n"
        f"- Penggunaan RAM: {ram_str}\n"
    )


# ==========================================
# File System Tools
# ==========================================

def _resolve_safe_path(filepath: str) -> Path:
    raw_path = Path(filepath.strip())
    if raw_path.is_absolute():
        return raw_path
    return (BASE_DIR / raw_path).resolve()


def create_file(query: str) -> str:
    """Creates or overwrites a file. Format: 'filename|content' or 'filename'."""
    parts = query.split("|", 1)
    filename = parts[0].strip()
    content = parts[1] if len(parts) > 1 else ""

    target_path = _resolve_safe_path(filename)
    logger.info(f"Creating file at: {target_path}")
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ Berhasil membuat file: `{target_path.name}` ({len(content)} karakter ditulis)."
    except Exception as e:
        logger.error(f"Failed to create file {filename}: {e}")
        return f"❌ Gagal membuat file `{filename}`: {str(e)}"


def read_file(query: str) -> str:
    """Reads content from a local file."""
    target_path = _resolve_safe_path(query)
    logger.info(f"Reading file: {target_path}")

    if not target_path.exists():
        return f"❌ File `{query}` tidak ditemukan."

    try:
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if len(content) > 4000:
            preview = content[:4000] + f"\n\n... [Dipangkas, total {len(content)} karakter]"
        else:
            preview = content

        return f"📄 **Isi File: `{target_path.name}`**\n\n```\n{preview}\n```"
    except Exception as e:
        return f"❌ Gagal membaca file `{query}`: {str(e)}"


def list_directory(query: str = ".") -> str:
    """Lists files and folders in a specified directory."""
    target_path = _resolve_safe_path(query or ".")
    if not target_path.exists():
        return f"❌ Direktori `{query}` tidak ditemukan."

    try:
        entries = []
        for item in sorted(target_path.iterdir()):
            icon = "📁" if item.is_dir() else "📄"
            entries.append(f"{icon} {item.name}")
        return f"📂 **Daftar Berkas: `{target_path.name}`**\n\n" + "\n".join(entries[:50])
    except Exception as e:
        return f"❌ Gagal membaca direktori `{query}`: {str(e)}"


def delete_file(query: str) -> str:
    """Deletes a file safely."""
    target_path = _resolve_safe_path(query)
    if not target_path.exists():
        return f"❌ Berkas `{query}` tidak ditemukan."

    try:
        if target_path.is_file():
            target_path.unlink()
            return f"🗑️ Berhasil menghapus file `{target_path.name}`."
        elif target_path.is_dir():
            shutil.rmtree(target_path)
            return f"🗑️ Berhasil menghapus folder `{target_path.name}`."
        return f"❌ Format berkas `{query}` tidak didukung."
    except Exception as e:
        return f"❌ Gagal menghapus `{query}`: {str(e)}"


# ==========================================
# Git Tools
# ==========================================

def _run_git(args: List[str]) -> str:
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=15.0
        )
        if res.returncode == 0:
            return res.stdout.strip() or "Perintah git berhasil tanpa output."
        return f"Git error: {res.stderr.strip()}"
    except Exception as e:
        return f"Gagal menjalankan git: {str(e)}"


def git_status(query: str = "") -> str:
    """Checks git repository status."""
    out = _run_git(["status", "--short"])
    return f"🌿 **Git Status:**\n```\n{out}\n```"


def git_log(query: str = "-5") -> str:
    """Shows git commit history."""
    n = query.strip() if query and query.strip().startswith("-") else "-5"
    out = _run_git(["log", "--oneline", n])
    return f"📜 **Git Log ({n}):**\n```\n{out}\n```"


def git_diff(query: str = "") -> str:
    """Shows unstaged changes in repository."""
    out = _run_git(["diff"])
    if not out:
        return "🌿 Tidak ada perubahan yang belum di-commit (working tree bersih)."
    return f"🔍 **Git Diff:**\n```diff\n{out[:3000]}\n```"


def git_commit(query: str) -> str:
    """Stages all changes and creates a commit with the specified message."""
    if not query or not query.strip():
        return "❌ Pesan commit tidak boleh kosong."

    _run_git(["add", "."])
    out = _run_git(["commit", "-m", query.strip()])
    return f"✅ **Git Commit:**\n{out}"


# ==========================================
# Codebase Ingest Tool (Memory Integration)
# ==========================================

def ingest_codebase(query: str) -> str:
    """Indexes source code files of a project directory into long-term vector RAG memory."""
    from scripts.build_index import build_codebase_index
    target_path = _resolve_safe_path(query)
    if not target_path.exists():
        return f"❌ Direktori `{query}` tidak ditemukan."

    try:
        count = build_codebase_index(str(target_path))
        return f"✅ **Berhasil mengindeks codebase!** Total {count} potongan kode tersimpan dalam memori RAG."
    except Exception as e:
        return f"❌ Gagal mengindeks codebase: {str(e)}"


# ==========================================
# Tool Definitions for Registry
# ==========================================

TOOL_DEFINITIONS = [
    {
        "name": "open_app",
        "description": "Membuka aplikasi desktop di sistem lokal (kalkulator, notepad, spotify, vscode, task manager, dll).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Nama aplikasi"}}, "required": ["query"]},
        "handler": open_app
    },
    {
        "name": "control_volume",
        "description": "Mengatur volume suara sistem (naikkan, turunkan, mute/unmute).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Instruksi volume (naikkan/turunkan/mute)"}}, "required": ["query"]},
        "handler": control_volume
    },
    {
        "name": "create_file",
        "description": "Membuat file baru di komputer. Format: namafile|isi_konten.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Format namafile|isi"}}, "required": ["query"]},
        "handler": create_file
    },
    {
        "name": "read_file",
        "description": "Membaca teks isi file dari direktori komputer.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Path berkas"}}, "required": ["query"]},
        "handler": read_file
    },
    {
        "name": "list_directory",
        "description": "Melihat daftar file dan folder dalam sebuah direktori.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Path direktori (default: .)"}}, "required": ["query"]},
        "handler": list_directory
    },
    {
        "name": "delete_file",
        "description": "Menghapus file atau direktori dari penyimpanan lokal.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Path berkas yang akan dihapus"}}, "required": ["query"]},
        "handler": delete_file
    },
    {
        "name": "git_status",
        "description": "Mengecek status perubahan git repository saat ini.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Kueri opsional"}}},
        "handler": git_status
    },
    {
        "name": "git_log",
        "description": "Melihat histori commit terbaru pada git repository.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Jumlah commit (contoh: -5)"}}},
        "handler": git_log
    },
    {
        "name": "git_diff",
        "description": "Melihat perubahan baris kode (diff) yang belum di-commit.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Kueri opsional"}}},
        "handler": git_diff
    },
    {
        "name": "git_commit",
        "description": "Melakukan git add . dan git commit dengan pesan yang ditentukan.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Pesan commit"}}, "required": ["query"]},
        "handler": git_commit
    },
    {
        "name": "ingest_codebase",
        "description": "Mengindeks seluruh file kode dalam sebuah direktori proyek ke dalam memori vektor (RAG).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Path direktori proyek"}}, "required": ["query"]},
        "handler": ingest_codebase
    }
]
