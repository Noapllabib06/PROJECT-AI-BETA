/**
 * src/tools/web_tools.js
 * Universal Web Tools - Browsing, Scraping, Search
 * Format: Registry Pattern — export array of tool objects
 */
const { exec } = require('child_process');
const axios = require('axios');
const cheerio = require('cheerio');
const logger = require('../utils/logger');
const { processWebContent } = require('../engine/context_manager');

// ===================== INTERNAL CONSTANTS & HELPERS =====================

const KNOWN_SITES_MAP = new Map([
    ['youtube', 'https://www.youtube.com'],
    ['youtube music', 'https://music.youtube.com'],
    ['google', 'https://www.google.com'],
    ['google maps', 'https://www.google.com/maps'],
    ['maps', 'https://www.google.com/maps'],
    ['gmail', 'https://mail.google.com'],
    ['github', 'https://github.com'],
    ['stackoverflow', 'https://stackoverflow.com'],
    ['reddit', 'https://www.reddit.com'],
    ['twitter', 'https://twitter.com'],
    ['x', 'https://x.com'],
    ['facebook', 'https://www.facebook.com'],
    ['instagram', 'https://www.instagram.com'],
    ['linkedin', 'https://www.linkedin.com'],
    ['whatsapp', 'https://web.whatsapp.com'],
    ['web whatsapp', 'https://web.whatsapp.com'],
    ['wa', 'https://web.whatsapp.com'],
    ['telegram', 'https://web.telegram.org'],
    ['discord', 'https://discord.com'],
    ['spotify', 'https://open.spotify.com'],
    ['netflix', 'https://www.netflix.com'],
    ['amazon', 'https://www.amazon.com'],
    ['wikipedia', 'https://www.wikipedia.org'],
    ['detik', 'https://www.detik.com'],
    ['kompas', 'https://www.kompas.com'],
    ['tokopedia', 'https://www.tokopedia.com'],
    ['shopee', 'https://shopee.co.id'],
    ['gojek', 'https://www.gojek.com'],
    ['grab', 'https://www.grab.com'],
    ['chatgpt', 'https://chat.openai.com'],
    ['chat gpt', 'https://chat.openai.com'],
    ['deepseek', 'https://chat.deepseek.com'],
    ['claude', 'https://claude.ai'],
    ['perplexity', 'https://www.perplexity.ai'],
    ['bing', 'https://www.bing.com'],
    ['yahoo', 'https://www.yahoo.com'],
    ['duckduckgo', 'https://duckduckgo.com'],
    ['tiktok', 'https://www.tiktok.com'],
    ['pinterest', 'https://www.pinterest.com'],
    ['canva', 'https://www.canva.com'],
    ['zoom', 'https://zoom.us'],
    ['meet', 'https://meet.google.com'],
    ['google meet', 'https://meet.google.com'],
    ['classroom', 'https://classroom.google.com'],
    ['google classroom', 'https://classroom.google.com'],
    ['drive', 'https://drive.google.com'],
    ['google drive', 'https://drive.google.com'],
    ['docs', 'https://docs.google.com'],
    ['google docs', 'https://docs.google.com'],
    ['sheets', 'https://sheets.google.com'],
    ['google sheets', 'https://sheets.google.com'],
    ['notion', 'https://www.notion.so'],
    ['figma', 'https://www.figma.com'],
    ['medium', 'https://medium.com'],
    ['quora', 'https://www.quora.com'],
    ['twitch', 'https://www.twitch.tv'],
    ['imdb', 'https://www.imdb.com'],
    ['cnn', 'https://www.cnn.com'],
    ['bbc', 'https://www.bbc.com'],
    ['the verge', 'https://www.theverge.com'],
    ['techcrunch', 'https://techcrunch.com'],
    ['wired', 'https://www.wired.com'],
    ['hacker news', 'https://news.ycombinator.com'],
    ['LMS Telkom University', 'https://lms.telkomuniversity.ac.id'],
    ['LMS Tel-U', 'https://lms.telkomuniversity.ac.id'],
    ['Igracias', 'https://igracias.telkomuniversity.ac.id'],
    ['zoom', 'https://zoom.us'],
]);

