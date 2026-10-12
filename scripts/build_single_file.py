"""Bundle the actual reference workbench into a portable index.html, with CSP hashes."""
from pathlib import Path
import base64
import hashlib
import re
import argparse
import json

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report',type=Path,default=ROOT/'examples/public-benchmark/report.json')
parser.add_argument('--output',type=Path,default=ROOT/'index.html')
args=parser.parse_args()
web=ROOT/'src/patchlens/web'
html=(web/'index.html').read_text(encoding='utf-8')
css=(web/'styles.css').read_text(encoding='utf-8')+'\n'+(web/'studio.css').read_text(encoding='utf-8')
scripts=[(web/name).read_text(encoding='utf-8') for name in ['analysis.js','workspace.js','benchmark.js','app.js']]
def encoded(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
payload='window.PATCHLENS_REPORT = '+encoded(json.loads(args.report.read_text(encoding='utf-8')))+';\n'
if (ROOT/'examples/fixture-run/report.json').resolve()!=args.report.resolve():
    extra={'fixtures':json.loads((ROOT/'examples/fixture-run/report.json').read_text(encoding='utf-8'))}
    cv_path=ROOT/'examples/repository-cross-validation/cross-validation-summary.json'
    if cv_path.exists():
        cv=json.loads(cv_path.read_text(encoding='utf-8'))
        for fold in range(5):
            fold_path=ROOT/f'examples/repository-cross-validation/fold-{fold}/run/report.json'
            if fold_path.exists():
                report=json.loads(fold_path.read_text(encoding='utf-8'))
                report['dataset']['workbench_label']=f'Vul4J · repository fold {fold+1}/5'
                report['cross_validation']=cv
                extra[f'fold-{fold}']=report
    payload+='window.PATCHLENS_EXTRA_REPORTS = '+encoded(extra)+';\n'
if any('</script' in code.lower() for code in [payload,*scripts]):
    raise ValueError('Unsafe script boundary in bundle')
icon='data:image/svg+xml;base64,'+base64.b64encode((web/'assets/mark.svg').read_bytes()).decode()
hashes=['sha256-'+base64.b64encode(hashlib.sha256(value.encode('utf-8')).digest()).decode() for value in [payload,*scripts]]
html=html.replace("script-src 'self'",'script-src '+ ' '.join("'"+x+"'" for x in hashes))
html=html.replace('<link rel="stylesheet" href="styles.css">','<style>'+css+'</style>')
html=html.replace('<link rel="stylesheet" href="studio.css">','')
html=re.sub(r'\s*<script src="(?:report-data|analysis|workspace|benchmark|app)\.js" defer></script>','',html)
html=html.replace('assets/mark.svg',icon)
html=html.replace('</body>','\n'.join('<script>'+code+'</script>' for code in [payload,*scripts])+'\n</body>')
args.output.write_text(html,encoding='utf-8',newline='\n')
print(f'Portable workbench: {args.output} ({len(html.encode())} bytes)')
