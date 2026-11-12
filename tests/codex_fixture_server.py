"""Loopback-only deterministic text responses for the installed Codex TUI.

This is a rendering fixture, not a model, API compatibility suite or tool runner.
Event schema: https://developers.openai.com/api/reference/resources/responses/streaming-events
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

COPY_TEXT = 'NEMOTERM_COPY 中文 e\u0301 \uf120 \U000f0001 END'
PASTE_TEXT = 'NEMOTERM_PASTE 中文 e\u0301 \U0001f642'


def response_text(turn):
    if turn == 1:
        return ('# Nemoterm real Codex rendering fixture\n\n'
                '**Bold**, *italic*, `inline code`, and 中文与组合字符 e\u0301.\n\n'
                '```python\nprint("中文与 Unicode")\n```\n\n'
                '| Check | Result |\n| --- | --- |\n| 中文 | 保留 |\n| ASCII | kept |\n\n'
                + '\n'.join(f'ROW_{i:03d} 中文 e\u0301: long-output scroll and redraw verification.'
                            for i in range(1, 81))
                + '\n\n' + COPY_TEXT + '\n\nNEMOTERM_REPLY_1_DONE')
    return f'Pasted Unicode received.\n\n{COPY_TEXT}\n\nNEMOTERM_REPLY_{turn}_DONE'


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), Handler)
        self.requests = []
        self.errors = []
        self.completed = []
        self.turns = 0
        self.lock = threading.Lock()
        self.preview_ready = threading.Event()
        self.preview_release = threading.Event()
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.preview_release.set()
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=5)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        # Also reject attempted WebSocket upgrades, so the client uses SSE.
        self.send_error(404)

    def do_POST(self):
        try:
            assert self.path == '/v1/responses', self.path
            size = int(self.headers.get('Content-Length', '0'))
            assert 0 < size <= 8 * 1024 * 1024, size
            assert not self.headers.get('Content-Encoding'), 'Unexpected compressed request'
            request = json.loads(self.rfile.read(size))
            assert request.get('stream') is True
            assert request.get('model') == 'nemoterm-ui-fixture'
            # Retain only submitted user text, not environment/developer context.
            user_text = [part.get('text', '') for item in request.get('input', [])
                         if item.get('role') == 'user' for part in item.get('content', [])
                         if isinstance(part, dict) and part.get('type') == 'input_text']
            auxiliary = bool(user_text and user_text[-1].startswith('Generate a concise, single-line task title'))
            with self.server.lock:
                if not auxiliary:
                    self.server.turns += 1
                turn = self.server.turns
                ident = len(self.server.requests)+1
                assert ident <= 8, 'Unexpected repeated requests'
                self.server.requests.append(dict(turn=turn, auxiliary=auxiliary, path=self.path,
                    user_text=[text for text in user_text if text.startswith('NEMOTERM_')]))
            text = 'Verify terminal rendering' if auxiliary else response_text(turn)
            response_id, item_id = f'resp_nemoterm_{ident}', f'msg_nemoterm_{ident}'
            response = dict(id=response_id, object='response', created_at=int(time.time()),
                            model='nemoterm-ui-fixture', status='in_progress', output=[])
            item = dict(id=item_id, type='message', role='assistant', status='in_progress', content=[])
            part = dict(type='output_text', text='', annotations=[], logprobs=[])
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            seq = 0

            def event(kind, **fields):
                nonlocal seq
                value = dict(type=kind, sequence_number=seq, **fields)
                seq += 1
                self.wfile.write(('event: ' + kind + '\ndata: ' + json.dumps(value) + '\n\n').encode())
                self.wfile.flush()

            event('response.created', response=response)
            event('response.in_progress', response=response)
            event('response.output_item.added', output_index=0, item=item)
            event('response.content_part.added', item_id=item_id, output_index=0, content_index=0, part=part)
            # Split inside Unicode words and markdown constructs; actual Codex
            # decides when and how to paint each received chunk.
            for offset in range(0, len(text), 37):
                event('response.output_text.delta', item_id=item_id, output_index=0,
                      content_index=0, delta=text[offset:offset + 37], logprobs=[])
                time.sleep(.015)
                if turn == 1 and not auxiliary and offset >= 400 and not self.server.preview_ready.is_set():
                    self.server.preview_ready.set()
                    assert self.server.preview_release.wait(timeout=20), 'Markdown preview was not inspected'
            part['text'] = text
            event('response.output_text.done', item_id=item_id, output_index=0, content_index=0,
                  text=text, logprobs=[])
            event('response.content_part.done', item_id=item_id, output_index=0, content_index=0, part=part)
            item.update(status='completed', content=[part])
            event('response.output_item.done', output_index=0, item=item)
            response.update(status='completed', output=[item], usage=dict(input_tokens=100,
                            output_tokens=len(text)//4, total_tokens=100+len(text)//4,
                            input_tokens_details=dict(cached_tokens=0),
                            output_tokens_details=dict(reasoning_tokens=0)))
            event('response.completed', response=response)
            if not auxiliary:
                self.server.completed.append(turn)
        except Exception as exc:
            self.server.errors.append(repr(exc))
            try:
                self.send_error(500)
            except OSError:
                pass

