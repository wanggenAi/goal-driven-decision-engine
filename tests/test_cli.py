import contextlib
import io
import json
import tempfile
from pathlib import Path
import unittest
from test_model import fixture, ROOT
from gqde.cli import main, load_json
from gqde import ValidationError, score_document
from gqde.reporting import markdown


class CLITests(unittest.TestCase):
    def run_cli(self,*args):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=main(list(args))
        return code,out.getvalue(),err.getvalue()

    def test_all_readonly_commands(self):
        path=str(ROOT/'examples/business.json')
        for args in [('score',path),('score',path,'--sensitivity'),('validate',path),('sensitivity',path),
                     ('what-if',path,str(ROOT/'examples/business_changes.json')),
                     ('evaluate',str(ROOT/'examples/outcomes.csv'))]:
            with self.subTest(command=args[0]):
                code,out,err=self.run_cli(*args)
                self.assertEqual(code,0,err)
                self.assertTrue(json.loads(out))

    def test_snapshot_history_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            saved=str(Path(directory)/'snapshot.json')
            code,_,err=self.run_cli('snapshot',str(ROOT/'examples/business.json'),'--predictions',
                                    str(ROOT/'examples/business_predictions.json'),'--output',saved)
            self.assertEqual(code,0,err)
            code,out,err=self.run_cli('history',saved,str(ROOT/'examples/business_outcomes.json'))
            self.assertEqual(code,0,err)
            self.assertEqual(json.loads(out)['spearman'],-.5)
            code,_,_=self.run_cli('snapshot',str(ROOT/'examples/business.json'),'--output',saved)
            self.assertEqual(code,2)

    def test_markdown_has_trace_evidence_and_uncertainty(self):
        result=markdown(score_document(fixture()))
        for word in ['Composite scores are not success probabilities','synthetic','unit_profit','price - cost - fees',
                     'Largest weighted','Failed hard constraints','Uncertainties','source=', 'observed_at=']:
            self.assertIn(word,result)

    def test_markdown_cli_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output=str(Path(directory)/'report.md')
            code,out,err=self.run_cli('score',str(ROOT/'examples/content.json'),'--sensitivity','--format','markdown','--output',output)
            self.assertEqual(code,0,err)
            self.assertEqual(out,'')
            self.assertIn('Weight robustness',Path(output).read_text())

    def test_bad_file_and_schema_returns_two(self):
        self.assertEqual(self.run_cli('score','/nonexistent/model.json')[0],2)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json'
            path.write_text('{"schema_version":"wrong"}')
            self.assertEqual(self.run_cli('score',str(path))[0],2)

    def test_strict_json_rejects_duplicate_keys_and_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json'
            for value in ['{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}']:
                path.write_text(value)
                with self.assertRaises(ValidationError):
                    load_json(path)

    def test_markdown_escapes_table_cells(self):
        doc=fixture();doc['candidates'][0]['id']='a|b\nc'
        result=markdown(score_document(doc))
        self.assertIn('a\\|b c',result)
