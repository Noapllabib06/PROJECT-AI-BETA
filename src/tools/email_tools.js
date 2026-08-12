/**
 * src/tools/email_tools.js
 * Email Tools — Cek email masuk (unread) via IMAP
 * Format: Registry Pattern — export array of tool objects
 *
 * DEPENDENSI BARU YANG PERLU DI-INSTALL:
 *   npm install imap-simple mailparser
 *
 * Catatan Tier 1 (VRAM/RAM):
 * Tool ini TIDAK memuat model AI apa pun — murni koneksi network (IMAP)
 * ke server email. Konsumsi VRAM: 0. Konsumsi RAM: minor, hanya selama
 * proses fetch & parsing email berlangsung.
 *
 * PENTING SOAL KREDENSIAL:
 * Tool ini REUSE credentialManager (src/utils/credentials.js) yang
 * SUDAH ADA di proyek — TIDAK membuat sistem penyimpanan password baru.
 * User harus simpan kredensial email dulu lewat tool `save_credential`
 * yang sudah ada, dengan format:
 *   site: "gmail" (atau "outlook", "yahoo", dst — nama provider)
 *   username: alamat email lengkap
 *   password: APP PASSWORD, bukan password akun biasa (lihat catatan di bawah)
 *
 * ⚠️ CATATAN KEAMANAN PENTING:
 * Gmail & Outlook modern TIDAK mengizinkan login IMAP dengan password akun
 * biasa (kebijakan keamanan mereka). User WAJIB generate "App Password"
 * khusus (butuh 2FA aktif dulu):
 *   - Gmail: https://myaccount.google.com/apppasswords
 *   - Outlook: https://account.live.com/proofs/AppPassword
 * JANGAN gunakan password utama akun email di sini.
 *
 * Ingat juga: credentialManager saat ini pakai master key yang di-derive
 * dari hostname+username+path (BUKAN passphrase rahasia asli) — jadi
 * anggap penyimpanan ini sebagai "obfuscation ringan", bukan enkripsi kuat.
 * Lihat diskusi sebelumnya soal ini sebelum menyimpan kredensial sensitif.
 */

const logger = require('../utils/logger');
const credentialManager = require('../utils/credentials');

// imap-simple bersifat opsional — jika belum di-install, tool ini
// akan mengembalikan pesan error yang jelas, bukan crash seluruh app.
// Catatan: mailparser TIDAK diperlukan lagi — imap-simple sudah otomatis
// mem-parsing HEADER jadi object, jadi tidak perlu parsing manual lagi.
let imaps = null;
try {
    imaps = require('imap-simple');
} catch (e) {
    logger.warn('EmailTools', 'Package "imap-simple" belum terinstall. Jalankan: npm install imap-simple');
}

// ===================== KNOWN PROVIDER HOSTS =====================

const PROVIDER_HOSTS = new Map([
    ['gmail', { host: 'imap.gmail.com', port: 993 }],
    ['google', { host: 'imap.gmail.com', port: 993 }],
    ['outlook', { host: 'outlook.office365.com', port: 993 }],
    ['hotmail', { host: 'outlook.office365.com', port: 993 }],
    ['office365', { host: 'outlook.office365.com', port: 993 }],
    ['yahoo', { host: 'imap.mail.yahoo.com', port: 993 }],
    ['icloud', { host: 'imap.mail.me.com', port: 993 }],
]);

function detectProvider(text) {
    const lower = (text || '').toLowerCase();
    for (const [key] of PROVIDER_HOSTS) {
        if (lower.includes(key)) return key;
    }
    return null;
}

function detectHostFromEmail(emailAddress) {
    const domain = emailAddress.split('@')[1]?.toLowerCase() || '';
    if (domain.includes('gmail')) return PROVIDER_HOSTS.get('gmail');
    if (domain.includes('outlook') || domain.includes('hotmail') || domain.includes('live')) return PROVIDER_HOSTS.get('outlook');
    if (domain.includes('yahoo')) return PROVIDER_HOSTS.get('yahoo');
    if (domain.includes('icloud') || domain.includes('me.com')) return PROVIDER_HOSTS.get('icloud');
    return null;
}

// ===================== INTERNAL TOOL LOGIC =====================

