from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest

from patchlens.cli import main
from patchlens.data import load_dataset, fixture_path
from patchlens.experiment import run_experiment, export_workbench
from patchlens.io import load_json, load_jsonl


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.report=run_experiment(load_dataset(fixture_path()),cls.root/'run',epochs=12)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_four_actual_runs_with_frozen_validation_thresholds(self):
        self.assertEqual(len(self.report['runs']),4)
        for run in self.report['runs']:
            self.assertEqual(len(run['predictions']),48)
            self.assertEqual(run['operating_point']['source_split'],'validation')
            self.assertLessEqual(run['operating_point']['validation_metrics']['fpr'],.2)
            self.assertEqual(run['splits']['test']['metrics']['n'],12)
            self.assertEqual(run['splits']['test']['metrics']['threshold'],run['threshold'])

    def test_cli_model_roundtrip(self):
        out=self.root/'roundtrip.jsonl'
        with redirect_stdout(io.StringIO()):
            code=main(['predict','--checkpoint',str(self.root/'run/model-weighted.json'),'--output',str(out)])
        self.assertEqual(code,0)
        expected=next(r['predictions'] for r in self.report['runs'] if r['id']=='weighted')
        self.assertEqual(load_jsonl(out),expected)

    def test_portable_export_escapes_script_boundaries(self):
        report=json.loads(json.dumps(self.report));report['samples'][0]['title']='</script><img src=x onerror=alert(1)>'
        export_workbench(report,self.root/'escaped')
        payload=(self.root/'escaped/report-data.js').read_text()
        self.assertNotIn('</script>',payload)
        self.assertIn('\\u003c/script>',payload)
        for name in ['index.html','app.js','styles.css','assets/mark.svg']:
            self.assertTrue((self.root/'escaped'/name).is_file())

    def test_unrelated_output_directory_protected(self):
        target=self.root/'unrelated';target.mkdir(exist_ok=True);(target/'important.txt').write_text('keep')
        with self.assertRaises(ValueError):run_experiment(load_dataset(fixture_path()),target,epochs=1)
        self.assertEqual((target/'important.txt').read_text(),'keep')

    def test_cli_errors_return_nonzero(self):
        with redirect_stderr(io.StringIO()):
            code=main(['predict','--checkpoint',str(self.root/'missing.json'),'--output',str(self.root/'bad.jsonl')])
        self.assertEqual(code,2)


if __name__ == '__main__': unittest.main()
