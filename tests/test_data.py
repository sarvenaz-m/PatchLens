from dataclasses import replace
import unittest
import numpy as np

from patchlens.data import Example, audit, fixture_path, load_dataset
from patchlens.features import Vectorizer, tokenize
from patchlens.cli import match_predictions


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.samples = load_dataset(fixture_path())

    def test_fixture_contract(self):
        a = audit(self.samples)
        self.assertEqual((a['examples'],a['pairs'],a['groups']),(48,24,24))
        self.assertEqual(a['splits'], {'test':12,'train':24,'validation':12})
        self.assertEqual(len(a['categories']),6)

    def test_fingerprint_independent_of_input_order(self):
        self.assertEqual(audit(self.samples)['fingerprint'],audit(list(reversed(self.samples)))['fingerprint'])

    def test_duplicate_id_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'): audit(self.samples+[self.samples[0]])

    def test_incomplete_pair_rejected(self):
        with self.assertRaisesRegex(ValueError,'Pair'): audit(self.samples[1:])

    def test_group_leakage_rejected(self):
        rows=self.samples.copy(); idx=next(i for i,s in enumerate(rows) if s.split=='test')
        rows[idx]=replace(rows[idx],group_id=rows[0].group_id)
        with self.assertRaisesRegex(ValueError,'Group leakage'): audit(rows)

    def test_duplicate_code_across_splits_rejected(self):
        rows=self.samples.copy(); idx=next(i for i,s in enumerate(rows) if s.split=='test' and s.label==rows[0].label)
        rows[idx]=replace(rows[idx],code='\n '+rows[0].code+'\n')
        with self.assertRaisesRegex(ValueError,'Code leakage'): audit(rows)

    def test_contradictory_label_rejected(self):
        rows=self.samples.copy();idx=next(i for i,s in enumerate(rows) if s.label!=rows[0].label)
        rows[idx]=replace(rows[idx],code=rows[0].code)
        with self.assertRaisesRegex(ValueError,'Contradictory'): audit(rows)

    def test_sample_field_validation(self):
        for field,value in [('label',True),('id','../file'),('group_id','bad/id'),('split','holdout'),('code','')]:
            row=self.samples[0].to_dict();row[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): Example.from_dict(row)

    def test_features_fitted_only_on_supplied_training_text(self):
        v=Vectorizer.fit(['const trainingOnly = 5;'])
        before=v.to_dict()
        x=v.transform(['const heldoutSecret = 7;'])
        self.assertNotIn('heldoutSecret',v.vocabulary)
        self.assertEqual(v.to_dict(),before)
        self.assertAlmostEqual(float(np.linalg.norm(x)),1)

    def test_feature_roundtrip(self):
        codes=[s.code for s in self.samples[:6]];v=Vectorizer.fit(codes)
        np.testing.assert_array_equal(v.transform(codes),Vectorizer.from_dict(v.to_dict()).transform(codes))

    def test_comment_and_literal_handling(self):
        t=tokenize('const x = "// text"; // comment\nlet y = 22;')
        self.assertNotIn('comment',t);self.assertIn('<string>',t);self.assertIn('<number>',t)

    def test_predictions_join_by_id_and_require_exact_coverage(self):
        predictions=[{'id':s.id,'score':.4} for s in reversed(self.samples)]
        self.assertEqual(len(match_predictions(self.samples,predictions)),48)
        with self.assertRaisesRegex(ValueError,'coverage'):match_predictions(self.samples,predictions[:-1])
        with self.assertRaisesRegex(ValueError,'Duplicate'):match_predictions(self.samples,predictions+[predictions[0]])


if __name__ == '__main__': unittest.main()
