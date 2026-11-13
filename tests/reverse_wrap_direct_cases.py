"""Viewport bounds are independent expectations where XTerm can report row 0."""
CSI = '\x1b['
CASES = []
for mode in ('45','1045','45;1045'):
    if mode == '45':
        CASES.append(('cold-top-normal','\x1bc'+CSI+'?45h\b'+CSI+'6n',CSI+'1;1R'))
    else:
        CASES.append(('cold-top-'+mode,'\x1bc'+CSI+'?'+mode+'h\b'+CSI+'6n',CSI+'24;80R'))
    for row,col,move,expected in [(1,1,'\b',(1,1)),(1,1,CSI+'7D',(1,1)),
                                 (1,1,CSI+'25D',(1,1)),(2,5,CSI+'7D',(1,5)),
                                 (2,5,CSI+'25D',(1,5))]:
        if mode == '45': continue
        CASES.append((f'bounded-{mode}-{row}-{col}-{move!r}',
            '\x1bc'+CSI+'?'+mode+'h'+CSI+'?69h'+CSI+'5;10s'+CSI+'3;6r'+
            f'{CSI}{row};{col}H'+move+CSI+'6n',f'{CSI}{expected[0]};{expected[1]}R'))
