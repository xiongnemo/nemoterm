/* SPDX-License-Identifier: MIT */
#include "nemo_kitty_placements.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>

struct NemoKittyPlacement {
    struct NemoKittyPlacement *next;
    NemoKittyImage *image;
    int32_t column, row, z;
    uint32_t id, columns, rows, offset_x, offset_y;
    double source_x, source_y, source_width, source_height;
};
struct NemoKittyPlacements {
    NemoKittyCache *cache;
    NemoKittyPlacement *first;
    size_t budget, used;
    unsigned count;
    uint64_t generation;
    NemoKittyPlacementAdmission admit;
    void *ctx;
};

size_t nemo_kitty_placements_memory(const NemoKittyPlacements *s) { return s ? s->used : 0; }
unsigned nemo_kitty_placements_count(const NemoKittyPlacements *s) { return s ? s->count : 0; }
uint64_t nemo_kitty_placements_generation(const NemoKittyPlacements *s) { return s ? s->generation : 0; }
const NemoKittyPlacement *nemo_kitty_placements_first(const NemoKittyPlacements *s) { return s ? s->first : NULL; }
const NemoKittyPlacement *nemo_kitty_placement_next(const NemoKittyPlacement *p) { return p ? p->next : NULL; }

NemoKittyPlacements *nemo_kitty_placements_new(NemoKittyCache *cache, size_t budget,
                                            NemoKittyPlacementAdmission admit, void *ctx)
{
    if (!cache || budget < sizeof(NemoKittyPlacements) ||
        (admit && !admit(ctx, 0, sizeof(NemoKittyPlacements)))) return NULL;
    NemoKittyPlacements *s = calloc(1, sizeof(*s));
    if (s) { s->cache=cache; s->budget=budget; s->used=sizeof(*s); s->admit=admit; s->ctx=ctx; }
    return s;
}

static void remove_view(NemoKittyPlacements *s, NemoKittyPlacement **link, bool callback)
{
    NemoKittyPlacement *p=*link;
    *link=p->next;
    if (!callback) nemo_kitty_image_reference(s->cache,p->image,false);
    s->used-=sizeof(*p); s->count--; s->generation++;
    free(p);
}

void nemo_kitty_placements_image_removed(NemoKittyPlacements *s, const NemoKittyImage *image)
{
    if (!s) return;
    NemoKittyPlacement **link=&s->first;
    while (*link) {
        if ((*link)->image==image) remove_view(s,link,true);
        else link=&(*link)->next;
    }
}

void nemo_kitty_placements_clear(NemoKittyPlacements *s)
{
    if (!s) return;
    while (s->first) {
        NemoKittyImage *image=s->first->image;
        remove_view(s,&s->first,false);
        if (!nemo_kitty_image_id(image) && !nemo_kitty_image_references(image))
            nemo_kitty_cache_remove(s->cache,image);
    }
}
void nemo_kitty_placements_free(NemoKittyPlacements *s)
{
    if (s) { nemo_kitty_placements_clear(s); free(s); }
}

bool nemo_kitty_placement_view(const NemoKittyPlacement *p, uint32_t cw, uint32_t ch,
                               NemoKittyView *out)
{
    if (!p || !out || !cw || !ch || cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX) return false;
    double left=(double)p->column*cw+p->offset_x, top=(double)p->row*ch+p->offset_y;
    double width=p->columns ? (double)p->columns*cw-p->offset_x :
        p->rows ? ((double)p->rows*ch-p->offset_y)*p->source_width/p->source_height : p->source_width;
    double height=p->rows ? (double)p->rows*ch-p->offset_y : width*p->source_height/p->source_width;
    if (width<=0 || height<=0) return false;
    *out=(NemoKittyView){p->image,nemo_kitty_image_id(p->image),p->id,p->z,
        left,top,left+width,top+height,p->source_x,p->source_y,
        p->source_x+p->source_width,p->source_y+p->source_height};
    return true;
}

/* The cell footprint includes pixel offsets, independently of the drawing
 * rectangle. Cropped source coordinates remain pixels; cell anchors remain
 * cells, so later font changes do not move the clipped edge into another row. */
static bool footprint(const NemoKittyPlacement *p,uint32_t cw,uint32_t ch,uint32_t *cols,uint32_t *rows)
{
    double x=p->columns ? p->columns : (p->rows ?
        ((double)p->rows*ch+p->offset_y)*p->source_width/p->source_height :
        p->source_width+p->offset_x)/cw;
    double y=p->rows ? p->rows : (p->columns ?
        ((double)p->columns*cw+p->offset_x)*p->source_height/p->source_width :
        p->source_height+p->offset_y)/ch;
    if (!(x>0 && y>0 && x<=UINT32_MAX && y<=UINT32_MAX)) return false;
    *cols=(uint32_t)x+((uint32_t)x<x); *rows=(uint32_t)y+((uint32_t)y<y); return true;
}

