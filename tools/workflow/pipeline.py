"""Local live monitor for one 1Codex timing journal, plus portable HTML export."""
import argparse
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
import webbrowser
from urllib.parse import urlsplit
from urllib.request import urlopen

try:
    from . import timing
    from .pipeline_model import CHAPTERS, atlas, snapshot
except ImportError:
    import timing
    from pipeline_model import CHAPTERS, atlas, snapshot


ASSETS = Path(__file__).with_name('pipeline_ui')


class MonitorServer(ThreadingHTTPServer):
    allow_reuse_address = os.name != 'nt'

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def bind_monitor(handler, port, ready):
    # Restore this journal's bookmark after the idle server exits.
    if ready and not port:
        try:
            saved = ready.read_text(encoding='ascii').strip()
        except (FileNotFoundError, UnicodeError):
            saved = ''
        match = re.fullmatch(r'http://127\.0\.0\.1:(\d{1,5})(/[0-9a-f]{32}/)', saved)
        if match and 1024 <= int(match[1]) <= 65535:
            try:
                return MonitorServer(('127.0.0.1', int(match[1])), handler), match[2]
            except OSError as exc:
                if exc.errno not in (errno.EADDRINUSE, errno.EACCES) and getattr(exc, 'winerror', None) not in (10013, 10048):
                    raise
    return MonitorServer(('127.0.0.1', port), handler), '/'+secrets.token_hex(16)+'/'

def read_state(journal):
    return snapshot(json.loads(Path(journal).read_text(encoding='utf-8')))


def page(state, live):
    bundle = dict(chapters=CHAPTERS, graphs=atlas(), state=state, live=live)
    # Text, including user-authored labels, stays data inside a non-executable script.
    data = json.dumps(bundle, ensure_ascii=False, separators=(',', ':')).replace('<', r'\u003c')
    template = (ASSETS / 'index.html').read_text(encoding='utf-8')
    return (template.replace('/* STYLES */', (ASSETS/'style.css').read_text(encoding='utf-8'))
            .replace('/* SCRIPT */', (ASSETS/'monitor.js').read_text(encoding='utf-8'))
            .replace('<!-- DATA -->', data))


def serve(journal, port, ready=None):
    initial = read_state(journal)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_GET(self):
            if self.headers.get('Host') != self.server.address:
                self.send_error(403)
                return
            if self.path not in (prefix, prefix+'state', prefix+'identity'):
                self.send_error(404)
                return
            try:
                if self.path.endswith('identity'):
                    body, mime = initial['run'], 'text/plain'
                else:
                    state = read_state(journal)
                    if self.path == prefix:
                        body, mime = page(state, True), 'text/html'
                    else:
                        body, mime = json.dumps(state, ensure_ascii=False), 'application/json'
            except (OSError, ValueError):
                self.send_error(503, 'Journal temporarily unavailable')
                return
            self.server.last_seen = time.monotonic()
            content = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', mime+'; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server, prefix = bind_monitor(Handler, port, ready)
    with server:
        server.address = f'127.0.0.1:{server.server_port}'
        url = 'http://' + server.address + prefix
        if ready:
            pending = ready.with_suffix('.pending')
            pending.write_text(url, encoding='ascii')
            pending.replace(ready)
        else:
            print(url, flush=True)
        server.timeout = 2
        server.last_seen = time.monotonic()
        while time.monotonic() - server.last_seen < 1800:
            server.handle_request()


def existing_url(ready, run):
    try:
        url = ready.read_text(encoding='ascii').strip()
        parts = urlsplit(url)
        if parts.scheme != 'http' or parts.hostname != '127.0.0.1' or not parts.port:
            return None
        with urlopen(url+'identity', timeout=.6) as response:
            if response.read(80).decode('ascii') == run:
                return url
    except (OSError, ValueError):
        pass
    return None


def open_monitor(journal):
    journal = Path(journal).resolve()
    run = read_state(journal)['run']
    folder = journal.parent / '.monitors'
    folder.mkdir(exist_ok=True)
    ready = folder / (journal.stem+'.url')
    with timing.base_lease(folder, ready):
        url = existing_url(ready, run)
        if url:
            return url
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'serve', str(journal),
                                 '--ready', str(ready)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, **options)
        for _ in range(100):
            url = existing_url(ready, run)
            if url:
                return url
            if proc.poll() is not None:
                break
            time.sleep(.05)
        if proc.poll() is None:
            proc.terminate()
        raise RuntimeError('Could not start monitor. Run pipeline.py serve JOURNAL for diagnostics.')


def run_command(journal, name, node, command, parent=None, after=None):
    """Run an external check with its regular console and exit code. Do not store argv."""
    if not command:
        raise ValueError('--cmd needs an executable and its arguments')
    stage = timing.begin(journal, name, parent, node=node, after=after)
    outcome = 'failed'
    try:
        code = subprocess.run(command).returncode
        if code:
            timing.signal(journal, stage, 'warning', 'Команда вернула код '+str(code))
        else:
            outcome = 'ok'
        return code
    except KeyboardInterrupt:
        outcome = 'interrupted'
        raise
    finally:
        timing.end(journal, stage, outcome)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    start = commands.add_parser('start')
    start.add_argument('--project', required=True, type=Path)
    start.add_argument('--label', required=True)
    start.add_argument('--no-browser', action='store_true', help='Print the URL for an app panel or headless host')
    for key in ('scenario','environment','dataset','revision'):
        start.add_argument('--'+key)
    run = commands.add_parser('run')
    run.add_argument('journal', type=Path)
    run.add_argument('--name', required=True)
    run.add_argument('--node', required=True)
    run.add_argument('--parent')
    run.add_argument('--after')
    run.add_argument('--cmd', required=True, nargs=argparse.REMAINDER)
    for action in ('open','serve','export'):
        command = commands.add_parser(action)
        command.add_argument('journal', type=Path)
        if action == 'open':
            command.add_argument('--no-browser', action='store_true', help='Print the URL without opening a tab')
        if action == 'serve':
            command.add_argument('--port', type=int, default=0)
            command.add_argument('--ready', type=Path, help=argparse.SUPPRESS)
        if action == 'export':
            command.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.action == 'run':
        return run_command(args.journal, args.name, args.node, args.cmd, args.parent, args.after)
    if args.action == 'serve':
        serve(args.journal, args.port, args.ready)
    elif args.action == 'export':
        if args.output.suffix.lower() != '.html':
            parser.error('Export requires a .html output file')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(page(read_state(args.journal), False), encoding='utf-8')
        print(args.output.resolve())
    else:
        journal = (timing.create(args.project, args.label, args.scenario, args.environment,
                                 args.dataset, args.revision) if args.action == 'start' else args.journal)
        # Print the durable journal even if local hosting is unavailable.
        print(json.dumps({'journal': str(journal.resolve())}, ensure_ascii=False), flush=True)
        url = open_monitor(journal)
        print(url, flush=True)
        if not args.no_browser:
            try:
                opened = webbrowser.open_new_tab(url)
            except (webbrowser.Error, OSError):
                opened = False
            if not opened:
                print('Откройте выведенную ссылку в браузере на компьютере проекта.', file=sys.stderr)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
