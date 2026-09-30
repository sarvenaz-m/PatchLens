/* Run with node --test tests/web.test.cjs; uses the checked-in real experiment. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {esc,metrics,validateReport,rankingCurve}=require('../src/patchlens/web/app.js');
const report=JSON.parse(fs.readFileSync(path.join(__dirname,'../examples/fixture-run/report.json'),'utf8'));
const clone=()=>JSON.parse(JSON.stringify(report));
test('reference report satisfies the browser contract',()=>assert.equal(validateReport(report),report));
test('all split metrics agree with the independent Python implementation',()=>{
  for(const run of report.runs)for(const split of ['train','validation','test']) {
    const m=metrics(report.samples.filter(s=>s.split===split),new Map(run.predictions.map(p=>[p.id,p])),run.threshold);
    for(const key of ['tp','tn','fp','fn','precision','recall','f1','fnr','fpr','accuracy'])assert.equal(m[key],run.splits[split].metrics[key],`${run.id}/${split}/${key}`);
  }
});
test('hostile strings are escaped as text',()=>assert.equal(esc('<img src="x" onerror=\'evil()\'>&'),'&lt;img src=&quot;x&quot; onerror=&#39;evil()&#39;&gt;&amp;'));
test('duplicate and missing predictions are refused',()=>{
  const r=clone();r.runs[0].predictions[1]=r.runs[0].predictions[0];assert.throws(()=>validateReport(r),/coverage/);
  r.runs[0].predictions.pop();assert.throws(()=>validateReport(r),/coverage/);
});
test('out of range, nonfinite and string scores are refused',()=>{
  for(const value of [NaN,Infinity,-.1,1.1,'0.2',true]){const r=clone();r.runs[0].predictions[0].score=value;assert.throws(()=>validateReport(r),/prediction/);}
});
test('cross-split group leakage is refused on import',()=>{
  const r=clone(),first=r.samples[0],other=r.samples.find(s=>s.split!==first.split);other.group_id=first.group_id;assert.throws(()=>validateReport(r),/group/);
});
test('PCA coordinates must be finite and uniquely cover the dataset',()=>{
  const r=clone();r.runs[0].projection.points[1]=r.runs[0].projection.points[0];assert.throws(()=>validateReport(r),/projection/);
});
test('JS ROC curve matches stored Python curve including score ties',()=>{
  for(const run of report.runs){const p=new Map(run.predictions.map(p=>[p.id,p]));const c=rankingCurve(report.samples.filter(s=>s.split==='test'),p,'roc');assert.deepEqual(c,run.splits.test.curves.roc.map(p=>({x:p.fpr,y:p.tpr})));}
});
test('undefined precision is displayed as null',()=>assert.equal(metrics([{id:'a',label:1}],new Map([['a',{score:.1,view_score:.2}]]),.5).precision,null));
