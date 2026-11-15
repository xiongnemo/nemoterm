"""Observe upstream header-order/error behavior during a real pending upload.

No expected replies or state changes are synthesized. This adds coverage to the
earlier valid-query capture without changing its immutable recorded observations.
"""
import itertools
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitty_features_oracle import command, main


def make_cases():
    seed = b'\x1b[3;4H' + command('a=T,i=7,p=2,f=24,s=2,v=2,C=1', bytes((255, 0, 0))*4)
    first = command('a=T,i=9,f=24,s=1,v=1,C=1,m=1', b'\x00\xff')
    last = command('m=0', b'\x00')
    cases = []

    def add(name, wire):
        cases.append((name, [('seed', seed), ('first-chunk', first),
                            ('interleaved', wire), ('last-chunk', last)]))

    for index, fields in enumerate(itertools.permutations(('a=q', 'i=31', 'e=T'))):
        add(f'valid-order-{index+1}', command(','.join((*fields, 'C=1'))))
    invalid = [('unknown-numeric', 'j=37'), ('unknown-text', 'j=x'),
               ('numeric-text', 'C=x'), ('negative-unsigned', 'C=-1'),
               ('overflow-unsigned', 'C=4294967296'), ('empty-selector', 'e='),
               ('long-selector', 'e=TT'), ('unknown-medium', 't=x'),
               ('unknown-compression', 'o=x'), ('quiet-three', 'q=3'),
               ('more-two', 'm=2'), ('conflicting-number', 'I=7'),
               ('empty-token', ''), ('no-equals', 'C')]
    for label, token in invalid:
        for position in (0, 2, 4):
            fields = ['a=q', 'i=31', 'e=T', 'C=1']
            fields.insert(position, token)
            add(f'{label}-position-{position}', command(','.join(fields)))
    for name, wire in [
        ('query-empty-id', command('a=q,i=,e=T')),
        ('query-numeric-selector', command('i=31,e=0,a=q')),
        ('query-selector-last-wins', command('i=31,e=t,a=q,e=T,C=1')),
        ('query-action-last-wins', command('a=t,e=T,i=31,a=q,C=1')),
        ('ordinary-malformed-header', command('a=t,i=31,C=x')),
        ('continuation-invalid-base64', b'\x1b_Gm=0;!\x1b\\'),
    ]:
        add(name, wire)
    assert len(cases) == 54 and len({name for name, _ in cases}) == 54
    return cases


if __name__ == '__main__':
    main(inputs=make_cases(), family='kitty-query-errors', fixture_path=__file__)
