import copy
import json
import math
import tempfile
from pathlib import Path
import unittest
from test_model import fixture, ROOT
from gqde import ValidationError
from gqde.history import snapshot, save_snapshot, verify_snapshot, evaluate_history, spearman, forecast_errors, digest


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.doc=fixture()
        self.predictions=json.loads((ROOT/'examples/business_predictions.json').read_text())
        self.saved=snapshot(self.doc,self.predictions)
        self.outcomes=json.loads((ROOT/'examples/business_outcomes.json').read_text())
        self.outcomes['snapshot_id']=self.saved['snapshot_id']

    def evaluate(self):
        return evaluate_history(self.saved,self.outcomes)

    def reset_snapshot(self, predictions=None):
        self.saved=snapshot(self.doc,self.predictions if predictions is None else predictions)
        self.outcomes['snapshot_id']=self.saved['snapshot_id']

    def test_replay_and_deterministic_hash(self):
        verify_snapshot(self.saved)
        self.assertEqual(snapshot(self.doc,self.predictions),self.saved)
        self.assertEqual(len(self.saved['snapshot_id']),64)
        self.doc['model_version']='new'
        self.assertNotEqual(snapshot(self.doc,self.predictions)['snapshot_id'],self.saved['snapshot_id'])

    def test_snapshot_is_independent_copy(self):
        original=copy.deepcopy(self.saved)
        self.doc['candidates'][0]['observations']['price']['value']=500
        self.predictions[0]['value']=0
        self.assertEqual(self.saved,original)

    def test_snapshot_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'decision.json'
            save_snapshot(self.saved,path)
            verify_snapshot(json.loads(path.read_text()))
            with self.assertRaises(FileExistsError):
                save_snapshot(self.saved,path)

    def test_tampered_snapshot_rejected(self):
        self.saved['report']['results'][0]['score']=100
        with self.assertRaisesRegex(ValidationError,'digest'):
            self.evaluate()

    def test_self_consistent_digest_still_requires_replay(self):
        self.saved['report']['results'][0]['score']=100
        self.saved['snapshot_id']=digest({k:v for k,v in self.saved.items() if k!='snapshot_id'})
        with self.assertRaisesRegex(ValidationError,'replay'):
            verify_snapshot(self.saved)

    def test_unknown_engine_replay_rejected(self):
        self.saved['engine_version']='999'
        self.saved['snapshot_id']=digest({k:v for k,v in self.saved.items() if k!='snapshot_id'})
        with self.assertRaisesRegex(ValidationError,'version unsupported'):
            verify_snapshot(self.saved)

    def test_history_known_ranking_and_baselines(self):
        result=self.evaluate()
        self.assertEqual(result['sample_count'],3)  # blocked candidate excluded
        self.assertAlmostEqual(result['spearman'],-.5)
        self.assertAlmostEqual(result['baseline_spearman'],.5)
        self.assertEqual(result['top_k']['composite']['mean_actual'],600)
        self.assertEqual(result['top_k']['baseline']['mean_actual'],900)
        self.assertEqual(result['top_k']['lift_over_all'],-300)
        self.assertEqual(result['top_k']['lift_over_baseline'],-300)
        self.assertEqual(result['effectiveness_claim'],'not established')

    def test_forecast_errors_not_score_errors(self):
        result=self.evaluate()['forecasts']
        self.assertEqual(result['unit'],'CNY')
        self.assertEqual(result['model']['sample_count'],4)
        self.assertEqual(result['model']['mae'],100)
        self.assertAlmostEqual(result['model']['rmse'],math.sqrt(15000))
        self.assertEqual(result['declared_baseline']['mae'],425)
        self.assertEqual(result['model']['mean_bias'],50)

    def test_numeric_metric_overflow_is_rejected(self):
        with self.assertRaises(ValidationError):
            forecast_errors([1e308],[-1e308])
        self.assertEqual(forecast_errors([1e200],[0])['rmse'],1e200)

    def test_no_predictions_no_mae(self):
        self.reset_snapshot([])
        self.assertIsNone(self.evaluate()['forecasts'])

    def test_partial_forecasts_have_explicit_count(self):
        self.reset_snapshot(self.predictions[:1])
        result=self.evaluate()['forecasts']
        self.assertEqual(result['model']['sample_count'],1)
        self.assertEqual(result['candidate_ids'],['business-A'])

    def test_insufficient_samples_and_synthetic_warning(self):
        warnings=' '.join(self.evaluate()['warnings'])
        self.assertIn('Insufficient',warnings)
        self.assertIn('SYNTHETIC',warnings)

    def test_prediction_units_checked_before_freeze(self):
        self.predictions[0]['unit']='USD'
        with self.assertRaisesRegex(ValidationError,'unit mismatch'):
            snapshot(self.doc,self.predictions)

    def test_prediction_duplicate_rejected(self):
        self.predictions.append(copy.deepcopy(self.predictions[0]))
        with self.assertRaises(ValidationError):
            snapshot(self.doc,self.predictions)

    def test_prediction_needs_baseline_basis(self):
        del self.predictions[0]['baseline_basis']
        with self.assertRaises(ValidationError):
            snapshot(self.doc,self.predictions)

    def test_wrong_snapshot_outcomes_rejected(self):
        self.outcomes['snapshot_id']='other'
        with self.assertRaises(ValidationError):
            self.evaluate()

    def test_wrong_measure_rejected(self):
        self.outcomes['success_measure']='revenue'
        with self.assertRaises(ValidationError):
            self.evaluate()

    def test_outcome_unit_mismatch_rejected(self):
        self.outcomes['outcomes'][0]['observation']['unit']='USD'
        with self.assertRaisesRegex(ValidationError,'unit mismatch'):
            self.evaluate()

    def test_outcome_estimate_is_not_actual(self):
        self.outcomes['outcomes'][0]['observation']['kind']='estimated'
        with self.assertRaisesRegex(ValidationError,'not actual'):
            self.evaluate()

    def test_mixed_synthetic_and_observed_outcomes_rejected(self):
        self.outcomes['outcomes'][0]['observation']['kind']='observed'
        with self.assertRaisesRegex(ValidationError,'mix'):
            self.evaluate()

    def test_outcome_horizon_must_match(self):
        self.outcomes['outcomes'][0]['observation']['observation_window']['start']='2026-10-24T00:00:00+08:00'
        with self.assertRaisesRegex(ValidationError,'horizon mismatch'):
            self.evaluate()

    def test_early_and_unavailable_outcomes_rejected(self):
        self.outcomes['as_of']='2026-10-30T00:00:00+08:00'
        with self.assertRaises(ValidationError):
            self.evaluate()
        self.outcomes['as_of']='2026-11-23T00:00:00+08:00'
        with self.assertRaisesRegex(ValidationError,'after as_of'):
            self.evaluate()

    def test_future_feature_cannot_be_frozen(self):
        self.doc['candidates'][0]['observations']['price']['observed_at']='2026-10-24T00:00:00+08:00'
        with self.assertRaisesRegex(ValidationError,'after as_of'):
            snapshot(self.doc)

    def test_missing_outcomes_explicit_coverage(self):
        self.outcomes['outcomes'].pop(0)
        report=self.evaluate()
        self.assertEqual(report['coverage'],.75)
        self.assertEqual(report['missing_outcomes'],['business-A'])
        self.assertIn('survivorship',' '.join(report['warnings']))

    def test_duplicate_outcomes_rejected(self):
        self.outcomes['outcomes'].append(copy.deepcopy(self.outcomes['outcomes'][0]))
        with self.assertRaises(ValidationError):
            self.evaluate()

    def test_minimize_outcome_ranking(self):
        self.doc['goal']['direction']='minimize'
        self.reset_snapshot()
        self.assertAlmostEqual(self.evaluate()['spearman'],.5)

    def test_target_outcome_ranking(self):
        self.doc['goal'].update(direction='target',target=600)
        self.reset_snapshot()
        self.assertAlmostEqual(self.evaluate()['spearman'],.5)

    def test_spearman_with_ties(self):
        self.assertAlmostEqual(spearman([1,1,3],[1,2,3]), math.sqrt(.75))
        self.assertEqual(spearman([1,2,3],[3,2,1]),-1)
        self.assertIsNone(spearman([1,1],[1,2]))
        self.assertIsNone(spearman([1],[2]))

    def test_top_k_fractional_tie_boundary(self):
        for dim in self.doc['dimensions']:
            dim['weight']=1 if dim['id']=='economics' else 0
        for cid in [0,1,2]:
            self.doc['candidates'][cid]['observations']['price']['value']=60
        self.reset_snapshot()
        top=self.evaluate()['top_k']['composite']
        self.assertTrue(all(abs(w-1/3)<1e-12 for w in top['inclusion_weights'].values()))
        self.assertAlmostEqual(top['mean_actual'],900)

    def test_invalid_top_k_rejected(self):
        self.doc['validation']['top_k']=4
        self.reset_snapshot()
        with self.assertRaisesRegex(ValidationError,'top_k'):
            self.evaluate()

    def test_both_domain_outcome_fixtures_replay(self):
        for name in ['business','content']:
            doc=fixture(name)
            preds=json.loads((ROOT/f'examples/{name}_predictions.json').read_text())
            outcomes=json.loads((ROOT/f'examples/{name}_outcomes.json').read_text())
            evaluate_history(snapshot(doc,preds),outcomes)
