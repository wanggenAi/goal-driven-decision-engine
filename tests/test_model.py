"""Contract, arithmetic, evidence and domain-independence acceptance tests."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gqde import ValidationError, score_document
from gqde.engine import _expression, _calculate
from gqde.model import normalize, shares

ROOT = Path(__file__).resolve().parents[1]


def fixture(name='business'):
    return json.loads((ROOT / 'examples' / f'{name}.json').read_text())


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.doc = fixture()
        self.metric = self.doc['dimensions'][0]['metrics'][0]
        self.obs = self.doc['candidates'][0]['observations']['price']

    def assert_invalid(self, doc=None):
        with self.assertRaises(ValidationError):
            score_document(self.doc if doc is None else doc)

    def test_gqm_trace_complete(self):
        report = score_document(self.doc)
        for row in report['results']:
            for mid, metric in row['metrics'].items():
                self.assertTrue(metric['question_ids'])
                for qid in metric['question_ids']:
                    question = next(q for q in report['questions'] if q['id'] == qid)
                    self.assertEqual(question['goal_id'], report['goal']['id'])
                    self.assertIn(mid, question['metrics'])
                self.assertTrue(set(metric['inputs']) <= row['evidence'].keys())

    def test_orphan_metric_rejected(self):
        self.doc['questions'].pop(0)
        self.assert_invalid()

    def test_question_unknown_goal_rejected(self):
        self.doc['questions'][0]['goal_id'] = 'missing'
        self.assert_invalid()

    def test_question_unknown_metric_rejected(self):
        self.doc['questions'][0]['metrics'] = ['unknown']
        self.assert_invalid()

    def test_duplicate_question_rejected(self):
        self.doc['questions'].append(copy.deepcopy(self.doc['questions'][0]))
        self.assert_invalid()

    def test_required_goal_fields(self):
        for key in self.doc['goal']:
            with self.subTest(key=key):
                doc = copy.deepcopy(self.doc)
                del doc['goal'][key]
                self.assert_invalid(doc)

    def test_unknown_fields_rejected(self):
        self.metric['wieght'] = 1
        self.assert_invalid()

    def test_schema_version_rejected(self):
        for value in [None, '3.0', 2, [], '']:
            with self.subTest(value=value):
                self.doc['schema_version'] = value
                self.assert_invalid()

    def test_model_shape_rejected(self):
        for key in ['goal', 'questions', 'dimensions', 'candidates', 'inputs', 'decision', 'validation', 'gates']:
            with self.subTest(key=key):
                doc = copy.deepcopy(self.doc)
                doc[key] = None
                self.assert_invalid(doc)

    def test_duplicate_ids_rejected(self):
        for section in ['candidates', 'dimensions']:
            doc = copy.deepcopy(self.doc)
            doc[section].append(copy.deepcopy(doc[section][0]))
            self.assert_invalid(doc)
        self.doc['dimensions'][1]['metrics'][0]['id'] = 'unit_profit'
        self.assert_invalid()

    def test_expression_names_must_match_inputs(self):
        self.metric['inputs'] = ['price']
        self.assert_invalid()

    def test_unused_input_rejected(self):
        self.doc['inputs']['extra'] = {'unit': '1', 'description': 'unused'}
        self.assert_invalid()

    def test_missing_input_not_zero_filled(self):
        del self.doc['candidates'][0]['observations']['price']
        self.assert_invalid()

    def test_observation_metadata_required(self):
        for key in ['unit','source','observed_at','kind','independently_verified']:
            doc = copy.deepcopy(self.doc)
            del doc['candidates'][0]['observations']['price'][key]
            self.assert_invalid(doc)

    def test_unit_mismatch(self):
        self.obs['unit'] = 'USD/unit'
        self.assert_invalid()

    def test_source_whitespace_rejected(self):
        self.obs['source'] = '  '
        self.assert_invalid()

    def test_future_and_naive_observations_rejected(self):
        for value in ['2026-10-23T09:00:00+08:00','2026-10-22T09:00:00', 'not-a-date']:
            self.obs['observed_at'] = value
            self.assert_invalid()

    def test_future_observation_window_rejected(self):
        self.obs['observation_window']['end'] = '2026-10-23T00:00:00+08:00'
        self.assert_invalid()

    def test_noncomparable_windows_rejected(self):
        self.obs['observation_window']['start'] = '2026-09-21T00:00:00+08:00'
        self.assert_invalid()

    def test_timezone_equivalent_windows_accepted(self):
        self.obs['observation_window'] = {'start':'2026-09-21T16:00:00Z', 'end':'2026-10-21T16:00:00Z'}
        score_document(self.doc)

    def test_required_window_rejected(self):
        for candidate in self.doc['candidates']:
            del candidate['observations']['price']['observation_window']
        self.assert_invalid()

    def test_stale_evidence_is_hard_failure(self):
        self.metric['evidence_requirements']['max_age_hours'] = .5
        report = score_document(self.doc)
        self.assertTrue(all(r['status'] == 'BLOCKED' for r in report['results']))
        self.assertTrue(any(g['rule'] == 'max_age_hours' for g in report['results'][0]['failed_gates']))

    def test_verification_requirement_is_hard_failure(self):
        self.metric['evidence_requirements']['independently_verified'] = True
        self.assertTrue(all(r['status']=='BLOCKED' for r in score_document(self.doc)['results']))

    def test_synthetic_cannot_be_claimed_verified(self):
        self.obs['independently_verified'] = True
        self.assert_invalid()

    def test_boolean_verification_not_string(self):
        self.obs['independently_verified'] = 'false'
        self.assert_invalid()

    def test_allowed_kind_requirement(self):
        self.metric['evidence_requirements']['allowed_kinds'] = ['observed']
        self.assertTrue(all(r['status']=='BLOCKED' for r in score_document(self.doc)['results']))

    def test_verified_observed_evidence_can_qualify(self):
        for c in self.doc['candidates']:
            for o in c['observations'].values():
                o.update(kind='observed', independently_verified=True, source='manual:test-fixture-not-real')
        self.doc['decision']['min_score']=60
        self.assertEqual(next(r for r in score_document(self.doc)['results'] if r['id']=='business-B')['status'], 'ELIGIBLE')

    def test_unverified_observed_evidence_needs_review(self):
        for c in self.doc['candidates']:
            for o in c['observations'].values():
                o['kind']='observed'
        self.assertEqual(score_document(self.doc)['results'][0]['status'], 'NEEDS_EVIDENCE')

    def test_invalid_numeric_values(self):
        for value in [True, None, '12', math.nan, math.inf, -math.inf, 10**400]:
            self.obs['value']=value
            self.assert_invalid()

    def test_negative_counts_rejected(self):
        self.doc['candidates'][0]['observations']['refunds']['value']=-1
        self.assert_invalid()

    def test_zero_denominator_rejected(self):
        self.doc['candidates'][0]['observations']['previous']['value']=0
        self.assert_invalid()

    def test_safe_arithmetic(self):
        tree, names=_expression('-(a - 2) / b + 3 * a')
        self.assertEqual(names, {'a','b'})
        self.assertEqual(_calculate(tree, {'a':4,'b':2}),11)

    def test_unsafe_expressions_rejected(self):
        for expression in ["__import__('os')",'price.__class__','price[0]','2**1000','[x for x in y]',
                           'True', '1 if price else 0', 'lambda: 1','1 < price','1e999','abs(price)']:
            self.metric['expression']=expression
            self.assert_invalid()

    def test_arithmetic_overflow_rejected(self):
        tree,_=_expression('a * b')
        with self.assertRaises(ValidationError):
            _calculate(tree, {'a':1e308,'b':1e308})

    def test_division_zero_in_expression(self):
        tree,_=_expression('a / b')
        with self.assertRaisesRegex(ValidationError,'division by zero'):
            _calculate(tree, {'a':1,'b':0})

    def test_min_max_normalization(self):
        spec={'method':'min_max','low':10,'high':30,'basis':'test'}
        self.assertEqual(normalize(15,spec,'higher'),25)
        self.assertEqual(normalize(15,spec,'lower'),75)
        self.assertEqual(normalize(-100,spec,'higher'),0)
        self.assertEqual(normalize(100,spec,'higher'),100)

    def test_target_normalization(self):
        spec={'method':'target','target':10,'tolerance':4,'basis':'test'}
        for value, expected in [(10,100),(8,50),(12,50),(6,0),(20,0)]:
            self.assertEqual(normalize(value,spec,'target'),expected)

    def test_invalid_normalization(self):
        for spec,direction in [({'method':'bad'},'higher'),
          ({'method':'min_max','low':1,'high':1,'basis':'test'},'higher'),
          ({'method':'min_max','low':-1e308,'high':1e308,'basis':'test'},'higher'),
          ({'method':'min_max','low':0,'high':1,'basis':'test'},'target'),
          ({'method':'target','target':1,'tolerance':0,'basis':'test'},'target'),
          ({'method':'target','target':1,'tolerance':1,'basis':'test'},'higher')]:
            with self.assertRaises(ValidationError):
                normalize(0,spec,direction)

    def test_extreme_normalization_clips_safely(self):
        self.assertEqual(normalize(1e308,{'method':'min_max','low':-10,'high':10,'basis':'test'},'higher'),100)

    def test_effective_weights_sum_and_contributions(self):
        report=score_document(self.doc)
        expected={'unit_profit':.4,'growth':.25,'refund_rate':.2,'competition':.15}
        for mid, weight in expected.items():
            self.assertAlmostEqual(report['effective_weights'][mid],weight)
        for row in report['results']:
            self.assertAlmostEqual(sum(m['contribution'] for m in row['metrics'].values()), row['score'])
            self.assertAlmostEqual(sum(d['contribution'] for d in row['dimensions'].values()), row['score'])

    def test_weight_boundaries(self):
        for bad in [-1,True,math.nan, math.inf,'1']:
            self.metric['weight']=bad
            self.assert_invalid()
        self.metric['weight']=0
        self.assert_invalid()  # its dimension has no remaining positive metric

    def test_zero_weight_metric_allowed_with_positive_sum(self):
        self.doc['dimensions'][2]['metrics'][1]['weight']=0
        self.assertEqual(score_document(self.doc)['effective_weights']['competition'],0)

    def test_large_weights_do_not_overflow(self):
        weights=shares({'a':1e308,'b':1e308})
        self.assertEqual(weights,{'a':.5,'b':.5})

    def test_hard_gate_uses_full_precision(self):
        self.doc['gates'][0]['value']=44.99999995
        row=next(r for r in score_document(self.doc)['results'] if r['id']=='business-A')
        self.assertFalse(any(g.get('id')=='positive_margin' for g in row['failed_gates']))
        self.doc['gates'][0]['value']=45.00000001
        row=next(r for r in score_document(self.doc)['results'] if r['id']=='business-A')
        self.assertEqual(row['status'],'BLOCKED')

    def test_gate_failure_cannot_be_outweighed(self):
        self.doc['dimensions'][0]['weight']=0
        row=next(r for r in score_document(self.doc)['results'] if r['id']=='business-D')
        self.assertAlmostEqual(row['score'],100)
        self.assertEqual(row['status'],'BLOCKED')
        self.assertIsNone(row['rank'])

    def test_unknown_gate_rejected(self):
        self.doc['gates'][0]['metric']='unknown'
        self.assert_invalid()

    def test_goal_direction_target(self):
        self.doc['goal'].update(direction='target',target=1000)
        score_document(self.doc)
        del self.doc['goal']['target']
        self.assert_invalid()

    def test_historical_feature_window_not_future(self):
        self.doc['goal']['evaluation_window']['start']='2026-10-21T00:00:00+08:00'
        self.assert_invalid()

    def test_cross_domain_same_kernel(self):
        business=score_document(self.doc)
        content=score_document(fixture('content'))
        self.assertEqual(business['engine_version'], content['engine_version'])
        self.assertEqual(business['results'][0]['id'],'business-B')
        self.assertAlmostEqual(business['results'][0]['score'],71)
        self.assertEqual(content['results'][0]['id'],'content-B')
        self.assertAlmostEqual(content['results'][0]['score'],72.875)
        self.assertTrue(all(o['kind']=='synthetic' for r in content['results'] for o in r['evidence'].values()))

    def test_score_does_not_mutate_input(self):
        before=copy.deepcopy(self.doc)
        self.assertEqual(score_document(self.doc),score_document(self.doc))
        self.assertEqual(before,self.doc)
