"""Native font zoom, resize, synchronization and history for Unicode images."""
import sys
from kitty_geometry_window_smoke import main

if __name__=='__main__':
    sys.argv.append('--unicode-images')
    main()
