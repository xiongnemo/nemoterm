"""Shared byte sequences for XTerm and Windows; no platform imports."""
C = '\x1b['
PAINT = C + '2;3HKEEP' + C + '7;11H'
QUERY = C + '6n' + C + '18t' + C + '31#y' + ''.join(
    C + f'{x};1;2;{x};2;{x}*y' for x in range(3, 7))
MARK = 'KEEP'
BLANK = '    '
HOME = (0, 0)
AWAY = (10, 6)


def saved_cases(allow, initial_132):
    # Most checks deliberately stay at 80 columns. An accepted same-width DECCOLM
    # still homes the cursor and optionally erases the page. This distinguishes
    # an ignored restore from incidental window resize notifications.
    def mode(p): return C + '?' + p
    def check(key, seq, width=80, cursor=HOME, text=MARK):
        return key, seq, width if allow else 80, cursor if allow else AWAY, text if allow else MARK
    return [
        check('save-startup-width', mode('40h')+mode('3s')+PAINT, cursor=AWAY),
        check('reset-width-to-80', mode('95h')+PAINT+mode('3l')),
        check('restore-startup-width', PAINT+mode('3r'), width=132 if initial_132 else 80),
        check('prepare-same-width', PAINT+mode('3l')),
        check('restore-keep', mode('40;95h')+mode('95s')+mode('95l')+PAINT+mode('95r')+mode('3l')),
        check('restore-clear', mode('95l')+mode('95s')+mode('95h')+PAINT+mode('95r')+mode('3l'), text=BLANK),
        check('restore-disabled', mode('40l')+mode('40s')+mode('40h')+PAINT+mode('40r')+mode('3l'), cursor=AWAY),
        check('restore-enabled', mode('40h')+mode('40s')+mode('40l')+PAINT+mode('40r')+mode('3l'), text=BLANK),
        check('restore-both', mode('40;95h')+mode('40;95s')+mode('40;95l')+PAINT+mode('40;95r')+mode('3l')),
        check('restore-width-80', mode('3l')+mode('3s')+PAINT+mode('3r')),
        check('save-width-132', PAINT+mode('3h')+mode('3s'), width=132),
        check('back-to-80', PAINT+mode('3l')),
        check('restore-width-132', PAINT+mode('3r'), width=132),
        check('narrow-before-disabled-save', PAINT+mode('3l')),
        check('ignore-disabled-save', mode('40l')+PAINT+mode('3s')+mode('40h')+mode('3r'), width=132),
    ]

