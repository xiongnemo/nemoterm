/* SPDX-License-Identifier: MIT */
#ifndef NEMO_KEY_INPUT_H
#define NEMO_KEY_INPUT_H

void nemo_keyboard_prepare(WinGuiSeat *, UINT, WPARAM, LPARAM, BYTE state[256]);
bool nemo_win32_input_active(WinGuiSeat *);
bool nemo_keyboard_input(WinGuiSeat *, UINT, WPARAM, LPARAM, const BYTE state[256], HKL);
bool nemo_keyboard_text(WinGuiSeat *, const wchar_t *, size_t);
void nemo_keyboard_focus_lost(WinGuiSeat *);
void nemo_keyboard_free(WinGuiSeat *);

#endif
