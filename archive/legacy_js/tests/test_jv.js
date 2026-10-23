const jv = require('../src/engine/json_validator.js');
const reg = require('../src/tools/registry');

reg.loadAll();

const output = '{"tool": "get_weather", "city": "Jakarta"}';
console.log(jv.parseAndValidateAIOutput(output));