const KNOWN_SITES = Object.fromEntries(KNOWN_SITES_MAP);

function isValidUrl(text) {
    if (text.startsWith('http://') || text.startsWith('https://')) return true;
    const domainRegex = /^([\da-z\.-]+)\.([a-z\.]{2,})(\/[^\s]*)?$/i;
    return domainRegex.test(text);
}

function isArticleTitle(text) {
    const cleaned = text.replace(/^(buka|open|browse)\s+/i, '').trim();
    const words = cleaned.split(/\s+/).filter(w => w.length > 0);
    if (words.length >= 3 && !cleaned.includes('.')) return true;
    if (cleaned.length > 60 && !cleaned.includes('.') && !cleaned.includes('/')) return true;
    return false;
}

function findKnownSite(text) {
    const lowerText = text.toLowerCase();
    if (KNOWN_SITES[lowerText]) return KNOWN_SITES[lowerText];

    const words = lowerText.split(/\s+/).filter(w => w.length > 1);

    for (const [key, url] of KNOWN_SITES_MAP) {
        const lowerKey = key.toLowerCase();
        if (lowerKey === lowerText) return url;

        const keyWords = lowerKey.split(/\s+/);

        const match = words.every(w => keyWords.some(kw => {
            // Alias pendek (<=3 karakter) wajib exact match, cegah substring collision
            if (kw.length <= 3 || w.length <= 3) {
                return kw === w;
            }
            return kw.includes(w) || w.includes(kw);
        }));

        if (match) return url;
    }
    return null;
}

function buildPlatformSearchUrl(text) {
    const lowerText = text.toLowerCase();
    const platforms = [
        { keywords: ['wikipedia', 'wiki'], url: (q) => `https://id.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(q)}` },
        { keywords: ['youtube', 'yt'], url: (q) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}` },
        { keywords: ['google'], url: (q) => `https://www.google.com/search?q=${encodeURIComponent(q)}` },
        { keywords: ['github'], url: (q) => `https://github.com/search?q=${encodeURIComponent(q)}` },
        { keywords: ['stackoverflow', 'stack overflow'], url: (q) => `https://stackoverflow.com/search?q=${encodeURIComponent(q)}` },
        { keywords: ['reddit'], url: (q) => `https://www.reddit.com/search/?q=${encodeURIComponent(q)}` },
        { keywords: ['twitter', 'x'], url: (q) => `https://twitter.com/search?q=${encodeURIComponent(q)}` },
        { keywords: ['instagram'], url: (q) => `https://www.instagram.com/search/?q=${encodeURIComponent(q)}` },
        { keywords: ['imdb'], url: (q) => `https://www.imdb.com/find?q=${encodeURIComponent(q)}` },
        { keywords: ['npm'], url: (q) => `https://www.npmjs.com/search?q=${encodeURIComponent(q)}` },
        { keywords: ['pypi', 'python package'], url: (q) => `https://pypi.org/search/?q=${encodeURIComponent(q)}` },
        { keywords: ['amazon', 'shop'], url: (q) => `https://www.amazon.com/s?k=${encodeURIComponent(q)}` },
    ];
    for (const platform of platforms) {
        const hasPlatform = platform.keywords.some(k => lowerText.includes(k));
        if (hasPlatform) {
            let searchQuery = text;
            for (const kw of platform.keywords) {
                searchQuery = searchQuery.replace(new RegExp(kw, 'gi'), '').trim();
            }
            searchQuery = searchQuery.replace(/^(buka|open|browse|website|web|situs|halaman)\s+/i, '').trim();
            searchQuery = searchQuery.replace(/\s+(tentang|di|pada|untuk|mengenai)\s+/gi, ' ').trim();
            if (searchQuery) return platform.url(searchQuery);
        }
    }
    const kampusWords = ['telkom', 'tel-u', 'telkomuniversity', 'polban', 'itb', 'ugm', 'ui', 'unpad', 'undip', 'univ', 'university'];
    const hasKampus = kampusWords.some(k => lowerText.includes(k));
    if (hasKampus) {
        if (lowerText.includes('telkom') || lowerText.includes('tel-u') || lowerText.includes('telkomuniversity')) return 'https://lms.telkomuniversity.ac.id';
        if (lowerText.includes('polban')) return 'https://lms.polban.ac.id';
    }
    return null;
}

