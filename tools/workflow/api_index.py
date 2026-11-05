"""Incremental local HTML API index with platform/source identity and bounded results.

Accepts extracted platform help, not guessed HBK archive internals. Supply the
original archive as --archive to invalidate extracted help when HBK changes.
"""
from pathlib import Path
from html.parser import HTMLParser
import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing

SCHEMA = 2
MAX_FILE_BYTES = 2_000_000
MAX_TEXT = 200_000


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}: self.skip += 1
    def handle_endtag(self, tag):
        if tag in {'script', 'style'}: self.skip = max(0, self.skip - 1)
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def files(root):
    root = Path(root).resolve()
    if not root.is_dir(): raise ValueError('Extracted HTML source directory does not exist')
    result = {}
    for path in sorted(root.rglob('*')):
        if path.suffix.casefold() not in {'.html', '.htm'}: continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('API sources may not escape their root')
        if not path.is_file(): continue
        info = path.stat()
        result[path.relative_to(root).as_posix()] = [info.st_size, info.st_mtime_ns]
    return result


def identity(root, platform_version, archive=None):
    result = {'platform_version': platform_version, 'source_root': str(Path(root).resolve()),
              'files': files(root)}
    if archive:
        path = Path(archive).resolve()
        result['archive'] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def connect(path):
    connection = sqlite3.connect(str(path))
    connection.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS documents (path TEXT PRIMARY KEY, title TEXT, body TEXT, stat TEXT, sha256 TEXT)')
    connection.execute('CREATE TABLE IF NOT EXISTS tokens (token TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY(token,path)) WITHOUT ROWID')
    connection.execute('CREATE INDEX IF NOT EXISTS token_paths ON tokens(path)')
    return connection


def metadata(connection):
    return {k: json.loads(v) for k, v in connection.execute('SELECT key,value FROM metadata')}


def build_index(source_root, cache_path, platform_version, archive=None, progress=None):
    if not platform_version or not platform_version.strip(): raise ValueError('Platform version is required')
    root, cache = Path(source_root).resolve(), Path(cache_path).resolve()
    if cache.suffix.casefold() in {'.html', '.htm'}: raise ValueError('Cache cannot overwrite API HTML')
    wanted = identity(root, platform_version, archive)
    cache.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=cache.name + '.', suffix='.pending', dir=cache.parent)
    os.close(fd)
    connection = None
    try:
        # Build privately; a failed update leaves the previous index readable.
        if cache.is_file():
            with closing(sqlite3.connect(str(cache))) as previous:
                connection = connect(temporary)
                previous.backup(connection)
        else: connection = connect(temporary)
        old = metadata(connection)
        compatible = old.get('schema_version') == SCHEMA and old.get('identity', {}).get('source_root') == str(root) and old.get('identity', {}).get('platform_version') == platform_version
        if not compatible:
            connection.execute('DELETE FROM documents')
            connection.execute('DELETE FROM tokens')
        old_rows = dict(connection.execute('SELECT path,stat FROM documents'))
        parsed = 0
        skipped = []
        for index, (relative, stat) in enumerate(wanted['files'].items(), 1):
            encoded_stat = json.dumps(stat)
            if old_rows.get(relative) != encoded_stat:
                path = root / relative
                if stat[0] > MAX_FILE_BYTES:
                    skipped.append(relative)
                    connection.execute('DELETE FROM documents WHERE path=?', (relative,))
                    connection.execute('DELETE FROM tokens WHERE path=?', (relative,))
                    continue
                raw = path.read_bytes()
                html = raw.decode('utf-8-sig', errors='replace')
                parser = Text(); parser.feed(html)
                body = re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()[:MAX_TEXT]
                heading = re.search(r'<title[^>]*>(.*?)</title\s*>', html, re.I | re.S)
                title = re.sub('<[^>]+>', '', heading.group(1)).strip() if heading else Path(relative).stem
                connection.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?)',
                                   (relative, title, body, encoded_stat, hashlib.sha256(raw).hexdigest()))
                connection.execute('DELETE FROM tokens WHERE path=?', (relative,))
                words = set(re.findall(r'\w+', (relative + ' ' + title + ' ' + body).casefold()))
                connection.executemany('INSERT INTO tokens VALUES (?,?)', ((word, relative) for word in words))
                parsed += 1
            if progress and (index % 100 == 0 or index == len(wanted['files'])):
                progress({'processed': index, 'total': len(wanted['files']), 'parsed': parsed})
        for deleted in old_rows.keys() - wanted['files'].keys():
            connection.execute('DELETE FROM documents WHERE path=?', (deleted,))
            connection.execute('DELETE FROM tokens WHERE path=?', (deleted,))
        if identity(root, platform_version, archive) != wanted:
            raise ValueError('API source changed while indexing; previous cache retained')
        values = {'schema_version': SCHEMA, 'identity': wanted, 'skipped_oversize': skipped}
        for key, value in values.items():
            connection.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))
        count = connection.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        connection.commit(); connection.close(); connection = None
        os.replace(temporary, cache)
        return {'documents': count, 'parsed': parsed, 'reused': parsed == 0,
                'platform_version': platform_version, 'skipped_oversize': skipped}
    finally:
        if connection is not None: connection.close()
        if Path(temporary).exists(): Path(temporary).unlink()


