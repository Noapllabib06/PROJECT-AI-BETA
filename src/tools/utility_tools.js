/**
 * src/tools/utility_tools.js
 * Utilitas tambahan: Cuaca, Pencarian File Lokal, dan RSS Feed
 */

const axios = require('axios');
const RSSParser = require('rss-parser');
const { exec } = require('child_process');
const logger = require('../utils/logger');

// ===================== WEATHER TOOL =====================
async function weatherTool(query) {
    try {
        const city = query || 'Jakarta'; // default
        
        // 1. Dapatkan kordinat (Geocoding API Open-Meteo - Gratis tanpa key)
        const geoUrl = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=en&format=json`;
        const geoRes = await axios.get(geoUrl);
        
        if (!geoRes.data.results || geoRes.data.results.length === 0) {
            return `❌ Tidak dapat menemukan lokasi untuk kota: ${city}`;
        }
        
        const loc = geoRes.data.results[0];
        
        // 2. Dapatkan cuaca (Forecast API Open-Meteo)
        const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${loc.latitude}&longitude=${loc.longitude}&current_weather=true`;
        const weatherRes = await axios.get(weatherUrl);
        
        const cw = weatherRes.data.current_weather;
        
        let report = `🌤️ **Cuaca Saat Ini di ${loc.name}, ${loc.country}**\n`;
        report += `- Temperatur: ${cw.temperature}°C\n`;
        report += `- Kecepatan Angin: ${cw.windspeed} km/h\n`;
        
        // Terjemahan sederhana kode cuaca WMO
        const wmoCodes = {
            0: 'Cerah', 1: 'Sebagian Berawan', 2: 'Berawan', 3: 'Mendung',
            45: 'Kabut', 48: 'Kabut', 
            51: 'Gerimis Ringan', 53: 'Gerimis Sedang', 55: 'Gerimis Lebat',
            61: 'Hujan Ringan', 63: 'Hujan Sedang', 65: 'Hujan Lebat',
            71: 'Salju Ringan', 73: 'Salju Sedang', 75: 'Salju Lebat',
            95: 'Badai Petir', 96: 'Badai Petir + Hujan Es', 99: 'Badai Petir Lebat'
        };
        const condition = wmoCodes[cw.weathercode] || 'Tidak diketahui';
        
        report += `- Kondisi: ${condition}\n`;
        return report;
    } catch (e) {
        logger.error('weatherTool', e);
        return `❌ Gagal mengambil cuaca: ${e.message}`;
    }
}

// ===================== RSS TOOL =====================
async function rssTool(url) {
    try {
        if (!url) return `❌ Mohon berikan URL RSS feed yang valid.`;
        
        const parser = new RSSParser();
        const feed = await parser.parseURL(url);
        
        let report = `📰 **Headline Berita: ${feed.title || 'RSS Feed'}**\n`;
        const items = feed.items.slice(0, 5); // Ambil 5 teratas
        
        items.forEach((item, index) => {
            report += `${index + 1}. [${item.title}](${item.link})\n`;
        });
        
        return report;
    } catch (e) {
        logger.error('rssTool', e);
        return `❌ Gagal mengambil RSS feed: ${e.message}`;
    }
}

// ===================== LOCAL FILE SEARCH =====================
function searchFileLokal(dir, filename) {
    return new Promise((resolve) => {
        // Menggunakan PowerShell Get-ChildItem karena lebih aman menangani spasi/karakter khusus dibanding cmd dir
        const psScript = `Get-ChildItem -Path "${dir}" -Filter "*${filename}*" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 10 -ExpandProperty FullName`;
        
        exec(`powershell -NoProfile -Command "${psScript}"`, (error, stdout) => {
            if (error) {
                // Jika tidak ketemu, PowerShell sering melempar error code
                resolve(`❌ Gagal mencari file atau file tidak ditemukan di ${dir}`);
                return;
            }
            
            const out = (stdout || '').trim();
            if (!out) {
                resolve(`🔍 File dengan nama "${filename}" tidak ditemukan di direktori: ${dir}`);
            } else {
                let report = `🔍 **Hasil Pencarian File untuk "${filename}":**\n`;
                const lines = out.split('\n');
                lines.forEach(l => {
                    if (l.trim()) report += `- \`${l.trim()}\`\n`;
                });
                resolve(report);
            }
        });
    });
}

// ===================== REGISTRY =====================
const utilityTools = [
    {
        name: 'get_weather',
        description: 'Mengambil informasi cuaca saat ini untuk kota tertentu. Menggunakan API wttr.in.',
        keywords: ['cuaca', 'suhu', 'hujan', 'panas', 'mendung', 'weather'],
        parameters: {
            type: 'object',
            properties: {
                city: { type: 'string', description: 'Nama kota (misal: Jakarta, Bandung, Tokyo)' }
            },
            required: ['city']
        },
        execute: async (args) => {
            return { success: true, data: await weatherTool(args.city) };
        }
    },
    {
        name: 'read_rss_feed',
        description: 'Membaca dan merangkum berita terbaru dari URL RSS Feed atau portal berita.',
        keywords: ['berita', 'berita terbaru', 'rss', 'feed', 'news', 'baca berita'],
        parameters: {
            type: 'object',
            properties: {
                url: { type: 'string', description: 'URL RSS Feed (misal: https://www.antaranews.com/rss/terkini.xml)' }
            },
            required: ['url']
        },
        execute: async (args) => {
            return { success: true, data: await rssTool(args.url) };
        }
    },
    {
        name: 'search_local_file',
        description: 'Mencari file berdasarkan nama di dalam direktori sistem menggunakan glob pattern (sangat cepat).',
        keywords: ['cari file', 'cari dokumen', 'file search', 'cari gambar', 'cari video'],
        parameters: {
            type: 'object',
            properties: {
                pattern: { type: 'string', description: 'Kata kunci atau glob pattern (misal: *laporan*.pdf)' },
                directory: { type: 'string', description: 'Direktori awal pencarian (default: direktori Documents user)' }
            },
            required: ['pattern']
        },
        execute: async (args) => {
            return { success: true, data: await fileSearchTool(args.pattern, args.directory) };
        }
    }
];

module.exports = utilityTools;
