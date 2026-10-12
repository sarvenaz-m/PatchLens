/* PatchLens: dependency-free, offline research workbench. No snippets are executed. */
(function () {
  'use strict';
  const esc = value => String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const score = x => finite(x) && x >= 0 && x <= 1;
  const identifier = x => typeof x === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$/.test(x);
  const textField = (x, max = 50000) => typeof x === 'string' && x.length > 0 && x.length <= max;
  const ratio = (a, b) => b ? a / b : null;

  function metrics(rows, predictions, threshold) {
    if (!score(threshold) || !rows.length) throw new Error('Invalid metric inputs.');
    let tp = 0, tn = 0, fp = 0, fn = 0, flips = 0, shift = 0, both = 0;
    for (const s of rows) {
      const p = predictions.get(s.id);
      if (!p || !score(p.score) || !score(p.view_score) || ![0,1].includes(s.label)) throw new Error('Invalid prediction.');
      const a = p.score >= threshold, b = p.view_score >= threshold;
      if (a && s.label) tp++; else if (a) fp++; else if (s.label) fn++; else tn++;
      flips += Number(a !== b); shift += Math.abs(p.score - p.view_score);
      both += Number(a === Boolean(s.label) && b === Boolean(s.label));
    }
    return {n:rows.length, tp,tn,fp,fn, precision:ratio(tp,tp+fp), recall:ratio(tp,tp+fn),
      f1:ratio(2*tp,2*tp+fp+fn), fnr:ratio(fn,tp+fn), fpr:ratio(fp,tn+fp),
      accuracy:(tp+tn)/rows.length, agreement:1-flips/rows.length, flips,
      mean_score_shift:shift/rows.length, both_correct:both/rows.length};
  }

  function validateReport(r) {
    const fail = message => { throw new Error('Invalid report: ' + message); };
    if (!r || r.schema_version !== '1.0' || r.project !== 'PatchLens') fail('expected PatchLens schema 1.0.');
    if (!identifier(r.experiment_id) || !textField(r.version,32)) fail('missing experiment identity.');
    if (!Array.isArray(r.samples) || r.samples.length < 6 || r.samples.length > 10000) fail('sample count is outside supported bounds.');
    const ids = new Set(), pairs = new Map(), groups = new Map();
    for (const s of r.samples) {
      if (!s || !identifier(s.id) || ids.has(s.id) || !identifier(s.pair_id) || !identifier(s.group_id)) fail('invalid or duplicate sample identity.');
      if (![0,1].includes(s.label) || !['train','validation','test'].includes(s.split)) fail('invalid label or split.');
      for (const k of ['cwe','title','code','view_code','rationale','assumptions','source','licence','review_status']) if (!textField(s[k])) fail('missing sample field: '+k);
      if(!/^CWE-(?:\d{1,10}|unknown)$/.test(s.cwe))fail('invalid weakness category.');
      ids.add(s.id);
      if (groups.has(s.group_id) && groups.get(s.group_id) !== s.split) fail('a group crosses splits.');
      groups.set(s.group_id,s.split);
      if (!pairs.has(s.pair_id)) pairs.set(s.pair_id,[]);
      pairs.get(s.pair_id).push(s);
    }
    for (const pair of pairs.values()) if (pair.length !== 2 || pair[0].label === pair[1].label || pair[0].split !== pair[1].split || pair[0].group_id !== pair[1].group_id || pair[0].cwe !== pair[1].cwe) fail('broken code pair.');
    for (const split of ['train','validation','test']) if (new Set(r.samples.filter(s=>s.split===split).map(s=>s.label)).size !== 2) fail('every split must contain both labels.');
    if (!Array.isArray(r.runs) || !r.runs.length || r.runs.length > 20) fail('missing runs.');
    const runIds = new Set();
    for (const run of r.runs) {
      if (!run || !identifier(run.id) || runIds.has(run.id) || !textField(run.name,150) || !score(run.threshold)) fail('invalid run.');
      runIds.add(run.id);
      if (!Array.isArray(run.predictions) || run.predictions.length !== ids.size) fail('incomplete prediction coverage.');
      const seen = new Set();
      for (const p of run.predictions) {
        if (!p || !ids.has(p.id) || seen.has(p.id) || !score(p.score) || !score(p.view_score)) fail('invalid prediction or coverage.');
        seen.add(p.id);
      }
      if (!run.operating_point || run.operating_point.source_split !== 'validation' || !score(run.operating_point.max_fpr)) fail('unknown operating-point provenance.');
      if(run.operating_point.threshold!==run.threshold)fail('operating threshold and provenance disagree.');
      if (!Array.isArray(run.history) || run.history.length > 10001 || run.history.some(h=>!finite(h.epoch)||!finite(h.loss))) fail('invalid training history.');
      if (!run.projection || !Array.isArray(run.projection.points)) fail('missing projection state.');
      if (run.projection.method === 'not_available') { if (run.projection.points.length) fail('unavailable projection contains points.'); }
      else if (run.projection.points.length !== ids.size) fail('missing projection.');
      const pointIds = new Set();
      for (const p of run.projection.points) {
        if (!ids.has(p.id) || pointIds.has(p.id) || !finite(p.x) || !finite(p.y) || Math.abs(p.x)>1e9 || Math.abs(p.y)>1e9) fail('invalid projection.');
        pointIds.add(p.id);
      }
    }
    if (!r.dataset || !textField(r.dataset.fingerprint,100) || !r.config || !r.environment || !Array.isArray(r.limitations) || !r.limitations.every(x=>textField(x,1000))) fail('missing provenance.');
    if (r.static_analysis) {
      const scan=r.static_analysis;
      if (!['not_run','failed','completed_with_errors','completed'].includes(scan.status) || !Array.isArray(scan.findings) || scan.findings.length>100000) fail('invalid scanner state.');
      if (scan.dataset_sha256 && scan.dataset_sha256 !== r.dataset.fingerprint) fail('scanner dataset mismatch.');
      if(scan.tools && (!Array.isArray(scan.tools)||scan.tools.some(t=>!t||!textField(t.name,200)||(t.version!=null&&typeof t.version!=='string'))))fail('invalid scanner metadata.');
      for(const f of scan.findings) if (!ids.has(f.example_id)||!textField(f.rule,1000)||typeof f.message!=='string'||f.message.length>50000||!Number.isInteger(f.line)||f.line<1||typeof f.severity!=='string') fail('invalid scanner finding.');
    }
    return r;
  }

  function rankingCurve(rows, predictions, kind) {
    const sorted = rows.map(s=>({label:s.label,score:predictions.get(s.id).score})).sort((a,b)=>b.score-a.score);
    const positives = rows.reduce((a,s)=>a+s.label,0), negatives = rows.length-positives;
    const points = [{x:0,y:kind==='pr'?1:0}];
    let tp=0,fp=0;
    for (let i=0;i<sorted.length;) {
      const value = sorted[i].score;
      do { sorted[i].label ? tp++ : fp++; i++; } while(i<sorted.length && sorted[i].score===value);
      points.push(kind==='pr'?{x:tp/positives,y:tp/(tp+fp)}:{x:fp/negatives,y:tp/positives});
    }
    return points;
  }

  // Expose only pure functions for the independent Node test suite.
  if (typeof module !== 'undefined' && module.exports) module.exports = {esc,metrics,validateReport,rankingCurve};
  if (typeof document === 'undefined') return;

  const $ = id => document.getElementById(id);
  const pct = x => x == null ? '—' : (x*100).toFixed(1)+'%';
  const dec = x => x == null ? '—' : x.toFixed(3);
  const bundledReports={current:window.PATCHLENS_REPORT,...(window.PATCHLENS_EXTRA_REPORTS||{})};
  const corpusSelect=document.getElementById('corpus-select');
  corpusSelect.innerHTML=Object.entries(bundledReports).map(([id,r])=>`<option value="${esc(id)}">${esc(r.dataset.name||'Imported report')}</option>`).join('');
  corpusSelect.hidden=Object.keys(bundledReports).length<2;
  const state = {report:null,route:'overview',runId:'weighted',split:'test',threshold:null,pairId:null,query:'',cwe:'all',pointId:null};
  const routes = {
    benchmark:['Public benchmark','Test a real correction.','Inspect repository-disjoint Java contexts and the pretrained encoder study.'],
    overview:['Overview','Inspect every prediction.','Follow the evidence from a code change to a model decision.'],
    pairs:['Code pairs','Read the security boundary.','Compare the vulnerable example with its context-dependent correction.'],
    experiments:['Experiments','Compare the trade-offs.','Check misses and false alarms before choosing an operating point.'],
    embeddings:['Embedding atlas','Explore the representation.','A training-fitted PCA view of the actual model features.'],
    provenance:['Provenance','Keep the evidence.','Trace every result to its data, configuration and stated limits.'],
    tools:['Tool findings','Compare independent signals.','Inspect scanner evidence alongside model decisions and contextual labels.'],
    diagnostics:['Diagnostics','Look beyond the headline.','Inspect reliability, weakness-level errors and the effect of each correction.'],
    compare:['Model comparison','Find what actually changed.','Follow improved decisions, regressions and shared errors on identical examples.'],
    review:['Review notebook','Give each observation a place.','Keep your review status and notes alongside the source evidence.']
  };
  const activeRun = () => state.report.runs.find(r=>r.id===state.runId) || state.report.runs[0];
  const rows = () => state.report.samples.filter(s=>s.split===state.split);
  const predictions = (run=activeRun()) => new Map(run.predictions.map(p=>[p.id,p]));
  const threshold = () => state.threshold === null ? activeRun().threshold : state.threshold;
  const currentMetrics = () => metrics(rows(),predictions(),threshold());
  const panelHead = (title,subtitle,tag='') => `<div class="panel-head"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div>${tag?`<span class="panel-tag">${esc(tag)}</span>`:''}</div>`;
  const stat = (title,value,detail,accent=false) => `<div class="stat${accent?' accent':''}"><div class="stat-title">${esc(title)}</div><div class="stat-value">${esc(value)}</div><div class="stat-detail">${esc(detail)}</div></div>`;
  const pill = (label,kind='') => `<span class="pill ${kind}">${esc(label)}</span>`;
  let toastTimer;
  function toast(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,4000); }
  const workspace=window.PatchLensWorkspace.create({state,rows,activeRun,predictions,threshold,panelHead,stat,pill,toast,setRoute,validateReport,esc,dec,pct,routes});

  function lineChart(points,{xLabel='',yLabel='',unit=false,height=240}={}) {
    const width=560,l=44,r=18,t=18,b=42;
    if (!points.length) return '<p class="empty">No chart data.</p>';
    const xmax=unit?1:Math.max(...points.map(p=>p.x),1), ymax=unit?1:Math.max(...points.map(p=>p.y),.001)*1.08;
    const sx=x=>l+x/xmax*(width-l-r), sy=y=>height-b-y/ymax*(height-t-b);
    let grid='';
    for(let i=0;i<=4;i++) {
      const y=ymax*i/4,x=xmax*i/4;
      grid+=`<line class="grid" x1="${l}" x2="${width-r}" y1="${sy(y)}" y2="${sy(y)}"/><text x="${l-8}" y="${sy(y)+4}" text-anchor="end">${unit?Math.round(y*100)+'%':y.toFixed(1)}</text><text x="${sx(x)}" y="${height-b+19}" text-anchor="middle">${unit?Math.round(x*100)+'%':Math.round(x)}</text>`;
    }
    const path=points.map((p,i)=>(i?'L':'M')+sx(p.x).toFixed(2)+','+sy(p.y).toFixed(2)).join(' ');
    return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(yLabel+' by '+xLabel)}">${grid}<path class="line" d="${path}"/><text class="axis-title" x="${width/2}" y="${height-3}" text-anchor="middle">${esc(xLabel)}</text><text class="axis-title" x="${l}" y="11">${esc(yLabel)}</text></svg>`;
  }

  function matrix(m) {
    return `<div class="matrix">${[['True positives',m.tp,false],['False negatives',m.fn,true],['False positives',m.fp,true],['True negatives',m.tn,false]].map(([label,count,error])=>`<div class="matrix-cell${error?' error':''}"><strong>${count}</strong><span>${label}</span></div>`).join('')}</div><p class="matrix-caption">Positive = vulnerable · score ≥ ${dec(threshold())}<br>${m.tp+m.fn} vulnerable / ${m.tn+m.fp} corrected examples.</p>`;
  }

  function comparisonTable() {
    return `<div class="table-wrap"><table><thead><tr><th scope="col">Model / objective</th><th scope="col" class="num">F1</th><th scope="col" class="num">Recall</th><th scope="col" class="num">Misses</th><th scope="col" class="num">Alarms</th></tr></thead><tbody>${state.report.runs.map(run=>{
      const m=metrics(rows(),predictions(run),run.threshold);
      return `<tr${run.id===state.runId?' class="selected-row"':''}><td><button class="table-button" data-model="${esc(run.id)}"><span class="model-name">${esc(run.name)}</span><span class="model-note">λ ${esc(run.contrastive_weight)} · positive weight ${esc(run.positive_weight)}</span></button></td><td class="num">${dec(m.f1)}</td><td class="num">${pct(m.recall)}</td><td class="num">${m.fn}/${m.tp+m.fn}</td><td class="num">${m.fp}/${m.tn+m.fp}</td></tr>`;
    }).join('')}</tbody></table></div><p class="metric-foot">Each model uses its own validation-selected threshold. Counts expose the small sample size; a higher score here is not evidence of general security performance.</p>`;
  }

  function renderOverview() {
    const m=currentMetrics(),run=activeRun(),ps=predictions();
    const errors=rows().filter(s=>Number(ps.get(s.id).score>=threshold())!==s.label);
    $('view-overview').innerHTML=workspace.overviewSignal()+`<div class="stats-grid">${stat('F1 score',dec(m.f1),`${m.n} ${state.split} examples`,true)}${stat('Vulnerabilities missed',`${m.fn} / ${m.tp+m.fn}`,`False-negative rate ${pct(m.fnr)}`)}${stat('False alarms',`${m.fp} / ${m.tn+m.fp}`,`False-positive rate ${pct(m.fpr)}`)}${stat('Rename consistency',pct(m.agreement),`${m.flips} prediction flips after renaming`)}</div>
      <div class="grid-main"><div class="panel">${panelHead('Ablation comparison',`One dataset. ${state.report.runs.length} recorded models.`,state.split.toUpperCase())}${comparisonTable()}</div><div class="panel">${panelHead('Where the model is wrong','Raw counts at the selected operating point.')}${matrix(m)}</div></div>
      <div class="grid-main"><div class="panel">${panelHead('Training trace',run.name+(run.kind==='external'?' · imported training record':' · full-batch Adam'),'ACTUAL RUN')}<div class="chart">${lineChart(run.history.map(h=>({x:h.epoch,y:h.loss})),{xLabel:'Epoch',yLabel:'Total objective'})}</div><p class="metric-foot">Loss values come from the recorded training history. Different objectives have different scales.</p></div><div class="panel">${panelHead('Inspection queue',`${errors.length} misclassified examples in this split.`, 'OPEN A PAIR')}<div class="error-list">${errors.length?errors.slice(0,5).map(s=>`<button class="error-row" data-open-pair="${esc(s.pair_id)}"><span><strong>${esc(s.title)}</strong><small>${esc(s.cwe)} · score ${dec(ps.get(s.id).score)}</small></span>${pill(s.label?'Missed':'False alarm','risk')}</button>`).join(''):'<p class="empty">No errors at this operating point on these examples. This small result does not establish real-world reliability.</p>'}</div></div></div>`;
  }

  function highlight(line) {
    const rx=/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|\b(const|let|var|function|return|if|else|throw|new|typeof|async|await|true|false|null|public|private|protected|class|static|void|final|int|boolean|try|catch|throws|import|package)\b|\b(\d+)\b/g;
    let out='',last=0;
    for(const match of line.matchAll(rx)) {
      out+=esc(line.slice(last,match.index));
      out+=`<span class="token-${match[1]?'string':match[2]?'keyword':'number'}">${esc(match[0])}</span>`;
      last=match.index+match[0].length;
    }
    return out+esc(line.slice(last));
  }
  function codePanel(s,other) {
    const p=predictions().get(s.id),otherLines=new Set(other.code.split('\n').map(x=>x.trim()));
    return `<div class="code-panel"><div class="code-head"><strong>${s.label?'Vulnerable example':'Corrected under stated assumptions'}</strong><button class="copy" data-copy="${esc(s.id)}" aria-label="Copy ${s.label?'vulnerable':'corrected'} example">Copy</button></div><pre aria-label="${esc(s.id)}"><code>${s.code.split('\n').map((line,i)=>`<span class="code-line${otherLines.has(line.trim())?'':' line-change '+(s.label?'before':'after')}"><span class="line-no" aria-hidden="true">${i+1}</span>${highlight(line)}</span>`).join('')}</code></pre><div class="code-score"><span>Vulnerability score <strong>${dec(p.score)}</strong></span><span>${p.score>=threshold()?'Flagged':'Not flagged'}</span></div></div>`;
  }
  function filteredPairs() {
    return rows().filter(s=>s.label===1 && (state.cwe==='all'||s.cwe===state.cwe) && (s.title+' '+s.cwe+' '+s.code+' '+s.pair_id).toLowerCase().includes(state.query.toLowerCase()));
  }
  function renderPairs(rebuild=true) {
    if(rebuild) $('view-pairs').innerHTML=`<div class="pair-layout"><aside class="panel pair-library"><label for="pair-search" class="micro-label">FIND A CODE PAIR</label><input id="pair-search" class="search" placeholder="Search code or title…" value="${esc(state.query)}"><div class="pair-filters"><select id="cwe-filter" aria-label="Weakness category"><option value="all">All weaknesses</option>${[...new Set(state.report.samples.map(s=>s.cwe))].sort().map(c=>`<option value="${esc(c)}"${state.cwe===c?' selected':''}>${esc(c)}</option>`).join('')}</select></div><div class="pair-list" id="pair-list"></div></aside><div class="pair-detail" id="pair-detail"></div></div>`;
    const pairs=filteredPairs();
    if(!pairs.some(s=>s.pair_id===state.pairId)) state.pairId=pairs[0]?.pair_id || null;
    $('pair-list').innerHTML=pairs.length?pairs.map(s=>`<button class="pair-option${s.pair_id===state.pairId?' selected':''}" data-pair="${esc(s.pair_id)}" aria-pressed="${s.pair_id===state.pairId}"><strong>${esc(s.title)}</strong><small>${esc(s.cwe)} · ${esc(s.split)}</small></button>`).join(''):'<p class="empty">No matching pairs in this split.</p>';
    const before=pairs.find(s=>s.pair_id===state.pairId);
    if(!before) { $('pair-detail').innerHTML='<div class="panel empty">Change the search, category or evaluation split to inspect a pair.</div>';return; }
    const after=state.report.samples.find(s=>s.pair_id===before.pair_id && !s.label);
    $('pair-detail').innerHTML=`<div class="pair-heading"><div><h2>${esc(before.title)}</h2><p>${esc(before.pair_id)} · ${esc(before.group_id)}</p></div>${pill(before.cwe)}</div><div class="code-grid">${codePanel(before,after)}${codePanel(after,before)}</div><div class="panel rationale"><h3>Why the boundary changes</h3><p>${esc(after.rationale)}</p><h3>Assumptions that matter</h3><p>${esc(after.assumptions)}</p><h3>Stored view</h3><p>${state.report.dataset.view_kind==='identity'?'Public contexts use an identity view. No renaming or augmentation robustness was measured.':'The authored view renames the local input parameter; stability uses its actual prediction.'} Highlights mark lines absent from the counterpart; this is not a semantic diff.</p>${/^https:\/\/github\.com\//.test(before.source)?`<p><a class="source-link" href="${esc(before.source)}" target="_blank" rel="noopener noreferrer">Open the original correction on GitHub ↗</a></p>`:''}<div class="pair-meta">${pill(before.review_status,'neutral')}${pill(before.licence,'neutral')}</div></div>`;
  }

  function renderExperiments() {
    const m=currentMetrics(),run=activeRun(),ps=predictions();
    $('view-experiments').innerHTML=`<div class="panel threshold-panel"><div class="threshold-copy"><h2>Explore the operating point</h2><p>${state.threshold===null?'Using the stored validation-selected threshold.':'Exploratory threshold override. This does not change the saved experiment.'}</p></div><div class="threshold-control"><input id="threshold-slider" aria-label="Exploratory classification threshold" type="range" min="0" max="1" step="0.005" value="${threshold()}"><output class="threshold-value" for="threshold-slider">${dec(threshold())}</output></div><button class="small-button" data-reset-threshold>Reset</button></div>
      <div class="stats-grid">${stat('Precision',pct(m.precision),'Vulnerable among flagged',true)}${stat('Recall',pct(m.recall),'Flagged among vulnerable')}${stat('False-negative rate',pct(m.fnr),`${m.fn} missed / ${m.fn+m.tp} vulnerable`)}${stat('False-positive rate',pct(m.fpr),`${m.fp} alarms / ${m.fp+m.tn} corrected`)}</div>
      <div class="grid-equal"><div class="panel">${panelHead('Precision–recall curve','All observed score thresholds; tied scores move together.')}<div class="chart">${lineChart(rankingCurve(rows(),ps,'pr'),{xLabel:'Recall',yLabel:'Precision',unit:true})}</div></div><div class="panel">${panelHead('ROC curve','Ranking behavior on the selected split.')}<div class="chart">${lineChart(rankingCurve(rows(),ps,'roc'),{xLabel:'False-positive rate',yLabel:'True-positive rate',unit:true})}</div></div></div>
      <div class="grid-main"><div class="panel">${panelHead('Controlled comparison','Stored validation operating points; unaffected by the slider.')}${comparisonTable()}</div><div class="panel">${panelHead(state.report.dataset.view_kind==='identity'?'Augmentation status':'Renaming stability',state.report.dataset.view_kind==='identity'?'Public contexts retain the original code as their stored view.':'Same code behavior under the authored assumptions.')}<div class="detail-figure">${state.report.dataset.view_kind==='identity'?'Not measured':pct(m.agreement)}</div><div class="detail-caption">${state.report.dataset.view_kind==='identity'?'Identity inputs · no augmentation experiment':'Prediction agreement across original / renamed views'}</div><dl class="key-values"><div class="kv-row"><dt>Both correct</dt><dd>${pct(m.both_correct)}</dd></div><div class="kv-row"><dt>Mean score shift</dt><dd>${dec(m.mean_score_shift)}</dd></div><div class="kv-row"><dt>Validation FPR ceiling</dt><dd>${pct(run.operating_point.max_fpr)}</dd></div></dl><p class="note-line">Agreement can include two wrong predictions. The validation ceiling is not a guarantee on the test split.</p></div></div>`;
  }

  function renderEmbeddings() {
    const run=activeRun(),selected=new Map(rows().map(s=>[s.id,s])),ps=predictions();
    if(run.projection.method==='not_available') {
      $('view-embeddings').innerHTML=`<div class="panel">${panelHead('Representations not supplied',run.name)}<p class="empty">This imported model supplied real scores but no embeddings. There is no projection to display.</p></div>`;return;
    }
    const points=run.projection.points.filter(p=>selected.has(p.id));
    const all=run.projection.points,width=660,height=380,l=46,r=24,t=24,b=43;
    let xmin=Math.min(...all.map(p=>p.x)),xmax=Math.max(...all.map(p=>p.x)),ymin=Math.min(...all.map(p=>p.y)),ymax=Math.max(...all.map(p=>p.y));
    const dx=(xmax-xmin||1)*.12,dy=(ymax-ymin||1)*.12;xmin-=dx;xmax+=dx;ymin-=dy;ymax+=dy;
    const sx=x=>l+(x-xmin)/(xmax-xmin)*(width-l-r),sy=y=>height-b-(y-ymin)/(ymax-ymin)*(height-t-b);
    let grid='';
    for(let i=0;i<=4;i++) {
      const x=xmin+(xmax-xmin)*i/4,y=ymin+(ymax-ymin)*i/4;
      grid+=`<line class="grid" x1="${l}" x2="${width-r}" y1="${sy(y)}" y2="${sy(y)}"/><text x="${l-8}" y="${sy(y)+4}" text-anchor="end">${y.toFixed(2)}</text><text x="${sx(x)}" y="${height-b+20}" text-anchor="middle">${x.toFixed(2)}</text>`;
    }
    if(!selected.has(state.pointId))state.pointId=points[0]?.id;
    const sample=selected.get(state.pointId),p=sample?ps.get(sample.id):null;
    const glyphs=points.map(p=>{const s=selected.get(p.id);return `<circle class="scatter-point" cx="${sx(p.x)}" cy="${sy(p.y)}" r="${s.id===state.pointId?8:6}" fill="${s.label?'var(--danger)':'var(--teal)'}" data-point="${esc(p.id)}" tabindex="0" role="button" aria-label="${esc(s.title+(s.label?', vulnerable':', corrected'))}"><title>${esc(s.title+' · '+s.cwe)}</title></circle>`;}).join('');
    $('view-embeddings').innerHTML=`<div class="embedding-layout"><div class="panel">${panelHead('Representation atlas',run.name+' · PCA fitted on training examples',state.split.toUpperCase())}<div class="legend"><span><i class="risk"></i>Vulnerable</span><span><i></i>Corrected under assumptions</span></div><div class="chart embedding-chart"><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Interactive PCA representation plot">${grid}${glyphs}<text class="axis-title" x="${width/2}" y="${height-3}" text-anchor="middle">Principal component 1</text><text class="axis-title" x="${l}" y="13">Principal component 2</text></svg></div><p class="note-line">Projection is descriptive. Two dimensions can hide structure; separation here does not demonstrate generalization. Axes stay fixed when switching the split.</p></div><div class="panel point-inspector">${panelHead('Point inspector','Select a point or use Tab and Enter.')}${sample?`<h3>${esc(sample.title)}</h3><div class="pair-meta">${pill(sample.cwe)}${pill(sample.label?'Vulnerable':'Corrected',sample.label?'risk':'')}</div><dl><dt>Example</dt><dd>${esc(sample.id)}</dd><dt>Vulnerability score</dt><dd>${dec(p.score)}</dd><dt>Decision at ${dec(threshold())}</dt><dd>${p.score>=threshold()?'Flagged':'Not flagged'}</dd><dt>Group</dt><dd>${esc(sample.group_id)}</dd></dl><button class="button" data-open-pair="${esc(sample.pair_id)}">Inspect code pair ↗</button>`:'<p>No points in this split.</p>'}</div></div>`;
  }

  function renderProvenance() {
    const r=state.report,run=activeRun(),groups=new Set(r.samples.map(s=>s.group_id)),pairCount=new Set(r.samples.map(s=>s.pair_id)).size;
    const kv=(k,v,hash=false)=>`<div class="kv-row"><dt>${esc(k)}</dt><dd${hash?' class="hash"':''}>${esc(v)}</dd></div>`;
    $('view-provenance').innerHTML=`<div class="stats-grid">${stat('Source examples',r.samples.length,`${pairCount} vulnerable / corrected pairs`,true)}${stat('Independent groups',groups.size,'Split boundary checked by group ID')}${stat('Weakness categories',new Set(r.samples.map(s=>s.cwe)).size,'Context-dependent binary labels')}${stat('Training seed',r.config.seed,'Deterministic within the recorded environment')}</div>
      <div class="grid-equal"><div class="panel">${panelHead('Dataset identity','Review the source and assumptions before reusing labels.')}<dl class="key-values">${kv('Dataset',r.dataset.name||'User supplied')}${kv('Scope',r.dataset.scope||'User supplied')}${kv('Samples by split',['train','validation','test'].map(split=>split+': '+r.samples.filter(s=>s.split===split).length).join(' · '))}${kv('SHA-256',r.dataset.fingerprint,true)}${kv('Sources',[...new Set(r.samples.map(s=>s.source))].join(', '))}${kv('Label review',[...new Set(r.samples.map(s=>s.review_status))].join(', '))}</dl></div><div class="panel">${panelHead('Run identity','The report preserves predictions, scores and configuration.')}<dl class="key-values">${kv('Experiment',r.experiment_id,true)}${kv('Created',r.created_at||'Not recorded')}${kv('Python / NumPy',r.environment.python+' / '+r.environment.numpy)}${kv('Epochs / seed',r.config.epochs+' / '+r.config.seed)}${kv('Threshold source',run.operating_point.source_split)}${kv('Predictions SHA-256',run.predictions_sha256||'Not recorded',true)}${kv('Static analysis',r.static_analysis?.status==='not_run'?'Not run — no scanner findings are claimed':r.static_analysis?.status||'Not recorded')}</dl></div></div>
      <div class="grid-equal"><div class="panel">${panelHead('Audit contract','These checks belong to the Python data audit.')}<ul class="checklist"><li>Unique identifiers and complete binary pairs</li><li>Group-disjoint train, validation and test splits</li><li>Whitespace-normalized exact duplicate leakage checks</li><li>Vocabulary and IDF fitted on training data only</li><li>Threshold chosen on validation, then frozen for test</li></ul><p class="note-line">Report import validates structure and coverage. It does not independently rerun the Python audit or authenticate the supplied hashes.</p></div><div class="panel">${panelHead('Interpretation limits','Make uncertainty part of the result.')}<ul>${r.limitations.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p class="note-line">The snippets are displayed as text. This workbench makes no network requests and does not execute, upload or repair imported code.</p></div></div>`;
  }

  function renderTools() {
    const scan=state.report.static_analysis||{status:'not_run',findings:[]};
    const labels={not_run:'Not run',failed:'Failed',completed_with_errors:'Completed with errors',completed:'Completed'};
    const selected=rows(),ids=new Set(selected.map(s=>s.id)),ps=predictions();
    const findings=scan.findings.filter(f=>ids.has(f.example_id));
    const flagged=new Set(findings.map(f=>f.example_id));
    const disagreements=selected.filter(s=>flagged.has(s.id)!==(ps.get(s.id).score>=threshold()));
    const toolNames=(scan.tools||[]).map(t=>String(t.name)+' '+String(t.version||'')).join(' · ');
    $('view-tools').innerHTML=`<div class="stats-grid">${stat('Scanner status',labels[scan.status]||'Not recorded',toolNames||'No completed scanner claimed',scan.status==='completed')}${stat('Reported findings',findings.length,'Selected evaluation split')}${stat('Examples with a finding',flagged.size,'A review signal, not a verdict')}${stat('Signal disagreements',scan.status==='completed'?disagreements.length:'—','Model decision versus reported finding')}</div>
      <div class="panel tool-explainer"><h2>Keep silence separate from evidence</h2><p>${scan.status==='not_run'?'No scanner has been run for this report. Import a report with an attached scan to inspect its findings.':scan.status==='failed'?'The scanner failed. Findings, if present, are partial and cannot establish absence of vulnerabilities.':'A reported finding and a model score answer different questions. Review the rule, source and assumptions before drawing a conclusion.'}</p><p class="note-line">${esc(scan.meaning||'No finding is not proof of secure code.')} ${esc(typeof scan.coverage==='string'?scan.coverage:'Coverage details are retained in the exported JSON.')}</p></div>
      <div class="grid-main"><div class="panel">${panelHead('Findings ledger','Open a finding to inspect its code pair.',state.split.toUpperCase())}<div class="tool-findings">${findings.length?findings.map(f=>{const s=selected.find(s=>s.id===f.example_id);return `<button class="finding-row" data-open-pair="${esc(s.pair_id)}"><span class="finding-marker">${esc(f.severity)}</span><span><strong>${esc(s.title)}</strong><small>${esc(f.rule)} · line ${f.line}</small><p>${esc(f.message)}</p><small>${s.label?'Label: vulnerable':'Label: corrected under assumptions'} · model score ${dec(ps.get(s.id).score)}</small></span><span aria-hidden="true">↗</span></button>`;}).join(''):'<p class="empty">No findings recorded for this split. Check scan status and coverage before interpreting this.</p>'}</div></div>
      <div class="panel">${panelHead('Review queue','Examples where the two signals differ.')}<div class="error-list">${scan.status==='completed'?disagreements.slice(0,20).map(s=>`<button class="error-row" data-open-pair="${esc(s.pair_id)}"><span><strong>${esc(s.title)}</strong><small>${flagged.has(s.id)?'Scanner finding / model not flagged':'Model flagged / no scanner finding'}</small></span>↗</button>`).join('')||'<p class="empty">Signals agree on these examples. Agreement is not a correctness guarantee.</p>':'<p class="empty">Complete the scan before using this comparison.</p>'}</div><p class="note-line">Raw errors and unmapped locations, when present, remain in the JSON export for investigation.</p></div></div>`;
  }

  function render() {
    const route=routes[state.route],run=activeRun();
    $('route-label').textContent=route[0];$('page-title').textContent=route[1];$('page-description').textContent=route[2];
    $('experiment-id').textContent=state.report.experiment_id;$('version').textContent=state.report.version;
    $('model-select').value=run.id;$('split-select').value=state.split;
    $('model-select').closest('.select-group').hidden=['compare','review'].includes(state.route);
    document.querySelectorAll('[data-route]').forEach(el=>{const active=el.dataset.route===state.route;el.classList.toggle('active',active);if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
    document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!=='view-'+state.route);
    const notice=$('notice');notice.hidden=state.threshold===null;
    notice.textContent=`Exploratory threshold ${dec(threshold())}. The saved experiment still uses validation threshold ${dec(run.threshold)}. Reset it in Experiments before interpreting the original operating point.`;
    ({benchmark:()=>{$('view-benchmark').innerHTML=window.PatchLensBenchmark.render(state.report,{esc,pct,dec,panelHead,stat});},overview:renderOverview,pairs:renderPairs,experiments:renderExperiments,embeddings:renderEmbeddings,provenance:renderProvenance,tools:renderTools,...workspace.renderers}[state.route])();
  }
  function setRoute(route) {state.route=routes[route]?route:'overview';render();}
  function load(report) {
    state.report=validateReport(report);state.runId=report.runs.some(r=>r.id==='codebert')?'codebert':report.runs.some(r=>r.id==='weighted')?'weighted':report.runs[0].id;
    state.threshold=null;state.pairId=null;state.pointId=null;state.cwe='all';state.query='';
    $('model-select').innerHTML=report.runs.map(r=>`<option value="${esc(r.id)}">${esc(r.name)}</option>`).join('');
    $('pair-count').textContent=new Set(report.samples.map(s=>s.pair_id)).size;
    document.querySelector('.fixture-badge').textContent=report.dataset.kind==='public_patch_context'?'Real Java corrections · Vul4J':report.samples.every(s=>s.source.startsWith('authored:'))?'Authored fixture experiment':'Imported research experiment';
    $('dataset-footer').textContent=report.dataset.kind==='public_patch_context'?'Real patch contexts · repository-disjoint study':'Authored / imported examples · pipeline validation';
    workspace.onLoad();
    render();
  }
  document.addEventListener('click',async event=>{
    const el=event.target.closest('button,[data-point]');if(!el||!state.report)return;
    if(el.dataset.route) {location.hash=el.dataset.route;setRoute(el.dataset.route);}
    if(el.dataset.model) {state.runId=el.dataset.model;state.threshold=null;render();}
    if(el.dataset.pair) {state.pairId=el.dataset.pair;renderPairs(false);}
    if(el.dataset.openPair) {state.pairId=el.dataset.openPair;state.query='';state.cwe='all';location.hash='pairs';setRoute('pairs');}
    if(el.dataset.point) {state.pointId=el.dataset.point;renderEmbeddings();document.querySelector(`[data-point="${state.pointId}"]`)?.focus();}
    if(el.hasAttribute('data-reset-threshold')) {state.threshold=null;render();}
    if(el.dataset.copy) {
      const sample=state.report.samples.find(s=>s.id===el.dataset.copy);
      try {if(!navigator.clipboard)throw new Error('clipboard unavailable');await navigator.clipboard.writeText(sample.code);toast('Example copied.');}
      catch {toast('Clipboard access is unavailable here. Select the code and copy it manually.');}
    }
  });
  document.addEventListener('keydown',event=>{if(event.target.matches('[data-point]') && ['Enter',' '].includes(event.key)){event.preventDefault();event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
  document.addEventListener('input',event=>{
    if(event.target.id==='pair-search'){state.query=event.target.value;renderPairs(false);}
    if(event.target.id==='threshold-slider'){state.threshold=Number(event.target.value);document.querySelector('output[for="threshold-slider"]').textContent=dec(state.threshold);}
  });
  document.addEventListener('change',event=>{
    if(event.target.id==='threshold-slider'){render();$('threshold-slider').focus();}
    if(event.target.id==='model-select'){state.runId=event.target.value;state.threshold=null;render();}
    if(event.target.id==='split-select'){state.split=event.target.value;state.pairId=null;state.pointId=null;render();}
    if(event.target.id==='cwe-filter'){state.cwe=event.target.value;renderPairs(false);}
  });
  corpusSelect.addEventListener('change',()=>{load(bundledReports[corpusSelect.value]);try{localStorage.setItem('patchlens-corpus',corpusSelect.value);}catch{}});
  $('import-button').addEventListener('click',()=>$('import-file').click());
  $('import-file').addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    try {if(file.size>20*1024*1024)throw new Error('Report limit is 20 MiB.');const report=JSON.parse(await file.text());validateReport(report);bundledReports.imported=report;if(!corpusSelect.querySelector('[value="imported"]'))corpusSelect.add(new Option('Imported report','imported'));corpusSelect.hidden=false;corpusSelect.value='imported';load(report);toast('Report loaded locally. No data was uploaded.');}
    catch(error){toast(error.message);}finally{event.target.value='';}
  });
  $('export-button').addEventListener('click',()=>{
    if(!state.report)return;const blob=new Blob([JSON.stringify(state.report,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download='patchlens-'+state.report.experiment_id+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Original report exported. Exploratory slider changes are not saved.');
  });
  function setTheme(theme){document.documentElement.dataset.theme=theme;$('theme-toggle').setAttribute('aria-label',theme==='dark'?'Switch to light appearance':'Switch to dark appearance');try{localStorage.setItem('patchlens-theme',theme);}catch{}}
  try{setTheme(localStorage.getItem('patchlens-theme')==='dark'?'dark':'light');}catch{setTheme('light');}
  $('theme-toggle').addEventListener('click',()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
  window.addEventListener('hashchange',()=>{
    const requested=location.hash.slice(1),next=routes[requested]?requested:'overview';
    // Buttons render immediately; their later hash event must not reset form input.
    if(state.report&&state.route!==next)setRoute(next);
  });
  state.route=routes[location.hash.slice(1)]?location.hash.slice(1):'overview';
  let initialCorpus='current';try{const saved=localStorage.getItem('patchlens-corpus');if(bundledReports[saved])initialCorpus=saved;}catch{}
  corpusSelect.value=initialCorpus;
  try{load(bundledReports[initialCorpus]);}catch(error){$('notice').hidden=false;$('notice').textContent=error.message+' Import a PatchLens report.json to begin.';$('experiment-id').textContent='No valid report loaded';}
})();
