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
let imaps = null;
let simpleParser = null;
try {
    imaps = require('imap-simple');
    simpleParser = require('mailparser').simpleParser;
} catch (e) {
    logger.warn('EmailTools', 'Package "imap-simple" atau "mailparser" belum terinstall. Jalankan: npm install imap-simple mailparser');
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

async function checkEmailTool(query = '', sender = '', date = '') {
    logger.tool('checkEmailTool', `Input: query="${query}", sender="${sender}", date="${date}"`);

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

        // 4. Ambil header email agar ringan
        let searchCriteria = ['ALL'];
        if (sender) {
            searchCriteria.push(['FROM', sender]);
        } else {
            searchCriteria.push('UNSEEN');
        }

        const fetchOptions = { bodies: ['HEADER'], markSeen: false };
        const messages = await connection.search(searchCriteria, fetchOptions);

        if (!messages || messages.length === 0) {
            connection.end();
            return { success: true, data: `📭 Tidak ada email ditemukan di **${providerKey}** (${cred.username}).` };
        }

        const maxEmails = sender ? 2 : 5;
        const recent = messages.slice(-maxEmails).reverse(); // terbaru
        
        // 5. Fetch full body hanya untuk email terbaru
        const uidsNum = recent.map(m => m.attributes.uid);
        const fullFetchOptions = { bodies: [''], markSeen: false };
        let fullMessages = [];
        if (uidsNum.length > 0) {
            const minUid = Math.min(...uidsNum);
            const maxUid = Math.max(...uidsNum);
            fullMessages = await connection.search([['UID', `${minUid}:${maxUid}`]], fullFetchOptions);
        }
        connection.end();

        let result = `📧 **${messages.length} Email Ditemukan** (${providerKey} — ${cred.username})\n\n`;

        const fs = require('fs');
        const path = require('path');
        const os = require('os');

        for (const msg of recent) {
            const uid = msg.attributes.uid;
            const fullMsg = fullMessages.find(m => m.attributes.uid === uid);
            let subject = '(Tanpa subjek)';
            let from = 'Tidak diketahui';
            let dateStr = '-';
            let textBody = '(Isi pesan tidak dapat dimuat)';
            let imagePaths = [];
            
            // Try mailparser if available and we have the full message body
            if (fullMsg) {
                const bodyPart = fullMsg.parts.find(p => p.which === '');
                if (simpleParser && bodyPart && bodyPart.body) {
                    try {
                        const parsed = await simpleParser(bodyPart.body);
                        subject = parsed.subject || subject;
                        from = parsed.from ? parsed.from.text : from;
                        dateStr = parsed.date ? new Date(parsed.date).toLocaleString('id-ID') : dateStr;
                        textBody = parsed.text || parsed.textAsHtml || '(Hanya HTML atau attachment)';
                        
                        // Coba ekstrak dari HTML jika teks aslinya terlalu pendek (biasa terjadi di email promosi/marketing)
                        if (parsed.html) {
                            let htmlText = parsed.html.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '') // Hapus blok style
                                                      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '') // Hapus blok script
                                                      .replace(/<[^>]+>/g, ' ') // Hapus semua tag HTML
                                                      .replace(/&nbsp;/g, ' ') // Bersihkan entitas HTML umum
                                                      .replace(/\s+/g, ' ') // Rapikan spasi berlebih
                                                      .trim();
                            if (htmlText.length > textBody.length) {
                                textBody = htmlText;
                            }
                        }
                        if (parsed.attachments && parsed.attachments.length > 0) {
                            for (const att of parsed.attachments) {
                                if (att.contentType && att.contentType.startsWith('image/')) {
                                    const safeName = (att.filename || 'img.png').replace(/[^a-z0-9.]/gi, '_');
                                    const tmpPath = path.join(os.tmpdir(), `email_img_${Date.now()}_${safeName}`);
                                    fs.writeFileSync(tmpPath, att.content);
                                    imagePaths.push(tmpPath);
                                }
                            }
                        }

                        // Clean up and truncate long emails
                        textBody = textBody.trim();
                        
                        // Hide very long URLs (tracking links) to prevent "luber" output
                        textBody = textBody.replace(/https?:\/\/[^\s\]\)>]+/gi, (url) => {
                            return url.length > 60 ? '[Tautan Panjang Disembunyikan]' : url;
                        });

                        if (textBody.length > 1500) {
                            textBody = textBody.substring(0, 1500) + '... [Teks dipotong]';
                        }
                    } catch (err) {
                        logger.error('EmailTools', 'Gagal parsing isi email: ' + err.message);
                    }
                }
            }
            
            // Fallback to headers if parsing fails
            if (subject === '(Tanpa subjek)') {
                const headerPart = msg.parts.find(p => p.which === 'HEADER');
                const header = headerPart?.body || {};
                subject = header.subject ? header.subject[0] : '(Tanpa subjek)';
                from = header.from ? header.from[0] : 'Tidak diketahui';
                const rawDate = header.date ? header.date[0] : null;
                dateStr = rawDate ? new Date(rawDate).toLocaleString('id-ID') : '-';
            }

            const isFullView = Boolean(sender && date);
            
            if (isFullView) {
                result += `📌 **${subject}**\n👤 Dari: ${from}\n🕐 ${dateStr}\n📄 Isi:\n${textBody}\n\n`;
                if (imagePaths.length > 0) {
                    result += `🖼️ **Gambar terlampir:**\n`;
                    for (const imgPath of imagePaths) {
                        const safePath = imgPath.replace(/\\/g, '\\\\');
                        result += `(Terdapat gambar terlampir di email. Untuk menampilkan gambar tersebut ke pengguna di UI Code Preview, gunakan format code block berikut di respons chat Anda:\n\`\`\`snippet.image\n{"path": "${safePath}", "explanation": "Gambar dari email: ${subject}"}\n\`\`\`\n)\n`;
                    }
                }
            } else {
                result += `📌 **${subject}**\n👤 Dari: ${from}\n🕐 ${dateStr}\n*(Gunakan parameter sender dan date spesifik pada tool check_email untuk membaca isi penuh email ini)*\n`;
            }
            result += `---\n\n`;
        }

        if (messages.length > maxEmails) {
            result += `_...dan ${messages.length - maxEmails} email lainnya._`;
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
                },
                sender: {
                    type: 'string',
                    description: 'Opsional. Nama atau email pengirim jika user meminta untuk mencari email dari pengirim tertentu (misal: "fab").'
                },
                date: {
                    type: 'string',
                    description: 'Opsional. Tanggal spesifik email jika user meminta membaca isi penuh dari satu email spesifik (misal: "14/8/2026"). Wajib diisi bersamaan dengan sender untuk menampilkan isi email.'
                }
            },
            required: []
        },
        execute: async (args) => {
            const result = await checkEmailTool(args.query || '', args.sender || '', args.date || '');
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