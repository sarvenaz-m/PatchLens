"""Bundle the actual reference workbench into a portable index.html, with CSP hashes."""
from pathlib import Path
import base64
import hashlib
import re

ROOT=Path(__file__).resolve().parents[1]
web=ROOT/'src/patchlens/web'
html=(web/'index.html').read_text(encoding='utf-8')
css=(web/'styles.css').read_text(encoding='utf-8')+'\n'+(web/'studio.css').read_text(encoding='utf-8')
scripts=[(web/name).read_text(encoding='utf-8') for name in ['analysis.js','workspace.js','app.js']]
payload=(ROOT/'examples/fixture-run/workbench/report-data.js').read_text(encoding='utf-8')
if any('</script' in code.lower() for code in [payload,*scripts]):
    raise ValueError('Unsafe script boundary in bundle')
icon='data:image/svg+xml;base64,'+base64.b64encode((web/'assets/mark.svg').read_bytes()).decode()
hashes=['sha256-'+base64.b64encode(hashlib.sha256(value.encode('utf-8')).digest()).decode() for value in [payload,*scripts]]
html=html.replace("script-src 'self'",'script-src '+ ' '.join("'"+x+"'" for x in hashes))
html=html.replace('<link rel="stylesheet" href="styles.css">','<style>'+css+'</style>')
html=html.replace('<link rel="stylesheet" href="studio.css">','')
html=re.sub(r'\s*<script src="(?:report-data|analysis|workspace|app)\.js" defer></script>','',html)
html=html.replace('assets/mark.svg',icon)
html=html.replace('</body>','\n'.join('<script>'+code+'</script>' for code in [payload,*scripts])+'\n</body>')
(ROOT/'index.html').write_text(html,encoding='utf-8')
print(f'Portable workbench: {ROOT / "index.html"} ({len(html.encode())} bytes)')
