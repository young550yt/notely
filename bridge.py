#!/usr/bin/env python3
"""Notely - local note server.

Serves the authoring page and a folder of plain .md files (the "vault"),
so your notes are real files on disk - readable, backed up, portable.

Routes:
  GET  /                 -> index.html
  GET  /api/ping         -> {ok, port, notes: count}
  GET  /api/notes        -> [{name, mtime, words}]   (vault index)
  GET  /api/note?name=x  -> {name, content}
  POST /api/note         -> {name, content}          (create or save)
  POST /api/delete       -> {name}                   (move to trash/)
  GET  /api/raw?name=x   -> text/plain of one note   (for manual open)
  GET  /file?name=x      -> any vault file (images referenced by notes)

Binds 127.0.0.1 only.
"""
import json
import mimetypes
import os
import re
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

APP_DIR = os.path.dirname(os.path.abspath(__file__))
NOTES_DIR = os.path.join(APP_DIR, 'notes')
TRASH_DIR = os.path.join(APP_DIR, 'trash')
INDEX_PATH = os.path.join(APP_DIR, 'index.html')
LOG_PATH = os.path.join(APP_DIR, 'server.log')
BASE_PORT = 8565
MAX_BODY = 8 * 1024 * 1024
MAX_NOTE_BYTES = 4 * 1024 * 1024

_lock = threading.Lock()


