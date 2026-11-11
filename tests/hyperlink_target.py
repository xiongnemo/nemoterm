"""Handler for a UUID-scoped test URI scheme; records argv, never opens URLs."""
import os
from pathlib import Path
import sys
import uuid
from fixture_io import write_snapshot

path = Path(sys.argv[1]) / (uuid.uuid4().hex + '.json')
write_snapshot(path, {'argv': sys.argv[2:], 'pid': os.getpid()})
