"""Execute both synthetic domains through the same kernel and save audit artifacts."""
import argparse
import json
from pathlib import Path

from gqde import score_document
from gqde.analysis import sensitivity, what_if
from gqde.history import evaluate_history, save_snapshot, snapshot
from gqde.reporting import markdown


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    # A fresh directory keeps decision snapshots from being overwritten.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent
    def load(filename):
        return json.loads((root / filename).read_text(encoding='utf-8'))
    def save(filename, value):
        (args.output_dir / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    summaries = {}
    for domain in ('business', 'content'):
        document = load(domain+'.json')
        report = score_document(document)
        report['sensitivity'] = sensitivity(document)
        frozen = snapshot(document, load(domain+'_predictions.json'))
        save_snapshot(frozen, args.output_dir / (domain+'.snapshot.json'))
        history = evaluate_history(frozen, load(domain+'_outcomes.json'))
        save(domain+'.report.json', report)
        save(domain+'.history.json', history)
        (args.output_dir / (domain+'.report.md')).write_text(markdown(report), encoding='utf-8')
        summaries[domain] = {'data_kind':'synthetic', 'snapshot_id':frozen['snapshot_id'],
                             'ranking':[{k:r[k] for k in ('id','score','rank','status')} for r in report['results']],
                             'first_place_stability':report['sensitivity']['first_place_stability'],
                             'spearman':history['spearman'], 'baseline_spearman':history['baseline_spearman'],
                             'top_k_lift_over_baseline':history['top_k']['lift_over_baseline'],
                             'effectiveness_claim':history['effectiveness_claim']}
    save('business.what-if.json', what_if(load('business.json'), load('business_changes.json')))
    save('summary.json',summaries)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
