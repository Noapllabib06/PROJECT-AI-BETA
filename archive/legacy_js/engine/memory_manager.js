const fs = require('fs');
const path = require('path');
const logger = require('../utils/logger');

const FACTS_FILE_PATH = path.join(__dirname, 'memory', 'facts.json');

class MemoryManager {
    constructor() {
        this._ensureFileExists();
    }

    _ensureFileExists() {
        try {
            const dir = path.dirname(FACTS_FILE_PATH);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            if (!fs.existsSync(FACTS_FILE_PATH)) {
                fs.writeFileSync(FACTS_FILE_PATH, JSON.stringify([], null, 2), 'utf-8');
            }
        } catch (e) {
            logger.error('MemoryManager', 'Gagal memastikan file fakta ada: ' + e.message);
        }
    }

    /**
     * Membaca semua fakta yang ada
     * @returns {Array<string>} List fakta pengguna
     */
    getFacts() {
        try {
            if (!fs.existsSync(FACTS_FILE_PATH)) return [];
            const data = fs.readFileSync(FACTS_FILE_PATH, 'utf-8');
            return JSON.parse(data);
        } catch (e) {
            logger.error('MemoryManager', 'Gagal membaca fakta: ' + e.message);
            return [];
        }
    }

    /**
     * Menambahkan sekumpulan fakta baru secara aman
     * @param {Array<string>|string} newFacts Fakta baru yang akan ditambahkan
     */
    addFacts(newFacts) {
        if (!newFacts) return;
        
        let factsToAdd = [];
        if (Array.isArray(newFacts)) {
            factsToAdd = newFacts;
        } else if (typeof newFacts === 'string') {
            factsToAdd = [newFacts];
        }

        if (factsToAdd.length === 0) return;

        try {
            const currentFacts = this.getFacts();
            // Hindari duplikasi sederhana
            const uniqueFacts = factsToAdd.filter(f => !currentFacts.includes(f));
            
            if (uniqueFacts.length > 0) {
                const updatedFacts = [...currentFacts, ...uniqueFacts];
                fs.writeFileSync(FACTS_FILE_PATH, JSON.stringify(updatedFacts, null, 2), 'utf-8');
                logger.info('MemoryManager', `Berhasil menambahkan ${uniqueFacts.length} fakta baru.`);
            }
        } catch (e) {
            logger.error('MemoryManager', 'Gagal menyimpan fakta: ' + e.message);
        }
    }
}

module.exports = new MemoryManager();
