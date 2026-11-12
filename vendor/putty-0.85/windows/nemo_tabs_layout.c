/* SPDX-License-Identifier: MIT */
#include "nemo_tabs_layout.h"
#include <stdint.h>
#include <limits.h>

static int lesser(int a, int b) { return a < b ? a : b; }
static int greater(int a, int b) { return a > b ? a : b; }
static int bound(int x, int low, int high) { return lesser(greater(x, low), high); }
static bool contains(NemoTabRect r, int x, int y)
{
    return x >= r.x && y >= r.y && (int64_t)x < (int64_t)r.x+r.width &&
        (int64_t)y < (int64_t)r.y+r.height;
}
static int scaled(int value, int dpi) { return (value*dpi+48)/96; }
NemoTabMetrics nemo_tabs_metrics(int dpi, int sidebar)
{
    dpi = bound(dpi ? dpi : 96, 48, 768);
    sidebar = bound(sidebar ? sidebar : 192, 96, 480);
    return (NemoTabMetrics){scaled(28,dpi), scaled(sidebar,dpi),
        scaled(84,dpi), scaled(168,dpi), scaled(4,dpi)};
}
static NemoTabRect along(const NemoTabLayout *l, int start, int length)
{
    if (length <= 0) return (NemoTabRect){0};
    if (l->vertical)
        return (NemoTabRect){l->bar.x,l->bar.y+start,l->bar.width,length};
    return (NemoTabRect){l->bar.x+start,l->bar.y,length,l->bar.height};
}
NemoTabLayout nemo_tabs_layout(int width, int height, NemoTabSide side,
                              NemoTabMetrics metrics, int count, int first)
{
    NemoTabLayout l = {0};
    width = greater(0,width); height = greater(0,height);
    l.side = side >= NEMO_TABS_TOP && side <= NEMO_TABS_RIGHT ? side : NEMO_TABS_TOP;
    l.vertical = l.side == NEMO_TABS_LEFT || l.side == NEMO_TABS_RIGHT;
    metrics.row = bound(metrics.row,1,4096);
    metrics.sidebar = bound(metrics.sidebar,1,4096);
    metrics.minimum = bound(metrics.minimum,1,4096);
    metrics.preferred = bound(metrics.preferred,metrics.minimum,4096);
    metrics.padding = bound(metrics.padding,0,metrics.row/2);
    l.metrics = metrics;
    l.count = greater(count,0);
    l.content = (NemoTabRect){0,0,width,height};
    int thickness = l.vertical ? lesser(metrics.sidebar,greater(0,width-1)) :
        lesser(metrics.row,greater(0,height-1));
    if (!width || !height || !thickness) return l;
    l.bar = (NemoTabRect){0,0,l.vertical ? thickness : width,l.vertical ? height : thickness};
    if (l.vertical) {
        l.content.width -= thickness;
        if (l.side == NEMO_TABS_LEFT) l.content.x = thickness;
        else l.bar.x = l.content.width;
    } else {
        l.content.height -= thickness;
        if (l.side == NEMO_TABS_TOP) l.content.y = thickness;
        else l.bar.y = l.content.height;
    }
    int length = l.vertical ? height : width;
    int button = lesser(metrics.row,length), available = length-button;
    int minimum = l.vertical ? metrics.row : metrics.minimum;
    l.add = along(&l,available,button);
    l.overflow = l.count > available/minimum;
    if (l.overflow) {
        /* Reserve two arrows without consuming the last possible tab pixel.
         * Wheel/keyboard scrolling still works when arrows become empty. */
        int arrow = lesser(metrics.row,available/3);
        l.next = along(&l,available-arrow,arrow);
        l.previous = along(&l,available-2*arrow,arrow);
        available -= 2*arrow;
    }
    if (!available || !l.count) return l;
    l.visible = lesser(l.count,greater(1,available/minimum));
    int preferred = l.vertical ? metrics.row : metrics.preferred;
    l.extent = lesser(preferred,available/l.visible);
    l.first = bound(first,0,l.count-l.visible);
    return l;
}
NemoTabRect nemo_tabs_item(const NemoTabLayout *l, int index)
{
    if (index < l->first || index-l->first >= l->visible)
        return (NemoTabRect){0};
    return along(l,(index-l->first)*l->extent,l->extent);
}
NemoTabRect nemo_tabs_close(const NemoTabLayout *l, int index)
{
    NemoTabRect r = nemo_tabs_item(l,index);
    int size = lesser(l->metrics.row,r.height)-2*l->metrics.padding;
    if (size <= 0 || r.width/2 < l->metrics.row) return (NemoTabRect){0};
    return (NemoTabRect){r.x+r.width-l->metrics.padding-size,
        r.y+(r.height-size)/2,size,size};
}
NemoTabHit nemo_tabs_hit(const NemoTabLayout *l, int x, int y)
{
    NemoTabHit result = {NEMO_TAB_NONE,-1};
    if (!contains(l->bar,x,y)) return result;
    if (contains(l->add,x,y)) result.kind = NEMO_TAB_ADD;
    else if (contains(l->previous,x,y)) result.kind = NEMO_TAB_PREVIOUS;
    else if (contains(l->next,x,y)) result.kind = NEMO_TAB_NEXT;
    else if (l->extent > 0) {
        int index = (l->vertical ? y-l->bar.y : x-l->bar.x)/l->extent;
        if (index < l->visible) {
            result.index = l->first+index;
            result.kind = contains(nemo_tabs_close(l,result.index),x,y) ?
                NEMO_TAB_CLOSE : NEMO_TAB_BODY;
        }
    }
    return result;
}
int nemo_tabs_reveal(const NemoTabLayout *l, int index)
{
    if (!l->visible || !l->count) return 0;
    index = bound(index,0,l->count-1);
    if (index < l->first) return index;
    if (index-l->first >= l->visible) return index-l->visible+1;
    return l->first;
}
static int fit(int64_t position, int origin, int length, int extent)
{
    int64_t last = (int64_t)origin+length-extent;
    if (position > last) position = last;
    if (position < origin) position = origin;
    return (int)position;
}
NemoTabRect nemo_tabs_preview(NemoTabRect anchor, NemoTabSide side,
                             NemoTabRect work, int width, int height, int gap)
{
    /* Intersect malformed extreme rectangles with the signed coordinate
     * domain before positioning. All intermediate screen sums are 64-bit. */
    work.width = (int)((int64_t)work.x+greater(0,work.width) > INT_MAX ?
        (int64_t)INT_MAX-work.x : greater(0,work.width));
    work.height = (int)((int64_t)work.y+greater(0,work.height) > INT_MAX ?
        (int64_t)INT_MAX-work.y : greater(0,work.height));
    width = bound(width,0,lesser(320,work.width));
    height = bound(height,0,lesser(200,work.height));
    gap = bound(gap,0,4096);
    int64_t x = anchor.x, y = anchor.y;
    int64_t right = (int64_t)work.x+work.width, bottom = (int64_t)work.y+work.height;
    switch (side) {
      case NEMO_TABS_LEFT:
        x += (int64_t)greater(0,anchor.width)+gap;
        if (x+width > right) x = (int64_t)anchor.x-gap-width;
        break;
      case NEMO_TABS_RIGHT:
        x -= (int64_t)gap+width;
        if (x < work.x) x = (int64_t)anchor.x+greater(0,anchor.width)+gap;
        break;
      case NEMO_TABS_BOTTOM:
        y -= (int64_t)gap+height;
        if (y < work.y) y = (int64_t)anchor.y+greater(0,anchor.height)+gap;
        break;
      default:
        y += (int64_t)greater(0,anchor.height)+gap;
        if (y+height > bottom) y = (int64_t)anchor.y-gap-height;
        break;
    }
    return (NemoTabRect){fit(x,work.x,work.width,width),
        fit(y,work.y,work.height,height),width,height};
}