function normalizeUrl(input) {
    let text = input.trim().toLowerCase();
    text = text.replace(/^(buka|open|browse)\s+/i, '').trim();
    text = text.replace(/^(website|web|situs|halaman)\s+/i, '').trim();
    text = text.replace(/\s+di\s+browser$/i, '').trim();
    if (text.startsWith('http://') || text.startsWith('https://')) return text;
    if (text.includes('.')) return text.startsWith('http') ? text : `https://${text}`;
    const knownUrl = findKnownSite(text);
    if (knownUrl) return knownUrl;
    
    // DIHAPUS: fallback tebak domain single-word (`https://www.${text}.com`)
    // Alasan: menebak domain yang belum tentu eksis, kontradiktif dengan
    // kebijakan "jangan menebak URL" yang sudah diterapkan di jalur lain.
    
    const platformUrl = buildPlatformSearchUrl(text);
    if (platformUrl) return platformUrl;
    return null; // null akan otomatis jatuh ke fallback Google Search di open_web_tool()
}

function extractLocation(rawQuery) {
    const stopWords = /\b(buka|tolong|carikan|cari|lalu|tampilkan|lokasi|dari|di|ke|menuju|sekitar|google|maps|map)\b/gi;
    let cleanLocation = rawQuery.replace(stopWords, '').trim();
    return cleanLocation.replace(/\s+/g, ' ');
}

function extractUrl(text) {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const match = text.match(urlRegex);
    if (!match) return null;
    let url = match[0];
    url = url.replace(/[)\]>]+$/, '');
    return url;
}

// ===================== INTERNAL TOOL LOGIC =====================

function open_web_tool(input) {
    logger.tool('open_web_tool', `Input: "${input}"`);
    try {
        const mapKeywords = ['maps', 'google maps', 'map', 'lokasi', 'cari di peta', 'petakan'];
        const lowerInput = input.toLowerCase();
        const isMapRequest = mapKeywords.some(k => lowerInput.includes(k)) &&
                            (lowerInput.includes('cari') || lowerInput.includes('lokasi') || 
                             lowerInput.includes('tempat') || lowerInput.includes('search') ||
                             lowerInput.includes('dari'));
        if (isMapRequest) {
            const location = extractLocation(input);
            if (location && location.length > 2) {
                const encodedLocation = encodeURIComponent(location);
                const mapSearchUrl = `https://www.google.com/maps/search/${encodedLocation}`;
                const jsonPayload = JSON.stringify({ url: mapSearchUrl, title: `Maps: ${location}` });
                logger.tool('open_web_tool', `Map search URL: ${mapSearchUrl}`);
                return `✅ Membuka lokasi ${location} di Google Maps...\n\n\`\`\`snippet.web\n${jsonPayload}\n\`\`\``;
            }
        }
        if (isArticleTitle(input)) {
            const msg = `❌ Input "${input}" tidak valid sebagai URL. Ini terlihat seperti teks biasa (mungkin judul artikel), bukan URL atau nama situs. Jangan membuat URL palsu. Gunakan search_web untuk mencari halaman ini.`;
            logger.warn('open_web_tool', msg);
            return msg;
        }
        let cleanedInput = input.replace(/^(buka|open|browse)\s+/i, '').trim();
        if (cleanedInput.includes('.')) {
            if (!isValidUrl(cleanedInput)) {
                const msg = `❌ "${cleanedInput}" bukan format URL/domain yang valid. Jangan menebak URL. Gunakan search_web untuk mencari informasi.`;
                logger.warn('open_web_tool', msg);
                return msg;
            }
        }
        const url = normalizeUrl(input);
        if (url) {
            logger.tool('open_web_tool', `Normalized URL: ${url}`);
            const jsonPayload = JSON.stringify({ url: url, title: cleanedInput });
            return `✅ **Membuka Halaman Web di Jarvis**\n🔗 ${url}\n\n\`\`\`snippet.web\n${jsonPayload}\n\`\`\``;
        } else {
            const searchQuery = encodeURIComponent(cleanedInput);
            const searchUrl = `https://www.google.com/search?q=${searchQuery}`;
            const jsonPayload = JSON.stringify({ url: searchUrl, title: `Search: ${cleanedInput}` });
            return `🔍 Mencari "${cleanedInput}" di Google...\n✅ Membuka hasil pencarian.\n\n\`\`\`snippet.web\n${jsonPayload}\n\`\`\``;
        }
    } catch (error) {
        logger.error('open_web_tool', error);
        return `❌ Gagal membuka: ${error.message}. Coba ketik "cari ${input}" untuk mencari di Google.`;
    }
}

