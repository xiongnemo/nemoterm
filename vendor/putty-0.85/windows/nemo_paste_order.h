#ifndef PUTTY_NEMO_PASTE_ORDER_H
#define PUTTY_NEMO_PASTE_ORDER_H
#define NEMO_PASTE_ORDER_TIMER 0x4e504f52u
void nemo_paste_order_request(WinGuiSeat *);
bool nemo_paste_order_accept(WinGuiSeat *, UINT_PTR ticket);
void nemo_paste_order_finish(WinGuiSeat *);
void nemo_paste_order_reset(WinGuiSeat *, bool send_keys);
void nemo_paste_order_timer(WinGuiSeat *);
bool nemo_clipboard_start_worker(WinGuiSeat *, UINT_PTR ticket);
#endif
