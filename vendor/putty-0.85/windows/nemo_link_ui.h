/* SPDX-License-Identifier: MIT */
#ifndef NEMO_LINK_UI_H
#define NEMO_LINK_UI_H

#define IDM_NEMO_OPEN_LINK 0x01C0
#define IDM_NEMO_COPY_LINK 0x01D0

bool nemo_link_button(WinGuiSeat *, UINT, WPARAM, LPARAM);
bool nemo_link_motion(WinGuiSeat *, WPARAM *, LPARAM);
void nemo_link_key(WinGuiSeat *, UINT, WPARAM);
void nemo_link_refresh(WinGuiSeat *);
void nemo_link_leave(WinGuiSeat *);
void nemo_link_cancel(WinGuiSeat *);
void nemo_link_free(WinGuiSeat *);
bool nemo_link_hand_cursor(WinGuiSeat *);
UINT nemo_link_menu(WinGuiSeat *, HMENU, POINT client_point);

#endif