async function scrape_web_tool(url) {
    const startTime = Date.now();
    logger.tool('scrape_web_tool', `Scraping: ${url}`);
    try {
        let targetUrl = url;
        if (!url.startsWith('http')) targetUrl = `https://${url}`;
        const response = await axios.get(targetUrl, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
            timeout: 15000
        });
        const $ = cheerio.load(response.data);
        $('script, style, nav, footer, header, iframe, noscript, svg, form, button, input').remove();
        
        let images = [];
        $('img').each((i, el) => {
            let src = $(el).attr('src') || $(el).attr('data-src');
            if (src && src.startsWith('http') && !src.includes('data:image') && !src.includes('logo') && !src.includes('icon')) {
                images.push(src);
            }
        });
        // Filter unik & batasi maksimal 5 gambar
        images = [...new Set(images)].slice(0, 5);
        let imagesText = images.length > 0 ? `\n\n🖼️ **Galeri Gambar:**\n${images.map(src => `![Image](${src})`).join('\n')}` : '';

        let text = '';
        $('p, h1, h2, h3, h4, h5, h6, li, td, th, blockquote, pre, code, article, section, div.content, div.main, div.article-body').each((i, el) => {
            const line = $(el).text().trim();
            if (line.length > 30) text += line + '\n\n';
        });
        if (text.length < 100) text = $('body').text().replace(/\s+/g, ' ').trim();
        const duration = Date.now() - startTime;
        if (text.length > 1500) {
            const { chunks, contextManager, stats } = processWebContent(text, targetUrl, 1500);
            logger.tool('scrape_web_tool', `Chunked: ${stats.totalChunks} chunks, ${stats.totalChars} chars (${duration}ms)`);
            const summary = chunks.find(c => c.isSummary) || chunks[0];
            const conclusion = chunks.find(c => c.isConclusion) || chunks[chunks.length - 1];
            return `📄 **Konten dari ${targetUrl}**\n\n📊 Statistik: ${stats.totalChunks} chunks, ${stats.totalChars} total chars\n\n📝 **Ringkasan:**\n${summary.text}\n\n💡 **Info:** Konten telah di-chunking.${imagesText}\n\n🔗 **Sumber:** ${targetUrl}`;
        } else {
            logger.tool('scrape_web_tool', `Success (${duration}ms, ${text.length} chars)`);
            return `📄 **Konten dari ${targetUrl}**\n\n${text}${imagesText}`;
        }
    } catch (error) {
        logger.error('scrape_web_tool', error, { url });
        return `❌ Gagal membaca halaman: ${error.message}`;
    }
}