def search_index(cache_path, query, platform_version, limit=10, max_excerpt=500, source_root=None):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50: raise ValueError('limit must be 1..50')
    if not isinstance(max_excerpt, int) or not 80 <= max_excerpt <= 2000: raise ValueError('excerpt must be 80..2000')
    terms = re.findall(r'\w+', query.casefold())
    if not terms or len(terms) > 12 or len(query) > 200: raise ValueError('Bounded nonempty query required')
    path = Path(cache_path)
    if not path.is_file(): raise ValueError('Build the API index first')
    connection = sqlite3.connect('file:' + path.resolve().as_posix() + '?mode=ro', uri=True)
    try:
        meta = metadata(connection)
        if meta.get('schema_version') != SCHEMA: raise ValueError('Unsupported API cache schema')
        recorded = meta['identity']
        if recorded['platform_version'] != platform_version: raise ValueError('Stale API cache: platform version changed')
        root = Path(source_root or recorded['source_root']).resolve()
        archive = recorded.get('archive', {}).get('path')
        if identity(root, platform_version, archive) != recorded: raise ValueError('Stale API cache: source changed; rebuild')
        matches = []
        # Indexed casefolded token prefixes support Russian without SQLite
        # extensions. Only matching documents are read; no HTML/body full scan.
        selects = ['SELECT path FROM tokens WHERE token>=? AND token<?' for _ in terms]
        sql = 'SELECT path,title,body,sha256 FROM documents WHERE path IN (' + ' INTERSECT '.join(selects) + ') ORDER BY path LIMIT ?'
        parameters = [value for term in terms for value in (term, term + '\U0010ffff')] + [limit]
        for relative, title, body, sha in connection.execute(sql, parameters):
            source = (root / relative).resolve()
            if not source.is_relative_to(root): raise ValueError('Unsafe path in API cache')
            if hashlib.sha256(source.read_bytes()).hexdigest() != sha:
                raise ValueError('Stale API cache: matched source content changed; rebuild')
            start = max(0, body.casefold().find(terms[0]) - max_excerpt // 4)
            matches.append({'path': relative, 'title': title, 'excerpt': body[start:start + max_excerpt],
                            'source_sha256': sha, 'platform_version': platform_version})
            if len(matches) == limit: break
        return {'matches': matches, 'limit': limit, 'platform_version': platform_version,
                'source_revalidated': True, 'skipped_oversize': meta.get('skipped_oversize', [])}
    finally: connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    build = sub.add_parser('build')
    build.add_argument('source', type=Path); build.add_argument('cache', type=Path)
    build.add_argument('--platform', required=True); build.add_argument('--archive', type=Path)
    search = sub.add_parser('search')
    search.add_argument('cache', type=Path); search.add_argument('query')
    search.add_argument('--platform', required=True); search.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    if args.operation == 'build':
        result = build_index(args.source, args.cache, args.platform, args.archive,
                             progress=lambda value: print(json.dumps({'progress': value}), flush=True))
    else: result = search_index(args.cache, args.query, args.platform, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
