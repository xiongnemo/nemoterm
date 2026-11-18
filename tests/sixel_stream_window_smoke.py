"""Exercise the saved XTerm Sixel colour stream option on one native window."""
from regis_window_smoke import before, main, reset, CSI, DCS, ST, os


def graphic(row, payload):
    return CSI+f'{row};3H'+DCS+'0;1q'+payload+ST


def exercise(phase, block):
    def pixels(row, *runs):
        return [block(row, 'black', count=24)]+[block(row, col, left=left, count=count)
                for left, count, col in runs]
    first=graphic(2,'#1;2;100;0;0!8~#2;2;100;0;17')
    red=pixels(2,(0,8,'red'))
    phase('pending-definition',reset()+first,red+pixels(6))
    phase('digits-replace-last-component',graphic(6,'  100!8~#2!8~'),
          red+pixels(6,(0,8,'vt340-green'),(8,8,'magenta')))
    phase('fresh-blue-picture',graphic(9,'#2;2;0;0;100!8~'),
          red+pixels(6,(0,8,'vt340-green'),(8,8,'magenta'))+pixels(9,(0,8,'blue')))
    phase('before-reset',reset()+first,red+pixels(6))
    phase('reset-clears-pixels-keeps-syntax',reset()+graphic(6,'#2;2;0;0;100!8~'),
          pixels(2)+pixels(6,(0,8,'vt340-green')))
    phase('reset-followup',graphic(9,'#2;2;0;0;100!8~'),
          pixels(6,(0,8,'vt340-green'))+pixels(9,(0,8,'blue')))


if __name__ == '__main__':
    main(exercise, suite_name='regis-window-sixel-stream', before_exercise=before,
         font=os.environ['NEMOTERM_TEST_FONT'], profile_values=dict(NemoTabs=0,SixelXtermColourContinuation=1))
