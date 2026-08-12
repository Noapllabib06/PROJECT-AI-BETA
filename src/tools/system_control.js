/**
 * src/tools/system_control.js
 * System Control Tools — Buka aplikasi lokal & kontrol volume sistem
 * Format: Registry Pattern — export array of tool objects
 *
 * DEPENDENSI BARU YANG PERLU DI-INSTALL:
 *   npm install loudness
 *
 * Catatan Tier 1 (VRAM/RAM):
 * Tool ini TIDAK memuat model AI apa pun. Semua operasi hanya
 * menjalankan command sistem (exec) atau memanggil library kecil
 * untuk kontrol volume. Konsumsi VRAM tambahan: 0. Konsumsi RAM
 * tambahan: minor (proses child sesaat, langsung selesai).
 */

const { exec } = require('child_process');
const logger = require('../utils/logger');

// loudness bersifat opsional — jika belum di-install, fitur volume
// akan mengembalikan pesan error yang jelas, bukan crash seluruh app.
let loudness = null;
try {
    loudness = require('loudness');
} catch (e) {
    logger.warn('SystemControl', 'Package "loudness" belum terinstall. Fitur volume tidak akan berfungsi. Jalankan: npm install loudness');
}

// ===================== KNOWN APPS MAP =====================
// Mapping nama umum (Bahasa Indonesia/Inggris) -> command yang dijalankan.
// Pakai `start ""` di Windows agar bisa jalankan app terdaftar di PATH/App Paths
// tanpa perlu tahu lokasi instalasi persis (mirip pola open_web_tool di web_tools.js).

const KNOWN_APPS = new Map([
    // Utilitas bawaan Windows
    ['notepad', 'notepad'],
    ['catatan', 'notepad'],
    ['kalkulator', 'calc'],
    ['calculator', 'calc'],
    ['paint', 'mspaint'],
    ['file explorer', 'explorer'],
    ['explorer', 'explorer'],
    ['this pc', 'explorer shell:MyComputerFolder'],
    ['task manager', 'taskmgr'],
    ['pengelola tugas', 'taskmgr'],
    ['control panel', 'control'],
    ['panel kontrol', 'control'],
    ['cmd', 'cmd'],
    ['command prompt', 'cmd'],
    ['powershell', 'powershell'],
    ['wordpad', 'wordpad'],
    ['snipping tool', 'snippingtool'],
    ['settings', 'start ms-settings:'],
    ['pengaturan', 'start ms-settings:'],

    // Aplikasi umum (asumsi sudah terinstall & terdaftar di App Paths/PATH)
    ['word', 'start winword'],
    ['microsoft word', 'start winword'],
    ['excel', 'start excel'],
    ['microsoft excel', 'start excel'],
    ['powerpoint', 'start powerpnt'],
    ['spotify', 'start spotify'],
    ['chrome', 'start chrome'],
    ['google chrome', 'start chrome'],
    ['firefox', 'start firefox'],
    ['edge', 'start msedge'],
    ['vscode', 'code'],
    ['visual studio code', 'code'],
    ['vs code', 'code'],
    ['discord', 'start discord'],
    ['telegram', 'start telegram'],
    ['steam', 'start steam'],
]);

/**
 * Validasi ringan: cegah command injection dari input user.
 * Karena kita cuma pakai command dari KNOWN_APPS map (whitelist),
 * bukan langsung dari input mentah, ini sudah aman secara desain.
 */
function findAppCommand(query) {
    const lower = query.toLowerCase().trim();
    if (KNOWN_APPS.has(lower)) return KNOWN_APPS.get(lower);

    // Coba partial match sederhana (mis. "buka word" -> "word")
    for (const [key, cmd] of KNOWN_APPS) {
        if (lower.includes(key)) return cmd;
    }
    return null;
}

// ===================== INTERNAL TOOL LOGIC =====================

/**
 * Cek apakah sebuah command/executable ada di PATH, TANPA memicu popup GUI.
 * Beda dengan `start`, command `where` selalu silent (cuma exit code),
 * jadi aman dipakai untuk verifikasi sebelum benar-benar menjalankan `start`.
 */
function commandExists(cmd) {
    return new Promise((resolve) => {
        exec(`where ${cmd}`, (error) => resolve(!error));
    });
}

