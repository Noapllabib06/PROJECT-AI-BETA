"""Web search, Wikipedia, Web scraper, Research, and YouTube Tools for JARVIS.

Consolidates:
- src/tools/web_tools.js
- src/tools/research_tool.js
- src/tools/yt_tools.js
"""

import os
import re
import urllib.parse
import webbrowser
from typing import Dict, Any, List, Optional
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from config.settings import settings, get_logger

logger = get_logger("WebSearchTools")


# ==========================================
# Query Normalization & Multi-Engine Helpers
# ==========================================

def clean_search_query(raw_query: str) -> str:
    """Removes Indonesian polite/conversational filler words for optimal search engine relevance."""
    if not raw_query:
        return ""
    cleaned = raw_query.strip()
    cleaned = re.sub(
        r"^(?:tolong\s+|coba\s+|bisa\s+|mohon\s+)*(?:carikan|cariin|cari)?\s*(?:di\s+internet|di\s+web|info\s+tentang|informasi\s+tentang|tentang)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:di\s+internet|di\s+web|di\s+google|dong|ya|sih|kah)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or raw_query.strip()


async def search_google_custom(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Searches using official Google Custom Search JSON API if API key and CX are configured."""
    api_key = (getattr(settings, "google_search_api_key", None) or os.getenv("GOOGLE_SEARCH_API_KEY") or "").strip()
    cx = (getattr(settings, "google_search_cx", None) or os.getenv("GOOGLE_SEARCH_CX") or "").strip()

    if not api_key or not cx:
        return []

    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": min(max_results, 10),
            "hl": "id",
            "gl": "id",
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                results = []
                for item in items:
                    title = item.get("title", "").strip()
                    link = item.get("link", "").strip()
                    snippet = item.get("snippet", "").strip()
                    if title and link:
                        results.append({
                            "source": "Google Search",
                            "title": title,
                            "link": link,
                            "snippet": snippet
                        })
                if results:
                    logger.info(f"Google Custom Search returned {len(results)} items for '{query}'")
                return results
            else:
                logger.warning(f"Google Custom Search API status {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        logger.warning(f"Google Custom Search error: {e}")
    return []


async def search_google_news(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Searches live Google News RSS (zero API key required, reliable Indonesian current events)."""
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=id&gl=ID&ceid=ID:id"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=7.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "xml")
                items = []
                for item in soup.find_all("item")[:max_results]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    source_elem = item.find("source")

                    title = title_elem.text.strip() if title_elem else ""
                    link = link_elem.text.strip() if link_elem else ""
                    pub = pub_elem.text.strip() if pub_elem else ""
                    src_name = source_elem.text.strip() if source_elem else "Google News"

                    if title and link:
                        items.append({
                            "source": f"Google News ({src_name})",
                            "title": title,
                            "link": link,
                            "snippet": f"Waktu: {pub}" if pub else ""
                        })
                return items
    except Exception as e:
        logger.debug(f"Google News RSS search warning: {e}")
    return []


async def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Searches web via DuckDuckGo."""
    results = []
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
            for r in raw_results:
                title = r.get("title", "").strip()
                snippet = r.get("body", "").strip()
                link = r.get("href", "").strip()
                if title and link:
                    results.append({
                        "source": "Web (DuckDuckGo)",
                        "title": title,
                        "link": link,
                        "snippet": snippet
                    })
    except Exception as e:
        logger.debug(f"DuckDuckGo search error: {e}")
    return results


# ==========================================
# Web & Wikipedia Search Tools
# ==========================================

async def search_web(query: str, max_results: int = 5) -> str:
    """Searches the live web using Google Custom Search API, Google News RSS, or DuckDuckGo."""
    if not query or not query.strip():
        return "❌ Kueri pencarian tidak boleh kosong."

    clean_q = clean_search_query(query)
    logger.info(f"Searching web for: '{query}' (cleaned: '{clean_q}')")

    has_google_credentials = bool(
        (getattr(settings, "google_search_api_key", None) or os.getenv("GOOGLE_SEARCH_API_KEY"))
        and (getattr(settings, "google_search_cx", None) or os.getenv("GOOGLE_SEARCH_CX"))
    )

    combined_results: List[Dict[str, str]] = []

    # 1. Official Google Custom Search JSON API (Primary if configured)
    if has_google_credentials:
        google_results = await search_google_custom(clean_q, max_results=max_results)
        combined_results.extend(google_results)

    # 2. If Google Custom API is unconfigured or returned no items, use Google News RSS + DuckDuckGo
    if not combined_results:
        news_results = await search_google_news(clean_q, max_results=3)
        ddg_results = await search_duckduckgo(clean_q, max_results=max_results)

        # Merge unique links
        seen_links = set()
        for item in news_results + ddg_results:
            link = item.get("link", "")
            if link and link not in seen_links:
                seen_links.add(link)
                combined_results.append(item)

    # 3. Format output
    if combined_results:
        formatted = []
        for idx, item in enumerate(combined_results[:max_results], 1):
            source = item.get("source", "Web")
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            snippet_str = f"\n   {snippet}" if snippet else ""
            formatted.append(f"{idx}. **[{title}]({link})** — *{source}*{snippet_str}\n")

        footer = ""
        if not has_google_credentials:
            footer = "\n\n💡 *Tip: Masukkan GOOGLE_SEARCH_API_KEY & GOOGLE_SEARCH_CX di file .env untuk hasil pencarian Google resmi indeks penuh.*"

        return f"🌐 **Hasil Pencarian Web ({len(formatted)} hasil):**\n\n" + "\n".join(formatted) + footer

    # 4. Fallback to Wikipedia if web engines returned nothing
    logger.info("Search engines returned no items, falling back to Wikipedia.")
    return await search_wikipedia(clean_q)


async def search_wikipedia(query: str) -> str:
    """Searches Indonesian and English Wikipedia for concepts, definitions, and bios."""
    clean_query = query.strip()
    logger.info(f"Searching Wikipedia for: '{clean_query}'")

    for lang in ["id", "en"]:
        try:
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(clean_query)}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url, headers={"User-Agent": "JARVIS-AI-Agent/2.0"})
                if res.status_code == 200:
                    data = res.json()
                    title = data.get("title", clean_query)
                    extract = data.get("extract", "")
                    page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

                    if extract:
                        return (
                            f"📚 **Wikipedia ({lang.upper()}): {title}**\n\n"
                            f"{extract}\n\n"
                            f"[Baca selengkapnya di Wikipedia]({page_url})"
                        )
        except Exception:
            continue

    return f"Informasi ensiklopedia untuk '{clean_query}' tidak ditemukan di Wikipedia."


async def read_webpage(url: str, max_chars: int = 3000) -> str:
    """Fetches a webpage, cleans HTML tags, and extracts readability text."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    logger.info(f"Reading webpage: {url}")
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            res = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            res.raise_for_status()

            soup = BeautifulSoup(res.text, "html.parser")

            # Remove noise
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "aside"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else url
            text = " ".join(soup.stripped_strings)

            if len(text) > max_chars:
                text = text[:max_chars] + "...\n\n[Konten dipotong karena panjang]"

            return f"📄 **Konten Webpage: {title}**\nURL: {url}\n\n{text}"

    except Exception as e:
        logger.error(f"Failed to read webpage {url}: {e}")
        return f"❌ Gagal membaca halaman web ({url}): {str(e)}"


COMMON_DOMAINS: Dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "yt": "https://www.youtube.com",
    "youtube music": "https://music.youtube.com",
    "yt music": "https://music.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "spotify": "https://open.spotify.com",
    "whatsapp": "https://web.whatsapp.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "reddit": "https://www.reddit.com",
    "chatgpt": "https://chatgpt.com",
    "tiktok": "https://www.tiktok.com",
    "netflix": "https://www.netflix.com",
    "wikipedia": "https://www.wikipedia.org",
}


def open_website(query: str) -> str:
    """Opens a website in the default browser."""
    target = query.strip()
    lower_target = target.lower()

    # Redirection check: if query is asking to play music/video, forward to specialized tool
    if any(k in lower_target for k in ["putar lagu", "putar musik", "play music", "play song", "dengarkan lagu", "setel lagu"]) or (
        lower_target.startswith("putar ") or lower_target.startswith("play ") or lower_target.startswith("setel ")
    ):
        logger.info(f"open_website redirected to play_music for query: {query}")
        return play_music(target)

    if lower_target in COMMON_DOMAINS:
        url = COMMON_DOMAINS[lower_target]
    elif not target.startswith("http://") and not target.startswith("https://"):
        if "." in target:
            url = "https://" + target
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote(target)}"
    else:
        url = target

    logger.info(f"Opening website in browser: {url}")
    webbrowser.open(url)
    return f"✅ Berhasil membuka situs web: {url}"


