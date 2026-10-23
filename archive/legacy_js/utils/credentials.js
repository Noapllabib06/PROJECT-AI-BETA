// src/utils/credentials.js
// Credential Manager untuk Jarvis AI Agent
// Menyimpan username/password secara LOKAL dan terenkripsi
// Hanya untuk penggunaan pribadi - 100% aman di komputer sendiri

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const logger = require('./logger');

const CREDENTIALS_FILE = path.join(__dirname, '..', '..', '.jarvis-credentials.json');
const ALGORITHM = 'aes-256-cbc';

class CredentialManager {
    constructor() {
        this.credentials = {};
        this.masterKey = this.getOrCreateMasterKey();
        this.loadCredentials();
        logger.info('CredentialManager', 'Credential manager initialized (local & encrypted)');
    }

    /**
     * Dapatkan atau buat master key dari machine ID + salt
     */
    getOrCreateMasterKey() {
        try {
            // Gunakan kombinasi hostname + user + path sebagai key unik
            const hostname = require('os').hostname();
            const username = require('os').userInfo().username;
            const projectPath = __dirname;
            const seed = `${hostname}-${username}-${projectPath}-jarvis-local-2024`;
            return crypto.createHash('sha256').update(seed).digest('hex').substring(0, 32);
        } catch {
            // Fallback key
            return crypto.randomBytes(16).toString('hex').substring(0, 32);
        }
    }

    /**
     * Enkripsi teks
     */
    encrypt(text) {
        try {
            const iv = crypto.randomBytes(16);
            const cipher = crypto.createCipheriv(ALGORITHM, this.masterKey, iv);
            let encrypted = cipher.update(text, 'utf8', 'hex');
            encrypted += cipher.final('hex');
            return iv.toString('hex') + ':' + encrypted;
        } catch (error) {
            logger.error('CredentialManager', 'Encrypt failed', error);
            return null;
        }
    }

    /**
     * Dekripsi teks
     */
    decrypt(encryptedText) {
        try {
            const parts = encryptedText.split(':');
            const iv = Buffer.from(parts[0], 'hex');
            const encrypted = parts[1];
            const decipher = crypto.createDecipheriv(ALGORITHM, this.masterKey, iv);
            let decrypted = decipher.update(encrypted, 'hex', 'utf8');
            decrypted += decipher.final('utf8');
            return decrypted;
        } catch (error) {
            logger.error('CredentialManager', 'Decrypt failed', error);
            return null;
        }
    }

    /**
     * Load credentials dari file
     */
    loadCredentials() {
        try {
            if (fs.existsSync(CREDENTIALS_FILE)) {
                const data = fs.readFileSync(CREDENTIALS_FILE, 'utf8');
                const decrypted = this.decrypt(data);
                if (decrypted) {
                    this.credentials = JSON.parse(decrypted);
                    logger.info('CredentialManager', `Loaded ${Object.keys(this.credentials).length} credentials`);
                }
            }
        } catch (error) {
            logger.error('CredentialManager', 'Failed to load credentials', error);
            this.credentials = {};
        }
    }

    /**
     * Simpan credentials ke file terenkripsi
     */
    saveCredentials() {
        try {
            const json = JSON.stringify(this.credentials, null, 2);
            const encrypted = this.encrypt(json);
            if (encrypted) {
                fs.writeFileSync(CREDENTIALS_FILE, encrypted, 'utf8');
                // Set permission: hanya user yang bisa baca (Windows: default sudah)
                logger.info('CredentialManager', `Saved ${Object.keys(this.credentials).length} credentials`);
            }
        } catch (error) {
            logger.error('CredentialManager', 'Failed to save credentials', error);
        }
    }

    /**
     * Simpan kredensial untuk sebuah situs
     * @param {string} site - Nama situs (contoh: "github", "gmail")
     * @param {string} username - Username/email
     * @param {string} password - Password
     */
    saveCredential(site, username, password) {
        const key = site.toLowerCase().trim();
        this.credentials[key] = {
            username: username,
            password: password,
            updatedAt: new Date().toISOString()
        };
        this.saveCredentials();
        logger.info('CredentialManager', `Saved credential for: ${key}`);
        return `✅ Kredensial untuk **${site}** berhasil disimpan secara lokal dan terenkripsi.`;
    }

