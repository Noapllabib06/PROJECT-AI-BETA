/**
 * src/tools/credential_tools.js
 * Credential Tools — Wrapper Registry Pattern untuk CredentialManager
 * yang sudah ada di src/utils/credentials.js
 *
 * PENTING: File ini WAJIB ada di src/tools/ (bukan src/utils/), karena
 * registry.js hanya auto-scan folder src/tools/. CredentialManager di
 * utils/credentials.js sendiri BUKAN tool — dia cuma "mesin" enkripsi/
 * penyimpanan. File ini yang menjembatani mesin itu ke sistem tool-calling LLM.
 *
 * Format query WAJIB: "site|username|password" (dipisah karakter |)
 * karena pipeline tool-calling proyek ini didesain 1 tool = 1 field query.
 */

const logger = require('../utils/logger');
const credentialManager = require('../utils/credentials');

// ===================== INTERNAL TOOL LOGIC =====================

function saveCredentialTool(query = '') {
    logger.tool('saveCredentialTool', `Input: "${query}"`);
    const parts = query.split('|').map(p => p.trim());

    if (parts.length !== 3 || parts.some(p => !p)) {
        return {
            success: false,
            error: 'Format salah. Query harus: "site|username|password". Contoh: "gmail|user@gmail.com|mypassword123"'
        };
    }

    const [site, username, password] = parts;
    try {
        credentialManager.saveCredential(site, username, password);
        logger.tool('saveCredentialTool', `Kredensial untuk "${site}" berhasil disimpan.`);
        return { success: true, data: `✅ Kredensial untuk **${site}** berhasil disimpan (terenkripsi).` };
    } catch (error) {
        logger.error('saveCredentialTool', error);
        return { success: false, error: `Gagal menyimpan kredensial: ${error.message}` };
    }
}

function listCredentialsTool() {
    logger.tool('listCredentialsTool', 'Mengambil daftar kredensial tersimpan.');
    try {
        const result = credentialManager.listCredentials(); // sudah string siap pakai, sync (bukan async!)
        return { success: true, data: result };
    } catch (error) {
        logger.error('listCredentialsTool', error);
        return { success: false, error: `Gagal mengambil daftar kredensial: ${error.message}` };
    }
}

function deleteCredentialTool(query = '') {
    logger.tool('deleteCredentialTool', `Input: "${query}"`);
    const site = query.trim();
    if (!site) {
        return { success: false, error: 'Sebutkan nama site yang mau dihapus kredensialnya.' };
    }
    try {
        const resultMsg = credentialManager.deleteCredential(site);
        const wasSuccessful = resultMsg.startsWith('✅');
        return { success: wasSuccessful, data: wasSuccessful ? resultMsg : null, error: wasSuccessful ? null : resultMsg };
    } catch (error) {
        logger.error('deleteCredentialTool', error);
        return { success: false, error: `Gagal menghapus kredensial: ${error.message}` };
    }
}

// ===================== REGISTRY TOOLS =====================

const credentialTools = [
    {
        name: 'save_credential',
        description: 'Menyimpan kredensial (username & password) untuk sebuah situs/layanan secara terenkripsi. Gunakan HANYA untuk password/kredensial/login, JANGAN untuk fakta biasa.',
        parameters: {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    description: 'WAJIB format "site|username|password". Contoh: "gmail|user@gmail.com|app-password-disini"'
                }
            },
            required: ['query']
        },
        execute: async (args) => {
            const result = saveCredentialTool(args.query || '');
            return result.success ? { success: true, data: result.data } : { success: false, error: result.error };
        }
    },
    {
        name: 'list_credentials',
        description: 'Menampilkan daftar nama situs/layanan yang kredensialnya sudah tersimpan (TIDAK menampilkan password).',
        parameters: { type: 'object', properties: {}, required: [] },
        execute: async () => {
            const result = listCredentialsTool();
            return result.success ? { success: true, data: result.data } : { success: false, error: result.error };
        }
    },
    {
        name: 'delete_credential',
        description: 'Menghapus kredensial tersimpan untuk sebuah situs/layanan tertentu.',
        parameters: {
            type: 'object',
            properties: {
                query: { type: 'string', description: 'Nama site yang kredensialnya mau dihapus, contoh: "gmail"' }
            },
            required: ['query']
        },
        execute: async (args) => {
            const result = deleteCredentialTool(args.query || '');
            return result.success ? { success: true, data: result.data } : { success: false, error: result.error };
        }
    }
];

module.exports = credentialTools;