# ==========================================
# YouTube Tools
# ==========================================

async def search_youtube(query: str, max_results: int = 4) -> str:
    """Searches YouTube videos and returns structured titles, links, and snippets."""
    logger.info(f"Searching YouTube for: '{query}'")
    search_term = f"site:youtube.com/watch {query}"
    try:
        videos = []
        with DDGS() as ddgs:
            raw = list(ddgs.text(search_term, max_results=max_results))
            for r in raw:
                href = r.get("href", "")
                if "youtube.com/watch" in href or "youtu.be/" in href:
                    title = r.get("title", "").replace(" - YouTube", "")
                    videos.append(f"🎥 **[{title}]({href})**\n{r.get('body', '')}\n")

        if videos:
            return "▶️ **Hasil Pencarian YouTube:**\n\n" + "\n".join(videos)
        
        fallback_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        return f"▶️ Hasil pencarian YouTube dapat dibuka langsung di: [Buka YouTube]({fallback_url})"

    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        fallback_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        return f"▶️ [Klik di sini untuk mencari '{query}' di YouTube]({fallback_url})"


import json

def extract_youtube_video_id(query: str) -> Optional[str]:
    """Extracts YouTube 11-char video ID from URL or scrapes top result from YouTube."""
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})", query)
    if m:
        return m.group(1)

    clean_query = query.strip()
    try:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_query)}"
        resp = httpx.get(
            url,
            timeout=4.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        if resp.status_code == 200:
            match = re.search(r"watch\?v=([a-zA-Z0-9_-]{11})", resp.text)
            if match:
                return match.group(1)
    except Exception as e:
        logger.debug(f"Failed to scrape YouTube video ID for '{query}': {e}")
    return None


def play_music(query: str) -> str:
    """Plays music directly in YouTube Music and activates the Snippet Player tab."""
    clean_query = re.sub(
        r"^(?:putar\s+lagu|putar\s+musik|putar|setel\s+lagu|setel|play\s+song|play\s+music|play|dengarkan\s+lagu|dengarkan)\s+",
        "",
        query.strip(),
        flags=re.IGNORECASE
    ).strip() or query.strip()

    video_id = extract_youtube_video_id(clean_query)

    if video_id:
        target_url = f"https://music.youtube.com/watch?v={video_id}"
    else:
        target_url = f"https://music.youtube.com/search?q={urllib.parse.quote(clean_query)}"

    logger.info(f"Opening YouTube Music: {target_url}")
    webbrowser.open(target_url)

    payload = {
        "videoId": video_id or "search",
        "type": "music",
        "title": clean_query,
        "url": target_url
    }
    json_str = json.dumps(payload)

    return (
        f"🎵 **Memutar Musik di YouTube Music:**\n"
        f"🎶 Lagu: **{clean_query}**\n"
        f"🔗 [Buka di YouTube Music]({target_url})\n\n"
        f"```snippet.youtube\n{json_str}\n```"
    )


def play_video(query: str) -> str:
    """Plays YouTube video directly in browser and activates the Snippet Player tab."""
    clean_query = re.sub(
        r"^(?:putar\s+video|putar\s+tutorial|putar|tonton|play\s+video|play)\s+",
        "",
        query.strip(),
        flags=re.IGNORECASE
    ).strip() or query.strip()

    video_id = extract_youtube_video_id(clean_query)

    if video_id:
        target_url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_query)}"

    logger.info(f"Opening YouTube Video: {target_url}")
    webbrowser.open(target_url)

    payload = {
        "videoId": video_id or "search",
        "type": "video",
        "title": clean_query,
        "url": target_url
    }
    json_str = json.dumps(payload)

    return (
        f"🎬 **Memutar Video di YouTube:**\n"
        f"🎥 Video: **{clean_query}**\n"
        f"🔗 [Tonton di YouTube]({target_url})\n\n"
        f"```snippet.youtube\n{json_str}\n```"
    )


