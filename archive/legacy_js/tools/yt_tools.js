/**
 * src/tools/yt_tools.js
 * YouTube Tools - Search, Play Music, Play Video
 * Format: Registry Pattern — export array of tool objects
 */
const { exec } = require('child_process');
const play = require('play-dl');
const logger = require('../utils/logger');

// ===================== INTERNAL HELPERS =====================

function extractVideoId(url) {
    if (!url) return null;
    const patterns = [
        /(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})/,
        /(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
        /(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
        /(?:https?:\/\/)?(?:www\.)?music\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
    ];
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) return match[1];
    }
    return null;
}

async function searchYouTube(query, limit = 5) {
    try {
        const searchResult = await play.search(query, { limit });
        return searchResult;
    } catch (error) {
        logger.error('ytSearch', `Search error: ${error.message}`);
        throw error;
    }
}

function parseMusicQuery(query) {
    let cleanQuery = query;
    const prefixes = ['putar lagu', 'putar musik', 'mainkan lagu', 'mainkan musik', 'play music', 'play song', 'putarkan lagu', 'putarkan musik'];
    for (const prefix of prefixes) {
        if (cleanQuery.toLowerCase().startsWith(prefix)) {
            cleanQuery = cleanQuery.substring(prefix.length).trim();
            break;
        }
    }
    cleanQuery = cleanQuery.replace(/^"|"$/g, '').trim();
    let songTitle = cleanQuery;
    let artist = '';
    const separators = [' dari ', ' by ', ' - ', ' — '];
    for (const sep of separators) {
        const idx = cleanQuery.toLowerCase().indexOf(sep);
        if (idx > 0) {
            songTitle = cleanQuery.substring(0, idx).trim();
            artist = cleanQuery.substring(idx + sep.length).trim();
            break;
        }
    }
    return { songTitle, artist, fullQuery: cleanQuery };
}

// ===================== EXPORTED TOOL LOGIC =====================

async function yt_search_tool(query) {
    logger.tool('yt_search_tool', `Searching YouTube: "${query}"`);
    try {
        const searchResult = await searchYouTube(query, 5);
        if (!searchResult || searchResult.length === 0) {
            return "Maaf, tidak ada hasil yang ditemukan di YouTube.";
        }
        let result = `🔍 **Hasil Pencarian YouTube untuk: "${query}"**\n\n`;
        searchResult.forEach((item, index) => {
            result += `${index + 1}. **${item.title}**\n`;
            result += `   👤 ${item.channel?.name || 'Unknown'}\n`;
            result += `   ⏱️ ${item.durationRaw || 'N/A'} | 👁️ ${item.views || 'N/A'}\n`;
            result += `   🔗 https://www.youtube.com/watch?v=${item.id}\n\n`;
        });
        return result;
    } catch (error) {
        logger.error('yt_search_tool', error);
        return `❌ Gagal mencari di YouTube: ${error.message}`;
    }
}

async function play_youtube_music(query) {
    logger.tool('play_youtube_music', `Playing: "${query}"`);
    try {
        const parsed = parseMusicQuery(query);
        let finalVideoId;
        let url;
        const videoId = extractVideoId(query);
        if (videoId) {
            finalVideoId = videoId;
            url = `https://music.youtube.com/watch?v=${videoId}`;
        } else {
            const searchResult = await searchYouTube(parsed.fullQuery, 1);
            if (!searchResult || searchResult.length === 0) {
                return `❌ Tidak dapat menemukan lagu "${query}" di YouTube.`;
            }
            const bestMatch = searchResult[0];
            finalVideoId = bestMatch.id;
            url = `https://music.youtube.com/watch?v=${bestMatch.id}`;
        }
        
        const jsonPayload = JSON.stringify({ videoId: finalVideoId, type: 'music', title: parsed.songTitle, artist: parsed.artist });
        return `🎵 **Memutar Musik di Jarvis**\n🎶 Lagu: ${parsed.songTitle}\n🎤 Artis: ${parsed.artist || '—'}\n\n\`\`\`snippet.youtube\n${jsonPayload}\n\`\`\``;
    } catch (error) {
        logger.error('play_youtube_music', error);
        return `❌ Gagal memutar musik: ${error.message}`;
    }
}

async function play_youtube_video(query) {
    logger.tool('play_youtube_video', `Playing video: "${query}"`);
    try {
        let finalVideoId;
        let url;
        const videoId = extractVideoId(query);
        if (videoId) {
            finalVideoId = videoId;
            url = `https://www.youtube.com/watch?v=${videoId}`;
        } else {
            const searchResult = await searchYouTube(query, 1);
            if (!searchResult || searchResult.length === 0) {
                return `❌ Tidak dapat menemukan video "${query}" di YouTube.`;
            }
            const bestMatch = searchResult[0];
            finalVideoId = bestMatch.id;
            url = `https://www.youtube.com/watch?v=${bestMatch.id}`;
        }
        
        const jsonPayload = JSON.stringify({ videoId: finalVideoId, type: 'video' });
        return `🎬 **Memutar Video di Jarvis**\n🔗 ${url}\n\n\`\`\`snippet.youtube\n${jsonPayload}\n\`\`\``;
    } catch (error) {
        logger.error('play_youtube_video', error);
        return `❌ Gagal memutar video: ${error.message}`;
    }
}

