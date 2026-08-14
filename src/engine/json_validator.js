/**
 * src/engine/json_validator.js
 * Validasi dan extract JSON dari output AI
 * Memastikan AI hanya mengeluarkan JSON yang valid untuk tool calling
 */

const logger = require('../utils/logger');

/**
 * Extract JSON dari teks yang mungkin mengandung narasi
 * Contoh: "Saya akan membuka youtube: {"tool": "open_web", "query": "youtube"}"
 * Hasil: {"tool": "open_web", "query": "youtube"}
 */
function extractJsonFromText(text) {
    if (!text || typeof text !== 'string') {
        return null;
    }

    // 1. Coba cari dan parse JSON array [ { ... } ]
    const arrayRegex = /\[\s*\{[\s\S]*\}\s*\]/;
    const arrayMatch = text.match(arrayRegex);
    if (arrayMatch) {
        try {
            return JSON.parse(arrayMatch[0]);
        } catch (e) {
            logger.warn('JsonValidator', `JSON.parse array gagal`);
        }
    }

    // 2. Coba tambahkan kurung siku jika formatnya object terpisah baris/koma
    try {
        const firstBrace = text.indexOf('{');
        const lastBrace = text.lastIndexOf('}');
        if (firstBrace !== -1 && lastBrace !== -1) {
            let jsonStr = text.substring(firstBrace, lastBrace + 1);
            // Replace "}\n{" atau "}, {" dengan "},{"
            jsonStr = jsonStr.replace(/\}\s*,?\s*\{/g, '},{');
            const wrapped = '[' + jsonStr + ']';
            const parsed = JSON.parse(wrapped);
            if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].tool) {
                return parsed;
            }
        }
    } catch (e) {
        // Abaikan dan lanjut ke regex fallback
    }

    // 3. Regex Fallback untuk multiline/broken JSON
    logger.warn('JsonValidator', `JSON.parse gagal, mencoba regex fallback untuk mengekstrak tool dan query...`);
    
    const regex = /\{\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"?query"?\s*:\s*"([\s\S]*?)"\s*\}/g;
    let match;
    const tools = [];
    
    while ((match = regex.exec(text)) !== null) {
        tools.push({
            tool: match[1],
            query: match[2].trim()
        });
    }

    if (tools.length > 0) {
        logger.debug('JsonValidator', `Regex fallback berhasil mengekstrak ${tools.length} tool.`);
        return tools;
    }

    logger.warn('JsonValidator', `Semua metode ekstraksi gagal.`);
    return null;
}

/**
 * Validasi struktur JSON sesuai schema yang diharapkan
 */
function validateToolCall(jsonArray) {
    if (!Array.isArray(jsonArray)) {
        return { valid: false, error: 'Output bukan array' };
    }

    const validTools = [
        'open_web', 'search_web', 'scrape_web',
        'play_music', 'play_video', 'search_youtube',
        'save_credential', 'list_credentials', 'delete_credential',
        'create_file', 'read_file', 'ingest_codebase', 'research_and_summarize', 'open_website', 'read_webpage', 'open_youtube_channel',
        'save_memory', 'search_memory','open_app', 'control_volume',
        'take_screenshot', 'check_email',
        'chat'
    ];

    const validatedData = [];

    for (const json of jsonArray) {
        if (!json || typeof json !== 'object') {
            return { valid: false, error: 'Terdapat item yang bukan object' };
        }

        // Edge case: Model output {"tool": ["t1", "t2"], "query": ["q1", "q2"]}
        if (Array.isArray(json.tool) && Array.isArray(json.query)) {
            const length = Math.min(json.tool.length, json.query.length);
            for (let i = 0; i < length; i++) {
                if (typeof json.tool[i] === 'string' && typeof json.query[i] === 'string') {
                    if (!validTools.includes(json.tool[i])) {
                        return { valid: false, error: `Tool "${json.tool[i]}" tidak valid. Harus salah satu dari: ${validTools.join(', ')}` };
                    }
                    validatedData.push({ tool: json.tool[i], query: json.query[i] });
                }
            }
            continue;
        }

        if (!json.tool || typeof json.tool !== 'string') {
            return { valid: false, error: 'Field "tool" tidak ditemukan atau bukan string' };
        }

        if (json.query === null || json.query === undefined) {
            json.query = ''; // normalisasi, bukan ditolak
        } else if (typeof json.query !== 'string') {
            return { valid: false, error: 'Field "query" harus berupa string' };
        }

        if (!validTools.includes(json.tool)) {
            return { valid: false, error: `Tool "${json.tool}" tidak valid. Harus salah satu dari: ${validTools.join(', ')}` };
        }
        
        validatedData.push(json);
    }

    return { valid: true, data: validatedData };
}

/**
 * Parse dan validasi output AI
 * Returns: { success: boolean, data?: object, error?: string, rawOutput?: string }
 */
function parseAndValidateAIOutput(aiOutput) {
    if (!aiOutput) {
        return {
            success: false,
            error: 'Output AI kosong',
            rawOutput: aiOutput
        };
    }

    logger.debug('JsonValidator', `Parsing AI output: ${aiOutput.substring(0, 200)}`);

    // Step 1: Extract JSON dari teks
    const extracted = extractJsonFromText(aiOutput);
    
    if (!extracted) {
        return {
            success: false,
            error: 'Tidak dapat menemukan JSON valid dalam output AI',
            rawOutput: aiOutput
        };
    }

    // Step 2: Validasi struktur
    const validation = validateToolCall(extracted);
    
    if (!validation.valid) {
        return {
            success: false,
            error: validation.error,
            rawOutput: aiOutput
        };
    }

    const parsedTools = validation.data.map(t => t.tool).join(', ');
    logger.debug('JsonValidator', `Valid JSON parsed: tools=[${parsedTools}]`);
    
    return {
        success: true,
        data: validation.data,
        rawOutput: aiOutput
    };
}

/**
 * Generate feedback message untuk AI jika output invalid
 */
function generateFeedbackMessage(aiOutput, error) {
    return `
⚠️ OUTPUT TIDAK VALID. Silakan perbaiki:

Error: ${error}

Output Anda yang salah:
${aiOutput}

Format yang BENAR (HANYA JSON ATAU ARRAY OF JSON, TANPA teks lain):
[{"tool": "nama_tool", "parameter_tool": "nilai"}]

Contoh Single:
{"tool": "open_web", "query": "youtube"}

Contoh dengan parameter spesifik:
{"tool": "check_email", "sender": "paimon", "date": "14/8/2026"}

ATURAN:
1. HANYA output JSON atau Array of JSON, TANPA penjelasan atau teks naratif
2. Format: {"tool": "...", "query": "..."} atau array dari format tersebut
3. Jangan tambahkan tanda kutip di luar JSON
4. Pastikan JSON valid (tidak ada trailing comma)

Coba lagi dengan format yang benar.`;
}

module.exports = {
    extractJsonFromText,
    validateToolCall,
    parseAndValidateAIOutput,
    generateFeedbackMessage
};