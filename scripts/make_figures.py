"""Generate exact, publication-friendly reference graphics from the saved report.

Optional developer dependency: matplotlib >= 3.8.
"""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'examples/fixture-run/report.json').read_text())
names=['Token\nbaseline','Supervised\nencoder','Contrastive\nencoder','Security-weighted\nencoder']
results=[r['splits']['test']['metrics'] for r in report['runs']]
ink='#142734';teal='#146d5d';copper='#a74332';bg='#f5f6f2';muted='#596d75'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':ink,'axes.labelcolor':ink,
                     'xtick.color':muted,'ytick.color':muted,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(12.8,5.2),facecolor=bg)
fig.subplots_adjust(left=.07,right=.98,top=.72,bottom=.25,wspace=.26)
fig.text(.065,.92,'PATCHLENS  /  REFERENCE EXPERIMENT',fontsize=9,color=teal,weight='bold')
fig.text(.065,.82,'Count the errors. Show the uncertainty.',fontsize=22,color=ink)
for ax,key,ci,label,color in [(axes[0],'fn','fnr_wilson_95','Vulnerabilities missed',copper),(axes[1],'fp','fpr_wilson_95','False alarms',teal)]:
    ax.set_facecolor(bg);x=np.arange(4);rates=[m['fnr' if key=='fn' else 'fpr'] for m in results]
    lower=[max(0.,rate-m[ci][0]) for rate,m in zip(rates,results)];upper=[max(0.,m[ci][1]-rate) for rate,m in zip(rates,results)]
    ax.bar(x,rates,width=.5,color=color,alpha=.9,zorder=3)
    ax.errorbar(x,rates,yerr=[lower,upper],fmt='none',ecolor=ink,capsize=5,elinewidth=1.2,zorder=4)
    for i,m in enumerate(results):ax.text(i,min(m[ci][1]+.045,.93),f"{m[key]} / 6",ha='center',color=ink,fontsize=11,weight='bold')
    ax.set_title(label,loc='left',fontsize=12,pad=13,weight='bold');ax.set_xticks(x,names,fontsize=9)
    ax.set_ylim(0,1);ax.set_yticks([0,.25,.5,.75,1],['0%','25%','50%','75%','100%'])
    ax.grid(axis='y',color='#dbe4df',zorder=0);ax.tick_params(length=0,pad=8)
    for spine in ax.spines.values():spine.set_visible(False)
fig.text(.065,.105,'Held-out fixtures · 6 vulnerable + 6 corrected · seed 17 · validation-selected thresholds',fontsize=9,color=muted)
fig.text(.065,.06,'Whiskers: 95% Wilson intervals. Authored examples are not a representative security benchmark.',fontsize=9,color=muted)
out=ROOT/'docs/assets';out.mkdir(parents=True,exist_ok=True)
fig.savefig(out/'reference-results.png',dpi=180,facecolor=bg)
fig.savefig(out/'reference-results.svg',facecolor=bg)
print(out/'reference-results.png')
