/* Keep Windows clipboard I/O off the GUI thread, without letting subsequent
 * user input overtake it. Only allocate an order queue during a paste. */
#include "putty.h"
#include "terminal.h"
#include "win-gui-seat.h"
#include "nemo_paste_order.h"

typedef struct InputItem {
    struct InputItem *next;
    size_t charge;
    int keylen; /* negative ldisc lengths denote special keys */
    bool paste;
} InputItem;
typedef struct NemoPasteOrder {
    InputItem *head, *tail;
    size_t bytes;
    UINT_PTR active;
    ULONGLONG deadline;
    bool delivering;
} NemoPasteOrder;
static UINT_PTR next_ticket;
enum { LIMIT = 64*1024, HOLD_MS = 5000 };

static void free_item(InputItem *item)
{
    smemclr(item, item->charge); sfree(item);
}
static InputItem *pop(NemoPasteOrder *q)
{
    InputItem *item=q->head;
    q->head=item->next; if (!q->head) q->tail=NULL;
    q->bytes-=item->charge; return item;
}
void nemo_paste_order_reset(WinGuiSeat *wgs, bool send_keys)
{
    NemoPasteOrder *q=wgs->paste_order;
    if (!q) return;
    wgs->paste_order=NULL;
    wgs->term->defer_key=NULL;
    if (q->deadline) KillTimer(wgs->term_hwnd, NEMO_PASTE_ORDER_TIMER);
    while (q->head) {
        InputItem *item=pop(q);
        if (send_keys && !item->paste && wgs->ldisc && !wgs->closing)
            term_keyinput(wgs->term,-1,item+1,item->keylen);
        free_item(item);
    }
    sfree(q);
}
static void abandon(WinGuiSeat *wgs)
{
    logevent(wgs->logctx,"Clipboard read abandoned to release pending keyboard input");
    nemo_paste_order_reset(wgs,true);
}
static void deadline(WinGuiSeat *wgs)
{
    NemoPasteOrder *q=wgs->paste_order;
    if (q && q->active && q->head->next && !q->deadline) {
        q->deadline=GetTickCount64()+HOLD_MS;
        if (!SetTimer(wgs->term_hwnd,NEMO_PASTE_ORDER_TIMER,HOLD_MS,NULL)) abandon(wgs);
    }
}
void nemo_paste_order_timer(WinGuiSeat *wgs)
{
    NemoPasteOrder *q=wgs->paste_order;
    if (q && q->deadline && GetTickCount64()>=q->deadline) abandon(wgs);
}
static void append(NemoPasteOrder *q, InputItem *i)
{
    i->next=NULL; q->bytes+=i->charge;
    if (q->tail) q->tail->next=i; else q->head=i;
    q->tail=i;
}
static bool defer_key(TermWin *win, const void *buf, int len)
{
    WinGuiSeat *wgs=container_of(win,WinGuiSeat,termwin);
    NemoPasteOrder *q=wgs->paste_order;
    if (!q || q->delivering) return false;
    size_t n=len<0 ? strlen(buf)+1 : (size_t)len;
    if (n > LIMIT-sizeof(InputItem) || q->bytes > LIMIT-sizeof(InputItem)-n) {
        abandon(wgs); return false;
    }
    InputItem *i=smalloc(sizeof(*i)+n);
    i->charge=sizeof(*i)+n; i->paste=false; i->keylen=len;
    if (n) memcpy(i+1,buf,n);
    append(q,i); deadline(wgs); return true;
}
static void advance(WinGuiSeat *wgs)
{
    NemoPasteOrder *q=wgs->paste_order;
    while (q->head) {
        if (q->head->paste) {
            if (!++next_ticket) ++next_ticket;
            q->active=next_ticket;
            if (nemo_clipboard_start_worker(wgs,q->active)) { deadline(wgs); return; }
            q->active=0;
        }
        InputItem *i=pop(q);
        if (!i->paste) {
            q->delivering=true;
            term_keyinput(wgs->term,-1,i+1,i->keylen);
            q->delivering=false;
        }
        free_item(i);
    }
    nemo_paste_order_reset(wgs,false);
}
void nemo_paste_order_request(WinGuiSeat *wgs)
{
    if (wgs->closing || !wgs->ldisc || !wgs->backend) return;
    if (wgs->paste_order && wgs->paste_order->bytes > LIMIT-sizeof(InputItem)) abandon(wgs);
    if (!wgs->paste_order) {
        wgs->paste_order=snew(NemoPasteOrder);
        memset(wgs->paste_order,0,sizeof(*wgs->paste_order));
        wgs->term->defer_key=defer_key;
    }
    InputItem *i=snew(InputItem); i->charge=sizeof(*i); i->paste=true; i->keylen=0;
    append(wgs->paste_order,i);
    if (wgs->paste_order->active) deadline(wgs); else advance(wgs);
}
bool nemo_paste_order_accept(WinGuiSeat *wgs, UINT_PTR ticket)
{
    NemoPasteOrder *q=wgs->paste_order;
    if (!q || !ticket || q->active!=ticket) return false;
    if (q->deadline) {
        KillTimer(wgs->term_hwnd,NEMO_PASTE_ORDER_TIMER);
        q->deadline=0;
    }
    q->delivering=true; return true; /* image gesture must precede deferred keys */
}
void nemo_paste_order_finish(WinGuiSeat *wgs)
{
    NemoPasteOrder *q=wgs->paste_order;
    assert(q && q->active && q->head->paste);
    free_item(pop(q)); q->delivering=false; q->active=0; advance(wgs);
}