static void insert(NemoKittyPlacements *s, NemoKittyPlacement *p)
{
    NemoKittyPlacement **link=&s->first;
    int32_t z=p->z;
    uint32_t id=nemo_kitty_image_id(p->image);
    while (*link) {
        int32_t other=(*link)->z;
        if (other>z || (other==z && nemo_kitty_image_id((*link)->image)>id)) break;
        link=&(*link)->next;
    }
    p->next=*link; *link=p;
}

NemoKittyPlacementStatus nemo_kitty_placements_put(
    NemoKittyPlacements *s, NemoKittyImage *image, const NemoKittyCommand *command,
    int32_t column, int32_t row, uint32_t cw, uint32_t ch, NemoKittyLayout *out)
{
    if (!s || !command || !out) return NEMO_KITTY_PLACE_INVALID;
    if (!image) return NEMO_KITTY_PLACE_NOT_FOUND;
    const NemoRaster *r=nemo_kitty_image_raster(image);
    NemoKittyLayout g;
    NemoKittyLayoutStatus status=nemo_kitty_layout(command,r->width,r->height,column,row,cw,ch,&g);
    if (status!=NEMO_KITTY_LAYOUT_OK)
        return status==NEMO_KITTY_LAYOUT_UNSUPPORTED ? NEMO_KITTY_PLACE_UNSUPPORTED :
            status==NEMO_KITTY_LAYOUT_LIMIT ? NEMO_KITTY_PLACE_LIMIT : NEMO_KITTY_PLACE_INVALID;
    uint32_t id=nemo_kitty_image_id(image) ? nemo_kitty_get(command,'p') : 0;
    NemoKittyPlacement **link=&s->first;
    while (*link && (!id || (*link)->image!=image || (*link)->id!=id)) link=&(*link)->next;
    NemoKittyPlacement *p=*link;
    if (p) *link=p->next;
    else {
        if (s->count>=NEMO_KITTY_PLACEMENT_MAX || sizeof(*p)>s->budget-s->used ||
            (s->admit && !s->admit(s->ctx,s->used,sizeof(*p)))) return NEMO_KITTY_PLACE_LIMIT;
        p=malloc(sizeof(*p));
        if (!p) return NEMO_KITTY_PLACE_NOMEM;
        if (!nemo_kitty_image_reference(s->cache,image,true)) { free(p); return NEMO_KITTY_PLACE_NOT_FOUND; }
        s->used+=sizeof(*p); s->count++;
    }
    *p=(NemoKittyPlacement){NULL,image,column,row,g.z,id,
        nemo_kitty_get(command,'c'),nemo_kitty_get(command,'r'),g.offset_x,g.offset_y,
        g.source_x,g.source_y,g.source_width,g.source_height};
    insert(s,p); s->generation++; *out=g;
    return NEMO_KITTY_PLACE_OK;
}

static bool overlaps(double a, double b, double start, double end) { return a<end && b>start; }

