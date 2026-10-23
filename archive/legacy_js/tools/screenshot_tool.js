/**
 * src/tools/screenshot_tool.js
 * Screenshot Tool — Mengambil tangkapan layar dan menyimpannya ke Desktop
 * Format: Registry Pattern — export array of tool objects
 *
 * DEPENDENSI BARU YANG PERLU DI-INSTALL:
 *   npm install screenshot-desktop
 *
 * Catatan Tier 1 (VRAM/RAM):
 * Tool ini TIDAK memuat model AI apa pun — murni memanggil API OS
 * untuk capture layar lalu simpan ke file PNG. Konsumsi VRAM: 0.
 * Konsumsi RAM: sesaat (buffer gambar di memori selama proses simpan,
 * lalu langsung dilepas begitu selesai ditulis ke disk).
 *
 * SINERGI TIER 2 (opsional, bukan bagian dari tool ini):
 * File PNG hasil tool ini bisa dilempar ke agent.js -> _executeVision()
 * (model llava:7b yang SUDAH ada) untuk deskripsi otomatis "apa yang
 * ada di layar saya", tanpa perlu model tambahan baru sama sekali.
 */

const path = require('path');
const os = require('os');
const fs = require('fs');
const logger = require('../utils/logger');

// screenshot-desktop bersifat opsional — jika belum di-install, tool ini
// akan mengembalikan pesan error yang jelas, bukan crash seluruh app.
let screenshot = null;
try {
    screenshot = require('screenshot-desktop');
} catch (e) {
    logger.warn('ScreenshotTool', 'Package "screenshot-desktop" belum terinstall. Jalankan: npm install screenshot-desktop');
}

// ===================== INTERNAL TOOL LOGIC =====================

function generateFilename() {
    const now = new Date();
    const stamp = [
        now.getFullYear(),
        String(now.getMonth() + 1).padStart(2, '0'),
        String(now.getDate()).padStart(2, '0'),
        '_',
        String(now.getHours()).padStart(2, '0'),
        String(now.getMinutes()).padStart(2, '0'),
        String(now.getSeconds()).padStart(2, '0')
    ].join('');
    return `screenshot_${stamp}.png`;
}

async function takeScreenshotTool(query = '') {
    logger.tool('takeScreenshotTool', `Mengambil screenshot. Input: "${query}"`);

    if (!screenshot) {
        return {
            success: false,
            error: 'Fitur screenshot belum aktif. Jalankan `npm install screenshot-desktop` di terminal proyek, lalu restart aplikasi.'
        };
    }

    try {
        const desktopPath = path.join(os.homedir(), 'Desktop');
        if (!fs.existsSync(desktopPath)) {
            fs.mkdirSync(desktopPath, { recursive: true });
        }

        const filename = generateFilename();
        const filePath = path.join(desktopPath, filename);

        // Cek apakah user minta screenshot dari display/monitor tertentu
        // Contoh: "screenshot layar 2" -> displayIndex = 1 (0-based)
        const displayMatch = query.match(/(?:layar|display|monitor)\s*(\d+)/i);
        const options = { filename: filePath };

        if (displayMatch) {
            const displays = await screenshot.listDisplays();
            const idx = parseInt(displayMatch[1], 10) - 1;
            if (displays[idx]) {
                options.screen = displays[idx].id;
            } else {
                logger.warn('takeScreenshotTool', `Layar ke-${displayMatch[1]} tidak ditemukan, pakai layar utama.`);
            }
        }

        await screenshot(options);

        const stats = fs.statSync(filePath);
        const fileSizeKB = (stats.size / 1024).toFixed(2);

        logger.tool('takeScreenshotTool', `Screenshot disimpan: ${filePath} (${fileSizeKB} KB)`);

        return {
            success: true,
            data: `✅ Screenshot berhasil disimpan di Desktop: **${filename}** (${fileSizeKB} KB).`,
            filePath: filePath // dipakai internal jika mau lanjut ke vision analysis (Tier 2)
        };
    } catch (error) {
        logger.error('takeScreenshotTool', error);
        return { success: false, error: `Gagal mengambil screenshot: ${error.message}` };
    }
}

// ===================== REGISTRY TOOLS =====================

const screenshotTools = [
    {
        name: 'take_screenshot',
        description: 'Mengambil tangkapan layar (screenshot) dan menyimpannya sebagai file PNG di Desktop. Gunakan saat user minta "screenshot", "tangkap layar", "ambil gambar layar".',
        parameters: {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    description: 'Opsional. Kosongkan untuk layar utama, atau sebutkan monitor tertentu seperti "layar 2" jika multi-monitor.'
                }
            },
            required: []
        },
        execute: async (args) => {
            const result = await takeScreenshotTool(args.query || '');
            if (result.success) {
                return { success: true, data: result.data };
            }
            return { success: false, error: result.error };
        }
    }
];

// Backward compatibility
screenshotTools.takeScreenshotTool = takeScreenshotTool;

module.exports = screenshotTools;