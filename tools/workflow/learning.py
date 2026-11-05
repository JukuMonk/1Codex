"""Evidence-based improvement decisions. Does not rewrite skills or publish changes."""
import argparse
import json
from pathlib import Path
import sys
try:
    from .analyze_timing import analyze
except ImportError:
    from analyze_timing import analyze


def compare_runs(paths, baseline, candidate):
    report=analyze(paths);results=[]
    for group in report['groups']:
        a=group['revisions'].get(baseline);b=group['revisions'].get(candidate)
        if not a or not b:continue
        runs=group['runs']
        def failure_rate(revision):
            values=[r for r in runs if r['revision']==revision]
            return sum(r['status']!='ok' for r in values)/len(values)
        decision='insufficient_samples'
        change=None
        if a['median_seconds'] and b['median_seconds'] is not None:
            change=100*(b['median_seconds']/a['median_seconds']-1)
        if min(a['samples'],b['samples'])>=5:
            if failure_rate(candidate)>failure_rate(baseline):decision='quality_regression'
            elif change is not None and change < -5:decision='improvement_candidate'
            elif change is not None and change > 5:decision='slower_review_tradeoff'
            else:decision='no_material_change'
        results.append({'scenario':group['scenario'],'environment':group['environment'],'dataset':group['dataset'],
            'baseline':a,'candidate':b,'median_change_percent':change,'decision':decision,
            'baseline_failure_rate':failure_rate(baseline),'candidate_failure_rate':failure_rate(candidate)})
    return {'baseline_revision':baseline,'candidate_revision':candidate,'comparisons':results,
        'invalid_runs':report['invalid_runs'],'incomplete_runs':report['incomplete_runs'],
        'note':'Descriptive comparison only. Review correctness, spread and changed work before adopting. No automatic publication.'}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True);p.add_argument('--baseline',required=True)
    p.add_argument('--candidate',required=True);p.add_argument('--hypothesis',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=compare_runs(list((args.project/'.platform/task-timings').glob('*.json')),args.baseline,args.candidate)
    result['hypothesis']=args.hypothesis
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
