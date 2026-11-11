"""Deterministic visible workload; never reads user files or runs a shell."""
import ctypes
import sys
import time

kernel = ctypes.windll.kernel32
mode = ctypes.c_ulong()
out = kernel.GetStdHandle(-11)
kernel.GetConsoleMode(out, ctypes.byref(mode))
kernel.SetConsoleMode(out, mode.value | 4)
sys.stdout.reconfigure(encoding="utf-8")
print('\x1b]2;Nemoterm rendering verification\x07\x1b[2J\x1b[H', end='')
print('NEMOTERM | Native C / Win32 / ConPTY')
print('Font: SarasaTermSC Nerd Font Light')
print('Chinese: 你好，世界。终端字体与全角字符测试')
print('Nerd: \uf120 \uf07b \ue0b0   Unicode: ┌──────┐ λ α → ✓')
print('Grid: 0123456789 | 中文中文中 | 0123456789')
print('\x1b[1mBold\x1b[0m  \x1b[4mUnderline\x1b[0m  \x1b[7mReverse\x1b[0m')
for row in range(4):
    print(''.join(f'\x1b[48;5;{16+row*36+c}m  ' for c in range(36))+'\x1b[0m')
print(''.join(f'\x1b[48;2;{i*4};{255-i*4};180m ' for i in range(64))+'\x1b[0m')
print('\nSelect this line; Ctrl+Shift+C copies. Right-click defaults to copy.')
print('Ctrl+right-click opens menu. Change Settings > Window/Selection.')
print('Sixel below: red, green, blue blocks (96 x 36 pixels)')
print('\x1bP0;1q"1;1;96;36#1;2;100;20;20#2;2;20;100;20#3;2;20;20;100' +
      ('#1!32~#2!32~#3!32~-' * 6) + '\x1b\\', end='')
sys.stdout.flush()
time.sleep(90)
