"""Reject malformed, duplicate or older stable versions before a marketplace build."""
import argparse
import json
import re
import subprocess


def version_tuple(value):
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',value):
        raise ValueError('Stable version must be MAJOR.MINOR.PATCH without leading zeros')
    return tuple(map(int,value.split('.')))


def validate(candidate, previous=None):
    value=version_tuple(candidate)
    if previous is not None and value<=version_tuple(previous):
        raise ValueError('Stable version must increase: '+candidate+' <= '+previous)
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--version',required=True)
    p.add_argument('--previous-version');p.add_argument('--previous-ref')
    args=p.parse_args()
    if args.previous_version and args.previous_ref:p.error('Choose one previous version source')
    previous=args.previous_version
    if args.previous_ref:
        # Missing/malformed history is an error, never silently treated as first publication.
        raw=subprocess.check_output(['git','show',args.previous_ref+':plugins/1codex/plugin.json'])
        previous=json.loads(raw)['version']
    validate(args.version,previous)
    print(json.dumps({'version':args.version,'previous':previous,'status':'PASS'}))


if __name__=='__main__':main()
