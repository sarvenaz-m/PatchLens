/* Pure analysis and review contracts shared by the UI and Node checks. */
(function (root) {
  'use strict';
  const number = x => typeof x === 'number' && Number.isFinite(x);
  const probability = x => number(x) && x >= 0 && x <= 1;
  const ratio = (a,b) => b ? a/b : null;
  function wilson(successes,n) {
    if(!n) return null;
    const z=1.959963984540054,p=successes/n,den=1+z*z/n;
    const centre=(p+z*z/(2*n))/den,half=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;
    return [successes===0?0:Math.max(0,centre-half),successes===n?1:Math.min(1,centre+half)];
  }
  function summary(rows,predictions,threshold,bins=10) {
    if(!rows.length || !probability(threshold) || !Number.isInteger(bins) || bins<2 || bins>20) throw new Error('Invalid analysis inputs.');
    let tp=0,tn=0,fp=0,fn=0,brier=0,loss=0;
    const buckets=Array.from({length:bins},(_,i)=>({lower:i/bins,upper:(i+1)/bins,n:0,sum:0,positive:0}));
    for(const row of rows) {
      const p=predictions.get(row.id)?.score;
      if(!probability(p)||![0,1].includes(row.label))throw new Error('Invalid analysis prediction.');
      const yes=p>=threshold;
      if(yes&&row.label)tp++;else if(yes)fp++;else if(row.label)fn++;else tn++;
      brier+=(p-row.label)**2;
      const clipped=Math.max(1e-15,Math.min(1-1e-15,p));
      loss-=row.label*Math.log(clipped)+(1-row.label)*Math.log(1-clipped);
      const bucket=buckets[Math.min(Math.floor(p*bins),bins-1)];bucket.n++;bucket.sum+=p;bucket.positive+=row.label;
    }
    const reliability=buckets.map(b=>({lower:b.lower,upper:b.upper,n:b.n,mean_score:ratio(b.sum,b.n),observed_rate:ratio(b.positive,b.n),observed_wilson_95:wilson(b.positive,b.n)}));
    const denominator=Math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn));
    return {n:rows.length,tp,tn,fp,fn,precision:ratio(tp,tp+fp),recall:ratio(tp,tp+fn),fpr:ratio(fp,fp+tn),fnr:ratio(fn,fn+tp),
      f1:ratio(2*tp,2*tp+fp+fn),accuracy:(tp+tn)/rows.length,balanced_accuracy:tp+fn&&tn+fp?(tp/(tp+fn)+tn/(tn+fp))/2:null,
      mcc:denominator?(tp*tn-fp*fn)/denominator:null,brier:brier/rows.length,log_loss:loss/rows.length,
      ece:reliability.reduce((total,b)=>total+(b.n?b.n/rows.length*Math.abs(b.mean_score-b.observed_rate):0),0),
      fnr_wilson_95:wilson(fn,tp+fn),fpr_wilson_95:wilson(fp,fp+tn),bins:reliability};
  }
  function slices(rows,predictions,threshold) {
    return [...new Set(rows.map(s=>s.cwe))].sort((a,b)=>Number(a.slice(4))-Number(b.slice(4))).map(cwe=>({cwe,...summary(rows.filter(s=>s.cwe===cwe),predictions,threshold)}));
  }
  function pairMargins(rows,predictions) {
    const groups=new Map();for(const s of rows){if(!groups.has(s.pair_id))groups.set(s.pair_id,[]);groups.get(s.pair_id).push(s);}
    return [...groups].map(([pair_id,pair])=>{
      const a=pair.find(s=>s.label===1),b=pair.find(s=>s.label===0);
      if(!a||!b||pair.length!==2)throw new Error('Incomplete pair.');
      const margin=predictions.get(a.id).score-predictions.get(b.id).score;
      return {pair_id,title:a.title,cwe:a.cwe,margin,before:predictions.get(a.id).score,after:predictions.get(b.id).score};
    }).sort((a,b)=>a.margin-b.margin||a.pair_id.localeCompare(b.pair_id));
  }
  function compatible(a,b) {
    if(a.dataset.fingerprint!==b.dataset.fingerprint||a.samples.length!==b.samples.length)throw new Error('Comparison requires the same dataset.');
    const fields=['id','pair_id','group_id','split','label','cwe','title','code','view_code','rationale','assumptions','source','licence','review_status'];
    const right=new Map(b.samples.map(s=>[s.id,s]));
    for(const s of a.samples){const t=right.get(s.id);if(!t||fields.some(k=>s[k]!==t[k]))throw new Error('Source, labels or split assignments differ.');}
    return true;
  }
  function compare(rows,a,b) {
    const pa=new Map(a.predictions.map(p=>[p.id,p])),pb=new Map(b.predictions.map(p=>[p.id,p]));
    const baseline=summary(rows,pa,a.threshold),candidate=summary(rows,pb,b.threshold);
    const changes=rows.map(s=>{
      const ca=Number(pa.get(s.id).score>=a.threshold)===s.label,cb=Number(pb.get(s.id).score>=b.threshold)===s.label;
      return {...s,baseline_score:pa.get(s.id).score,candidate_score:pb.get(s.id).score,
        outcome:cb&&!ca?'improved':ca&&!cb?'regressed':ca?'both_correct':'both_wrong'};
    });
    const outcomes=Object.fromEntries(['improved','regressed','both_correct','both_wrong'].map(k=>[k,changes.filter(c=>c.outcome===k).length]));
    return {baseline,candidate,changes,outcomes,accuracy_delta:candidate.accuracy-baseline.accuracy};
  }
  function reviewBundle(report,entries) {
    return {schema_version:'patchlens-review-v1',dataset_sha256:report.dataset.fingerprint,entries:Object.values(entries)};
  }
  function validateReview(bundle,report) {
    if(!bundle||bundle.schema_version!=='patchlens-review-v1'||bundle.dataset_sha256!==report.dataset.fingerprint||!Array.isArray(bundle.entries)||bundle.entries.length>report.samples.length)throw new Error('Review file does not match this dataset.');
    const ids=new Set(report.samples.map(s=>s.id)),result=Object.create(null);
    for(const row of bundle.entries){
      if(!row||!ids.has(row.id)||Object.hasOwn(result,row.id)||!['unreviewed','needs_attention','reviewed'].includes(row.status)||typeof row.note!=='string'||row.note.length>5000||typeof row.updated_at!=='string'||!Number.isFinite(Date.parse(row.updated_at)))throw new Error('Invalid review entry.');
      result[row.id]={id:row.id,status:row.status,note:row.note,updated_at:row.updated_at};
    }
    return result;
  }
  function csv(rows) {
    const cell=value=>{
      let text=value==null?'':String(value);
      if(typeof value==='string'&&/^[\s]*[=+@-]/.test(text))text="'"+text;
      return '"'+text.replace(/"/g,'""')+'"';
    };
    return rows.map(row=>row.map(cell).join(',')).join('\r\n')+'\r\n';
  }
  const api={wilson,summary,slices,pairMargins,compatible,compare,reviewBundle,validateReview,csv};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.PatchLensAnalysis=api;
})(typeof globalThis!=='undefined'?globalThis:this);
