"""Common child output for physical XTerm and Windows pointer observations."""
CSI='\x1b['
# Explicitly select mouse reporting per case, even after a reset.
def cases(initial):
    rows=[]
    def add(name,wire,hide):rows.append((name,wire,hide))
    for label,value in [('never','0'),('without-tracking','1'),('always','2'),('focused','3'),('omitted','')]:
        for tracking in (False,True):
            add(label+('-tracking' if tracking else '-plain'),CSI+'>'+value+'p'+CSI+'?1000'+('h' if tracking else 'l'),
                value in ('2','3') or value in ('1','') and not tracking)
    add('soft-reset',CSI+'>2p'+CSI+'!p',True)
    add('alternate',CSI+'>2p'+CSI+'?1049h',True)
    add('main',CSI+'?1049l',True)
    add('hard-reset',CSI+'>2p'+'\x1bc',initial)
    add('omitted-first',CSI+'?1000h'+CSI+'>;0p',False)
    add('extra-parameter',CSI+'>2;0p',True)
    return rows
