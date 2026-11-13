"""Capture reset boundaries for indexed, special and dynamic colours in XTerm."""
import argparse
from xterm_state_oracle import run_cases

CSI, OSC, ST = '\x1b[', '\x1b]', '\x1b\\'
QUERY = (OSC+'4;1;?;16;?;255;?'+ST+OSC+'5;0;?;1;?;2;?;3;?;4;?'+ST+
         OSC+'10;?;?;?'+ST+OSC+'17;?'+ST+OSC+'19;?'+ST)
SET = (CSI+'?1049l'+CSI+'?5l'+OSC+'4;1;#112233;16;#445566;255;#778899'+ST+
       OSC+'5;0;#112233;1;#445566;2;#778899;3;#aabbcc;4;#ddeeff'+ST+
       OSC+'10;#123456;#234567;#345678'+ST+OSC+'17;#abcdef'+ST+OSC+'19;#fedcba'+ST)


def cases():
    result = {}
    controls = {'ris': '\x1bc', 'decstr': CSI+'!p', 'sgr': CSI+'0m',
                'alternate': CSI+'?1049h'+CSI+'?1049l'}
    for name, control in controls.items():
        for state, prefix in (('normal', ''), ('alternate', CSI+'?1049h'),
                              ('reverse', CSI+'?5h')):
            result[name+'-'+state] = SET+prefix+control+QUERY
        result[name+'-saved-palette'] = SET+CSI+'1#P'+control+QUERY+CSI+'1#Q'+QUERY
    for command in (10, 11, 12):
        result[f'reverse-set-{command}'] = SET+CSI+'?5h'+OSC+str(command)+';#56789a'+ST+QUERY+CSI+'?5l'+QUERY
        result[f'reverse-reset-{command}'] = SET+CSI+'?5h'+OSC+str(command+100)+ST+QUERY+CSI+'?5l'+QUERY
    for name, colour in (('foreground', '#123456'), ('background', '#234567'), ('independent', '#456789')):
        result['cursor-reverse-'+name] = SET+OSC+'12;'+colour+ST+CSI+'?5h'+QUERY+CSI+'?5l'+QUERY
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', required=True)
    parser.add_argument('--output', default='research/reset-palette-xterm.json')
    args = parser.parse_args()
    # Match the existing PuTTY default palette while keeping dynamic and
    # selection colours explicit in every sequence. No product replies used.
    resources = ['-ti', 'vt520', '-fg', '#bbbbbb', '-bg', '#000000',
                 '-xrm', '*color1: #bb0000', '-xrm', '*color16: #000000',
                 '-xrm', '*color255: #eeeeee']
    for mode in ('BD', 'UL', 'BL', 'RV', 'IT'):
        resources += ['-xrm', f'*color{mode}: #bbbbbb']
    run_cases(args.xterm, args.output, cases(), resources, raw_replies=True)
