"""Create the repository's vector banner from the recorded fixture results."""
from pathlib import Path
import json
from html import escape

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / 'examples/fixture-run/report.json').read_text())
weighted = next(r for r in report['runs'] if r['id'] == 'weighted')
metrics = weighted['splits']['test']['metrics']
category_chips = ''.join(f'<g transform="translate({945 + i % 3 * 165},{438 + i // 3 * 42})"><rect width="150" height="30" rx="7" fill="#25464a"/><text x="15" y="20" font-size="12" fill="#c0d5cb">{escape(cwe)}</text></g>' for i, cwe in enumerate(sorted(report['dataset']['categories'], key=lambda c: int(c[4:]))))
bars = ''.join(f'<g transform="translate(946,{276+i*33})"><text x="0" y="12" font-size="12" fill="#b6cfcc">{escape(label)}</text><rect x="150" y="2" width="268" height="9" rx="4" fill="#2b494f"/><rect x="150" y="2" width="{268*run["splits"]["test"]["metrics"]["f1"]}" height="9" rx="4" fill="{colour}"/><text x="480" y="12" font-size="12" fill="#dbebe3" text-anchor="end">{run["splits"]["test"]["metrics"]["f1"]:.3f}</text></g>' for i,(run,label,colour) in enumerate(zip(report['runs'],['Token baseline','Supervised','Contrastive','Security-weighted'],['#72958e','#91b0a0','#aad8b6','#d0e9c0'])))
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="640" viewBox="0 0 1600 640" role="img" aria-labelledby="title description">
<title id="title">PatchLens — code security, made inspectable.</title>
<desc id="description">Security research studio. Recorded fixture results on twelve test examples; four model objectives, forty-eight authored examples and six weakness categories.</desc>
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#112b35"/><stop offset="1" stop-color="#1b4248"/></linearGradient><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#9bc4bb" opacity=".10"/></pattern></defs>
<rect width="1600" height="640" rx="22" fill="url(#bg)"/><rect width="1600" height="640" rx="22" fill="url(#dots)"/>
<g fill="none" stroke="#99c6ac" opacity=".10"><circle cx="824" cy="318" r="305"/><circle cx="824" cy="318" r="258"/><path d="M700 0v640M0 556h1600"/></g>
<g font-family="Arial,Helvetica,sans-serif">
<rect x="65" y="57" width="38" height="38" rx="11" fill="#bfe3be"/><g fill="none" stroke="#214a41" stroke-width="2.2"><circle cx="82" cy="74" r="8"/><path d="m88 80 7 7M72 63h22v27H72z" opacity=".65"/></g>
<text x="120" y="82" font-size="13" letter-spacing="3" fill="#b5d5c6">SECURITY RESEARCH STUDIO</text>
<text x="60" y="239" font-size="112" font-weight="600" letter-spacing="-6" fill="#f2f5e9">PatchLens</text>
<text x="67" y="302" font-size="32" letter-spacing="-1" fill="#c6e8c0">Code security, made inspectable.</text>
<text x="68" y="355" font-size="17" fill="#abc4c4">Compare models. Trace errors. Keep the evidence.</text>
<g transform="translate(67,416)"><rect width="134" height="33" rx="16" fill="#c9e6bf"/><text x="18" y="22" font-size="12" font-weight="600" fill="#244a3e">VERSION 1.0.0</text><text x="155" y="22" font-size="12" fill="#c3d4cc" letter-spacing="1">LOCAL · REPRODUCIBLE · INSPECTABLE</text></g>
<text x="67" y="587" font-size="12" fill="#a7c3ba" letter-spacing="2">PAIRS / DIAGNOSTICS / COMPARISON / REVIEW</text>
<rect x="909" y="61" width="620" height="475" rx="20" fill="#102b35" stroke="#547c7666"/>
<circle cx="941" cy="89" r="4" fill="#c98772"/><circle cx="957" cy="89" r="4" fill="#dab57e"/><circle cx="973" cy="89" r="4" fill="#9dceae"/>
<text x="1493" y="94" text-anchor="end" font-size="10" fill="#a7c7bf" letter-spacing="2">FIXTURE SNAPSHOT</text>
<line x1="929" y1="114" x2="1509" y2="114" stroke="#31545b"/>
<text x="945" y="151" font-size="10" letter-spacing="2" fill="#a7c7bf">SECURITY-WEIGHTED MODEL · TEST F1</text>
<text x="943" y="224" font-size="73" fill="#d1eac2" letter-spacing="-4">{metrics['f1']:.3f}</text>
<text x="1190" y="190" font-size="14" fill="#deebe2">{metrics['fn']} / {metrics['fn']+metrics['tp']} missed</text><text x="1190" y="218" font-size="14" fill="#deebe2">{metrics['fp']} / {metrics['fp']+metrics['tn']} false alarms</text>
<text x="945" y="253" font-size="10" fill="#9ebcb8">Authored fixture test · n = {metrics['n']} · validation-selected thresholds</text>
{bars}<line x1="945" y1="417" x2="1485" y2="417" stroke="#31545b"/>{category_chips}
<text x="1529" y="587" text-anchor="end" font-size="11" fill="#a7c3ba">Research fixtures · not a production benchmark</text>
</g></svg>'''
(ROOT/'docs/assets/github-banner.svg').write_text(svg)
print('Wrote docs/assets/github-banner.svg')
