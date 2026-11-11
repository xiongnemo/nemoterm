/* SPDX-License-Identifier: MIT */
#ifndef NEMO_OSC52_UI_H
#define NEMO_OSC52_UI_H
#define WM_NEMO_OSC52_READY (WM_APP + 20)
#define NEMO_OSC52_TIMER 0x4e4f5352
bool nemo_osc52_system_write(TermWin *, const char *, size_t);
bool nemo_osc52_system_read(TermWin *, uint64_t);
void nemo_osc52_poll(WinGuiSeat *, WPARAM cookie);
void nemo_osc52_window_free(WinGuiSeat *);
#endif
