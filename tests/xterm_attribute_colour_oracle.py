"""Independent reference collector for an authorized Linux test environment.

Explicit special-colour resources make the
reset expectations independent of the user's XTerm resource database.
"""
import argparse
import json
from pathlib import Path
from attribute_colour_cases import CASES, COLORS, SET, command, query, replies


# Exact upstream replies from runs 43454910323 and 43456769586, not product
# expectations. Keep these deliberate divergences visible and fail if either
# upstream behaviour or any other reply changes. The selective reset quirk
# depends on bytes after the logical OSC terminator in the pinned parser.
REFERENCE_DIVERGENCES = {
    'reset-one-special': replies((COLORS[0], 'ffffff', 'ffffff', *COLORS[3:])),
    'overflow-index': replies(('ff0000', *COLORS[1:])),
}
from xterm_state_oracle import run_cases

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/attribute-colour-xterm.json')
    args = parser.parse_args()
    resources = ['-ti', 'vt520', '-fg', '#ffffff', '-bg', '#000000']
    for mode in ('BD', 'UL', 'BL', 'RV', 'IT'):
        resources += ['-xrm', f'*color{mode}: #ffffff']
    cases = {name: sequence for name, sequence, _ in CASES}
    # Diagnose the pinned reference's single-index reset independently of the
    # product expectations. Preserve complete replies, including any preceding
    # query, instead of assuming identical parser behaviour across histories.
    for prior_name, prior in (('set', ''), ('short-query', command(5, '0;?')),
                              ('long-query', query()), ('alias-query', query(4))):
        for suffix in ('2', '2;'):
            cases[f'reference-reset-{prior_name}-{suffix}'] = SET+prior+command(105, suffix)+query()
    run_cases(args.xterm, args.output, cases,
              resources, raw_replies=True)
    actual = json.loads(Path(args.output).read_text(encoding='utf-8'))['cases']
    failures, matched, divergences = [], [], []
    for name, sequence, expected in CASES:
        upstream_expected = REFERENCE_DIVERGENCES.get(name, expected)
        record = actual[name]
        if record['sequence'] != sequence or record['reply_hex'] != upstream_expected.encode().hex():
            failures.append(name)
        elif name in REFERENCE_DIVERGENCES:
            divergences.append(dict(name=name, product_expected_hex=expected.encode().hex(),
                                    reference_reply_hex=record['reply_hex']))
        else:
            matched.append(name)
    comparison = dict(matching_product_cases=matched, known_differences=divergences,
                      unexpected_cases=failures, additional_reference_cases=8,
                      product_parity=len(divergences) == 0 and not failures)
    output = Path(args.output)
    output.with_name(output.stem+'-comparison.json').write_text(
        json.dumps(comparison, indent=2)+'\n', encoding='utf-8')
    if failures:
        raise SystemExit('Unexpected reference differences retained: '+', '.join(failures))
    print(f'{len(matched)} product cases match; {len(divergences)} documented reference differences verified')
