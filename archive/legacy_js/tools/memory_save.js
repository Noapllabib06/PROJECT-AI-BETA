const axios = require('axios');
const { OllamaEmbeddings } = require("@langchain/ollama");

// VRAM GUARD: Fungsi unload
async function _unloadModel(modelName) {
    try {
        await axios.post('http://127.0.0.1:11434/api/generate', {
            model: modelName,
            keep_alive: 0
        });
        console.log(`🧠 [VRAM_Manager] Model ${modelName} unloaded.`);
    } catch (e) {
        console.error(`❌ [VRAM_Manager] Gagal unload model ${modelName}:`, e.message);
    }
}

const memorySaveTool = {
    name: "save_memory",
    description: "Gunakan tool ini JIKA pengguna memberikan fakta baru, preferensi, atau informasi penting tentang diri mereka atau sesuatu yang harus diingat di masa depan.",
    parameters: {
        type: "object",
        properties: {
            query: {
                type: "string",
                description: "Fakta, detail, atau informasi yang harus diingat."
            }
        },
        required: ["query"]
    },
    execute: async ({ query }) => {
        try {
            console.log(`\n🧠 [Agent] Menanamkan memori baru: "${query}"...`);
            
            // Inisialisasi OllamaEmbeddings
            const embeddings = new OllamaEmbeddings({
                model: "nomic-embed-text",
                baseUrl: "http://127.0.0.1:11434"
            });
            
            // Menghasilkan vektor menggunakan Langchain OllamaEmbeddings
            const vector = await embeddings.embedQuery(query);

            // POST ke Python Backend
            const id = "doc_" + Date.now();
            await axios.post('http://127.0.0.1:8000/add_memory', {
                id: id,
                text: query,
                vector: vector
            });

            console.log("🧠 [Agent] Memori berhasil ditanamkan!");
            return `Sistem: Fakta "${query}" telah berhasil disimpan ke dalam memori jangka panjang.`;

        } catch (error) {
            console.error("\n❌ [Tool Error] Gagal menyimpan memori:", error.message);
            return `Sistem Error: Gagal menyimpan memori (${error.message})`;
        } finally {
            // VRAM GUARD: unload nomic-embed-text agar Qwen / LLaVA tidak OOM
            await _unloadModel("nomic-embed-text");
        }
    }
};

module.exports = memorySaveTool;