NemoKittyPlacementStatus nemo_kitty_placements_delete(
    NemoKittyPlacements *s, const NemoKittyCommand *c, int32_t cursor_column,
    int32_t cursor_row, uint32_t columns, uint32_t rows, uint32_t cw, uint32_t ch,
    unsigned *deleted)
{
    if (!s || !c || !deleted || !columns || !rows || !cw || !ch ||
        cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX ||
        (nemo_kitty_has(c,'i') && nemo_kitty_has(c,'I'))) return NEMO_KITTY_PLACE_INVALID;
    uint32_t action=nemo_kitty_get(c,'d');
    bool release=action>='A' && action<='Z';
    if (release) action+='a'-'A';
    if (!action || action>127 || !strchr("aincpqrxyz",(int)action)) return NEMO_KITTY_PLACE_UNSUPPORTED;
    uint32_t x=nemo_kitty_get(c,'x'), y=nemo_kitty_get(c,'y'), id=nemo_kitty_get(c,'p');
    if ((action=='x' || action=='p' || action=='q') && !x) return NEMO_KITTY_PLACE_INVALID;
    if ((action=='y' || action=='p' || action=='q') && !y) return NEMO_KITTY_PLACE_INVALID;
    if (action=='r' && x>y) return NEMO_KITTY_PLACE_INVALID;
    NemoKittyImage *target=action=='i' ? nemo_kitty_cache_find(s->cache,nemo_kitty_get(c,'i'),0) :
        action=='n' ? nemo_kitty_cache_find(s->cache,0,nemo_kitty_get(c,'I')) : NULL;
    NemoKittyImage *candidates[NEMO_KITTY_IMAGE_MAX]; unsigned count=0,removed=0;
    /* Uppercase id/number also frees a matching image with no placements. */
    if (release && target && !id) candidates[count++]=target;
    NemoKittyPlacement **link=&s->first;
    while (*link) {
        NemoKittyPlacement *p=*link; NemoKittyView v;
        bool match=false;
        uint32_t cell_columns,cell_rows;
        if (nemo_kitty_placement_view(p,cw,ch,&v) && footprint(p,cw,ch,&cell_columns,&cell_rows)) {
            double px=action=='c' ? cursor_column : (double)x-1;
            double py=action=='c' ? cursor_row : (double)y-1;
            bool inx=px>=p->column && px<(double)p->column+cell_columns;
            bool iny=py>=p->row && py<(double)p->row+cell_rows;
            switch (action) {
              case 'a': match=overlaps(v.left,v.right,0,(double)columns*cw) &&
                            overlaps(v.top,v.bottom,0,(double)rows*ch); break;
              case 'i': case 'n': match=p->image==target && (!id || p->id==id); break;
              case 'c': case 'p': match=inx && iny; break;
              case 'q': match=inx && iny && v.z==nemo_kitty_signed(c,'z'); break;
              case 'r': match=v.id && v.id>=x && v.id<=y; break;
              case 'x': match=inx; break;
              case 'y': match=iny; break;
              case 'z': match=v.z==nemo_kitty_signed(c,'z'); break;
            }
        }
        if (!match) { link=&p->next; continue; }
        NemoKittyImage *image=p->image;
        if (release || !nemo_kitty_image_id(image)) {
            unsigned i=0; while (i<count && candidates[i]!=image) i++;
            if (i==count && count<NEMO_KITTY_IMAGE_MAX) candidates[count++]=image;
        }
        remove_view(s,link,false); removed++;
    }
    for (unsigned i=0;i<count;i++)
        if (!nemo_kitty_image_references(candidates[i])) nemo_kitty_cache_remove(s->cache,candidates[i]);
    if (release && action=='r' && !id) nemo_kitty_cache_prune_range(s->cache,x,y);
    *deleted=removed; return NEMO_KITTY_PLACE_OK;
}

void nemo_kitty_placements_scroll(NemoKittyPlacements *s, int32_t top, int32_t bottom,
    int32_t lines, bool margins, uint32_t history_rows, uint32_t cw, uint32_t ch)
{
    if (!s || !lines || top<0 || bottom<top || !cw || !ch ||
        cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX) return;
    NemoKittyPlacement **link=&s->first;
    while (*link) {
        NemoKittyPlacement *p=*link; NemoKittyView v;uint32_t cols,rows;
        if (!nemo_kitty_placement_view(p,cw,ch,&v) || !footprint(p,cw,ch,&cols,&rows) ||
            (margins && (p->row<top || (int64_t)p->row+rows>(int64_t)bottom+1)) ||
            (!margins && lines<0 && (int64_t)p->row+rows<=0)) {
            link=&p->next; continue;
        }
        int64_t row=(int64_t)p->row-lines;
        int64_t end=row+rows;
        bool discard=row<INT32_MIN || row>INT32_MAX ||
            end<=(margins ? (int64_t)top : -(int64_t)history_rows) || (margins && row>bottom);
        double source_y=p->source_y,source_height=p->source_height;
        uint32_t clipped=0,offset_y=p->offset_y;
        if (!discard && margins) {
            /* Crop in source pixels, then retain the surviving row anchor.
             * A later cell-size change scales explicit row counts normally. */
            double scale=p->source_height/(v.bottom-v.top);
            if (row<top) {
                clipped=(uint32_t)((int64_t)top-row);
                double cut=((double)clipped*ch-offset_y)*scale;
                source_y+=cut;source_height-=cut;row=top;offset_y=0;
            } else if (end>(int64_t)bottom+1) {
                clipped=(uint32_t)(end-bottom-1);
                double visible=((double)(rows-clipped)*ch-offset_y)*scale;
                if (visible<source_height) source_height=visible;
            }
            discard=source_height<=0 || clipped>=rows || (p->rows && clipped>=p->rows);
        }
        if (discard) {
            NemoKittyImage *image=p->image;
            remove_view(s,link,false);
            if (!nemo_kitty_image_id(image) && !nemo_kitty_image_references(image)) nemo_kitty_cache_remove(s->cache,image);
            continue;
        }
        p->row=(int32_t)row;
        p->source_y=source_y;p->source_height=source_height;p->offset_y=offset_y;
        if (p->rows) p->rows-=clipped;
        s->generation++; link=&p->next;
    }
}
