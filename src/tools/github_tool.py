"""GitHub Ingestion & Scraper Tool Suite for JARVIS.

Enables deep reading and scraping of GitHub repositories, raw files, directory trees,
and cloning for codebase memory indexing.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from config.settings import settings, get_logger

logger = get_logger("GitHubTool")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _get_github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "JARVIS-AI-Agent/2.0"
    }
    token = (getattr(settings, "github_token", None) or os.getenv("GITHUB_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """Extracts owner, repo, branch, and filepath from a GitHub URL."""
    clean_url = url.strip()
    # Match patterns like:
    # https://github.com/owner/repo
    # https://github.com/owner/repo/blob/main/path/to/file.py
    # https://github.com/owner/repo/tree/master/docs
    pattern = r"github\.com/([^/]+)/([^/]+)(?:/(blob|tree)/([^/]+)/(.+))?"
    match = re.search(pattern, clean_url)
    if not match:
        return None

    owner = match.group(1)
    repo = match.group(2).removesuffix(".git")
    ref_type = match.group(3) or "tree"
    branch = match.group(4) or "main"
    subpath = match.group(5) or ""

    return {
        "owner": owner,
        "repo": repo,
        "type": ref_type,
        "branch": branch,
        "path": subpath
    }


async def read_github_repo(query: str) -> str:
    """Reads a GitHub repository: metadata, architectural file tree, and full README."""
    parsed = parse_github_url(query)
    if not parsed:
        # If user gave "owner/repo" directly
        parts = query.strip().split("/")
        if len(parts) == 2 and not query.startswith("http"):
            parsed = {"owner": parts[0], "repo": parts[1], "branch": "main", "path": "", "type": "tree"}
        else:
            return f"❌ Format URL GitHub tidak valid: `{query}`. Contoh: `https://github.com/owner/repo`"

    owner = parsed["owner"]
    repo = parsed["repo"]
    headers = _get_github_headers()

    logger.info(f"Reading GitHub repo: {owner}/{repo}")

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # 1. Fetch Repository Metadata
        repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
        repo_data: Dict[str, Any] = {}
        try:
            r = await client.get(repo_api_url, headers=headers)
            if r.status_code == 200:
                repo_data = r.json()
            elif r.status_code == 404:
                return f"❌ Repositori `{owner}/{repo}` tidak ditemukan di GitHub atau bersifat privat."
        except Exception as e:
            logger.warning(f"Failed to fetch repo metadata: {e}")

        default_branch = repo_data.get("default_branch", parsed.get("branch", "main"))
        description = repo_data.get("description") or "Tidak ada deskripsi."
        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
        language = repo_data.get("language") or "Multi-language"
        license_name = repo_data.get("license", {}).get("spdx_id") if repo_data.get("license") else "N/A"
        topics = ", ".join(f"`{t}`" for t in repo_data.get("topics", [])) or "None"

        # 2. Fetch Full README
        readme_content = ""
        for branch_candidate in [default_branch, "main", "master"]:
            for fname in ["README.md", "readme.md", "README", "ReadMe.md"]:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch_candidate}/{fname}"
                try:
                    raw_res = await client.get(raw_url)
                    if raw_res.status_code == 200 and raw_res.text.strip():
                        readme_content = raw_res.text.strip()
                        break
                except Exception:
                    continue
            if readme_content:
                break

        # Fallback to API readme if raw didn't hit
        if not readme_content:
            try:
                api_readme = await client.get(f"{repo_api_url}/readme", headers=headers)
                if api_readme.status_code == 200:
                    import base64
                    encoded = api_readme.json().get("content", "")
                    readme_content = base64.b64decode(encoded).decode("utf-8", errors="replace")
            except Exception:
                pass

        # 3. Fetch File Tree (Structure)
        tree_summary = []
        try:
            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
            tree_res = await client.get(tree_url, headers=headers)
            if tree_res.status_code == 200:
                tree_items = tree_res.json().get("tree", [])
                files = [item["path"] for item in tree_items if item.get("type") == "blob"]
                dirs = [item["path"] for item in tree_items if item.get("type") == "tree"]

                # Top-level folders
                top_dirs = sorted({p.split("/")[0] for p in dirs if "/" in p or p})
                tree_summary.append(f"📁 **Direktori Utama:** {', '.join(f'`{d}/`' for d in top_dirs[:15])}")

                # Key configuration and entrypoint files
                key_files = [f for f in files if any(f.endswith(ext) or f in ["Dockerfile", "docker-compose.yml", "Makefile"] for ext in [".json", ".yaml", ".yml", ".toml", ".txt", ".md"])]
                if key_files:
                    tree_summary.append(f"📄 **File Konfigurasi Kunci:** {', '.join(f'`{f}`' for f in key_files[:12])}")
                tree_summary.append(f"📊 **Statistik Berkas:** Total {len(files)} file di dalam repositori.")
        except Exception as e:
            logger.debug(f"Failed to fetch tree: {e}")

    # Build comprehensive output
    output_parts = [
        f"# 📦 Repositori GitHub: [{owner}/{repo}](https://github.com/{owner}/{repo})\n",
        f"**Deskripsi:** {description}",
        f"- 🌟 **Stars:** {stars:,} | 🍴 **Forks:** {forks:,}",
        f"- 💻 **Bahasa Utama:** {language} | 📜 **Lisensi:** {license_name}",
        f"- 🏷️ **Topik:** {topics}",
        f"- 🌿 **Default Branch:** `{default_branch}`\n",
    ]

    if tree_summary:
        output_parts.append("### 🗂️ Struktur Proyek\n" + "\n".join(tree_summary) + "\n")

    if readme_content:
        # Truncate README if extremely large to prevent context window blowout
        max_readme_chars = 6000
        truncated = False
        if len(readme_content) > max_readme_chars:
            readme_content = readme_content[:max_readme_chars]
            truncated = True

        output_parts.append("### 📖 Dokumentasi README.md\n" + readme_content)
        if truncated:
            output_parts.append("\n\n*(README dipotong karena panjang. Gunakan `read_github_file` untuk membaca bagian/file spesifik.)*")
    else:
        output_parts.append("*(README.md tidak ditemukan dalam repositori ini)*")

    return "\n".join(output_parts)


async def read_github_file(query: str) -> str:
    """Reads the source code or raw text of a specific file from GitHub."""
    parsed = parse_github_url(query)
    if not parsed or not parsed.get("path"):
        return f"❌ Mohon berikan URL lengkap ke file GitHub. Contoh: `https://github.com/owner/repo/blob/main/src/app.py`"

    owner = parsed["owner"]
    repo = parsed["repo"]
    branch = parsed["branch"]
    filepath = parsed["path"]

    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filepath}"
    logger.info(f"Fetching raw GitHub file: {raw_url}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            res = await client.get(raw_url)
            if res.status_code == 200:
                content = res.text
                ext = Path(filepath).suffix.lstrip(".") or "txt"
                line_count = len(content.splitlines())
                size_kb = f"{len(content.encode('utf-8')) / 1024:.2f}"

                max_chars = 8000
                display_content = content
                truncated_note = ""
                if len(content) > max_chars:
                    display_content = content[:max_chars]
                    truncated_note = f"\n\n*(File dipotong pada 8000 karakter dari total {line_count} baris)*"

                return (
                    f"📄 **GitHub File:** `{filepath}` ({owner}/{repo})\n"
                    f"🔗 [Buka di GitHub]({query}) | 📏 {line_count} baris ({size_kb} KB)\n\n"
                    f"```{ext}\n{display_content}\n```{truncated_note}"
                )
            elif res.status_code == 404:
                return f"❌ File `{filepath}` tidak ditemukan di branch `{branch}` pada repositori `{owner}/{repo}`."
            else:
                return f"❌ Gagal mengambil file dari GitHub (Status HTTP {res.status_code})."
        except Exception as e:
            return f"❌ Terjadi kesalahan saat membaca file GitHub: {str(e)}"


def clone_and_ingest_github(query: str) -> str:
    """Clones a GitHub repository locally with depth 1 and indexes it into codebase RAG memory."""
    from scripts.build_index import build_codebase_index

    parsed = parse_github_url(query)
    if not parsed:
        return f"❌ URL GitHub tidak valid: `{query}`"

    owner = parsed["owner"]
    repo = parsed["repo"]
    clone_url = f"https://github.com/{owner}/{repo}.git"

    cache_dir = BASE_DIR / getattr(settings.github, "cache_dir", "data/raw/github_repos")
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_repo_dir = cache_dir / f"{owner}_{repo}"

    logger.info(f"Cloning/Updating GitHub repo: {clone_url} -> {target_repo_dir}")

    try:
        if (target_repo_dir / ".git").exists():
            # Pull latest
            subprocess.run(["git", "-C", str(target_repo_dir), "pull"], check=True, capture_output=True, timeout=60)
            status_msg = "Repositori sudah ada, berhasil di-pull ke versi terbaru."
        else:
            if target_repo_dir.exists():
                shutil.rmtree(target_repo_dir, ignore_errors=True)
            # Clone shallow
            cmd = ["git", "clone", "--depth", "1", clone_url, str(target_repo_dir)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            status_msg = "Repositori baru berhasil di-clone."

        # Ingest into codebase vector memory
        count = build_codebase_index(str(target_repo_dir))
        return (
            f"✅ **GitHub Codebase Berhasil Diingest!**\n"
            f"- 📦 Repositori: `{owner}/{repo}`\n"
            f"- 📁 Lokasi Lokal: `{target_repo_dir}`\n"
            f"- 🔄 Status: {status_msg}\n"
            f"- 🧠 Indeks RAG: Total {count} potongan kode tersimpan dalam memori pengetahuan JARVIS."
        )
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        logger.error(f"Git clone error: {err}")
        return f"❌ Gagal meng-clone repositori GitHub: {err}"
    except Exception as e:
        logger.error(f"Failed to clone and ingest GitHub repo: {e}")
        return f"❌ Kesalahan proses ingest GitHub: {str(e)}"


# ==========================================
# Tool Definitions for Registry
# ==========================================

TOOL_DEFINITIONS = [
    {
        "name": "read_github_repo",
        "description": "Membaca dan menganalisis repositori GitHub: mengekstrak deskripsi, stars, susunan pohon berkas (file tree/arsitektur), dan isi dokumentasi README.md lengkap.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "URL repositori GitHub (misal: 'https://github.com/facebook/react' atau 'owner/repo')"
                }
            },
            "required": ["query"]
        },
        "handler": read_github_repo
    },
    {
        "name": "read_github_file",
        "description": "Membaca teks atau source code dari file spesifik yang ada di GitHub secara langsung.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "URL file GitHub (misal: 'https://github.com/owner/repo/blob/main/src/index.js')"
                }
            },
            "required": ["query"]
        },
        "handler": read_github_file
    },
    {
        "name": "clone_and_ingest_github",
        "description": "Mengkloning repositori GitHub ke komputer lokal dan langsung mengindeks seluruh kodenya ke memori RAG jangka panjang.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "URL repositori GitHub yang ingin dikloning dan dipelajari"
                }
            },
            "required": ["query"]
        },
        "handler": clone_and_ingest_github
    }
]
