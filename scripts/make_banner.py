"""Build a code-native banner from the recorded public five-fold study."""
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / 'examples/repository-cross-validation/cross-validation-summary.json').read_text())
models = [('linear', 'Token baseline'), ('supervised', 'Supervised'), ('contrastive', 'Contrastive'), ('weighted', 'Security-weighted'), ('codebert', 'CodeBERT probe'), ('constant', 'Constant control')]
bars = []
for i, (key, label) in enumerate(models):
    score = report['models'][key]['macro_balanced_accuracy']
    bars.append(f'<g transform="translate(940,{292+i*34})"><text y="12" font-size="12" fill="#c3d9d3">{escape(label)}</text><rect x="153" y="2" width="270" height="10" rx="5" fill="#294950"/><rect x="153" y="2" width="{270*score:.3f}" height="10" rx="5" fill="#a5d9bb"/><text x="525" y="12" text-anchor="end" font-size="12" fill="#e5f1e8">{score:.1%}</text></g>')
score = report['models']['codebert']['macro_balanced_accuracy']
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="640" viewBox="0 0 1600 640" role="img" aria-labelledby="title description">
<title id="title">PatchLens — real code, inspectable evidence</title>
<desc id="description">Version 2.0.0: {report['pairs']} real Java security corrections, {report['repositories']} repositories, five evaluation folds. All bars are repository macro balanced accuracy on a zero-to-one scale.</desc>
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#112b35"/><stop offset="1" stop-color="#1b4248"/></linearGradient><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#9bc4bb" opacity=".10"/></pattern></defs>
<rect width="1600" height="640" rx="22" fill="url(#bg)"/><rect width="1600" height="640" rx="22" fill="url(#dots)"/>
<g fill="none" stroke="#99c6ac" opacity=".10"><circle cx="814" cy="310" r="285"/><circle cx="814" cy="310" r="240"/></g>
<g font-family="Arial,Helvetica,sans-serif">
<rect x="65" y="57" width="38" height="38" rx="11" fill="#bfe3be"/><g fill="none" stroke="#214a41" stroke-width="2.2"><circle cx="82" cy="74" r="8"/><path d="m88 80 7 7M72 63h22v27H72z" opacity=".65"/></g>
<text x="120" y="82" font-size="13" letter-spacing="3" fill="#b5d5c6">SECURITY RESEARCH STUDIO</text>
<text x="60" y="239" font-size="112" font-weight="600" letter-spacing="-6" fill="#f2f5e9">PatchLens</text>
<text x="67" y="302" font-size="32" letter-spacing="-1" fill="#c6e8c0">Real code. Inspectable evidence.</text>
<text x="68" y="355" font-size="17" fill="#bfd4d3">62 security corrections · 40 repositories · 5 folds</text>
<g transform="translate(67,416)"><rect width="134" height="33" rx="16" fill="#c9e6bf"/><text x="18" y="22" font-size="12" font-weight="600" fill="#244a3e">VERSION 2.0.0</text><text x="155" y="22" font-size="12" fill="#c3d4cc" letter-spacing="1">LOCAL · REPRODUCIBLE · TRACEABLE</text></g>
<text x="67" y="587" font-size="12" fill="#b6d1c8" letter-spacing="2">JAVA PATCHES / PRETRAINED ENCODER / ERROR ANALYSIS</text>
<rect x="904" y="61" width="625" height="479" rx="20" fill="#102b35" stroke="#547c76"/>
<circle cx="936" cy="89" r="4" fill="#c98772"/><circle cx="952" cy="89" r="4" fill="#dab57e"/><circle cx="968" cy="89" r="4" fill="#9dceae"/>
<text x="1493" y="94" text-anchor="end" font-size="10" fill="#c0d8ce" letter-spacing="2">PUBLIC FIVE-FOLD STUDY</text><line x1="924" y1="114" x2="1509" y2="114" stroke="#31545b"/>
<text x="940" y="151" font-size="11" letter-spacing="1.4" fill="#bcd7ce">CODEBERT · REPOSITORY MACRO BALANCED ACCURACY</text>
<text x="938" y="227" font-size="73" fill="#d1eac2" letter-spacing="-4">{score:.1%}</text>
<text x="1200" y="194" font-size="14" fill="#deebe2">40 / 62 misses</text><text x="1200" y="222" font-size="14" fill="#deebe2">15 / 62 false alarms</text>
<text x="940" y="264" font-size="11" fill="#b4ccc6">124 held-out contexts · one test prediction per model per context</text>
{''.join(bars)}
<text x="940" y="519" font-size="11" fill="#b4ccc6">Each bar: 0–100% · exploratory intervals in the full report</text>
<text x="1529" y="587" text-anchor="end" font-size="11" fill="#b6d1c8">Paired CodeBERT gain interval includes zero</text>
</g></svg>'''
(ROOT / 'docs/assets/github-banner.svg').write_text(svg, encoding='utf-8')
print('Wrote docs/assets/github-banner.svg')
