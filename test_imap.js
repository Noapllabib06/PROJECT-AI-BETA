const imaps = require('imap-simple');
const credentialManager = require('./src/utils/credentials');
const PROVIDER_HOSTS = new Map([
    ['gmail', { host: 'imap.gmail.com', port: 993 }]
]);

async function test() {
    const cred = credentialManager.getCredential('gmail');
    const hostConfig = PROVIDER_HOSTS.get('gmail');
    
    const config = {
        imap: {
            user: cred.username,
            password: cred.password,
            host: hostConfig.host,
            port: hostConfig.port,
            tls: true,
            authTimeout: 10000,
            tlsOptions: { rejectUnauthorized: false }
        }
    };
    
    console.log("Connecting...");
    const connection = await imaps.connect(config);
    await connection.openBox('INBOX');
    
    console.log("Searching UNSEEN...");
    const messages = await connection.search(['ALL'], { bodies: ['HEADER'], markSeen: false });
    if(messages.length === 0) { console.log("No messages"); return; }
    
    const recent = messages.slice(-5).reverse();
    const uids = recent.map(m => m.attributes.uid);
    console.log("UIDs to fetch full:", uids);
    
    const fullFetchOptions = { bodies: [''], markSeen: false };
    const minUid = Math.min(...uids);
    const maxUid = Math.max(...uids);
    const fullMessages = await connection.search([['UID', `${minUid}:${maxUid}`]], fullFetchOptions);
    console.log("Fetched full messages:", fullMessages.length);
    
    for (const msg of fullMessages) {
        console.log(`UID: ${msg.attributes.uid}`);
        for (const p of msg.parts) {
            console.log(`  Part which: '${p.which}', size: ${p.size}`);
        }
    }
    connection.end();
}
test().catch(console.error);
