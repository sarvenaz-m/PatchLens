const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const A=require('../src/patchlens/web/analysis.js');
const {validateReport}=require('../src/patchlens/web/app.js');
const root=path.resolve(__dirname,'..');
const report=JSON.parse(fs.readFileSync(path.join(root,'examples/fixture-run/report.json')));
const diagnostics=JSON.parse(fs.readFileSync(path.join(root,'examples/analysis/weighted-test.json')));
const comparison=JSON.parse(fs.readFileSync(path.join(root,'examples/analysis/linear-vs-weighted.json')));
const rows=report.samples.filter(s=>s.split==='test');
const weighted=report.runs.find(r=>r.id==='weighted');
const predictions=new Map(weighted.predictions.map(p=>[p.id,p]));
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-12,`${a} differs from ${b}`);
test('browser diagnostics agree with independent Python calculations',()=>{
  const m=A.summary(rows,predictions,weighted.threshold);
  for(const k of ['balanced_accuracy','mcc','brier'])close(m[k],diagnostics.metrics[k]);
  for(const k of ['ece','log_loss'])close(m[k],diagnostics.calibration[k]);
  m.bins.forEach((b,i)=>{const expected=diagnostics.calibration.bins[i];assert.equal(b.n,expected.n);if(b.n){close(b.mean_score,expected.mean_score);close(b.observed_rate,expected.observed_rate);b.observed_wilson_95.forEach((v,j)=>close(v,expected.observed_wilson_95[j]));}});
});
test('CWE slices and pair score margins match Python',()=>{
  for(const slice of A.slices(rows,predictions,weighted.threshold)){assert.equal(slice.fn,diagnostics.by_cwe[slice.cwe].fn);assert.equal(slice.n,2);}
  const expected=new Map(diagnostics.pair_margins.map(p=>[p.pair_id,p]));
  for(const pair of A.pairMargins(rows,predictions))close(pair.margin,expected.get(pair.pair_id).score_margin);
});
test('paired outcomes match Python and remain independent of row order',()=>{
  const candidate=structuredClone(weighted);candidate.predictions.reverse();
  const result=A.compare(rows,report.runs[0],candidate);
  assert.deepEqual(result.outcomes,comparison.outcomes);close(result.accuracy_delta,comparison.accuracy_delta);
});
test('comparison verifies source content beyond the asserted fingerprint',()=>{
  const candidate=structuredClone(report);candidate.samples[0].code+='\n// changed';
  assert.throws(()=>A.compatible(report,candidate),/Source/);
  candidate.samples[0].code=report.samples[0].code;candidate.samples.reverse();assert.equal(A.compatible(report,candidate),true);
});
test('calibration handles 0, 1, empty bins and undefined MCC',()=>{
  const m=A.summary([{id:'a',label:0},{id:'b',label:1}],new Map([['a',{score:0}],['b',{score:1}]]),.5);
  assert.equal(m.ece,0);assert.equal(m.brier,0);assert.equal(m.bins[9].n,1);assert.equal(m.bins[5].mean_score,null);
  assert.equal(A.summary([{id:'a',label:0}],new Map([['a',{score:0}]]),.5).mcc,null);
});
test('review roundtrip preserves notes as data and rejects wrong dataset',()=>{
  const entry={id:rows[0].id,status:'needs_attention',note:'<img src=x onerror=alert(1)>',updated_at:'2026-09-30T10:00:00Z'};
  const bundle=A.reviewBundle(report,{[entry.id]:entry});
  assert.deepEqual(A.validateReview(bundle,report)[entry.id],entry);
  bundle.dataset_sha256='wrong';assert.throws(()=>A.validateReview(bundle,report),/dataset/);
});
test('review import rejects duplicate IDs, invalid states and oversized notes',()=>{
  const row={id:rows[0].id,status:'reviewed',note:'',updated_at:'2026-09-30T10:00:00Z'};
  const make=entries=>({schema_version:'patchlens-review-v1',dataset_sha256:report.dataset.fingerprint,entries});
  assert.throws(()=>A.validateReview(make([row,row]),report),/Invalid/);
  assert.throws(()=>A.validateReview(make([{...row,status:'verified-secure'}]),report),/Invalid/);
  assert.throws(()=>A.validateReview(make([{...row,note:'x'.repeat(5001)}]),report),/Invalid/);
});
test('CSV escapes quotes, line breaks and formula-like text',()=>{
  assert.equal(A.csv([['=cmd','a"b','line\nbreak',-1]]),'"\'=cmd","a""b","line\nbreak","-1"\r\n');
});
test('import refuses incompatible pair CWE metadata and malformed scanners',()=>{
  const t=structuredClone(report);t.runs[0].threshold=.37;assert.throws(()=>validateReport(t),/provenance/);
  const r=structuredClone(report);r.samples[0].cwe='CWE-99999';assert.throws(()=>validateReport(r),/pair/);
  const s=structuredClone(report);s.static_analysis.tools='not an array';assert.throws(()=>validateReport(s),/metadata/);
});
