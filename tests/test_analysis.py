import copy
import unittest
from test_model import fixture
from gqde import ValidationError
from gqde.analysis import sensitivity, what_if, ranking


class AnalysisTests(unittest.TestCase):
    def test_known_rank_reversal_and_winner_stability(self):
        result=sensitivity(fixture(),.05)
        self.assertEqual(result['baseline']['winners'],['business-B'])
        self.assertEqual(result['scenario_count'],8)
        self.assertEqual(result['first_place_stability'],.75)
        scenario=next(s for s in result['scenarios'] if s['metric']=='unit_profit' and s['actual_delta']>0)
        self.assertEqual(scenario['winners'],['business-C'])
        self.assertAlmostEqual(scenario['effective_weights']['unit_profit'],.45)
        self.assertAlmostEqual(sum(scenario['effective_weights'].values()),1)
        self.assertEqual(result['rank_ranges']['business-C'],{'best':1,'worst':2})
        self.assertIn('unit_profit',[r['metric'] for r in result['sensitive_metrics']])

    def test_deterministic_and_no_input_mutation(self):
        doc=fixture(); original=copy.deepcopy(doc)
        self.assertEqual(sensitivity(doc),sensitivity(doc))
        self.assertEqual(doc,original)

    def test_blocked_candidate_never_in_sensitivity_ranking(self):
        doc=fixture();doc['dimensions'][0]['weight']=0
        result=sensitivity(doc)
        self.assertNotIn('business-D',result['baseline']['order'])
        self.assertTrue(all('business-D' not in s['order'] for s in result['scenarios']))

    def test_stable_first_does_not_mean_stable_full_ranking(self):
        report=sensitivity(fixture('content'))
        self.assertEqual(report['first_place_stability'],1)
        self.assertTrue(report['sensitive_metrics'])

    def test_invalid_delta(self):
        for delta in [0,1,-.1,True,float('nan'),'0.1']:
            with self.assertRaises(ValidationError):
                sensitivity(fixture(),delta)

    def test_exact_ties_are_not_broken_into_false_winner(self):
        ranks=ranking({'z':10,'a':10,'b':0})
        self.assertEqual(ranks['ranks'],{'a':1,'z':1,'b':3})
        self.assertEqual(ranks['winners'],['a','z'])
        doc=fixture();doc['candidates'][1]['observations']=copy.deepcopy(doc['candidates'][0]['observations'])
        doc['candidates'][2]['observations']=copy.deepcopy(doc['candidates'][0]['observations'])
        report=sensitivity(doc)
        self.assertIsNone(report['first_place_stability'])
        self.assertEqual(report['top_set_stability'],1)

    def test_no_feasible_candidates(self):
        doc=fixture();doc['gates'][0]['value']=1000
        report=sensitivity(doc)
        self.assertEqual(report['baseline']['order'],[])
        self.assertIsNone(report['first_place_stability'])
        self.assertIsNone(report['top_set_stability'])

    def test_boundary_weights_remain_finite_and_nonnegative(self):
        doc=fixture()
        for d in doc['dimensions']:
            d['weight']=1 if d['id']=='economics' else 0
        report=sensitivity(doc,.9)
        for scenario in report['scenarios']:
            self.assertAlmostEqual(sum(scenario['effective_weights'].values()),1)
            self.assertTrue(all(w>=0 for w in scenario['effective_weights'].values()))

    def test_input_counterfactual_rechecks_gates(self):
        doc=fixture();before=copy.deepcopy(doc)
        report=what_if(doc,{'candidate_id':'business-B','inputs':{'fees':35}})
        row=next(r for r in report['report']['results'] if r['id']=='business-B')
        self.assertEqual(row['status'],'BLOCKED')
        self.assertEqual(row['evidence']['fees']['kind'],'synthetic')
        self.assertEqual(doc,before)

    def test_weight_counterfactual(self):
        report=what_if(fixture(),{'metric_weights':{'refund_rate':0}})
        self.assertEqual(report['report']['effective_weights']['refund_rate'],0)
        self.assertNotEqual(report['score_changes']['business-A']['delta'],0)

    def test_bad_counterfactual_rejected(self):
        for changes in [{},{'candidate_id':'unknown','inputs':{'fees':1}},
                        {'candidate_id':'business-B','inputs':{'fake':1}},
                        {'metric_weights':{'unit_profit':-1}},{'metric_weights':{'fake':1}}]:
            with self.assertRaises(ValidationError):
                what_if(fixture(),changes)