def log(msg):
    line = '%s %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    with _lock:
        try:
            with open(LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass


def safe_name(name):
    """Vault-relative note name -> safe 'some-note.md'. No traversal."""
    name = unquote(str(name or '')).replace('\\', '/').split('/')[-1]
    name = re.sub(r'[\\/:*?"<>|]+', '-', name).strip(' .')
    if not name:
        return ''
    if not name.lower().endswith('.md'):
        name += '.md'
    return name[:120]


def note_path(name):
    safe = safe_name(name)
    if not safe:
        return ''
    return os.path.join(NOTES_DIR, safe)


def word_count(text):
    return len(re.findall(r'\S+', text))


class Handler(BaseHTTPRequestHandler):
    server_version = 'Notely/1.0'
    port = BASE_PORT

    def _json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def _bytes(self, raw, ctype, status=200):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _origin_ok(self):
        own = {'http://127.0.0.1:%d' % self.port, 'http://localhost:%d' % self.port}
        origin = self.headers.get('Origin')
        if origin and origin not in own:
            return False
        ref = self.headers.get('Referer')
        if ref:
            m = re.match(r'^(https?://[^/]+)', ref)
            if not m or m.group(1) not in own:
                return False
        return True

    def _host_ok(self):
        host = (self.headers.get('Host') or '').lower()
        return host.startswith('127.0.0.1') or host.startswith('localhost')

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0:
            return b''
        if n > MAX_BODY:
            raise ValueError('body too large')
        return self.rfile.read(n)

    # ------------------------------------------------------------- GET
    def do_GET(self):
        try:
            if not self._host_ok() or not self._origin_ok():
                return self._json({'error': 'forbidden'}, 403)
            u = urlparse(self.path)
            path = u.path

            if path in ('/', '/index.html'):
                try:
                    with open(INDEX_PATH, 'rb') as f:
                        return self._bytes(f.read(), 'text/html; charset=utf-8')
                except OSError:
                    return self._json({'error': 'index.html missing'}, 404)

            if path == '/favicon.ico':
                self.send_response(204)
                self.end_headers()
                return

            if path == '/api/ping':
                return self._json({'ok': True, 'port': self.port,
                                   'notes': len(list_notes())})

            if path == '/api/notes':
                return self._json({'notes': list_notes()})

            if path == '/api/note':
                name = safe_name(parse_qs(u.query).get('name', [''])[0])
                fp = note_path(name)
                if not fp or not os.path.isfile(fp):
                    return self._json({'error': 'no such note'}, 404)
                with open(fp, encoding='utf-8', errors='replace') as f:
                    content = f.read()
                return self._json({'name': name, 'content': content})

            if path == '/api/raw':
                name = safe_name(parse_qs(u.query).get('name', [''])[0])
                fp = note_path(name)
                if not fp or not os.path.isfile(fp):
                    return self._json({'error': 'no such note'}, 404)
                with open(fp, 'rb') as f:
                    return self._bytes(f.read(), 'text/plain; charset=utf-8')

            if path == '/file':
                name = safe_name(parse_qs(u.query).get('name', [''])[0])
                fp = note_path(name)
                if not fp or not os.path.isfile(fp):
                    return self._json({'error': 'no such file'}, 404)
                ctype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
                if ctype.startswith('text/') or ctype == 'application/json':
                    ctype += '; charset=utf-8'
                with open(fp, 'rb') as f:
                    return self._bytes(f.read(), ctype)

            self._json({'error': 'not found'}, 404)
        except BrokenPipeError:
            pass
        except Exception:
            log('GET error:\n' + traceback.format_exc())
            try:
                self._json({'error': 'server error'}, 500)
            except Exception:
                pass

    # ------------------------------------------------------------- POST
    def do_POST(self):
        try:
            if not self._host_ok() or not self._origin_ok():
                return self._json({'error': 'forbidden'}, 403)
            path = urlparse(self.path).path
            raw = self._body()
            try:
                data = json.loads(raw.decode('utf-8'))
            except Exception:
                return self._json({'error': 'bad json'}, 400)

            if path == '/api/note':
                name = safe_name(data.get('name') or '')
                content = str(data.get('content') or '')
                if not name:
                    return self._json({'error': 'bad name'}, 400)
                if len(content.encode('utf-8')) > MAX_NOTE_BYTES:
                    return self._json({'error': 'note too large (4 MB max)'}, 400)
                os.makedirs(NOTES_DIR, exist_ok=True)
                fp = os.path.join(NOTES_DIR, name)
                tmp = fp + '.tmp'
                with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(content)
                os.replace(tmp, fp)
                return self._json({'ok': True, 'name': name,
                                   'words': word_count(content)})

            if path == '/api/delete':
                name = safe_name(data.get('name') or '')
                fp = note_path(name)
                if not fp or not os.path.isfile(fp):
                    return self._json({'error': 'no such note'}, 404)
                os.makedirs(TRASH_DIR, exist_ok=True)
                stamp = time.strftime('%Y%m%d-%H%M%S')
                dest = os.path.join(TRASH_DIR, '%s-%s' % (stamp, name))
                os.replace(fp, dest)
                return self._json({'ok': True, 'name': name})

            self._json({'error': 'not found'}, 404)
        except BrokenPipeError:
            pass
        except Exception:
            log('POST error:\n' + traceback.format_exc())
            try:
                self._json({'error': 'server error'}, 500)
            except Exception:
                pass

    def log_message(self, fmt, *args):
        pass


def list_notes():
    out = []
    try:
        for n in sorted(os.listdir(NOTES_DIR)):
            if not n.lower().endswith('.md'):
                continue
            fp = os.path.join(NOTES_DIR, n)
            try:
                st = os.stat(fp)
                with open(fp, encoding='utf-8', errors='replace') as f:
                    words = word_count(f.read())
                out.append({'name': n, 'mtime': int(st.st_mtime), 'words': words,
                            'size': st.st_size})
            except OSError:
                continue
    except FileNotFoundError:
        pass
    out.sort(key=lambda x: -x['mtime'])
    return out


def port_free(p):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return s.connect_ex(('127.0.0.1', p)) != 0
    finally:
        s.close()


def main():
    os.makedirs(NOTES_DIR, exist_ok=True)
    os.makedirs(TRASH_DIR, exist_ok=True)
    httpd = None
    chosen = None
    for p in range(BASE_PORT, BASE_PORT + 12):
        if not port_free(p):
            continue                    # already running (second launch)
        try:
            Handler.port = p
            httpd = ThreadingHTTPServer(('127.0.0.1', p), Handler)
            chosen = p
            break
        except OSError:
            continue
    if httpd is None:
        log('no free port %d-%d - exiting' % (BASE_PORT, BASE_PORT + 11))
        return 0
    httpd.daemon_threads = True
    log('notely listening on http://127.0.0.1:%d/' % chosen)
    print('notely on http://127.0.0.1:%d/' % chosen)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
