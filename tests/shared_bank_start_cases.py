"""ASCII streams shared by the XTerm collector and native-window colour probe."""
E='\x1b'; C=E+'['; ST=E+'\\'
REGIS_QUERY=E+'P1pR(P)'+ST

def bank_starts():
    # No RIS in the common setup: XTerm initializes the shared bank differently
    # at startup and on hard reset. Four adjacent 4x6 stripes begin at (0,0).
    select=C+'?1070l'; private=C+'?1070h'
    stripes=E+'P9;1q#0!4~#1!4~#3!4~#15!4~'+ST
    setup=C+'?25l'+C+'?80l'+E+']11;#ff00ff\x07'+C+'2J'+C+'H'
    return {name: [prefix+setup+mode+stripes] for name,prefix,mode in (
        ('fresh-shared','',select),('fresh-private','',private),('after-ris',E+'c',select),
        ('after-decstr',C+'!p',select),('regis-first',select+REGIS_QUERY,select),
        ('private-first',private+REGIS_QUERY,select),
        ('defined-shared',select+E+'P9;1q#3;2;100;0;0$'+ST,select))}