async function open_youtube_channel(query) {
    logger.tool('open_youtube_channel', `Searching channel: "${query}"`);
    try {
        // Bersihkan prefix umum dari query
        let cleanQuery = query.trim();
        const prefixes = ['buka youtube channel', 'buka channel', 'buka youtube chanel',
                          'open channel', 'channel', 'chanel', 'kanal'];
        for (const prefix of prefixes) {
            if (cleanQuery.toLowerCase().startsWith(prefix)) {
                cleanQuery = cleanQuery.substring(prefix.length).trim();
                break;
            }
        }
        if (!cleanQuery) {
            return `❌ Nama channel tidak boleh kosong.`;
        }

        // Cari channel via play-dl (type: 'channel', bukan 'video')
        const searchResult = await play.search(cleanQuery, { limit: 3, type: 'channel' });

        if (!searchResult || searchResult.length === 0) {
            // Fallback: kalau search channel kosong, coba search biasa dan ambil info channel dari video teratas
            const videoResults = await play.search(cleanQuery, { limit: 1 });
            if (videoResults && videoResults.length > 0 && videoResults[0].channel?.url) {
                const channelUrl = videoResults[0].channel.url;
                const channelName = videoResults[0].channel.name;
                const command = process.platform === 'win32' ? `start "" "${channelUrl}"` : `open "${channelUrl}"`;
                exec(command, (error) => { if (error) logger.error('open_youtube_channel', `exec error: ${error.message}`); });
                return `✅ Membuka channel **${channelName}**\n🔗 ${channelUrl}\n\n💡 Catatan: channel ditemukan lewat video terkait, bukan pencarian channel langsung.`;
            }
            return `❌ Tidak dapat menemukan channel "${cleanQuery}" di YouTube. Coba cek ejaan nama channel-nya.`;
        }

        const bestMatch = searchResult[0];
        const channelUrl = bestMatch.url;
        const channelName = bestMatch.name || cleanQuery;
        const subscribers = bestMatch.subscribers || 'N/A';

        const command = process.platform === 'win32' ? `start "" "${channelUrl}"` : `open "${channelUrl}"`;
        exec(command, (error) => { if (error) logger.error('open_youtube_channel', `exec error: ${error.message}`); });

        logger.tool('open_youtube_channel', `Opened: ${channelName} -> ${channelUrl}`);
        return `✅ **Membuka Channel YouTube**\n📺 ${channelName}\n👥 Subscriber: ${subscribers}\n🔗 ${channelUrl}`;

    } catch (error) {
        logger.error('open_youtube_channel', error);
        return `❌ Gagal membuka channel: ${error.message}. Coba gunakan search_youtube untuk mencari manual.`;
    }
}

async function getVideoInfo(url) {
    logger.tool('getVideoInfo', `Getting info: "${url}"`);
    try {
        const videoId = extractVideoId(url);
        if (!videoId) throw new Error('URL YouTube tidak valid');
        const info = await play.video_info(`https://www.youtube.com/watch?v=${videoId}`);
        const videoDetails = info.video_details;
        return {
            title: videoDetails.title || 'Unknown',
            description: videoDetails.description || 'No description',
            descriptionInfo: videoDetails.description?.substring(0, 200) || '',
            duration: videoDetails.durationRaw || 'N/A',
            views: videoDetails.views || 0,
            channel: videoDetails.channel?.name || 'Unknown',
            thumbnail: videoDetails.thumbnail?.url || '',
            url: `https://www.youtube.com/watch?v=${videoId}`,
            videoId: videoId
        };
    } catch (error) {
        logger.error('getVideoInfo', error);
        throw error;
    }
}

async function getAudioStream(url) {
    logger.tool('getAudioStream', `Getting audio stream: "${url}"`);
    try {
        const stream = await play.stream(url, { quality: 0 });
        return stream;
    } catch (error) {
        logger.error('getAudioStream', error);
        throw error;
    }
}

// ===================== REGISTRY TOOLS =====================

const ytTools = [
    {
        name: "search_youtube",
        description: "Mencari konten video/musik di YouTube dan mengembalikan 5 hasil teratas dengan judul, channel, durasi, dan link.",
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Kata kunci pencarian di YouTube. Contoh: 'tutorial react js', 'podcast AI', 'lagu indonesia'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const result = await yt_search_tool(args.query || '');
            return { success: true, data: result };
        }
    },
    {
        name: "play_music",
        description: "Memutar lagu/musik dari YouTube Music di browser. Cari judul lagu dan artis, lalu buka di music.youtube.com.",
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Judul lagu atau URL YouTube. Contoh: 'bohemian rhapsody queen', 'https://youtu.be/abc123'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const result = await play_youtube_music(args.query || '');
            return { success: true, data: result };
        }
    },
    {
        name: "play_video",
        description: "Memutar video dari YouTube di browser. Cari judul video atau gunakan URL langsung.",
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Judul video atau URL YouTube. Contoh: 'tutorial react js', 'https://youtu.be/abc123'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const result = await play_youtube_video(args.query || '');
            return { success: true, data: result };
        }
    },
    {
        name: "open_youtube_channel",
        description: "Mencari dan langsung membuka halaman channel YouTube tertentu di browser. Gunakan ini khusus saat user eksplisit minta 'buka channel X' atau 'buka kanal X', BUKAN untuk mencari video/lagu biasa.",
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Nama channel YouTube yang ingin dibuka. Contoh: 'MiawAug', 'Jerome Polin', 'Deddy Corbuzier'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const result = await open_youtube_channel(args.query || '');
            return { success: true, data: result };
        }
    }
];

// Backward compatibility untuk code lama
ytTools.yt_search_tool = yt_search_tool;
ytTools.play_youtube_music = play_youtube_music;
ytTools.play_youtube_video = play_youtube_video;
ytTools.open_youtube_channel = open_youtube_channel;
ytTools.getVideoInfo = getVideoInfo;
ytTools.getAudioStream = getAudioStream;

module.exports = ytTools;