function decodeBingUrl(bingUrl) {
    if (!bingUrl) return '';
    if (bingUrl.includes('&u=a1')) {
        try {
            const uParam = bingUrl.split('&u=a1')[1].split('&')[0];
            return Buffer.from(uParam, 'base64').toString('utf8');
        } catch (e) {
            return bingUrl;
        }
    }
    return bingUrl;
}

function cleanSearchQuery(rawQuery) {
    if (!rawQuery || typeof rawQuery !== 'string') return '';
    let cleaned = rawQuery.trim();
    // Hilangkan kata-kata basa-basi percakapan yang sering merusak hasil mesin pencari
    cleaned = cleaned.replace(/^(tolong|coba|bisa|mohon|carikan|cariin|cari)\s+(di\s+internet|di\s+web|info\s+tentang|informasi\s+tentang|tentang)?\s*/gi, '');
    cleaned = cleaned.replace(/\b(di\s+internet|di\s+web|di\s+google|dong|ya|sih|kah)\b/gi, '');
    cleaned = cleaned.replace(/\s+/g, ' ').trim();
    return cleaned || rawQuery;
}

/**
 * Pencarian Faktual Ensiklopedia via Wikipedia Indonesia API resmi
 */
async function searchWikipedia(query, limit = 2) {
    try {
        const cleanQ = cleanSearchQuery(query);
        const searchUrl = `https://id.wikipedia.org/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(cleanQ)}&utf8=&format=json&srlimit=${limit}`;
        const res = await axios.get(searchUrl, {
            headers: { 'User-Agent': 'JarvisAI/1.0 (jarvis@project-ai.local)' },
            timeout: 8000
        });
        const list = res.data?.query?.search || [];
        if (list.length === 0) return [];

        // Ambil kutipan pengantar (extract) untuk artikel teratas
        const topTitle = list[0].title;
        let fullExtract = '';
        try {
            const extractUrl = `https://id.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=1&explaintext=1&titles=${encodeURIComponent(topTitle)}&format=json`;
            const extractRes = await axios.get(extractUrl, {
                headers: { 'User-Agent': 'JarvisAI/1.0 (jarvis@project-ai.local)' },
                timeout: 5000
            });
            const pages = extractRes.data?.query?.pages || {};
            const pageId = Object.keys(pages)[0];
            if (pageId && pages[pageId]?.extract) {
                fullExtract = pages[pageId].extract.substring(0, 800);
            }
        } catch (e) {}

        return list.map((item, idx) => {
            const link = `https://id.wikipedia.org/wiki/${encodeURIComponent(item.title.replace(/\s+/g, '_'))}`;
            const snippet = (idx === 0 && fullExtract) ? fullExtract : item.snippet.replace(/<[^>]+>/g, '').trim();
            return {
                source: 'Wikipedia Indonesia',
                title: item.title,
                link: link,
                snippet: snippet
            };
        });
    } catch (e) {
        logger.warn('searchWikipedia', `Wikipedia API error: ${e.message}`);
        return [];
    }
}

/**
 * Pencarian Berita & Artikel Terkini via Google News RSS
 */
async function searchGoogleNews(query, limit = 4) {
    try {
        const cleanQ = cleanSearchQuery(query);
        const url = `https://news.google.com/rss/search?q=${encodeURIComponent(cleanQ)}&hl=id&gl=ID&ceid=ID:id`;
        const res = await axios.get(url, { 
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
            timeout: 8000 
        });
        const $ = cheerio.load(res.data, { xmlMode: true });
        const items = [];
        $('item').slice(0, limit).each((i, el) => {
            const title = $(el).find('title').text().trim();
            const link = $(el).find('link').text().trim();
            const pubDate = $(el).find('pubDate').text().trim();
            const source = $(el).find('source').text().trim() || 'Google News';
            if (title && link) {
                items.push({
                    source: `Google News (${source})`,
                    title: title,
                    link: link,
                    snippet: `Dipublikasikan: ${pubDate}`
                });
            }
        });
        return items;
    } catch (e) {
        logger.warn('searchGoogleNews', `Google News error: ${e.message}`);
        return [];
    }
}

