const { OllamaEmbeddings } = require('@langchain/ollama');
const registry = require('../src/tools/registry');

function cosineSimilarity(vecA, vecB) {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < vecA.length; i++) {
        dotProduct += vecA[i] * vecB[i];
        normA += vecA[i] * vecA[i];
        normB += vecB[i] * vecB[i];
    }
    if (normA === 0 || normB === 0) return 0;
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

function calculateWordOverlapBoost(query, description, toolName) {
    const stopWords = ['yang', 'dari', 'untuk', 'dengan', 'atau', 'pada', 'dalam', 'kamu', 'bisa', 'akan', 'ingin'];
    const qWords = query.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/).filter(w => w.length > 2 && !stopWords.includes(w));
    const dWords = description.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/).filter(w => w.length > 2 && !stopWords.includes(w));
    const nWords = toolName.toLowerCase().split('_').filter(w => w.length > 2 && !stopWords.includes(w));
    
    let overlapCount = 0;
    let matches = [];
    for (const qw of qWords) {
        if (dWords.includes(qw) || nWords.includes(qw)) {
            overlapCount++;
            matches.push(qw);
        }
    }
    return { boost: overlapCount * 0.2, matches };
}

async function testRouter() {
    registry.loadAll();
    const embeddings = new OllamaEmbeddings({ model: 'nomic-embed-text' });
    
    const defs = registry.getToolDefinitions();
    const docs = defs.map(d => `${d.function.name}: ${d.function.description}`);
    const names = defs.map(d => d.function.name);
    const descriptions = defs.map(d => d.function.description);
    
    console.log('Embedding tools...');
    const vectors = await embeddings.embedDocuments(docs);
    
    const query = "Coba cek status baterai laptop dan juga suhu cuaca di Bandung";
    console.log(`Embedding query: "${query}"...`);
    const qVec = await embeddings.embedQuery(query);
    
    const scores = [];
    for (let i = 0; i < vectors.length; i++) {
        let score = cosineSimilarity(qVec, vectors[i]);
        let { boost, matches } = calculateWordOverlapBoost(query, descriptions[i], names[i]);
        scores.push({ name: names[i], baseScore: score, boost: boost, finalScore: score + boost, matches });
    }
    
    scores.sort((a, b) => b.finalScore - a.finalScore);
    console.log(scores.slice(0, 5));
}

testRouter().catch(console.error);
