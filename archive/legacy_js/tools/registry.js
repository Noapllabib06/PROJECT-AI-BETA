/**
 * src/tools/registry.js
 * Tool Registry Pattern — semua tool didaftarkan secara otomatis dari folder src/tools/.
 * Menyediakan definisi tool untuk native function-calling Ollama.
 * 
 * Setiap file tool harus export array of object dengan format:
 * {
 *   name: "nama_unik_snake_case",
 *   description: "deskripsi jelas untuk model",
 *   parameters: { type: "object", properties: { ... }, required: [...] },
 *   execute: async (args) => { return { success: true, data: "..." }; }
 * }
 */

const path = require('path');
const fs = require('fs');
const logger = require('../utils/logger');
const memorySearchTool = require('./memory_search_tool');
const memorySaveTool = require('./memory_save');

class ToolRegistry {
    constructor() {
        this.tools = new Map(); // name -> tool object
        this.loaded = false;
        
        // Manual registration for bundled tools
        const manualTools = [memorySearchTool, memorySaveTool];
        for (const tool of manualTools) {
            if (this._validateTool(tool, 'manual')) {
                this.tools.set(tool.name, tool);
            }
        }
    }

    /**
     * Memindai semua file .js di direktori src/tools/ (kecuali registry.js sendiri),
     * me-load masing-masing, dan mendaftarkan tool yang diekspor.
     */
    loadAll() {
        if (this.loaded) return;
        
        const toolsDir = path.join(__dirname); // src/tools/
        const files = fs.readdirSync(toolsDir).filter(f => 
            f.endsWith('.js') && f !== 'registry.js' && f !== 'memory_search_tool.js' && f !== 'memory_save.js'
        );

        let totalTools = this.tools.size;
        const toolNames = Array.from(this.tools.keys());

        for (const file of files) {
            const filePath = path.join(toolsDir, file);
            try {
                const exported = require(filePath);
                
                // Ekspor bisa berupa array of tool objects, atau satu tool object
                let toolList = [];
                if (Array.isArray(exported)) {
                    toolList = exported;
                } else if (exported && typeof exported === 'object') {
                    // Cek apakah object memiliki properti tool (single tool)
                    // atau merupakan namespace dengan fungsi-fungsi
                    if (exported.name && exported.execute) {
                        // Single tool object langsung
                        toolList = [exported];
                    } else {
                        // Mungkin merupakan module lama dengan export fungsi2
                        // Skip — akan di-refactor
                        logger.warn('ToolRegistry', `File ${file} tidak dalam format registry. Skip (harus di-refactor).`);
                        continue;
                    }
                }
                
                for (const tool of toolList) {
                    if (!this._validateTool(tool, file)) {
                        continue;
                    }
                    
                    if (this.tools.has(tool.name)) {
                        logger.warn('ToolRegistry', `Duplikat tool name: "${tool.name}" dari file ${file}. Skip.`);
                        continue;
                    }
                    
                    this.tools.set(tool.name, tool);
                    totalTools++;
                    toolNames.push(tool.name);
                }
            } catch (err) {
                logger.warn('ToolRegistry', `Gagal me-load file ${file}: ${err.message}`);
            }
        }

        this.loaded = true;
        logger.info('ToolRegistry', `${totalTools} tool termuat: [${toolNames.join(', ')}]`);
    }

    /**
     * Validasi struktur tool object.
     */
    _validateTool(tool, fileName) {
        if (!tool.name || typeof tool.name !== 'string') {
            logger.warn('ToolRegistry', `Tool di file ${fileName} tidak punya 'name' yang valid. Skip.`);
            return false;
        }
        if (!tool.description || typeof tool.description !== 'string') {
            logger.warn('ToolRegistry', `Tool "${tool.name}" di file ${fileName} tidak punya 'description'. Skip.`);
            return false;
        }
        if (!tool.parameters || typeof tool.parameters !== 'object') {
            logger.warn('ToolRegistry', `Tool "${tool.name}" di file ${fileName} tidak punya 'parameters'. Skip.`);
            return false;
        }
        if (typeof tool.execute !== 'function') {
            logger.warn('ToolRegistry', `Tool "${tool.name}" di file ${fileName} tidak punya 'execute' function. Skip.`);
            return false;
        }
        return true;
    }

    /**
     * Return array definisi tool dalam format yang siap dikirim ke Ollama.
     * Format: [{ type: "function", function: { name, description, parameters } }]
     */
    getToolDefinitions() {
        const definitions = [];
        for (const [, tool] of this.tools) {
            definitions.push({
                type: 'function',
                function: {
                    name: tool.name,
                    description: tool.description,
                    parameters: tool.parameters
                }
            });
        }
        return definitions;
    }

    /**
     * Menjalankan tool berdasarkan nama.
     * Selalu return object konsisten: { success: true, data } atau { success: false, error }
     */
    async execute(name, args) {
        const tool = this.tools.get(name);
        if (!tool) {
            return { success: false, error: `Tool "${name}" tidak ditemukan di registry.` };
        }

        try {
            logger.tool('ToolRegistry.execute', `Menjalankan: ${name}`, args);
            const result = await tool.execute(args || {});
            
            // Pastikan return object konsisten
            if (result && typeof result === 'object' && 'success' in result) {
                return result;
            }
            
            // Jika tool return string atau tipe lain, bungkus
            return { success: true, data: result };
        } catch (err) {
            logger.error('ToolRegistry.execute', err, { tool: name });
            return { success: false, error: `Tool "${name}" gagal: ${err.message}` };
        }
    }

    /**
     * Mendapatkan daftar nama tool yang terdaftar.
     */
    getToolNames() {
        return Array.from(this.tools.keys());
    }
}

module.exports = new ToolRegistry();