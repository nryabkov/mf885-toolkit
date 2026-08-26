const test=require('node:test');
const assert=require('node:assert/strict');
const child=require('node:child_process');
const path=require('node:path');

test('derived R2.2 SMS passes the complete R2.1 one-POST and fail-closed suite',()=>{
  const target=path.join(__dirname,'webui-community-r21-sms-dom.test.js');
  const result=child.spawnSync(process.execPath,['--test',target],{
    encoding:'utf8',
    env:{...process.env,MF885_TEST_R22_SMS:'1'}
  });
  assert.equal(result.status,0,result.stdout+'\n'+result.stderr);
});
