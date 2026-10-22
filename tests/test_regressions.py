"""Regressions for baseline defects and metadata isolation found in review."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from test_model import fixture, ROOT
from gqde import ValidationError, score_document
from gqde.evaluate import evaluate_csv
from gqde.history import snapshot, verify_snapshot, forecast_errors, spearman, save_snapshot


class RegressionTests(unittest.TestCase):
    def legacy(self):
        return json.loads((ROOT/'examples/candidates.json').read_text())

    def test_legacy_small_positive_margin_not_rounded_into_gate_failure(self):
        doc=self.legacy()
        obs=doc['candidates'][0]['observations']
        obs['sale_price']['value']=40.0000001
        obs['purchase_cost']['value']=28
        obs['fees']['value']=4
        obs['service_cost']['value']=8
        row=next(r for r in score_document(doc)['results'] if r['id']=='fictional-A')
        self.assertFalse(any(g['metric']=='unit_profit' for g in row['failed_gates']))
        self.assertEqual(row['status'],'NEEDS_EVIDENCE')

    def test_legacy_near_boundary_violation_not_rounded_into_pass(self):
        doc=self.legacy()
        doc['candidates'][0]['observations']['refund_count']['value']=7.0000001
        row=next(r for r in score_document(doc)['results'] if r['id']=='fictional-A')
        self.assertTrue(any(g['metric']=='refund_rate' for g in row['failed_gates']))
        self.assertEqual(row['status'],'BLOCKED')

    def test_legacy_large_weight_multiplication_stays_finite(self):
        doc=self.legacy()
        doc['dimensions'][0]['weight']=1e307
        self.assertTrue(0 <= score_document(doc)['results'][0]['score'] <=100)

    def test_legacy_unrepresentable_span_rejected(self):
        doc=self.legacy()
        doc['dimensions'][0]['metrics'][0]['normalize'].update(low=-1e308,high=1e308)
        with self.assertRaisesRegex(ValidationError,'finite'):
            score_document(doc)

    def test_legacy_forecast_rmse_avoids_unnecessary_square_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'large.csv'
            path.write_text('candidate_id,predicted,actual\na,1e200,0\n')
            self.assertEqual(evaluate_csv(path)['rmse'],1e200)

    def test_snapshot_and_report_do_not_alias_model_metadata(self):
        doc=fixture()
        saved=snapshot(doc)
        original=copy.deepcopy(saved)
        doc['dimensions'][0]['metrics'][0]['normalize']['low']=-100
        doc['dimensions'][0]['metrics'][0]['inputs'].append('extra')
        doc['dimensions'][0]['metrics'][0]['evidence_requirements']['max_age_hours']=1
        self.assertEqual(saved,original)
        verify_snapshot(saved)

    def test_invalid_statistical_samples_rejected(self):
        for fn in (spearman,forecast_errors):
            for x,y in [([],[]),([1],[1,2]),([float('nan')],[1]),([True],[1])]:
                with self.assertRaises(ValidationError):
                    fn(x,y)

    def test_invalid_snapshot_not_saved(self):
        saved=snapshot(fixture());saved['report']['results'][0]['score']=999
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json'
            with self.assertRaises(ValidationError):
                save_snapshot(saved,path)
            self.assertFalse(path.exists())

    def test_malformed_contract_fields_fail_with_validation_error(self):
        base=fixture()
        paths=[['goal','direction'],['gates',0,'op'],['gates',0,'metric'],['validation','baseline_metric'],
               ['dimensions',0,'metrics',0,'direction'],['candidates',0,'observations','price','kind']]
        for path in paths:
            for bad in [None,[],{},True,'',0]:
                doc=copy.deepcopy(base);value=doc
                for part in path[:-1]:
                    value=value[part]
                value[path[-1]]=bad
                with self.subTest(path=path,bad=bad),self.assertRaises(ValidationError):
                    score_document(doc)
