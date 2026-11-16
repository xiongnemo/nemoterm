/* Exercise the production allocator without creating a window or GPU device.
 * Fully clipped copies leave no queued GPU work. A later reservation must
 * nevertheless stay inside the pre-existing staging strip. No out-of-bounds
 * pixel write is performed, including when testing the old implementation. */
#include "../vendor/putty-0.85/windows/nemo_d3d11.c"

void modalfatalbox(const char *format, ...)
{
    va_list args;va_start(args,format);vfprintf(stderr,format,args);va_end(args);
    abort();
}

static int reserve_checked(NemoD3D11 *g, int width, int height, unsigned step)
{
    int x=-1,y=-1;
    if (!reserve_run(g,width,height,&x,&y) || x<0 || y<0 ||
        x>g->strip_width-width || y>g->strip_height-height) {
        fprintf(stderr,"Reservation %u escaped strip: %dx%d at %d,%d in %dx%d\n",
                step,width,height,x,y,g->strip_width,g->strip_height);
        return 0;
    }
    RECT outside={0,g->height+1,width,g->height+1+height};
    queue_copy(g,outside,x,y);
    if (g->batch_count || g->failed) {
        fprintf(stderr,"Fully clipped reservation unexpectedly queued work\n");
        return 0;
    }
    return 1;
}

int main(void)
{
    NemoD3D11 g={0};
    g.width=g.strip_width=64;g.height=g.strip_height=32;g.limit=16384;
    /* Two discarded full-width rows fill the strip; the third must wrap. */
    for (unsigned i=1;i<=12;i++)
        if (!reserve_checked(&g,64,16,i)) return 1;
    /* Independent bounds checks across many discarded rectangle shapes. */
    unsigned state=1;
    for (unsigned i=0;i<10000;i++) {
        state=1664525U*state+1013904223U;int width=1+(int)((state>>16)%64);
        state=1664525U*state+1013904223U;int height=1+(int)((state>>16)%32);
        if (!reserve_checked(&g,width,height,13+i)) return 1;
    }
    reset_batch(&g);
    int x,y;
    if (!reserve_run(&g,32,16,&x,&y)) return 1;
    /* Overlay readback flushes while a current reservation is still active.
     * An empty flush must not globally reset that live packing cursor. */
    int before[]={g.batch_x,g.batch_y,g.batch_row,g.batch_bottom};
    if (!flush_batch(&g) || g.batch_x!=before[0] || g.batch_y!=before[1] ||
        g.batch_row!=before[2] || g.batch_bottom!=before[3]) {
        fprintf(stderr,"Empty flush invalidated an active reservation\n");
        return 1;
    }
    puts("DirectX staging reservations: 10012 discarded rectangles and active-overlay control passed");
    return 0;
}
