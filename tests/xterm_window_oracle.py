"""Capture independent XTerm window/title behavior on a private Xvfb display."""
import argparse
import json
from pathlib import Path

from xterm_state_oracle import run_cases

CSI = '\x1b['
ST = '\x1b\\'


def title(text, target=0):
    return f'\x1b]{target};{text}{ST}'


def op(*args):
    return CSI+';'.join(map(str, args))+'t'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xterm', required=True)
    parser.add_argument('--output', default='research/window-xterm.json')
    args = parser.parse_args()
    # Independent cases reset title modes and drain the preceding test's stack.
    # Explicit UTF-8 title I/O removes the X server locale from these cases.
    # Draining only the stack does not clear indexed slots. Invalid selector 3
    # writes an empty item in each slot without increasing the stack depth.
    reset = (op(23, 0)*48+''.join(op(22, 3, slot) for slot in range(1, 11))+
             CSI+'>0;1T'+CSI+'>2;3t'+title('BASE'))
    query = op(20)+op(21)
    cases = {
        'set-both': reset+title('BOTH')+query,
        'set-separate': reset+title('ICON', 1)+title('WINDOW', 2)+query,
        'utf8': reset+title('中文 e\u0301 👋')+query,
        'pop-empty': reset+op(23, 0)+query,
        'push-default': reset+op(22)+title('CHANGED')+op(23)+query,
        'push-both': reset+op(22, 0)+title('CHANGED')+op(23, 0)+query,
        'push-icon': reset+op(22, 1)+title('CHANGED')+op(23, 1)+query,
        'push-window': reset+op(22, 2)+title('CHANGED')+op(23, 2)+query,
        'push-icon-pop-both': reset+op(22, 1)+title('CHANGED')+op(23, 0)+query,
        'push-window-pop-both': reset+op(22, 2)+title('CHANGED')+op(23, 0)+query,
        'mixed-stack': reset+op(22, 0)+title('MIDDLE')+op(22, 1)+title('TOP')+
                       op(23, 0)+query+op(23, 0)+query,
        'opposite-pop': reset+op(22, 0)+title('MIDDLE')+op(22, 1)+title('TOP')+
                        op(23, 2)+query+op(23, 1)+query,
        'invalid-push-kind': reset+op(22, 0)+title('MIDDLE')+op(22, 3)+title('TOP')+
                             op(23, 0)+query+op(23, 0)+query,
        'invalid-pop-kind': reset+op(22, 0)+title('TOP')+op(23, 3)+op(23, 0)+query,
        'direct-slot-repeat': reset+op(22, 0, 3)+title('TOP')+op(23, 0, 3)+query+
                              title('AGAIN')+op(23, 0, 3)+query,
        'direct-slot-outside-documented-range': reset+op(22, 0, 11)+title('TOP')+
                                                op(23, 0, 1)+query,
        'direct-slot-and-stack': reset+op(22, 0)+title('SLOT')+op(22, 0, 1)+title('TOP')+
                                 op(23, 0)+query+op(23, 0, 1)+query,
        'stack-ris': reset+op(22, 0)+title('TOP')+'\x1bc'+op(23, 0)+query,
        'stack-soft-reset': reset+op(22, 0)+title('TOP')+CSI+'!p'+op(23, 0)+query,
        'stack-alternate': reset+op(22, 0)+CSI+'?1049h'+title('ALT')+op(23, 0)+query+
                           CSI+'?1049l'+query,
        'extra-parameters': reset+op(22, 0, 0, 123)+title('TOP')+op(23, 0, 0, 123)+query,
        'title-query-hex': reset+title('A中文')+CSI+'>1t'+query+CSI+'>1T',
        'title-set-hex': reset+CSI+'>0t'+title('A中文'.encode().hex())+CSI+'>0T'+query,
        'title-invalid-hex': reset+CSI+'>0t'+title('414G42')+CSI+'>0T'+query,
        'title-odd-hex': reset+CSI+'>0t'+title('414')+CSI+'>0T'+query,
        'title-hex-nul': reset+CSI+'>0t'+title('410042')+CSI+'>0T'+query,
        'title-hex-controls': reset+CSI+'>0t'+title('410a420d4309441b45')+CSI+'>0T'+query,
        'title-long': reset+title('x'*4096)+query,
        'geometry': op(11)+op(13)+op(13, 2)+op(14)+op(14, 2)+op(15)+op(16)+op(18)+op(19),
    }
    overflow = reset+''.join(title(f'STACK{i}')+op(22, 0) for i in range(12))+title('TOP')
    cases['stack-overflow'] = overflow+(op(23, 0)+query)*13
    run_cases(args.xterm, args.output, cases, (
        '-xrm', '*allowTitleOps: true', '-xrm', '*allowWindowOps: true',
        '-xrm', '*disallowedWindowOps:', '-xrm', '*titleModes: 12'))
    data = json.loads(Path(args.output).read_text())
    replies = data['cases']
    def expected(icon, window):
        return '\x1b]L'+icon+ST+'\x1b]l'+window+ST
    for name, icon, window in [('set-both', 'BOTH', 'BOTH'),
            ('set-separate', 'ICON', 'WINDOW'), ('push-both', 'BASE', 'BASE'),
            ('push-default', 'BASE', 'BASE'), ('push-icon', 'BASE', 'CHANGED'),
            ('push-window', 'CHANGED', 'BASE')]:
        assert replies[name]['reply'] == expected(icon, window), (name, replies[name])
    assert replies['utf8']['reply'] == expected('中文 e\u0301 👋', '中文 e\u0301 👋')
    print(f'Captured {len(cases)} independent window/title cases; baseline assertions passed')


if __name__ == '__main__':
    main()
