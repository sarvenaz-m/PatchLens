"""Plot actual public out-of-fold metrics and repository bootstrap intervals."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / 'examples/repository-cross-validation/cross-validation-summary.json').read_text())
keys = ['linear', 'supervised', 'contrastive', 'weighted', 'codebert', 'constant']
labels = ['Token baseline', 'Supervised encoder', 'Contrastive encoder', 'Security-weighted encoder', 'CodeBERT · frozen probe', 'Constant 0.5 control']
scores = np.array([report['models'][k]['macro_balanced_accuracy'] for k in keys]) * 100
intervals = np.array([report['models'][k]['bootstrap']['percentile_95']['macro_balanced_accuracy'] for k in keys]) * 100
misses = [report['models'][k]['pooled_counts']['fn'] for k in keys]
alarms = [report['models'][k]['pooled_counts']['fp'] for k in keys]
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10, 'axes.spines.top':False, 'axes.spines.right':False, 'svg.fonttype':'none'})
fig, (left, right) = plt.subplots(1, 2, figsize=(13.1, 5.9), gridspec_kw={'width_ratios':[1.6,1]}, facecolor='#f5f6f2')
for ax in (left, right):
    ax.set_facecolor('#f5f6f2')
    ax.set_ylim(5.7, -.7)
    ax.grid(axis='x', color='#dde5df', linewidth=.6)
    ax.set_axisbelow(True)
y = np.arange(6)
left.axvline(50, linestyle='--', color='#82938c', linewidth=1, label='Constant-control reference')
left.errorbar(scores, y, xerr=np.vstack([scores-intervals[:,0], intervals[:,1]-scores]), fmt='o', color='#146d5d', ecolor='#72958e', markersize=7, capsize=4, linewidth=2)
left.set_yticks(y, labels)
left.set_xlim(0, 100)
left.set_xticks([0,25,50,75,100], ['0%','25%','50%','75%','100%'])
left.set_xlabel('Repository macro balanced accuracy · 95% interval')
left.set_title('Each repository gets equal weight', loc='left', fontweight='bold', pad=18)
for i, value in enumerate(scores):
    left.text(78, i, f'{value:.1f}% ({intervals[i,0]:.1f}–{intervals[i,1]:.1f})', va='center', fontsize=9, color='#244337')
right.barh(y-.16, misses, height=.28, color='#a74332', label='Missed before contexts')
right.barh(y+.16, alarms, height=.28, color='#ca8b54', label='False alarms on after contexts')
right.set_yticks(y, ['']*6)
right.set_xlim(0, 72)
right.set_xticks([0,20,40,62])
right.set_xlabel('Pooled error counts · denominator 62 per class')
right.set_title('Errors at fold-specific thresholds', loc='left', fontweight='bold', pad=18)
for i, (fn, fp) in enumerate(zip(misses, alarms)):
    right.text(fn+.8, i-.16, str(fn), va='center', fontsize=9)
    right.text(fp+.8, i+.16, str(fp), va='center', fontsize=9)
right.legend(loc='upper center', bbox_to_anchor=(.46, -.16), frameon=False, fontsize=9)
fig.suptitle('PatchLens v2 · real Java security corrections', x=.065, y=.98, ha='left', fontsize=18, fontweight='bold', color='#142734')
fig.text(.065,.925, '62 pairs · 40 repositories · 5 held-out folds · training seed 17 · 2,000 whole-repository bootstrap draws', fontsize=10, color='#496258')
fig.text(.065,.015, 'Exploratory intervals: small corpus and overlapping fold training sets. CodeBERT − token baseline: +2.29 pp (95%: −5.42 to +9.58).', fontsize=9, color='#496258')
fig.subplots_adjust(left=.21, right=.98, top=.81, bottom=.22, wspace=.17)
for extension in ('png','svg'):
    fig.savefig(ROOT / f'docs/assets/public-results.{extension}', dpi=160, facecolor=fig.get_facecolor())
svg_path = ROOT / 'docs/assets/public-results.svg'
svg_path.write_text('\n'.join(line.rstrip() for line in svg_path.read_text().splitlines()) + '\n')
plt.close(fig)
print('Wrote public-results.png and public-results.svg from actual cross-validation-summary.json')