/**
 * Pencarian Web Lengkap via Google Custom Search JSON API (jika API key tersedia di .env)
 */
async function searchGoogleCustom(query, limit = 5) {
    const apiKey = process.env.GOOGLE_SEARCH_API_KEY;
    const cx = process.env.GOOGLE_SEARCH_CX;
    if (!apiKey || !cx) return [];

    try {
        const cleanQ = cleanSearchQuery(query);
        const url = `https://www.googleapis.com/customsearch/v1?key=${apiKey}&cx=${cx}&q=${encodeURIComponent(cleanQ)}&num=${limit}&hl=id&gl=id`;
        const res = await axios.get(url, { timeout: 8000 });
        const items = res.data?.items || [];
        return items.map(item => ({
            source: 'Google Search',
            title: item.title,
            link: item.link,
            snippet: item.snippet
        }));
    } catch (e) {
        logger.warn('searchGoogleCustom', `Google Custom Search API error: ${e.message}`);
        return [];
    }
}

async function performWebSearch(query) {
    const cleanQ = cleanSearchQuery(query);
    logger.info('performWebSearch', `Query original: "${query}" -> Cleaned: "${cleanQ}"`);

    // 1. Cek Google Custom Search (jika API key terpasang di .env)
    const googleCustomResults = await searchGoogleCustom(cleanQ, 5);
    
    // 2. Eksekusi Wikipedia dan Google News secara paralel
    const [wikiResults, newsResults] = await Promise.all([
        searchWikipedia(cleanQ, 2),
        searchGoogleNews(cleanQ, 4)
    ]);

    const combined = [...googleCustomResults, ...wikiResults, ...newsResults];

    if (combined.length === 0) {
        return [];
    }

    return combined.map((item, index) => {
        return `${index + 1}. [${item.title}](${item.link}) — *${item.source}*\n   Deskripsi: ${item.snippet}\n`;
    });
}

async function search_web_tool(query) {
    const startTime = Date.now();
    logger.tool('search_web_tool', `Searching: "${query}"`);
    try {
        const results = await performWebSearch(query);
        if (results.length === 0) return "Maaf, tidak ada hasil yang ditemukan dari mesin pencari.";
        const duration = Date.now() - startTime;
        logger.tool('search_web_tool', `Success (${duration}ms, ${results.length} results)`);
        return `🔍 **Hasil Pencarian Web (Google & Wikipedia) untuk: "${query}"**\n\n` + results.join('\n');
    } catch (error) {
        logger.error('search_web_tool', error);
        const fallbackUrl = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
        const command = process.platform === 'win32' ? `start "" "${fallbackUrl}"` : `open "${fallbackUrl}"`;
        exec(command);
        return `❌ Gagal mencari di web: ${error.message}\n✅ Membuka halaman hasil pencarian di browser: ${fallbackUrl}`;
    }
}

async function readWebTool(url) {
    logger.tool('readWebTool', `Reading URL: "${url.substring(0, 100)}"`);
    try {
        const { data } = await axios.get(url, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' },
            timeout: 15000
        });
        const $ = cheerio.load(data);
        $('script, style, nav, footer, header, aside, iframe, noscript').remove();
        let cleanText = $('body').text().replace(/\s+/g, ' ').trim();
        const MAX_CHARS = 4000;
        if (cleanText.length > MAX_CHARS) {
            cleanText = cleanText.substring(0, MAX_CHARS) + "\n\n... [TEKS DIPOTONG: Halaman terlalu panjang]";
        }
        return cleanText || "[KOSONG] Halaman tidak mengandung teks yang bisa dibaca.";
    } catch (error) {
        return `Gagal membaca web: ${error.message}`;
    }
}

// ===================== REGISTRY TOOLS =====================