    /**
     * Hapus kredensial untuk sebuah situs
     */
    deleteCredential(site) {
        const key = site.toLowerCase().trim();
        if (this.credentials[key]) {
            delete this.credentials[key];
            this.saveCredentials();
            return `✅ Kredensial untuk **${site}** berhasil dihapus.`;
        }
        return `❌ Tidak ada kredensial untuk **${site}**.`;
    }

    deleteAllCredentials() {
        const count = Object.keys(this.credentials).length;
        this.credentials = {};
        this.saveCredentials();
        return `✅ Semua kredensial (${count} akun) berhasil dihapus.`;
    }

    /**
     * Dapatkan kredensial untuk sebuah situs
     * @param {string} site - Nama situs
     * @returns {object|null} - { username, password } atau null
     */
    getCredential(site) {
        const key = site.toLowerCase().trim();
        return this.credentials[key] || null;
    }

    /**
     * Cari kredensial berdasarkan partial match
     * @param {string} query - Kata kunci pencarian
     * @returns {object|null}
     */
    findCredential(query) {
        const lower = query.toLowerCase();
        for (const [key, value] of Object.entries(this.credentials)) {
            if (key.includes(lower) || lower.includes(key)) {
                return { site: key, ...value };
            }
        }
        return null;
    }

    /**
     * Dapatkan daftar semua situs yang tersimpan
     */
    listCredentials() {
        const sites = Object.keys(this.credentials);
        if (sites.length === 0) {
            return '📭 Belum ada kredensial yang disimpan.';
        }
        let result = '🔐 **Kredensial Tersimpan:**\n\n';
        sites.forEach(site => {
            const cred = this.credentials[site];
            result += `• **${site}** — ${cred.username}\n`;
        });
        result += `\n_Total: ${sites.length} akun_`;
        return result;
    }

    /**
     * Buat URL login dengan parameter (untuk situs yang mendukung)
     * @param {string} site - Nama situs
     * @returns {string|null} - URL login atau null
     */
    getLoginUrl(site) {
        const cred = this.getCredential(site);
        if (!cred) return null;

        const siteLower = site.toLowerCase();
        
        // Daftar URL login untuk situs populer
        const loginUrls = {
            'github': `https://github.com/login`,
            'gmail': `https://mail.google.com`,
            'google': `https://accounts.google.com`,
            'youtube': `https://accounts.google.com`,
            'facebook': `https://www.facebook.com/login`,
            'instagram': `https://www.instagram.com/accounts/login/`,
            'twitter': `https://twitter.com/login`,
            'x': `https://x.com/login`,
            'linkedin': `https://www.linkedin.com/login`,
            'reddit': `https://www.reddit.com/login`,
            'spotify': `https://accounts.spotify.com/login`,
            'netflix': `https://www.netflix.com/login`,
            'amazon': `https://www.amazon.com/ap/signin`,
            'tokopedia': `https://www.tokopedia.com/login`,
            'shopee': `https://shopee.co.id/buyer/login`,
            'gojek': `https://www.gojek.com/login`,
            'grab': `https://grab.com/login`,
            'canva': `https://www.canva.com/login`,
            'figma': `https://www.figma.com/login`,
            'notion': `https://www.notion.so/login`,
            'medium': `https://medium.com/login`,
            'quora': `https://www.quora.com/login`,
            'twitch': `https://www.twitch.tv/login`,
            'discord': `https://discord.com/login`,
            'telegram': `https://web.telegram.org`,
            'whatsapp': `https://web.whatsapp.com`,
            'chatgpt': `https://chat.openai.com/auth/login`,
            'deepseek': `https://chat.deepseek.com`,
            'claude': `https://claude.ai/login`,
            'perplexity': `https://www.perplexity.ai`,
            'bing': `https://www.bing.com`,
            'yahoo': `https://login.yahoo.com`,
            'detik': `https://www.detik.com`,
            'kompas': `https://www.kompas.com`,
            'lms telkom': `https://lms.telkomuniversity.ac.id`,
            'igracias': `https://igracias.telkomuniversity.ac.id`,
        };

        // Cari URL login
        for (const [key, url] of Object.entries(loginUrls)) {
            if (siteLower.includes(key) || key.includes(siteLower)) {
                return url;
            }
        }

        // Fallback: buka situs langsung
        return `https://www.${siteLower}.com/login`;
    }
}

// Singleton instance
const credentialManager = new CredentialManager();

module.exports = credentialManager;