/**
 * Fallback: cari shortcut .lnk di Start Menu (user & common) berdasarkan nama app.
 * Ini jauh lebih reliable dibanding menebak nama command langsung, karena
 * hampir semua installer Windows selalu membuat shortcut Start Menu,
 * apapun lokasi instalasi aslinya (App Paths tidak selalu terdaftar,
 * terutama untuk app Electron self-updating seperti Discord/Spotify).
 */
function launchViaStartMenu(appName) {
    return new Promise((resolve) => {
        const safeName = appName.replace(/[^a-zA-Z0-9 ]/g, ''); // sanitasi dasar
        const psScript = [
            '$paths = @(',
            '  "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs",',
            '  "$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs"',
            ');',
            '$shortcut = Get-ChildItem -Path $paths -Recurse -Filter *.lnk -ErrorAction SilentlyContinue |',
            `  Where-Object { $_.BaseName -like '*${safeName}*' } | Select-Object -First 1;`,
            'if ($shortcut) { Start-Process $shortcut.FullName; Write-Output "FOUND:$($shortcut.FullName)" }',
            'else { Write-Output "NOTFOUND" }'
        ].join(' ');

        exec(`powershell -NoProfile -Command "${psScript.replace(/"/g, '\\"')}"`, (error, stdout) => {
            if (error) {
                resolve({ success: false, error: error.message });
                return;
            }
            const out = (stdout || '').trim();
            if (out.startsWith('FOUND:')) {
                resolve({ success: true, path: out.substring(6) });
            } else {
                resolve({ success: false, error: 'Shortcut tidak ditemukan di Start Menu' });
            }
        });
    });
}

/**
 * Command bawaan Windows yang DIJAMIN selalu ada di sistem manapun
 * (bagian dari OS, bukan aplikasi pihak ketiga). Aman dieksekusi
 * langsung tanpa perlu verifikasi `where` dulu.
 */
const TRUSTED_SYSTEM_COMMANDS = new Set([
    'notepad', 'calc', 'mspaint', 'explorer', 'taskmgr', 'control',
    'cmd', 'powershell', 'wordpad', 'snippingtool'
]);

async function openAppTool(query) {
    logger.tool('openAppTool', `Membuka aplikasi: "${query}"`);
    try {
        let cleaned = query.replace(/^(buka|open|jalankan|start)\s+/i, '').trim();
        const command = findAppCommand(cleaned);

        if (command && process.platform === 'win32') {
            // Ekstrak nama executable murni dari command (buang prefix 'start ')
            const bareCmd = command.replace(/^start\s+/i, '').split(' ')[0];
            const isUriScheme = bareCmd.includes(':'); // mis. "ms-settings:"
            const isTrusted = TRUSTED_SYSTEM_COMMANDS.has(bareCmd) || isUriScheme;

            // Command bawaan Windows / URI scheme: langsung eksekusi, dijamin ada.
            // Command app pihak ketiga: WAJIB verifikasi dulu pakai `where`
            // (silent, tidak memicu popup GUI), baru eksekusi kalau memang ada.
            const shouldTryDirect = isTrusted || await commandExists(bareCmd);

            if (shouldTryDirect) {
                const execCommand = command.startsWith('start')
                    ? command.replace('start', 'start ""')
                    : `start "" "${command}"`;

                const directResult = await new Promise((resolve) => {
                    exec(execCommand, (error) => resolve({ success: !error, error: error?.message }));
                });

                if (directResult.success) {
                    logger.tool('openAppTool', `Command langsung berhasil: ${execCommand}`);
                    return `✅ Membuka **${cleaned}**...`;
                }
                logger.warn('openAppTool', `Command langsung gagal (${directResult.error}), mencoba fallback Start Menu...`);
            } else {
                logger.debug('openAppTool', `Command "${bareCmd}" tidak ditemukan di PATH, skip langsung ke fallback Start Menu (hindari popup GUI).`);
            }
        }

        // Fallback: cari shortcut di Start Menu berdasarkan nama
        const fallbackResult = await launchViaStartMenu(cleaned);
        if (fallbackResult.success) {
            logger.tool('openAppTool', `Ditemukan via Start Menu: ${fallbackResult.path}`);
            return `✅ Membuka **${cleaned}** (via shortcut: ${fallbackResult.path})...`;
        }

        return `❌ Tidak dapat membuka "${cleaned}". Tidak ditemukan command sistem maupun shortcut Start Menu yang cocok. Pastikan aplikasinya sudah terinstall, atau coba nama yang lebih spesifik.`;
    } catch (error) {
        logger.error('openAppTool', error);
        return `❌ Gagal membuka aplikasi: ${error.message}`;
    }
}

