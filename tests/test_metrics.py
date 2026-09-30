import math
import unittest

from patchlens.metrics import binary_metrics, choose_threshold, curves, stability, wilson


class MetricTests(unittest.TestCase):
    def test_confusion_and_boundary(self):
        m = binary_metrics([1, 1, 0, 0], [.8, .2, .5, .1], .5)
        self.assertEqual([m[x] for x in ('tp','fn','fp','tn')], [1,1,1,1])
        for key in ('precision','recall','f1','fnr','fpr','accuracy'):
            self.assertEqual(m[key], .5)
        self.assertAlmostEqual(m['brier'], (.04+.64+.25+.01)/4)

    def test_undefined_precision_is_not_zero(self):
        m = binary_metrics([0,1], [.1,.2], .9)
        self.assertIsNone(m['precision'])
        self.assertEqual(m['f1'], 0)
        self.assertEqual(m['fnr'], 1)

    def test_ties_move_together(self):
        c = curves([1,0,1,0], [.5,.5,.5,.5])
        self.assertEqual(len(c['roc']), 2)
        self.assertEqual(c['roc_auc'], .5)
        self.assertEqual(c['average_precision'], .5)

    def test_known_ranking(self):
        c = curves([1,0,1,0], [.9,.8,.7,.1])
        self.assertAlmostEqual(c['average_precision'], 5/6)
        self.assertEqual(c['roc_auc'], .75)

    def test_single_class_rankings(self):
        self.assertIsNone(curves([0,0], [.1,.9])['average_precision'])
        self.assertIsNone(curves([1,1], [.1,.9])['roc_auc'])

    def test_threshold_constraint_and_no_test_labels(self):
        result = choose_threshold([1,1,0,0], [.9,.8,.85,.1], max_fpr=0)
        self.assertEqual(result['source_split'], 'validation')
        self.assertEqual(result['validation_metrics']['fp'], 0)
        self.assertEqual(result['validation_metrics']['recall'], .5)

    def test_infeasible_threshold_is_not_silently_relaxed(self):
        with self.assertRaises(ValueError):
            choose_threshold([0,1], [1.,.8], 0)

    def test_input_rejection(self):
        for labels,scores,threshold in [([True],[.5],.5),([0],[float('nan')],.5),([1],[1.1],.5),([0],['.2'],.5),([],[],.5),([0],[.1],True),([0],[.1],float('nan'))]:
            with self.subTest(labels=labels,scores=scores), self.assertRaises(ValueError):
                binary_metrics(labels,scores,threshold)

    def test_stability_exposes_shared_errors(self):
        s = stability([1,0],[.1,.9],[.2,.8],.5)
        self.assertEqual(s['agreement'],1)
        self.assertEqual(s['both_correct'],0)

    def test_wilson_uncertainty_for_tiny_sample(self):
        low,high = wilson(0,6)
        self.assertAlmostEqual(low,0)
        self.assertGreater(high,.39)
        self.assertIsNone(wilson(0,0))


if __name__ == '__main__': unittest.main()
