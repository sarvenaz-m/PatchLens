/* Parse only. Never execute intentionally vulnerable source examples. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawnSync}=require('node:child_process');
const rows=fs.readFileSync(path.join(__dirname,'../src/patchlens/data/fixtures.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
const directory=fs.mkdtempSync(path.join(os.tmpdir(),'patchlens-syntax-'));
try {
  for(const row of rows)for(const field of ['code','view_code']) {
    const file=path.join(directory,'fixture.js');fs.writeFileSync(file,row[field]);
    const result=spawnSync(process.execPath,['--check',file],{encoding:'utf8'});
    if(result.status!==0)throw new Error(`${row.id}/${field}: ${result.stderr}`);
  }
  console.log(`Syntax valid: ${rows.length} originals and ${rows.length} renamed views. No snippets executed.`);
} finally {fs.rmSync(directory,{recursive:true,force:true});}