def open_youtube_channel(query: str) -> str:
    """Opens a YouTube channel directly in browser."""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}&sp=EgIQAg%253D%253D"
    webbrowser.open(url)
    return f"📺 Membuka kanal YouTube '{query}': {url}"


# ==========================================
# Deep Research Tool
# ==========================================

async def research_and_summarize(query: str) -> str:
    """Performs multi-angle web research and summarizes findings."""
    logger.info(f"Performing deep research on: '{query}'")
    search_results = await search_web(query, max_results=4)
    wiki_info = await search_wikipedia(query)

    parts = [
        f"# Riset Terpadu: {query}\n",
        f"### Ringkasan Ensiklopedia:\n{wiki_info}\n",
        f"### Temuan Web Terkini:\n{search_results}"
    ]
    return "\n".join(parts)


# ==========================================
# Tool Definitions for Registry
# ==========================================

TOOL_DEFINITIONS = [
    {
        "name": "search_web",
        "description": "Mencari informasi artikel, berita, harga, dan fakta real-time di internet via mesin pencari.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Kata kunci pencarian"}}, "required": ["query"]},
        "handler": search_web
    },
    {
        "name": "search_wikipedia",
        "description": "Mencari definisi konsep, ensiklopedia ilmiah, sejarah, biografi tokoh, dan profil institusi.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Topik atau nama tokoh"}}, "required": ["query"]},
        "handler": search_wikipedia
    },
    {
        "name": "read_webpage",
        "description": "Mengekstrak dan membaca teks dari URL halaman situs web tertentu.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "URL halaman web"}}, "required": ["query"]},
        "handler": read_webpage
    },
    {
        "name": "open_website",
        "description": "Membuka alamat website di browser pengguna (misal: 'google.com', 'github.com', 'youtube.com'). JANGAN gunakan untuk memutar lagu atau musik — gunakan play_music.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Nama domain atau URL"}}, "required": ["query"]},
        "handler": open_website
    },
    {
        "name": "search_youtube",
        "description": "Mencari video dan konten di YouTube.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Judul video atau topik"}}, "required": ["query"]},
        "handler": search_youtube
    },
    {
        "name": "play_music",
        "description": "Memutar lagu atau musik di YouTube Music (misal: 'putar sunshine', 'play OneRepublic - Sunshine', 'putar lagu laskar pelangi').",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Judul lagu atau artis"}}, "required": ["query"]},
        "handler": play_music
    },
    {
        "name": "play_video",
        "description": "Memutar video atau tutorial di YouTube (misal: 'putar tutorial python', 'play video masak').",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Judul video tutorial"}}, "required": ["query"]},
        "handler": play_video
    },
    {
        "name": "open_youtube_channel",
        "description": "Membuka halaman kanal / channel kreator YouTube.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Nama channel YouTube"}}, "required": ["query"]},
        "handler": open_youtube_channel
    },
    {
        "name": "research_and_summarize",
        "description": "Melakukan riset multi-sumber secara mendalam mengenai topik tertentu dan menyusun ringkasannya.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Topik riset"}}, "required": ["query"]},
        "handler": research_and_summarize
    }
]
