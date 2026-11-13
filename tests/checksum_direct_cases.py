"""Explicit retained-cell expectations where XTerm uses a different model."""
RESET = '\x1b[64;1"p\x1bc'
QUERY = '\x1b[7;1;1;1;1;1*y'
CASES = [
    ('empty-identifier-is-zero', RESET+'A\x1b[23#y\x1b[;1;1;1;1;1*y', '\x1bP0!~0041\x1b\\'),
    ('decomposed-base', RESET+'e\u0301\x1b[23#y'+QUERY, '\x1bP7!~0065\x1b\\'),
    ('decomposed-legacy-untrimmed', RESET+'e\u0301\x1b[5#y'+QUERY, '\x1bP7!~0366\x1b\\'),
    ('decomposed-legacy-trimmed', RESET+'e\u0301\x1b[1#y'+QUERY, '\x1bP7!~0065\x1b\\'),
    ('multiple-marks-retained', RESET+'a\u0308\u0301\x1b[5#y'+QUERY, '\x1bP7!~066A\x1b\\'),
    ('unicode-legacy-is-stable', RESET+'éñÿĀḀ🙂\x1b[1#y\x1b[7;1;1;1;1;7*y', '\x1bP7!~014B\x1b\\'),
    ('utf8-national-charset', RESET+'\x1b(A#\x1b(B\x1b[1#y'+QUERY, '\x1bP7!~0023\x1b\\'),
    ('colon-mode-is-ignored', RESET+'A\x1b[23#y\x1b[0:0#y'+QUERY, '\x1bP7!~0041\x1b\\'),
]
