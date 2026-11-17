"""Read the pinned TTF's English Windows family name without loading the font."""
import json
from pathlib import Path
import struct
import sys

data = Path(sys.argv[1]).read_bytes()
count = struct.unpack_from('>H', data, 4)[0]
tables = {tag: (offset, size) for tag, checksum, offset, size in
          (struct.unpack_from('>4sIII', data, 12+i*16) for i in range(count))}
offset, size = tables[b'name']
table = data[offset:offset+size]
_, count, strings = struct.unpack_from('>HHH', table)
names = {}
for i in range(count):
    platform, encoding, language, name, length, start = struct.unpack_from('>HHHHHH', table, 6+i*12)
    if platform == 3 and language == 0x409:
        names[str(name)] = table[strings+start:strings+start+length].decode('utf-16-be')
family = names['1']
if not all(word in family.lower() for word in ('sarasa', 'sc', 'nerd', 'light')) or len(family) >= 32:
    raise ValueError(f'Unexpected Windows Light family: {names}')
print(json.dumps(dict(family=family, names=names)))
