const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {validateReport,esc}=require('../src/patchlens/web/app.js'),A=require('../src/patchlens/web/analysis.js'),B=require('../src/patchlens/web/benchmark.js');
const root=path.resolve(__dirname,'..');
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p)));
const report=read('examples/public-benchmark/report.json');
const reports=[17,29,43].map(seed=>read(`examples/public-benchmark/seed-${seed}/report.json`)).concat([0,1,2,3,4].map(fold=>read(`examples/repository-cross-validation/fold-${fold}/run/report.json`)));
const near=(a,b)=>a==null||b==null?assert.equal(a,b):assert.ok(Math.abs(a-b)<1e-12,`${a} differs from ${b}`);
test('all real reports and repository folds satisfy browser import contracts',()=>{for(const r of reports)assert.equal(validateReport(r),r);});
test('public metrics agree with Python in all 144 model/split states',()=>{
  let count=0;
  for(const r of reports)for(const run of r.runs)for(const split of ['train','validation','test']){
    const rows=r.samples.filter(s=>s.split===split),pred=new Map(run.predictions.map(p=>[p.id,p])),m=A.summary(rows,pred,run.threshold),expected=run.splits[split].metrics;
    for(const key of ['tp','tn','fp','fn','precision','recall','fpr','fnr','f1','accuracy','brier'])near(m[key],expected[key]);
    const groupValues=[...new Set(rows.map(s=>s.group_id))].map(group=>A.summary(rows.filter(s=>s.group_id===group),pred,run.threshold).balanced_accuracy);
    near(groupValues.reduce((a,b)=>a+b,0)/groupValues.length,run.repository_metrics[split].macro_balanced_accuracy);count++;
  }assert.equal(count,144);
});
test('unmapped upstream CWE is preserved without inventing a weakness number',()=>{assert.ok(report.samples.some(s=>s.cwe==='CWE-unknown'));assert.equal(validateReport(report),report);});
test('public error-count injection and missing repository metadata are rejected',()=>{
  let r=structuredClone(report);r.cross_validation.models.codebert.pooled_counts.fn='<img src=x>';assert.throws(()=>validateReport(r),/out-of-fold error counts/);
  r=structuredClone(report);delete r.dataset.components;assert.throws(()=>validateReport(r),/repository ledger/);
});
test('public benchmark escapes supplemental source metadata even before validation',()=>{
  const r=structuredClone(report);r.runs.find(m=>m.id==='codebert').provenance.truncated_examples='<img src=x onerror=alert(1)>';
  r.dataset.components[0].repositories=['<svg onload=alert(1)>'];
  const html=B.render(r,{esc,pct:x=>x==null?'—':(x*100).toFixed(1)+'%',dec:x=>String(x),panelHead:(t,s)=>`<h2>${esc(t)}</h2><p>${esc(s)}</p>`,stat:(t,v,s)=>`${esc(t)} ${esc(v)} ${esc(s)}`});
  assert.ok(html.includes('&lt;img'));assert.ok(html.includes('&lt;svg'));assert.ok(!html.includes('<img src=x'));assert.ok(!html.includes('<svg onload'));
});
