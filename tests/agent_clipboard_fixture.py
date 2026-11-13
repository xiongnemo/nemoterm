"""Owned real-client clipboard fixture, with a text-only loopback provider.

The desktop controller uses the returned HWND for actual keyboard input. This
process supplies generated clipboard pixels, records only submitted image
metadata, and restores the previous clipboard before its private job closes.
No live model, user credentials, existing client session or tool response is used.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import re
from pathlib import Path
import struct
import subprocess
import threading
import time
import uuid
import winreg
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from native_test_utils import c, k, u, find_window, wait_for
from clipboard_test_utils import SavedClipboard
from owned_job import OwnedJob
from fixture_io import write_snapshot, read_snapshot


class Provider(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), Handler)
        self.requests, self.errors = [], []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_error(404)

    def do_POST(self):
        try:
            assert self.path in ('/v1/responses', '/v1/chat/completions'), self.path
            size = int(self.headers.get('Content-Length', '0'))
            assert 0 < size <= 8 * 1024 * 1024
            request = json.loads(self.rfile.read(size))
            assert request['model'] == 'nemoterm-image-fixture'
            assert request.get('stream') is True
            images, text = [], []
            for item in request.get('input', request.get('messages', [])):
                if item.get('role') != 'user':
                    continue
                content = item.get('content', [])
                if isinstance(content, str):
                    text.extend(re.findall(r'NEMOTERM_[A-Z0-9_]+',content))
                    continue
                for part in content:
                    if part.get('type') in ('input_image', 'image_url'):
                        value = part.get('image_url')
                        if isinstance(value, dict):
                            value = value['url']
                        assert value.startswith('data:image/'), 'Only generated embedded fixture images are expected'
                        kind, encoded = value.split(',', 1)
                        data = base64.b64decode(encoded, validate=True)
                        assert data.startswith(b'\x89PNG\r\n\x1a\n') and struct.unpack('>II',data[16:24])==(32,16)
                        from PIL import Image
                        rgb=Image.open(io.BytesIO(data)).convert('RGB')
                        expected=b''.join(bytes((230,40,180) if (x//4+y//4)%2 else (70,210,30))
                                          for y in reversed(range(16)) for x in range(32))
                        images.append(dict(mime=kind.split(';')[0][5:], bytes=len(data),
                                           generated_pixels_match=rgb.size==(32,16) and rgb.tobytes()==expected,
                                           sha256=hashlib.sha256(data).hexdigest(),
                                           png_size=list(struct.unpack('>II', data[16:24]))
                                           if data.startswith(b'\x89PNG\r\n\x1a\n') else None))
                    elif part.get('type') in ('input_text', 'text'):
                        value = part.get('text', '')
                        text.extend(re.findall(r'NEMOTERM_[A-Z0-9_]+',value))
            self.server.requests.append(dict(path=self.path, images=images, text=text,
                                              advertised_tools=len(request.get('tools', [])),
                                              tool_names=[t.get('name',t.get('function',{}).get('name',t.get('type')))
                                                          for t in request.get('tools', [])]))
            assert len(self.server.requests) <= 12
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Connection', 'close')
            self.end_headers()
            answer = 'NEMOTERM_IMAGE_ACCEPTED' if images else 'NEMOTERM_TEXT_ACCEPTED'
            if self.path.endswith('chat/completions'):
                for delta, finish in [({'role': 'assistant', 'content': answer}, None), ({}, 'stop')]:
                    value = dict(id='chatcmpl-fixture', object='chat.completion.chunk', created=int(time.time()),
                                 model=request['model'], choices=[dict(index=0, delta=delta, finish_reason=finish)])
                    self.wfile.write(('data: '+json.dumps(value)+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
            else:
                response = dict(id='resp_fixture', object='response', created_at=int(time.time()),
                                model=request['model'], status='in_progress', output=[])
                item = dict(id='msg_fixture', type='message', role='assistant', status='in_progress', content=[])
                part = dict(type='output_text', text='', annotations=[], logprobs=[])
                events = [
                    ('response.created', dict(response=response.copy())),
                    ('response.output_item.added', dict(output_index=0, item=item.copy())),
                    ('response.content_part.added', dict(item_id=item['id'], output_index=0, content_index=0, part=part.copy())),
                    ('response.output_text.delta', dict(item_id=item['id'], output_index=0, content_index=0, delta=answer)),
                    ('response.output_text.done', dict(item_id=item['id'], output_index=0, content_index=0, text=answer)),
                ]
                part['text'] = answer
                item.update(status='completed', content=[part])
                response.update(status='completed', output=[item], usage=dict(input_tokens=1, output_tokens=1, total_tokens=2))
                events += [('response.output_item.done', dict(output_index=0, item=item)),
                           ('response.completed', dict(response=response))]
                for seq, (kind, fields) in enumerate(events):
                    value = dict(type=kind, sequence_number=seq, **fields)
                    self.wfile.write(('event: '+kind+'\ndata: '+json.dumps(value)+'\n\n').encode())
            self.wfile.flush()
        except Exception as exc:
            self.server.errors.append(repr(exc))
            try:
                self.send_error(500)
            except OSError:
                pass


def put_bitmap(hwnd):
    width, height = 32, 16
    # A small generated blue/red checkerboard, never an image from the user.
    pixels = b''.join(bytes((180, 40, 230) if (x//4+y//4)%2 else (30, 210, 70))
                      for y in range(height) for x in range(width))
    data = struct.pack('<IiiHHIIiiII', 40, width, height, 1, 24, 0, len(pixels), 0, 0, 0, 0)+pixels
    handle = k.GlobalAlloc(2, len(data))
    assert handle
    ptr = k.GlobalLock(handle)
    assert ptr
    c.memmove(ptr, data, len(data))
    k.GlobalUnlock(handle)
    try:
        wait_for(lambda: u.OpenClipboard(hwnd))
        try:
            assert u.EmptyClipboard()
            assert u.SetClipboardData(8, handle)  # CF_DIB
            handle = None
        finally:
            u.CloseClipboard()
    finally:
        if handle:
            k.GlobalFree(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=('codex', 'opencode'), required=True)
    parser.add_argument('--client-exe', required=True)
    parser.add_argument('--terminal', required=True)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--automation', action='store_true')
    parser.add_argument('--font',default='SarasaTermSC Nerd Font Light')
    args = parser.parse_args()
    folder = Path(args.directory).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    home, work = folder/'home', folder/'work'
    home.mkdir(); work.mkdir()
    subprocess.run(['git','init','--quiet',str(work)],check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    for name in ('config', 'data', 'cache', 'state', 'appdata', 'localappdata', 'temp'):
        (home/name).mkdir()
    env = {name: value for name, value in os.environ.items() if name.upper() in {
        'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATH', 'PATHEXT', 'PROGRAMFILES',
        'PROGRAMFILES(X86)', 'PROGRAMDATA', 'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE'}}
    env.update(USERPROFILE=str(home), APPDATA=str(home/'appdata'), LOCALAPPDATA=str(home/'localappdata'),
               TEMP=str(home/'temp'), TMP=str(home/'temp'), XDG_CONFIG_HOME=str(home/'config'),
               XDG_DATA_HOME=str(home/'data'), XDG_CACHE_HOME=str(home/'cache'), XDG_STATE_HOME=str(home/'state'),
               NEMOTERM_CONPTY='bundled', TERM='xterm-256color')
    # Route proxy-aware optional fetches to a closed port; the configured model
    # provider is loopback-only and never returns a tool call.
    env.update(HTTP_PROXY='http://127.0.0.1:9', HTTPS_PROXY='http://127.0.0.1:9',
               ALL_PROXY='http://127.0.0.1:9', NO_PROXY='127.0.0.1,localhost')
    profile = 'image-fixture-'+uuid.uuid4().hex
    registry = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry) as key:
        winreg.SetValueEx(key, 'WarnOnClose', 0, winreg.REG_DWORD, 0)
        winreg.SetValueEx(key, 'CloseOnExit', 0, winreg.REG_DWORD, 1)
    server = Provider()
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_port}/v1'
    if args.client == 'codex':
        env['CODEX_HOME'] = str(home)
        config = f'''model = "nemoterm-image-fixture"
model_provider = "nemoterm_fixture"
check_for_update_on_startup = false
sandbox_mode = "read-only"
approval_policy = "never"
web_search = "disabled"
[features]
shell_tool = false
apply_patch_freeform = false
multi_agent = false
[model_providers.nemoterm_fixture]
name = "Nemoterm image fixture"
base_url = "{base}"
wire_api = "responses"
requires_openai_auth = false
[analytics]
enabled = false
[feedback]
enabled = false
'''
        config += '\n[projects.'+json.dumps(str(work))+']\ntrust_level = "trusted"\n'
        (home/'config.toml').write_text(config, encoding='utf-8')
        command = [args.client_exe, '--no-daemon', '--cd', str(work)]
    else:
        config = dict(model='nemoterm_fixture/nemoterm-image-fixture',
                      small_model='nemoterm_fixture/nemoterm-image-fixture', enabled_providers=['nemoterm_fixture'],
                      permission='deny', tools={'*': False}, mcp={}, plugin=[], lsp=False, formatter=False,
                      snapshot=False, share='disabled', autoupdate=False,
                      provider={'nemoterm_fixture': dict(npm='@ai-sdk/openai-compatible', name='Nemoterm image fixture',
                        options=dict(baseURL=base, apiKey='fixture-unused'), models={'nemoterm-image-fixture':
                        dict(name='Nemoterm image fixture', attachment=True, limit=dict(context=32000, output=2048),
                             modalities=dict(input=['text', 'image'], output=['text']))})})
        config_path = home/'opencode.json'
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
        env.update(OPENCODE_CONFIG=str(config_path), OPENCODE_DISABLE_PROJECT_CONFIG='1',
                   OPENCODE_TEST_HOME=str(home),
                   OPENCODE_DISABLE_AUTOUPDATE='1', OPENCODE_DISABLE_MODELS_FETCH='1',
                   OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER='1', OPENCODE_PERMISSION='{"*":"deny"}',
                   OPENCODE_PURE='1')
        command = [args.client_exe, str(work)]
    report = dict(client=args.client, client_sha256=hashlib.sha256(Path(args.client_exe).read_bytes()).hexdigest(),
                  terminal_sha256=hashlib.sha256(Path(args.terminal).read_bytes()).hexdigest(),
                  backend=base, generated_bitmap=[32, 16], requests=server.requests, errors=server.errors)
    saved = None
    try:
        with OwnedJob() as job:
            process = job.spawn([args.terminal, '-load', profile, *(['--automation'] if args.automation else []), '--cols', '100', '--rows', '30',
                                 '--font', args.font, '-e', *command],
                                cwd=work, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
            hwnd = wait_for(lambda: find_window(process.pid), timeout=20)
            report.update(pid=process.pid, hwnd=hwnd)
            saved = SavedClipboard(hwnd)
            serial = None
            deadline = time.monotonic()+600
            print(json.dumps(dict(pid=process.pid, hwnd=hwnd, directory=str(folder))), flush=True)
            try:
                while time.monotonic()<deadline and process.poll() is None:
                    control = read_snapshot(folder/'control.json') or {}
                    if control.get('id') != serial:
                        serial = control.get('id')
                        action = control.get('action')
                        if action == 'bitmap':
                            put_bitmap(hwnd)
                            report['clipboard_action'] = serial
                        elif action == 'restore':
                            if saved:
                                saved.restore();saved=None
                            report['clipboard_restored']=True
                        elif action == 'finish':
                            break
                    write_snapshot(folder/'observed.json', report)
                    time.sleep(.1)
            finally:
                if saved:
                    saved.restore(); saved = None
                report['cleanup'] = job.finish()
                write_snapshot(folder/'observed.json', report)
    finally:
        if saved:
            saved.restore()
        server.shutdown(); server.server_close(); thread.join(timeout=3)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry)


if __name__ == '__main__':
    main()
