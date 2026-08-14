const fs = require('fs');
const path = require('path');
const logger = require('../utils/logger');

// We save the config file in the project root
const CONFIG_PATH = path.join(__dirname, '..', '..', '.jarvis-config.json');

const DEFAULT_CONFIG = {
    activeModel: 'qwen2.5:7b'
};

class ConfigManager {
    constructor() {
        this.config = { ...DEFAULT_CONFIG };
        this.loadConfig();
    }

    loadConfig() {
        try {
            if (fs.existsSync(CONFIG_PATH)) {
                const data = fs.readFileSync(CONFIG_PATH, 'utf8');
                const parsed = JSON.parse(data);
                this.config = { ...this.config, ...parsed };
                logger.info('ConfigManager', 'Config loaded successfully.');
            } else {
                this.saveConfig();
            }
        } catch (error) {
            logger.error('ConfigManager', 'Failed to load config: ' + error.message);
        }
    }

    saveConfig() {
        try {
            fs.writeFileSync(CONFIG_PATH, JSON.stringify(this.config, null, 2), 'utf8');
            logger.info('ConfigManager', 'Config saved successfully.');
        } catch (error) {
            logger.error('ConfigManager', 'Failed to save config: ' + error.message);
        }
    }

    get(key) {
        return this.config[key];
    }

    set(key, value) {
        this.config[key] = value;
        this.saveConfig();
    }

    getAll() {
        return { ...this.config };
    }
}

module.exports = new ConfigManager();
