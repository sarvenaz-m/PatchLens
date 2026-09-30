/* Interaction layer for diagnostics, comparison and dataset-scoped review notes. */
(function () {
  'use strict';
  window.PatchLensWorkspace = {create(api) {
    const {state,rows,activeRun,predictions,threshold,panelHead,stat,pill,toast,setRoute,validateReport,esc,dec,pct}=api;
    const A=window.PatchLensAnalysis,$=id=>document.getElementById(id);
    let comparisonReport=null,baselineId='linear',candidateId='weighted',reviewEntries=Object.create(null),reviewDrafts=Object.create(null),reviewId=null,reviewFilter='all',reviewQuery='';
    const statuses={unreviewed:'Not reviewed',needs_attention:'Needs attention',reviewed:'Reviewed'};
    const storageKey=()=> 'patchlens-review:'+state.report.dataset.fingerprint;
    const options=(report,id)=>report.runs.map(r=>`<option value="${esc(r.id)}"${r.id===id?' selected':''}>${esc(r.name)}</option>`).join('');
    const download=(name,payload,type='application/json')=>{
      const url=URL.createObjectURL(new Blob([type==='application/json'?JSON.stringify(payload,null,2):payload],{type}));
      const link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    };
    const reviewCount=()=>{$('review-count').textContent=Object.values(reviewEntries).filter(e=>e.status==='reviewed').length;};
    function persistReview() {
      reviewCount();
      try {localStorage.setItem(storageKey(),JSON.stringify(A.reviewBundle(state.report,reviewEntries)));return true;}
      catch {return false;}
    }
    function onLoad() {
      comparisonReport=null;baselineId=state.report.runs[0].id;candidateId=activeRun().id;reviewId=null;reviewFilter='all';reviewQuery='';reviewEntries=Object.create(null);reviewDrafts=Object.create(null);
      try {const saved=localStorage.getItem(storageKey());if(saved)reviewEntries=A.validateReview(JSON.parse(saved),state.report);} catch {toast('Saved notes could not be loaded. Import a review backup if needed.');}
      reviewCount();
    }
    function overviewSignal() {
      const selected=rows(),p=predictions(),m=A.summary(selected,p,threshold());
      const cells=selected.slice(0,60).map(s=>{const correct=Number(p.get(s.id).score>=threshold())===s.label;return `<button class="evidence-cell ${correct?'correct':'incorrect'}" data-open-pair="${esc(s.pair_id)}" aria-label="${esc(s.title+' · '+(correct?'correct decision':'model error'))}" title="${esc(s.title)}">${correct?'✓':'!'}</button>`;}).join('');
      return `<div class="studio-hero"><div class="hero-copy"><span class="hero-kicker">THE EXPERIMENT, AT A GLANCE</span><h2>From a score<br>to the source.</h2><p>${selected.length} examples. ${new Set(selected.map(s=>s.cwe)).size} weakness categories.<br>Every decision has a code pair behind it.</p><div class="hero-actions"><button class="button primary" data-route="diagnostics">Explore diagnostics <span>↗</span></button><button class="hero-link" data-route="compare">Compare models →</button></div></div><div class="hero-evidence"><div class="hero-evidence-heading"><span>DECISION MAP</span><span>${m.tp+m.tn} / ${m.n} correct</span></div><div class="evidence-map">${cells}</div><div class="hero-legend"><span><i></i>Correct at selected threshold</span><span><i class="error"></i>Open an error</span></div><p>${selected.length>60?'First 60 examples':'One tile per example'} · ${esc(state.split)} split</p></div></div>`;
    }
    function reliabilityChart(m) {
      const x=v=>48+v*420,y=v=>244-v*206;
      let grid='';for(let i=0;i<=4;i++)grid+=`<line class="grid" x1="48" x2="468" y1="${y(i/4)}" y2="${y(i/4)}"/><text x="36" y="${y(i/4)+4}" text-anchor="end">${i*25}%</text><text x="${x(i/4)}" y="265" text-anchor="middle">${i*25}%</text>`;
      const dots=m.bins.filter(b=>b.n).map(b=>`<g><line class="confidence-line" x1="${x(b.mean_score)}" x2="${x(b.mean_score)}" y1="${y(b.observed_wilson_95[0])}" y2="${y(b.observed_wilson_95[1])}"/><circle cx="${x(b.mean_score)}" cy="${y(b.observed_rate)}" r="${5+Math.sqrt(b.n)}" class="calibration-dot"><title>n=${b.n}; mean score ${dec(b.mean_score)}; observed ${pct(b.observed_rate)}</title></circle></g>`).join('');
      return `<svg viewBox="0 0 500 292" role="img" aria-label="Mean vulnerability score versus observed vulnerable fraction, with 95 percent Wilson intervals">${grid}<path class="reference-line" d="M48 244 L468 38"/>${dots}<text class="axis-title" x="250" y="287" text-anchor="middle">Mean vulnerability score</text><text class="axis-title" x="48" y="19">Observed vulnerable fraction</text></svg>`;
    }
    function scoreHistogram() {
      const selected=rows(),p=predictions(),buckets=Array.from({length:10},()=>[0,0]);
      for(const s of selected)buckets[Math.min(9,Math.floor(p.get(s.id).score*10))][s.label]++;
      const max=Math.max(1,...buckets.flat());
      return `<div class="histogram" role="img" aria-label="Score distribution in ten equal-width bins; corrected in teal and vulnerable in coral">${buckets.map((b,i)=>`<div class="histogram-bin"><div class="histogram-bars"><span style="height:${b[0]/max*100}%" title="${b[0]} corrected"></span><span class="vulnerable" style="height:${b[1]/max*100}%" title="${b[1]} vulnerable"></span></div><small>${(i/10).toFixed(1)}</small></div>`).join('')}</div><div class="legend"><span><i></i>Corrected under assumptions</span><span><i class="risk"></i>Vulnerable</span></div>`;
    }
    function diagnostics() {
      const p=predictions(),selected=rows(),m=A.summary(selected,p,threshold()),slices=A.slices(selected,p,threshold()),margins=A.pairMargins(selected,p);
      $('view-diagnostics').innerHTML=`<div class="stats-grid">${stat('Balanced accuracy',pct(m.balanced_accuracy),'Equal weight to both classes',true)}${stat('Matthews correlation',dec(m.mcc),'−1 to +1 · undefined if degenerate')}${stat('Brier score',dec(m.brier),'Mean squared score error · lower is better')}${stat('Calibration gap',pct(m.ece),'ECE · 10 equal-width bins')}</div><div class="grid-equal"><div class="panel">${panelHead('Score reliability','Occupied bins with 95% Wilson intervals.','DESCRIPTIVE')}<div class="chart">${reliabilityChart(m)}</div><p class="metric-foot">The dashed diagonal is the ideal reference. Sparse bins have wide uncertainty; these results do not establish probability calibration.</p></div><div class="panel">${panelHead('Score distribution','Where the two contextual classes overlap.',state.split.toUpperCase())}${scoreHistogram()}<div class="distribution-summary"><div><span>Log loss</span><strong>${dec(m.log_loss)}</strong></div><div><span>Operating threshold</span><strong>${dec(threshold())}</strong></div></div><p class="metric-foot">Scores are model outputs. A low score is not a security verdict.</p></div></div><div class="panel section-panel">${panelHead('Weakness-level diagnostics','Counts and uncertainty stay visible for every slice.','CWE SLICES')}<div class="table-wrap"><table><thead><tr><th>Weakness</th><th class="num">Examples</th><th class="num">F1</th><th class="num">Misses</th><th class="num">Alarms</th><th>Miss rate · 95% interval</th></tr></thead><tbody>${slices.map(s=>`<tr><td><button class="table-button cwe-button" data-cwe-open="${esc(s.cwe)}">${esc(s.cwe)} ↗</button></td><td class="num">${s.n}</td><td class="num">${dec(s.f1)}</td><td class="num">${s.fn}/${s.fn+s.tp}</td><td class="num">${s.fp}/${s.fp+s.tn}</td><td><div class="interval-track"><span style="left:${s.fnr_wilson_95[0]*100}%;width:${(s.fnr_wilson_95[1]-s.fnr_wilson_95[0])*100}%"></span><i style="left:${s.fnr*100}%"></i></div><small class="interval-label">${pct(s.fnr_wilson_95[0])}–${pct(s.fnr_wilson_95[1])}</small></td></tr>`).join('')}</tbody></table></div></div><div class="panel section-panel">${panelHead('Does the correction move the score?','Vulnerable score minus corrected score; smallest margins first.',`${margins.filter(m=>m.margin>0).length}/${margins.length} EXPECTED ORDER`)}<div class="margin-list">${margins.map(m=>`<button class="margin-row" data-open-pair="${esc(m.pair_id)}"><span><strong>${esc(m.title)}</strong><small>${esc(m.cwe)}</small></span><span class="dumbbell"><span style="left:${Math.min(m.before,m.after)*100}%;width:${Math.abs(m.margin)*100}%"></span><i style="left:${m.after*100}%" title="Corrected: ${dec(m.after)}"></i><i class="before" style="left:${m.before*100}%" title="Vulnerable: ${dec(m.before)}"></i></span><strong class="${m.margin<=0?'text-danger':''}">${m.margin>0?'+':''}${m.margin!==0&&Math.abs(m.margin)<.0005?m.margin.toExponential(1):dec(m.margin)}</strong></button>`).join('')}</div><p class="metric-foot">Teal = corrected; coral = vulnerable. Score ordering and classification correctness are separate checks.</p></div>`;
    }
    function comparisonData() {
      const report=comparisonReport||state.report;
      const a=state.report.runs.find(r=>r.id===baselineId)||state.report.runs[0];
      const b=report.runs.find(r=>r.id===candidateId)||report.runs[0];
      baselineId=a.id;candidateId=b.id;
      return {a,b,report,...A.compare(rows(),a,b)};
    }
    function compare() {
      const c=comparisonData(),labels={improved:'Improved',regressed:'Regressed',both_correct:'Both correct',both_wrong:'Both wrong'};
      const changed=c.changes.filter(s=>s.outcome!=='both_correct');
      $('view-compare').innerHTML=`<div class="comparison-selectors panel"><div><label for="baseline-select" class="micro-label">BASELINE · CURRENT REPORT</label><select id="baseline-select">${options(state.report,c.a.id)}</select><small>${esc(state.report.experiment_id)}</small></div><span class="compare-arrow" aria-hidden="true">→</span><div><label for="candidate-select" class="micro-label">CANDIDATE · ${comparisonReport?'IMPORTED':'CURRENT'} REPORT</label><select id="candidate-select">${options(c.report,c.b.id)}</select><small>${esc(c.report.experiment_id)}</small></div><div class="comparison-actions"><button class="button" id="comparison-import">Import candidate report</button>${comparisonReport?'<button class="subtle-link" id="comparison-reset">Use current report</button>':''}</div></div><div class="stats-grid">${stat('Accuracy difference',`${c.accuracy_delta>=0?'+':''}${(c.accuracy_delta*100).toFixed(1)} pp`,'Candidate minus baseline',true)}${stat('Improved decisions',c.outcomes.improved,'Baseline wrong → candidate correct')}${stat('Regressed decisions',c.outcomes.regressed,'Baseline correct → candidate wrong')}${stat('Errors in both',c.outcomes.both_wrong,'Shared failures deserve inspection')}</div><div class="grid-equal"><div class="panel">${panelHead('The comparison contract','Same examples. Independent stored thresholds.','PAIRED')}<dl class="key-values"><div class="kv-row"><dt>Dataset</dt><dd>${rows().length} identical examples · ${esc(state.split)}</dd></div><div class="kv-row"><dt>Baseline threshold</dt><dd>${dec(c.a.threshold)} · selected on validation</dd></div><div class="kv-row"><dt>Candidate threshold</dt><dd>${dec(c.b.threshold)} · selected on validation</dd></div><div class="kv-row"><dt>Source verification</dt><dd>IDs, code, labels, groups and split assignments match</dd></div></dl><p class="metric-foot">The exploratory threshold slider does not change this comparison. Import a matched report to compare another seed or external model.</p></div><div class="panel">${panelHead('Metric movement','Read gains alongside regressions.')}<div class="table-wrap"><table><thead><tr><th>Metric</th><th class="num">Baseline</th><th class="num">Candidate</th></tr></thead><tbody>${[['F1','f1'],['Recall','recall'],['False-positive rate','fpr'],['Balanced accuracy','balanced_accuracy'],['Brier score','brier']].map(([label,key])=>`<tr><td>${label}</td><td class="num">${dec(c.baseline[key])}</td><td class="num"><strong>${dec(c.candidate[key])}</strong></td></tr>`).join('')}</tbody></table></div><p class="metric-foot">One authored test set cannot establish general superiority. The CLI comparison adds a paired bootstrap by group.</p></div></div><div class="panel"><div class="panel-head"><div><h2>Changed decisions & shared errors</h2><p>All ${rows().length} examples are included in the CSV export.</p></div><button class="small-button" id="comparison-csv">Export CSV ↗</button></div>${changed.length?`<div class="table-wrap"><table><thead><tr><th>Example</th><th>Outcome</th><th class="num">Baseline score</th><th class="num">Candidate score</th></tr></thead><tbody>${changed.map(s=>`<tr><td><button class="table-button" data-open-pair="${esc(s.pair_id)}">${esc(s.title)} ↗</button><small class="table-subtitle">${esc(s.cwe)} · ${s.label?'vulnerable':'corrected'}</small></td><td>${pill(labels[s.outcome],s.outcome==='regressed'||s.outcome==='both_wrong'?'risk':'')}</td><td class="num">${dec(s.baseline_score)}</td><td class="num">${dec(s.candidate_score)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="empty">Both models correctly classify every example in this split.</p>'}</div>`;
    }
    function review(rebuild=true) {
      if(rebuild)$('view-review').innerHTML=`<div class="review-toolbar panel"><div><h2>A notebook beside the evidence.</h2><p>Dataset-scoped notes stay in this browser. Export a backup to keep or transfer them.</p></div><div><button class="button" id="review-import">Import notes</button><button class="button primary" id="review-export">Export notes ↗</button></div></div><div class="review-layout"><aside class="panel review-list-panel"><label for="review-search" class="micro-label">FIND AN EXAMPLE</label><input id="review-search" class="search" placeholder="Search title, ID or CWE…" value="${esc(reviewQuery)}"><label class="sr-only" for="review-filter">Review status</label><select id="review-filter"><option value="all">All statuses</option>${Object.entries(statuses).map(([k,v])=>`<option value="${k}"${reviewFilter===k?' selected':''}>${v}</option>`).join('')}</select><div id="review-list"></div></aside><div id="review-detail"></div></div>`;
      const selected=rows().filter(s=>(reviewFilter==='all'||(reviewEntries[s.id]?.status||'unreviewed')===reviewFilter)&&(s.title+' '+s.id+' '+s.cwe).toLowerCase().includes(reviewQuery.toLowerCase()));
      if(!selected.some(s=>s.id===reviewId))reviewId=selected[0]?.id||null;
      $('review-list').innerHTML=selected.length?selected.map(s=>`<button class="review-option${s.id===reviewId?' selected':''}" data-review-id="${esc(s.id)}"><strong>${esc(s.title)}</strong><small>${s.label?'Vulnerable':'Corrected'} · ${esc(s.cwe)}</small>${pill(statuses[reviewEntries[s.id]?.status||'unreviewed'],reviewEntries[s.id]?.status==='needs_attention'?'risk':'neutral')}</button>`).join(''):'<p class="empty">No examples match this split and filter.</p>';
      const s=selected.find(s=>s.id===reviewId);if(!s){$('review-detail').innerHTML='<div class="panel empty">Choose another status, search or evaluation split.</div>';return;}
      const entry=reviewDrafts[s.id]||reviewEntries[s.id]||{status:'unreviewed',note:''};
      $('review-detail').innerHTML=`<div class="panel review-editor"><div class="panel-head"><div><h2>${esc(s.title)}</h2><p>${esc(s.id)}</p></div><button class="small-button" data-open-pair="${esc(s.pair_id)}">Open pair ↗</button></div><div class="pair-meta">${pill(s.cwe)}${pill(s.label?'Label: vulnerable':'Label: corrected',s.label?'risk':'')}</div><pre class="review-code"><code>${esc(s.code)}</code></pre><p class="review-assumption">${esc(s.assumptions)}</p><form id="review-form"><label for="review-status" class="micro-label">REVIEW STATUS</label><select id="review-status">${Object.entries(statuses).map(([k,v])=>`<option value="${k}"${entry.status===k?' selected':''}>${v}</option>`).join('')}</select><label for="review-note" class="micro-label">YOUR OBSERVATIONS</label><textarea id="review-note" maxlength="5000" rows="6" placeholder="Record the source, assumptions and evidence you checked…">${esc(entry.note)}</textarea><div class="review-save"><span id="review-save-state">Up to 5,000 characters · ${entry.draft?'Unsaved changes':entry.updated_at?'Last saved '+esc(new Date(entry.updated_at).toLocaleString()):'Not saved yet'}</span><button type="submit" class="button primary">Save review</button></div></form><p class="note-line">Review status records your workflow. Notes never change dataset labels, model scores or the original report.</p></div>`;
    }
    const commandItems=()=>[
      ...Object.entries(api.routes).map(([id,route])=>({label:route[0],detail:'Workspace page',action:()=>{location.hash=id;setRoute(id);}})),
      {label:'Import report',detail:'Open a local experiment JSON',action:()=>$('import-file').click()},
      {label:'Toggle appearance',detail:'Switch light / dark',action:()=>$('theme-toggle').click()},
      ...state.report.samples.filter(s=>s.label===1).map(s=>({label:s.title,detail:s.cwe+' · '+s.split,action:()=>{state.split=s.split;state.query='';state.cwe='all';state.pairId=s.pair_id;location.hash='pairs';setRoute('pairs');}}))
    ];
    let visibleCommands=[];
    function renderCommands() {const query=$('command-search').value.toLowerCase();visibleCommands=commandItems().filter(c=>(c.label+' '+c.detail).toLowerCase().includes(query)).slice(0,30);$('command-results').innerHTML=visibleCommands.map((c,i)=>`<button class="command-item" data-command="${i}"><span><strong>${esc(c.label)}</strong><small>${esc(c.detail)}</small></span><span>↗</span></button>`).join('')||'<p class="empty">No matching page or code pair.</p>';}
    function openCommands(){if(!state.report)return;$('command-search').value='';renderCommands();$('command-dialog').showModal();$('command-search').focus();}
    $('command-button').addEventListener('click',openCommands);$('command-close').addEventListener('click',()=>$('command-dialog').close());$('command-search').addEventListener('input',renderCommands);
    $('command-dialog').addEventListener('click',event=>{const button=event.target.closest('[data-command]');if(button){$('command-dialog').close();visibleCommands[Number(button.dataset.command)]?.action();}});
    document.addEventListener('keydown',event=>{
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();if($('command-dialog').open)$('command-dialog').close();else openCommands();}
      if(!$('command-dialog').open)return;
      const buttons=[...$('command-results').querySelectorAll('button')],index=buttons.indexOf(document.activeElement);
      if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();const next=event.key==='ArrowDown'?Math.min(index+1,buttons.length-1):Math.max(0,index-1);buttons[next]?.focus();}
      if(event.key==='Enter'&&event.target===$('command-search')){event.preventDefault();buttons[0]?.click();}
    });
    document.addEventListener('click',event=>{
      if(!state.report)return;const button=event.target.closest('button');if(!button)return;
      if(button.dataset.cweOpen){state.cwe=button.dataset.cweOpen;state.query='';state.pairId=null;location.hash='pairs';setRoute('pairs');}
      if(button.dataset.reviewId){reviewId=button.dataset.reviewId;review(false);}
      if(button.id==='comparison-import')$('comparison-file').click();
      if(button.id==='comparison-reset'){comparisonReport=null;candidateId=activeRun().id;compare();}
      if(button.id==='comparison-csv'){const c=comparisonData();download('patchlens-comparison-'+state.report.experiment_id+'.csv',A.csv([['id','cwe','split','label','baseline_score','candidate_score','outcome'],...c.changes.map(s=>[s.id,s.cwe,s.split,s.label,s.baseline_score,s.candidate_score,s.outcome])]),'text/csv;charset=utf-8');}
      if(button.id==='review-export')download('patchlens-review-'+state.report.experiment_id+'.json',A.reviewBundle(state.report,reviewEntries));
      if(button.id==='review-import')$('review-file').click();
    });
    function keepDraft(){if(!reviewId||!$('review-note'))return;reviewDrafts[reviewId]={id:reviewId,status:$('review-status').value,note:$('review-note').value,draft:true};$('review-save-state').textContent='Unsaved changes · select Save review to keep them.';}
    document.addEventListener('input',event=>{if(event.target.id==='review-note')keepDraft();if(event.target.id==='review-search'){reviewQuery=event.target.value;review(false);}});
    document.addEventListener('change',event=>{
      if(event.target.id==='review-status')keepDraft();
      if(event.target.id==='baseline-select'){baselineId=event.target.value;compare();}
      if(event.target.id==='candidate-select'){candidateId=event.target.value;compare();}
      if(event.target.id==='review-filter'){reviewFilter=event.target.value;review(false);}
    });
    document.addEventListener('submit',event=>{if(event.target.id!=='review-form')return;event.preventDefault();reviewEntries[reviewId]={id:reviewId,status:$('review-status').value,note:$('review-note').value.slice(0,5000),updated_at:new Date().toISOString()};delete reviewDrafts[reviewId];const saved=persistReview();review(false);toast(saved?'Review saved in this browser.':'Saved for this session only. Export notes to keep them.');});
    $('comparison-file').addEventListener('change',async event=>{
      const file=event.target.files[0];if(!file)return;
      try{if(file.size>20*1024*1024)throw new Error('Report limit is 20 MiB.');const r=validateReport(JSON.parse(await file.text()));A.compatible(state.report,r);comparisonReport=r;candidateId=r.runs.some(r=>r.id==='weighted')?'weighted':r.runs[0].id;compare();toast('Matched candidate report loaded.');}catch(error){toast(error.message);}finally{event.target.value='';}
    });
    $('review-file').addEventListener('change',async event=>{
      const file=event.target.files[0];if(!file)return;
      try{if(file.size>5*1024*1024)throw new Error('Review file limit is 5 MiB.');const incoming=A.validateReview(JSON.parse(await file.text()),state.report);let added=0;for(const [id,entry] of Object.entries(incoming)){if(!reviewEntries[id]||Date.parse(entry.updated_at)>Date.parse(reviewEntries[id].updated_at)){reviewEntries[id]=entry;added++;}}const saved=persistReview();review();toast(`${added} newer review entries imported.${saved?'':' Export a backup; browser storage is unavailable.'}`);}catch(error){toast(error.message);}finally{event.target.value='';}
    });
    return {onLoad,overviewSignal,renderers:{diagnostics,compare,review}};
  }};
})();
