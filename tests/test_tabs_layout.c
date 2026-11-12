/* SPDX-License-Identifier: MIT */
#include "nemo_tabs_layout.h"
#undef NDEBUG
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>

static bool inside(NemoTabRect a, NemoTabRect b)
{
    if (!a.width || !a.height) return true;
    return a.x >= b.x && a.y >= b.y && (int64_t)a.x+a.width <= (int64_t)b.x+b.width &&
        (int64_t)a.y+a.height <= (int64_t)b.y+b.height;
}
static int64_t area(NemoTabRect r) { return (int64_t)r.width*r.height; }
static bool overlaps(NemoTabRect a, NemoTabRect b)
{
    return area(a) && area(b) && (int64_t)a.x+a.width > b.x && (int64_t)b.x+b.width > a.x &&
        (int64_t)a.y+a.height > b.y && (int64_t)b.y+b.height > a.y;
}
static void verify(NemoTabLayout l, int width, int height)
{
    NemoTabRect client = {0,0,width,height};
    assert(inside(l.bar,client) && inside(l.content,client));
    assert(area(l.bar)+area(l.content)==area(client));
    assert(!overlaps(l.bar,l.content));
    assert(inside(l.add,l.bar) && inside(l.previous,l.bar) && inside(l.next,l.bar));
    assert(!overlaps(l.add,l.previous) && !overlaps(l.add,l.next) && !overlaps(l.previous,l.next));
    assert(l.first >= 0 && l.visible >= 0 && l.first <= l.count-l.visible);
    for (int i=0;i<l.visible;i++) {
        int index=l.first+i;
        NemoTabRect r=nemo_tabs_item(&l,index), close=nemo_tabs_close(&l,index);
        assert(area(r)>0 && inside(r,l.bar) && inside(close,r));
        assert(!overlaps(r,l.add) && !overlaps(r,l.previous) && !overlaps(r,l.next));
        if (i) assert(!overlaps(r,nemo_tabs_item(&l,index-1)));
        NemoTabHit hit=nemo_tabs_hit(&l,r.x,r.y);
        assert(hit.kind==NEMO_TAB_BODY && hit.index==index);
        if (area(close)) {
            hit=nemo_tabs_hit(&l,close.x,close.y);
            assert(hit.kind==NEMO_TAB_CLOSE && hit.index==index);
        }
    }
    assert(nemo_tabs_hit(&l,-1,-1).kind==NEMO_TAB_NONE);
    assert(nemo_tabs_hit(&l,width,height).kind==NEMO_TAB_NONE);
    if (area(l.content)) assert(nemo_tabs_hit(&l,l.content.x,l.content.y).kind==NEMO_TAB_NONE);
    if (area(l.add)) assert(nemo_tabs_hit(&l,l.add.x,l.add.y).kind==NEMO_TAB_ADD);
    if (area(l.previous)) assert(nemo_tabs_hit(&l,l.previous.x,l.previous.y).kind==NEMO_TAB_PREVIOUS);
    if (area(l.next)) assert(nemo_tabs_hit(&l,l.next.x,l.next.y).kind==NEMO_TAB_NEXT);
}
int main(void)
{
    NemoTabMetrics m=nemo_tabs_metrics(96,0);
    NemoTabLayout l=nemo_tabs_layout(800,600,NEMO_TABS_TOP,m,3,0);
    assert(l.bar.height==28 && l.content.y==28 && l.content.height==572);
    assert(l.visible==3 && l.extent==168 && !l.overflow);
    l=nemo_tabs_layout(800,600,NEMO_TABS_BOTTOM,m,3,0);
    assert(l.bar.y==572 && l.content.y==0 && l.content.height==572);
    l=nemo_tabs_layout(800,600,NEMO_TABS_LEFT,m,3,0);
    assert(l.bar.width==192 && l.content.x==192 && l.extent==28);
    l=nemo_tabs_layout(800,600,NEMO_TABS_RIGHT,m,3,0);
    assert(l.bar.x==608 && l.content.width==608 && l.content.x==0);
    for (int side=0;side<4;side++) {
        l=nemo_tabs_layout(800,600,(NemoTabSide)side,m,100,0);
        assert(l.overflow && l.visible>0);
        int first=nemo_tabs_reveal(&l,99);
        l=nemo_tabs_layout(800,600,(NemoTabSide)side,m,100,first);
        assert(area(nemo_tabs_item(&l,99))>0 && nemo_tabs_reveal(&l,0)==0);
        assert(!area(nemo_tabs_item(&l,-1)) && !area(nemo_tabs_item(&l,INT_MAX)));
        verify(l,800,600);
    }
    unsigned cases=0;
    for (int dpi=96;dpi<=288;dpi+=48)
        for (int side=0;side<4;side++)
            for (int width=0;width<300;width+=13)
                for (int height=0;height<240;height+=17)
                    for (int count=0;count<30;count+=3) {
                        l=nemo_tabs_layout(width,height,(NemoTabSide)side,nemo_tabs_metrics(dpi,0),count,INT_MAX);
                        verify(l,width,height);cases++;
                    }
    const int extremes[]={INT_MIN,-1,0,1,2,INT_MAX};
    for (unsigned i=0;i<sizeof(extremes)/sizeof(*extremes);i++) {
        int v=extremes[i];
        m=nemo_tabs_metrics(v,v);
        l=nemo_tabs_layout(v,v,(NemoTabSide)v,m,v,v);
        /* Bound enumeration when exercising extreme client dimensions. */
        assert(l.visible<=l.count && l.visible>=0);
        assert(inside(l.bar,(NemoTabRect){0,0,v>0?v:0,v>0?v:0}));
        (void)nemo_tabs_hit(&l,INT_MAX,INT_MAX);
        (void)nemo_tabs_item(&l,INT_MIN);
        (void)nemo_tabs_close(&l,INT_MAX);
        (void)nemo_tabs_reveal(&l,INT_MIN);
    }
    NemoTabRect work={-1920,-1080,1920,1040}, anchor={-1600,-900,100,28};
    for (int side=0;side<4;side++) {
        NemoTabRect p=nemo_tabs_preview(anchor,(NemoTabSide)side,work,640,480,8);
        assert(p.width==320 && p.height==200 && inside(p,work));
    }
    NemoTabRect p=nemo_tabs_preview((NemoTabRect){-500,-50,200,28},NEMO_TABS_TOP,work,320,200,8);
    assert(p.y==-258); /* Flip above the anchor near the bottom work-area edge. */
    p=nemo_tabs_preview((NemoTabRect){0},NEMO_TABS_LEFT,(NemoTabRect){-5,-9,10,12},320,200,8);
    assert(p.x==-5 && p.y==-9 && p.width==10 && p.height==12);
    for (unsigned i=0;i<sizeof(extremes)/sizeof(*extremes);i++)
        for (unsigned j=0;j<sizeof(extremes)/sizeof(*extremes);j++) {
            int a=extremes[i],b=extremes[j];
            p=nemo_tabs_preview((NemoTabRect){a,a,b,b},(NemoTabSide)a,
                (NemoTabRect){b,b,a,a},INT_MAX,INT_MAX,INT_MAX);
            assert(p.width>=0 && p.width<=320 && p.height>=0 && p.height<=200);
        }
    printf("Tab layout: %u small-window/DPI/overflow cases plus edge and preview checks passed\n",cases);
    return 0;
}