const webTools = [
    {
        name: "open_website",
        description: "Membuka URL atau nama situs populer di browser default. Contoh: 'buka youtube', 'open google maps', 'https://example.com'.",
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Nama situs, URL, atau perintah untuk dibuka. Contoh: 'youtube', 'google maps jakarta', 'https://github.com'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const result = open_web_tool(args.query || '');
            return { success: true, data: result };
        }
    },
    {
        name: "search_web",
        description: "Mencari informasi terkini, artikel, berita, dan fakta di internet via Google dan Wikipedia. Mengembalikan judul, tautan (URL), sumber, dan deskripsi cuplikan.",
        keywords: ['cari di web', 'cari di internet', 'search web', 'google', 'berita terbaru', 'info terbaru', 'siapa presiden', 'harga', 'cari berita'],
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Kata kunci inti pencarian (tanpa kata sambung berlebih). Contoh: 'Presiden Indonesia saat ini', 'contoh esai anti korupsi', 'harga laptop ASUS ROG'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const query = args.query || '';
            try {
                if (!query) return { success: false, error: "Query pencarian tidak boleh kosong." };

                const results = await performWebSearch(query);

                if (results.length === 0) {
                    return { success: false, error: "Tidak ada hasil yang ditemukan dari mesin pencari." };
                }

                return { 
                    success: true, 
                    data: `🔍 **Hasil Pencarian Web (Google & Wikipedia) untuk: "${query}"**\n\n${results.join('\n')}` 
                };
            } catch (error) {
                console.error("[search_web_tool_registry] Raw Error:", error);
                logger.error('search_web_tool_registry', error);
                return { success: false, error: error.message || "Failed to execute search" };
            }
        }
    },
    {
        name: "search_wikipedia",
        description: "Mencari ensiklopedia Wikipedia Indonesia untuk definisi konsep, sejarah, biografi tokoh, sains, hukum, dan pengetahuan umum faktual.",
        keywords: ['wikipedia', 'wiki', 'apa itu', 'siapa itu', 'sejarah', 'definisi', 'biografi', 'pengertian'],
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Topik atau nama entitas yang ingin dicari di Wikipedia. Contoh: 'Kecerdasan buatan', 'Soekarno', 'Hukum Newton', 'KPK'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const query = args.query || '';
            try {
                if (!query) return { success: false, error: "Query pencarian tidak boleh kosong." };
                const results = await searchWikipedia(query, 3);
                if (results.length === 0) {
                    return { success: false, error: `Tidak ditemukan artikel Wikipedia untuk topik "${query}".` };
                }
                const formatted = results.map((r, i) => `${i + 1}. [${r.title}](${r.link})\n   Kutipan: ${r.snippet}\n`).join('\n');
                return {
                    success: true,
                    data: `📚 **Hasil Ensiklopedia Wikipedia untuk: "${query}"**\n\n${formatted}`
                };
            } catch (error) {
                logger.error('search_wikipedia', error);
                return { success: false, error: error.message || "Gagal mencari di Wikipedia" };
            }
        }
    },
    {
        name: "read_webpage",
        description: "Membaca konten teks dari sebuah halaman web/artikel. Berguna untuk merangkum berita, dokumentasi, atau artikel panjang.",
        parameters: {
            type: "object",
            properties: {
                url: {
                    type: "string",
                    description: "URL lengkap halaman web yang ingin dibaca. Contoh: 'https://id.wikipedia.org/wiki/Kecerdasan_buatan'."
                }
            },
            required: ["url"]
        },
        execute: async (args) => {
            const result = await scrape_web_tool(args.url || '');
            return { success: true, data: result };
        }
    }
];

// Backward compatibility exports untuk code lama yang masih import secara langsung
webTools.open_web_tool = open_web_tool;
webTools.scrape_web_tool = scrape_web_tool;
webTools.search_web_tool = search_web_tool;
webTools.readWebTool = readWebTool;
webTools.extractUrl = extractUrl;
webTools.KNOWN_SITES = KNOWN_SITES;

module.exports = webTools;