const draftingTools = require('./src/tools/drafting_tools');

async function runTest() {
    const saveTool = draftingTools.find(t => t.name === 'save_draft_section');
    const checkTool = draftingTools.find(t => t.name === 'check_draft_status');
    const compileTool = draftingTools.find(t => t.name === 'compile_draft_article');
    
    console.log("Saving section 1...");
    const res1 = await saveTool.execute({
        articleTitle: "Test Article AI",
        sectionName: "1. Pendahuluan",
        content: "Ini adalah pendahuluan dari artikel AI."
    });
    console.log(res1);
    
    console.log("Saving section 2...");
    const res2 = await saveTool.execute({
        articleTitle: "Test Article AI",
        sectionName: "2. Metode",
        content: "Metode yang digunakan adalah deep learning."
    });
    console.log(res2);
    
    console.log("Checking status...");
    const res3 = await checkTool.execute({ articleTitle: "Test Article AI" });
    console.log(res3);
    
    console.log("Compiling...");
    const res4 = await compileTool.execute({ articleTitle: "Test Article AI" });
    console.log(res4);
}

runTest();
