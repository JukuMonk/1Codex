"""Bounded read-only capture of new error texts from local 1C 8.5 .lgp logs."""
import re
from pathlib import Path


def cursor(database):
    return {str(p): p.stat().st_size for p in (Path(database)/'1Cv8Log').glob('*.lgp')}


def quoted(text, start):
    result = []
    i = start
    while i < len(text):
        if text[i] == '"':
            if i + 1 < len(text) and text[i+1] == '"':
                result.append('"'); i += 2; continue
            return ''.join(result)
        result.append(text[i]); i += 1
    return None  # Incomplete record is not a proven error text.


def collect(database, before, needle, secrets=(), limit=1024*1024):
    if not needle:
        return []
    results = []
    for path in sorted((Path(database)/'1Cv8Log').glob('*.lgp')):
        size = path.stat().st_size
        offset = before.get(str(path), 0)
        if size < offset:  # Log was replaced/truncated during this run.
            continue
        with path.open('rb') as stream:
            stream.seek(max(offset, size-limit))
            text = stream.read(limit).decode('utf-8-sig', errors='replace')
        for record in re.split(r'(?m)(?=^\{\d{14},)', text):
            header = re.match(r'^\{\d{14},[^"\n]*(?:\n[^"\n]*){0,3}?,E,"', record)
            if not header:
                continue
            message = quoted(record, header.end())
            if not message or needle not in message or 'ВнешняяОбработка.ТестUIМенеджер.' in message:
                continue
            for secret in secrets:
                if secret:
                    message = message.replace(secret, '[REDACTED]')
            if message not in results:
                results.append(message)
    return results