async function checkEmailTool(query = '') {
    logger.tool('checkEmailTool', `Input: "${query}"`);

    if (!imaps) {
        return {
            success: false,
            error: 'Fitur email belum aktif. Jalankan `npm install imap-simple mailparser` di terminal proyek, lalu restart aplikasi.'
        };
    }

    try {
        // 1. Tentukan akun mana yang mau dicek (default: "gmail" kalau tidak disebutkan)
        const providerKey = detectProvider(query) || 'gmail';
        const cred = credentialManager.getCredential(providerKey);

        if (!cred) {
            return {
                success: false,
                error: `Belum ada kredensial tersimpan untuk "${providerKey}". Simpan dulu pakai tool save_credential dengan site="${providerKey}", username=email lengkap, password=App Password (BUKAN password akun biasa). Lihat komentar di email_tools.js untuk cara generate App Password.`
            };
        }

        // 2. Tentukan host IMAP
        const hostConfig = PROVIDER_HOSTS.get(providerKey) || detectHostFromEmail(cred.username);
        if (!hostConfig) {
            return {
                success: false,
                error: `Tidak dapat menentukan server IMAP untuk "${providerKey}". Provider yang didukung otomatis: ${Array.from(PROVIDER_HOSTS.keys()).join(', ')}.`
            };
        }

        // 3. Koneksi ke server IMAP
        const config = {
            imap: {
                user: cred.username,
                password: cred.password,
                host: hostConfig.host,
                port: hostConfig.port,
                tls: true,
                authTimeout: 10000,
                tlsOptions: { rejectUnauthorized: false }
            }
        };

        const connection = await imaps.connect(config);
        await connection.openBox('INBOX');

        // 4. Ambil email UNSEEN (belum dibaca), maksimal 5 terbaru
        const searchCriteria = ['UNSEEN'];
        const fetchOptions = { bodies: ['HEADER'], markSeen: false };
        const messages = await connection.search(searchCriteria, fetchOptions);

        connection.end();

        if (!messages || messages.length === 0) {
            return { success: true, data: `📭 Tidak ada email belum dibaca di **${providerKey}** (${cred.username}).` };
        }

        const recent = messages.slice(-5).reverse(); // 5 terbaru
        let result = `📧 **${messages.length} Email Belum Dibaca** (${providerKey} — ${cred.username})\n\n`;

        for (const msg of recent) {
            const headerPart = msg.parts.find(p => p.which === 'HEADER');
            // PENTING: imap-simple SUDAH otomatis parsing HEADER jadi object
            // (bukan raw string), jadi TIDAK perlu mailparser di sini lagi.
            // Format headerPart.body: { subject: [...], from: [...], date: [...] }
            const header = headerPart.body || {};
            const subject = header.subject ? header.subject[0] : '(Tanpa subjek)';
            const from = header.from ? header.from[0] : 'Tidak diketahui';
            const rawDate = header.date ? header.date[0] : null;
            const date = rawDate ? new Date(rawDate).toLocaleString('id-ID') : '-';
            result += `📌 **${subject}**\n👤 Dari: ${from}\n🕐 ${date}\n\n`;
        }

        if (messages.length > 5) {
            result += `_...dan ${messages.length - 5} email lainnya._`;
        }

        logger.tool('checkEmailTool', `Berhasil: ${messages.length} email unread ditemukan`);
        return { success: true, data: result };

    } catch (error) {
        logger.error('checkEmailTool', error);
        let hint = '';
        if (error.message?.includes('Invalid credentials') || error.message?.includes('AUTHENTICATIONFAILED')) {
            hint = ' Pastikan pakai App Password, bukan password akun biasa (terutama untuk Gmail/Outlook).';
        }
        return { success: false, error: `Gagal mengecek email: ${error.message}.${hint}` };
    }
}

// ===================== REGISTRY TOOLS =====================

const emailTools = [
    {
        name: 'check_email',
        description: 'Mengecek email yang belum dibaca (unread) di inbox. Gunakan saat user minta "cek email", "ada email baru?", "cek gmail", "cek inbox".',
        parameters: {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    description: 'Opsional. Sebutkan provider jika bukan gmail, misal "outlook", "yahoo". Kosongkan untuk default gmail.'
                }
            },
            required: []
        },
        execute: async (args) => {
            const result = await checkEmailTool(args.query || '');
            if (result.success) {
                return { success: true, data: result.data };
            }
            return { success: false, error: result.error };
        }
    }
];

// Backward compatibility
emailTools.checkEmailTool = checkEmailTool;
emailTools.PROVIDER_HOSTS = PROVIDER_HOSTS;

module.exports = emailTools;