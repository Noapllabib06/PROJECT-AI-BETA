const fs = require('fs');
const path = require('path');
const os = require('os');
const logger = require('../utils/logger');

const DRAFTS_DIR = path.join(os.homedir(), 'Documents', 'Jarvis_Drafts');

// Helper to sanitize folder/file names
function sanitizeName(name) {
    return name.replace(/[^a-zA-Z0-9_-]/g, '_');
}

// Helper to ensure drafts dir exists
function ensureDraftsDir() {
    if (!fs.existsSync(DRAFTS_DIR)) {
        fs.mkdirSync(DRAFTS_DIR, { recursive: true });
    }
}

// Helper to get article dir
function getArticleDir(articleTitle) {
    ensureDraftsDir();
    const articleDir = path.join(DRAFTS_DIR, sanitizeName(articleTitle));
    if (!fs.existsSync(articleDir)) {
        fs.mkdirSync(articleDir, { recursive: true });
    }
    return articleDir;
}

// 1. Tool untuk menyimpan bagian draf
async function saveDraftSectionTool(articleTitle, sectionName, content) {
    try {
        const articleDir = getArticleDir(articleTitle);
        // Add timestamp or prefix to keep order? Actually we can just use the section name.
        // We will store all metadata in a status.json file to keep track of order
        const statusFile = path.join(articleDir, 'status.json');
        let status = { sections: [] };
        
        if (fs.existsSync(statusFile)) {
            status = JSON.parse(fs.readFileSync(statusFile, 'utf8'));
        }
        
        const fileName = `${sanitizeName(sectionName)}.md`;
        const filePath = path.join(articleDir, fileName);
        
        fs.writeFileSync(filePath, content, 'utf8');
        
        // Add to status if not exists
        const existingSection = status.sections.find(s => s.name === sectionName);
        if (!existingSection) {
            status.sections.push({ name: sectionName, file: fileName });
        }
        
        fs.writeFileSync(statusFile, JSON.stringify(status, null, 2));
        
        return `✅ Berhasil menyimpan bagian "${sectionName}" untuk artikel "${articleTitle}". Path: ${filePath}`;
    } catch (e) {
        logger.error('DraftingTools', `Gagal menyimpan draft: ${e.message}`);
        return `❌ Gagal menyimpan draft: ${e.message}`;
    }
}

// 2. Tool untuk mengecek status draf
async function checkDraftStatusTool(articleTitle) {
    try {
        const articleDir = path.join(DRAFTS_DIR, sanitizeName(articleTitle));
        if (!fs.existsSync(articleDir)) {
            return `Belum ada draf apapun untuk artikel "${articleTitle}". Silakan mulai dari awal.`;
        }
        
        const statusFile = path.join(articleDir, 'status.json');
        if (!fs.existsSync(statusFile)) {
             return `Draf untuk "${articleTitle}" ditemukan tapi kosong.`;
        }
        
        const status = JSON.parse(fs.readFileSync(statusFile, 'utf8'));
        if (status.sections.length === 0) {
            return `Belum ada bagian yang tersimpan untuk artikel "${articleTitle}".`;
        }
        
        let report = `Status Draf Artikel: "${articleTitle}"\nBagian yang sudah selesai:\n`;
        status.sections.forEach((s, idx) => {
            report += `${idx + 1}. ${s.name}\n`;
        });
        report += `\nSilakan tentukan bagian mana yang belum ditulis dan lanjutkan penulisan.`;
        
        return report;
    } catch (e) {
         return `❌ Gagal mengecek status: ${e.message}`;
    }
}

// 3. Tool untuk menggabungkan (compile) draf
async function compileDraftArticleTool(articleTitle) {
    try {
        const articleDir = path.join(DRAFTS_DIR, sanitizeName(articleTitle));
        const statusFile = path.join(articleDir, 'status.json');
        
        if (!fs.existsSync(statusFile)) {
             return `❌ Tidak ada data draf yang bisa di-compile untuk "${articleTitle}".`;
        }
        
        const status = JSON.parse(fs.readFileSync(statusFile, 'utf8'));
        let finalContent = `# ${articleTitle}\n\n`;
        
        status.sections.forEach(s => {
            const filePath = path.join(articleDir, s.file);
            if (fs.existsSync(filePath)) {
                finalContent += `## ${s.name}\n\n`;
                finalContent += fs.readFileSync(filePath, 'utf8') + `\n\n`;
            }
        });
        
        const finalFile = path.join(DRAFTS_DIR, `${sanitizeName(articleTitle)}_Final.md`);
        fs.writeFileSync(finalFile, finalContent, 'utf8');
        
        return `✅ **Sukses!** Artikel "${articleTitle}" berhasil digabungkan.\n\nFile akhir tersimpan di: \`${finalFile}\`\n\nAnda bisa menawarkan untuk menampilkannya dengan tool read_file atau membukanya langsung.`;
    } catch (e) {
         return `❌ Gagal melakukan compile: ${e.message}`;
    }
}

const draftingTools = [
    {
        name: 'save_draft_section',
        description: 'Menyimpan bagian tertentu (misal: "Abstrak", "Pendahuluan") dari sebuah artikel ke draf sementara.',
        keywords: ['simpan draf', 'simpan bagian', 'save section', 'tulis draf', 'buat artikel bertahap', 'artikel ilmiah', 'secara bertahap', 'buat artikel'],
        parameters: {
            type: 'object',
            properties: {
                articleTitle: { type: 'string', description: 'Judul artikel (digunakan sebagai nama folder)' },
                sectionName: { type: 'string', description: 'Nama bagian yang disimpan (contoh: "1. Pendahuluan")' },
                content: { type: 'string', description: 'Isi konten dari bagian tersebut (gunakan format Markdown)' }
            },
            required: ['articleTitle', 'sectionName', 'content']
        },
        execute: async (args) => {
            return { success: true, data: await saveDraftSectionTool(args.articleTitle, args.sectionName, args.content) };
        }
    },
    {
        name: 'check_draft_status',
        description: 'Mengecek bagian mana saja dari artikel yang sudah ditulis dan disimpan di draf.',
        keywords: ['cek status draf', 'bagian apa saja', 'draft status', 'sampai mana'],
        parameters: {
            type: 'object',
            properties: {
                articleTitle: { type: 'string', description: 'Judul artikel' }
            },
            required: ['articleTitle']
        },
        execute: async (args) => {
            return { success: true, data: await checkDraftStatusTool(args.articleTitle) };
        }
    },
    {
        name: 'compile_draft_article',
        description: 'Menggabungkan semua bagian artikel yang sudah tersimpan menjadi satu file Markdown akhir yang utuh.',
        keywords: ['gabungkan draf', 'selesai artikel', 'compile artikel', 'gabungkan artikel', 'jadikan satu'],
        parameters: {
            type: 'object',
            properties: {
                articleTitle: { type: 'string', description: 'Judul artikel yang ingin digabungkan' }
            },
            required: ['articleTitle']
        },
        execute: async (args) => {
            return { success: true, data: await compileDraftArticleTool(args.articleTitle) };
        }
    }
];

module.exports = draftingTools;