async function controlVolumeTool(query) {
    logger.tool('controlVolumeTool', `Input: "${query}"`);

    if (!loudness) {
        return '❌ Fitur kontrol volume belum aktif. Jalankan `npm install loudness` di terminal proyek, lalu restart aplikasi.';
    }

    try {
        const lower = query.toLowerCase().trim();

        // Mute / Unmute
        // Cek UNMUTE DULU sebelum mute (urutan penting!)
        if (/(unmute|batal.*mute|nyalakan.*suara)/i.test(lower)) {
            await loudness.setMuted(false);
            return '🔊 Suara di-unmute.';
        }
        if (/(mute|bisukan|senyapkan)/i.test(lower)) {
            await loudness.setMuted(true);
            return '🔇 Suara di-mute.';
        }

        // Set volume ke angka spesifik: "set volume ke 50", "volume 30%"
        const numMatch = lower.match(/(\d{1,3})\s*%?/);
        if (numMatch && (lower.includes('set') || lower.includes('ke') || lower.includes('atur'))) {
            let target = parseInt(numMatch[1], 10);
            target = Math.max(0, Math.min(100, target));
            await loudness.setVolume(target);
            return `🔊 Volume diatur ke **${target}%**.`;
        }

        // Naik / Turun relatif (default step 10%)
        const currentVolume = await loudness.getVolume();
        if (/(naik|tambah|kencangkan|kenceng|up|louder)/i.test(lower)) {
            const newVolume = Math.min(100, currentVolume + 10);
            await loudness.setVolume(newVolume);
            return `🔊 Volume dinaikkan ke **${newVolume}%** (sebelumnya ${currentVolume}%).`;
        }
        if (/(turun|kecilkan|pelankan|down|lower|quieter)/i.test(lower)) {
            const newVolume = Math.max(0, currentVolume - 10);
            await loudness.setVolume(newVolume);
            return `🔉 Volume diturunkan ke **${newVolume}%** (sebelumnya ${currentVolume}%).`;
        }

        // Default: cuma laporkan volume saat ini kalau perintah tidak jelas
        return `ℹ️ Volume saat ini: **${currentVolume}%**. Gunakan perintah seperti "naikkan volume", "turunkan volume", "set volume ke 70", atau "mute".`;
    } catch (error) {
        logger.error('controlVolumeTool', error);
        return `❌ Gagal mengontrol volume: ${error.message}`;
    }
}

// ===================== REGISTRY TOOLS =====================

const systemControlTools = [
    {
        name: 'open_app',
        description: 'Membuka aplikasi desktop lokal (bukan situs web). Contoh: "buka notepad", "buka word", "buka spotify", "buka file explorer".',
        parameters: {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    description: 'Nama aplikasi yang ingin dibuka. Contoh: "notepad", "word", "spotify", "vscode", "task manager".'
                }
            },
            required: ['query']
        },
        execute: async (args) => {
            const result = await openAppTool(args.query || '');
            return { success: true, data: result };
        }
    },
    {
        name: 'control_volume',
        description: 'Mengontrol volume suara sistem: naik, turun, set ke persentase tertentu, mute, atau unmute. Contoh: "naikkan volume", "set volume ke 50", "mute".',
        parameters: {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    description: 'Perintah kontrol volume. Contoh: "naikkan volume", "turunkan volume", "set volume ke 70", "mute", "unmute".'
                }
            },
            required: ['query']
        },
        execute: async (args) => {
            const result = await controlVolumeTool(args.query || '');
            return { success: true, data: result };
        }
    }
];

// Backward compatibility
systemControlTools.openAppTool = openAppTool;
systemControlTools.controlVolumeTool = controlVolumeTool;
systemControlTools.KNOWN_APPS = KNOWN_APPS;

module.exports = systemControlTools;