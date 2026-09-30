import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from patchlens.data import fixture_path, load_dataset
from patchlens.external import attach_predictions, attach_scan
from patchlens.generation import extract_code, generation_summary, validate_prompts
from patchlens.hf_training import TrainingConfig, model_options
from patchlens.integrations import export_sources, import_sarif, run_codeql
from patchlens.io import fingerprint, load_json, write_json


class IntegrationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = load_dataset(fixture_path())
        cls.report = load_json(Path(__file__).resolve().parents[1] / 'examples/fixture-run/report.json')

    def test_source_export_preserves_code_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as path:
            manifest = export_sources(self.samples, Path(path) / 'sources')
            self.assertEqual(len(manifest['files']), 48)
            self.assertEqual((Path(path) / 'sources' / manifest['files'][0]['path']).read_text(), self.samples[0].code)
            with self.assertRaises(ValueError):
                export_sources(self.samples, Path(path) / 'sources')

    def sarif(self, execution=True, uri='src/example.js'):
        return {'version': '2.1.0', 'runs': [{'tool': {'driver': {'name': 'Test scanner', 'version': 'test', 'rules': [{'id': 'test-rule'}]}},
                'invocations': [{'executionSuccessful': execution}], 'artifacts': [{'location': {'uri': uri}}],
                'results': [{'ruleIndex': 0, 'message': {'text': '<unsafe text>'}, 'locations': [{'physicalLocation': {
                    'artifactLocation': {'index': 0}, 'region': {'startLine': 3}}}]}]}]}

    def test_sarif_resolves_artifact_and_rule_indices(self):
        m = {'files': [{'path': 'src/example.js', 'example_id': 'example'}], 'dataset_sha256': 'hash'}
        scan = import_sarif(self.sarif(uri='file:///home/research/src/example.js'), m)
        self.assertEqual(scan['status'], 'completed')
        self.assertEqual(scan['findings'][0]['example_id'], 'example')
        self.assertEqual(scan['findings'][0]['rule'], 'test-rule')
        self.assertIn('not established', scan['coverage'])

    def test_failed_scan_and_unmapped_locations_remain_visible(self):
        m = {'files': [{'path': 'src/example.js', 'example_id': 'example'}], 'dataset_sha256': 'hash'}
        scan = import_sarif(self.sarif(False, 'different.js'), m)
        self.assertEqual(scan['status'], 'failed')
        self.assertEqual(scan['findings'], [])
        self.assertEqual(len(scan['unmapped']), 1)

    def test_sarif_duplicate_and_invalid_lines(self):
        m = {'files': [{'path': 'src/example.js', 'example_id': 'example'}], 'dataset_sha256': 'hash'}
        payload = self.sarif()
        payload['runs'][0]['results'] *= 2
        self.assertEqual(len(import_sarif(payload, m)['findings']), 1)
        payload['runs'][0]['results'][0]['locations'][0]['physicalLocation']['region']['startLine'] = -1
        with self.assertRaises(ValueError): import_sarif(payload, m)

    def test_codeql_orchestration_keeps_source_root_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / 'source', Path(directory) / 'output'
            export_sources(self.samples, source)
            commands = []
            def invoke(command, **kwargs):
                commands.append(command)
                if command[2] == 'analyze':
                    write_json(output / 'results.sarif', self.sarif(uri=self.samples[0].id + '.js'))
                return subprocess.CompletedProcess(command, 0, 'recorded test output', '')
            with patch('patchlens.integrations.shutil.which', return_value='/test/codeql'), patch('patchlens.integrations.subprocess.run', side_effect=invoke):
                result = run_codeql(source, output, query_suite='test-suite')
            self.assertEqual(len(commands), 2)
            self.assertEqual(result['findings'][0]['example_id'], self.samples[0].id)
            self.assertTrue((output / 'stage-0.log').exists())

    def test_codeql_timeout_writes_failed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / 'source', Path(directory) / 'output'
            export_sources(self.samples, source)
            with patch('patchlens.integrations.shutil.which', return_value='/test/codeql'), patch('patchlens.integrations.subprocess.run', side_effect=subprocess.TimeoutExpired('codeql', 1)):
                with self.assertRaises(ValueError): run_codeql(source, output, query_suite='test-suite', timeout=1)
            self.assertEqual(load_json(output / 'status.json')['status'], 'failed')

    def test_external_scores_do_not_invent_embeddings(self):
        scores = self.report['runs'][0]['predictions']
        result = attach_predictions(self.report, list(reversed(scores)), run_id='external', name='Recorded classifier', provenance={'origin': 'test'})
        run = result['runs'][-1]
        self.assertEqual(run['projection']['method'], 'not_available')
        self.assertEqual(run['projection']['points'], [])
        self.assertEqual(run['operating_point']['source_split'], 'validation')
        self.assertEqual(len(self.report['runs']), 4)

    def test_external_import_requires_real_view_predictions(self):
        scores = [{'id': p['id'], 'score': p['score']} for p in self.report['runs'][0]['predictions']]
        with self.assertRaises(ValueError):
            attach_predictions(self.report, scores, run_id='external', name='External', provenance={'origin': 'test'})

    def test_scan_cannot_attach_to_other_dataset(self):
        with self.assertRaises(ValueError):
            attach_scan(self.report, {'dataset_sha256': 'wrong', 'status': 'completed', 'findings': []})

    def test_remote_models_require_exact_revision(self):
        with self.assertRaises(ValueError): model_options('public/model', 'main', True)
        self.assertEqual(model_options('public/model', 'a' * 40, False)['local_files_only'], True)

    def test_training_config_rejects_nonfinite_or_frozen_contrastive(self):
        for config in [TrainingConfig(mode='frozen'), TrainingConfig(temperature=0), TrainingConfig(learning_rate=float('nan'))]:
            with self.assertRaises(ValueError): config.validate()

    def test_generation_prompt_validation_and_code_extraction(self):
        validate_prompts([{'id': 'safe-id', 'prompt': 'Write JavaScript.', 'assumptions': 'Teaching use.'}])
        with self.assertRaises(ValueError): validate_prompts([{'id': '../escape', 'prompt': 'x', 'assumptions': 'x'}])
        self.assertEqual(extract_code('```js\nconst a = 1;\n```'), 'const a = 1;')
        self.assertEqual(extract_code('plain'), 'plain')

    def test_incomplete_scan_has_no_generation_density(self):
        records = [{'id': 'one', 'nonblank_physical_lines': 2}]
        scan = {'dataset_sha256': fingerprint(records), 'status': 'failed', 'findings': []}
        self.assertIsNone(generation_summary(records, scan)['findings_per_100_nonblank_lines'])
        self.assertIsNone(generation_summary(records, scan)['adjudicated_vulnerabilities'])


if __name__ == '__main__': unittest.main()
