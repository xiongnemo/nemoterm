"""Observe missing and explicitly stored colour-stream preferences in a real renderer."""
import os
import sys
from regis_window_smoke import before, main, reset, private_sequence
from sixel_stream_window_smoke import graphic

# Present=1 is the marker written by save_open_settings, including by versions
# before SixelXtermColourContinuation existed. Sparse profiles lack that marker.
profiles={
    'fresh': ({}, True),
    'saved-before-option': ({'Present':1}, False),
    'saved-off': ({'Present':1,'SixelXtermColourContinuation':0}, False),
    'saved-on': ({'Present':1,'SixelXtermColourContinuation':1}, True),
}
if __name__=='__main__':
    name=sys.argv.pop(1)
    values,enabled=profiles[name]
    def exercise(phase, block):
        red=block(2,'red',count=8)
        phase('first-red-and-pending',reset()+graphic(2,'#1;2;100;0;0!8~#2;2;100;0;17'),
              [red,block(6,'black',count=8)],expected_reply=b'')
        following=block(6,'vt340-green' if enabled else 'blue',count=8)
        phase('read-leading-selector',graphic(6,'#2;2;0;0;100!8~'),[red,following],expected_reply=b'')
        phase('explicit-blue-afterwards',graphic(9,'#2;2;0;0;100!8~'),
              [red,following,block(9,'blue',count=8)],expected_reply=b'')
        if name=='saved-off': private_sequence(phase,block,legacy=True)
    main(exercise,suite_name='regis-window-profile-'+name,before_exercise=before,
         font=os.environ['NEMOTERM_TEST_FONT'],profile_values=dict(NemoTabs=0,**values))
