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
    uint64_t sequence;
    NemoKittyPlacements *owner;
    uint64_t parent;
    int32_t parent_x, parent_y;
    uint64_t prototype;
    bool virtual;
};
struct NemoKittyPlacements {
    NemoKittyCache *cache;
    NemoKittyPlacement *first;
    size_t budget, used;
    unsigned count, cells, virtuals;
    uint64_t generation, sequence;
    NemoKittyPlacementAdmission admit;
    void *ctx;
    /* Prototypes never exceed the ordinary-placement limit. Keep their
     * identity index separate from the much larger derived-cell list. */
    NemoKittyPlacement *virtual_index[NEMO_KITTY_PLACEMENT_MAX];
    /* During a cell refresh, later cells of an image follow its earlier
     * cells in drawing order. Any unlink/replacement invalidates all hints. */
    NemoKittyPlacement *cell_insert[NEMO_KITTY_IMAGE_MAX];
    unsigned cell_insert_count;
};

static const NemoKittyPlacement *virtual_by_sequence(const NemoKittyPlacements *s,
                                                   uint64_t sequence)
{
    unsigned lo=0,hi=s->virtuals;
    while (lo<hi) {
        unsigned mid=lo+(hi-lo)/2;
        if (s->virtual_index[mid]->sequence<sequence) lo=mid+1;
        else hi=mid;
    }
    return lo<s->virtuals && s->virtual_index[lo]->sequence==sequence ?
        s->virtual_index[lo] : NULL;
}

static void virtual_remove(NemoKittyPlacements *s, const NemoKittyPlacement *p)
{
    for (unsigned i=0;i<s->virtuals;i++) {
        if (s->virtual_index[i]!=p) continue;
        s->virtuals--;
        memmove(s->virtual_index+i,s->virtual_index+i+1,
                (s->virtuals-i)*sizeof(*s->virtual_index));
        return;
    }
}

static void virtual_insert(NemoKittyPlacements *s, NemoKittyPlacement *p)
{
    unsigned i=s->virtuals;
    while (i && s->virtual_index[i-1]->sequence>p->sequence) {
        s->virtual_index[i]=s->virtual_index[i-1];i--;
    }
    s->virtual_index[i]=p;s->virtuals++;
}

static const NemoKittyPlacement *by_sequence(const NemoKittyPlacements *s, uint64_t sequence)
{
    if (sequence) {
        const NemoKittyPlacement *p=virtual_by_sequence(s,sequence);
        if (p) return p;
        for (const NemoKittyPlacement *p=s->first;p;p=p->next)
            if (p->sequence==sequence) return p;
    }
    return NULL;
}

/* Parent identity never stores a pointer that could survive a deletion.
 * Stored creation anchors remain separate from resolved drawing coordinates:
 * upstream scrolling/deletion filters operate on the former. */
static bool resolve(const NemoKittyPlacement *p, int64_t *column, int64_t *row)
{
    int64_t x=0,y=0;
    unsigned depth=0;
    while (p->parent) {
        if (depth++>=NEMO_KITTY_PARENT_DEPTH_MAX) return false;
        x+=p->parent_x;y+=p->parent_y;
        p=by_sequence(p->owner,p->parent);
        if (!p) return false;
    }
    int32_t anchor_x=p->column,anchor_y=p->row;
    if (p->virtual) {
        bool found=false;
        for (const NemoKittyPlacement *q=p->owner->first;q;q=q->next) {
            if (q->prototype!=p->sequence) continue;
            if (!found || q->column<anchor_x) anchor_x=q->column;
            if (!found || q->row<anchor_y) anchor_y=q->row;
            found=true;
        }
        if (!found) return false;
    }
    *column=(int64_t)anchor_x+x;*row=(int64_t)anchor_y+y;
    return true;
}

static bool ancestry_alive(const NemoKittyPlacement *p)
{
    unsigned depth=0;
    while (p->parent) {
        if (depth++>=NEMO_KITTY_PARENT_DEPTH_MAX) return false;
        p=by_sequence(p->owner,p->parent);
        if (!p) return false;
    }
    return true;
}

size_t nemo_kitty_placements_memory(const NemoKittyPlacements *s) { return s ? s->used : 0; }
unsigned nemo_kitty_placements_count(const NemoKittyPlacements *s) { return s ? s->count : 0; }
bool nemo_kitty_placements_have_cells(const NemoKittyPlacements *s) { return s && (s->virtuals || s->cells); }
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
    s->cell_insert_count=0;
    *link=p->next;
    if (!callback) nemo_kitty_image_reference(s->cache,p->image,false);
    if (p->prototype) s->cells--;
    if (p->virtual) virtual_remove(s,p);
    s->used-=sizeof(*p); s->count--; s->generation++;
    free(p);
}

static void collect_orphans(NemoKittyPlacements *s)
{
    bool changed;
    do {
        changed=false;
        NemoKittyPlacement **link=&s->first;
        while (*link) {
            NemoKittyPlacement *p=*link;
            if (p->parent && !ancestry_alive(p) &&
                nemo_kitty_cache_release_orphan(s->cache,p->image)) {
                remove_view(s,link,true);
                changed=true;
            } else link=&p->next;
        }
    } while (changed);
    /* This is a no-op while inside a cache callback. The cache drains its
     * deferred removals after the current image/list operation is complete. */
    nemo_kitty_cache_prune_orphans(s->cache);
}

void nemo_kitty_placements_image_removed(NemoKittyPlacements *s, const NemoKittyImage *image)
{
    if (!s) return;
    NemoKittyPlacement **link=&s->first;
    while (*link) {
        if ((*link)->image==image) remove_view(s,link,true);
        else link=&(*link)->next;
    }
    collect_orphans(s);
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

static bool placement_view_at(const NemoKittyPlacement *p, uint32_t cw, uint32_t ch,
                              int64_t column, int64_t row, NemoKittyView *out)
{
    if (!p || !out || !cw || !ch || cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX) return false;
    double left=(double)column*cw+p->offset_x, top=(double)row*ch+p->offset_y;
    double width=p->columns ? (double)p->columns*cw-p->offset_x :
        p->rows ? ((double)p->rows*ch-p->offset_y)*p->source_width/p->source_height : p->source_width;
    double height=p->rows ? (double)p->rows*ch-p->offset_y : width*p->source_height/p->source_width;
    if (width<=0 || height<=0) return false;
    *out=(NemoKittyView){p->image,nemo_kitty_image_id(p->image),p->id,p->z,
        left,top,left+width,top+height,p->source_x,p->source_y,
        p->source_x+p->source_width,p->source_y+p->source_height};
    return true;
}

bool nemo_kitty_placement_view(const NemoKittyPlacement *p, uint32_t cw, uint32_t ch,
                               NemoKittyView *out)
{
    int64_t column,row;
    if (!p || p->virtual) return false;
    if (p->prototype) {
        const NemoKittyPlacement *prototype=virtual_by_sequence(p->owner,p->prototype);
        if (!prototype || !prototype->virtual) return false;
    }
    return p && resolve(p,&column,&row) && placement_view_at(p,cw,ch,column,row,out);
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
    if (p->prototype) {
        unsigned i=0;
        while (i<s->cell_insert_count && s->cell_insert[i]->image!=p->image) i++;
        if (i<s->cell_insert_count) link=&s->cell_insert[i]->next;
        else if (i<NEMO_KITTY_IMAGE_MAX) s->cell_insert_count++;
        if (i<NEMO_KITTY_IMAGE_MAX) s->cell_insert[i]=p;
    }
    int32_t z=p->z;
    uint64_t order=nemo_kitty_image_sequence(p->image);
    while (*link) {
        int32_t other=(*link)->z;
        uint64_t other_order=nemo_kitty_image_sequence((*link)->image);
        if (other>z || (other==z && (other_order>order ||
            (other_order==order && (*link)->sequence>p->sequence)))) break;
        link=&(*link)->next;
    }
    p->next=*link; *link=p;
}

void nemo_kitty_placements_remove_cells(NemoKittyPlacements *s, int32_t first, int32_t last)
{
    if (!s) return;
    NemoKittyPlacement **link=&s->first;
    while (*link) {
        NemoKittyPlacement *p=*link;
        bool discard=p->prototype && p->row>=first && p->row<=last;
        if (p->prototype && !discard) {
            const NemoKittyPlacement *prototype=virtual_by_sequence(s,p->prototype);
            discard=!prototype || !prototype->virtual;
        }
        if (discard)
            remove_view(s,link,false);
        else link=&p->next;
    }
    /* Refreshing text references does not discard named image data. */
    collect_orphans(s);
}

void nemo_kitty_placements_erase_all(NemoKittyPlacements *s)
{
    if (!s) return;
    NemoKittyImage *unused[NEMO_KITTY_IMAGE_MAX];unsigned count=0;
    NemoKittyPlacement **link=&s->first;
    while (*link) {
        NemoKittyPlacement *p=*link;
        if (!p->virtual) {
            NemoKittyImage *image=p->image;
            remove_view(s,link,false);
            if (!nemo_kitty_image_id(image) && !nemo_kitty_image_references(image))
                unused[count++]=image;
        } else link=&p->next;
    }
    collect_orphans(s);
    for (unsigned i=0;i<count;i++) nemo_kitty_cache_remove_unreferenced(s->cache,unused[i]);
}

bool nemo_kitty_placements_cell(NemoKittyPlacements *s, uint32_t image_id,
    uint32_t placement_id, uint32_t image_column, uint32_t image_row,
    uint32_t columns, int32_t column, int32_t row, uint32_t cw, uint32_t ch)
{
    if (!s || !image_id || !columns || !cw || !ch ||
        cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX) return false;
    const NemoKittyPlacement *prototype=NULL;
    for (unsigned i=0;i<s->virtuals;i++) {
        const NemoKittyPlacement *q=s->virtual_index[i];
        if (nemo_kitty_image_id(q->image)==image_id && (!placement_id || q->id==placement_id)) {
            prototype=q;break;
        }
    }
    if (!prototype) return false;
    NemoKittyImage *image=prototype->image;
    const NemoRaster *r=nemo_kitty_image_raster(image);
    uint32_t grid_columns=prototype->columns ? prototype->columns : (r->width-1)/cw+1;
    uint32_t grid_rows=prototype->rows ? prototype->rows : (r->height-1)/ch+1;
    double box_width=(double)grid_columns*cw,box_height=(double)grid_rows*ch;
    double scale_x=box_width/r->width,scale_y=box_height/r->height;
    double scale=scale_x<scale_y ? scale_x : scale_y;
    double x=((double)image_column*cw-(box_width-r->width*scale)/2)/scale;
    double y=((double)image_row*ch-(box_height-r->height*scale)/2)/scale;
    double width=(double)columns*cw/scale,height=(double)ch/scale;
    uint32_t offset_x=0,offset_y=0,rows=1;
    int64_t anchor_x=column,anchor_y=row;
    if (x<0) {
        double offset=-x*scale;
        if (offset>=UINT32_MAX) return false;
        offset_x=(uint32_t)offset;
        uint32_t skip=offset_x/cw;
        if (skip>=columns) return false;
        anchor_x+=skip;columns-=skip;offset_x%=cw;width+=x;x=0;
    }
    if (y<0) {
        double offset=-y*scale;
        if (offset>=ch) return false;
        offset_y=(uint32_t)offset;height+=y;y=0;
    }
    if (x+width>r->width) {
        double redundant=(x+width-r->width)*scale;
        if (redundant>=UINT32_MAX) return false;
        uint32_t skip=(uint32_t)redundant/cw;
        if (skip>=columns) return false;
        width-=(double)skip*cw/scale;columns-=skip;
    }
    if (y+height>r->height && (y+height-r->height)*scale>=ch) return false;
    if (width<=0 || height<=0 || anchor_x<INT32_MIN || anchor_x>INT32_MAX ||
        s->cells>=NEMO_KITTY_CELL_RUN_MAX || s->sequence==UINT64_MAX ||
        sizeof(NemoKittyPlacement)>s->budget-s->used ||
        (s->admit && !s->admit(s->ctx,s->used,sizeof(NemoKittyPlacement)))) return false;
    NemoKittyPlacement *p=malloc(sizeof(*p));
    if (!p) return false;
    if (!nemo_kitty_image_reference(s->cache,image,true)) { free(p);return false; }
    *p=(NemoKittyPlacement){NULL,image,(int32_t)anchor_x,(int32_t)anchor_y,-1,0,
        columns,rows,offset_x,offset_y,x,y,width,height,++s->sequence,s,0,0,0,
        prototype->sequence,false};
    s->used+=sizeof(*p);s->count++;s->cells++;s->generation++;
    insert(s,p);
    return true;
}

NemoKittyPlacementStatus nemo_kitty_placements_put(
    NemoKittyPlacements *s, NemoKittyImage *image, const NemoKittyCommand *command,
    int32_t column, int32_t row, uint32_t cw, uint32_t ch, NemoKittyLayout *out)
{
    if (!s || !command || !out) return NEMO_KITTY_PLACE_INVALID;
    uint32_t parent_id=nemo_kitty_get(command,'P');
    bool virtual=nemo_kitty_get(command,'U')!=0;
    if (parent_id && virtual) return NEMO_KITTY_PLACE_INVALID;
    if (!image) return NEMO_KITTY_PLACE_NOT_FOUND;
    const NemoKittyPlacement *parent=NULL;
    uint32_t parent_view=nemo_kitty_get(command,'Q');
    if (parent_id) {
        for (const NemoKittyPlacement *q=s->first;q;q=q->next)
            if (nemo_kitty_image_id(q->image)==parent_id &&
                (!parent_view || q->id==parent_view) &&
                (!parent || q->sequence<parent->sequence)) parent=q;
        if (!parent) return NEMO_KITTY_PLACE_NO_PARENT;
    }
    uint32_t id=nemo_kitty_image_id(image) ? nemo_kitty_get(command,'p') : 0;
    NemoKittyPlacement **link=&s->first;
    while (*link && (!id || (*link)->image!=image || (*link)->id!=id)) link=&(*link)->next;
    NemoKittyPlacement *p=*link;
    if (parent && parent==p) return NEMO_KITTY_PLACE_INVALID;
    unsigned depth=1;
    for (const NemoKittyPlacement *q=parent;q;) {
        if (depth>NEMO_KITTY_PARENT_DEPTH_MAX) return NEMO_KITTY_PLACE_DEPTH;
        if (q==p) return NEMO_KITTY_PLACE_CYCLE;
        if (!q->parent) break;
        q=by_sequence(s,q->parent);
        if (!q) return NEMO_KITTY_PLACE_NO_PARENT;
        depth++;
    }
    NemoKittyCommand geometry=*command;
    if (parent || virtual) {
        geometry.values['P'-'A']=0;
        geometry.values['U'-'A']=0;
        geometry.values['C'-'A']=1;
        geometry.present|=UINT64_C(1)<<('C'-'A');
    }
    if (virtual) {
        /* Prototypes fit the full image into their cell box. Crop, offsets and
         * z apply to ordinary placements; they do not crop derived cells. */
        const char *keys="xywhXY";
        for (const char *key=keys;*key;key++)
            geometry.values[*key>='a' ? *key-'a'+26 : *key-'A']=0;
    }
    const NemoRaster *r=nemo_kitty_image_raster(image);
    NemoKittyLayout g;
    NemoKittyLayoutStatus status=nemo_kitty_layout(&geometry,r->width,r->height,column,row,cw,ch,&g);
    if (status!=NEMO_KITTY_LAYOUT_OK)
        return status==NEMO_KITTY_LAYOUT_UNSUPPORTED ? NEMO_KITTY_PLACE_UNSUPPORTED :
            status==NEMO_KITTY_LAYOUT_LIMIT ? NEMO_KITTY_PLACE_LIMIT : NEMO_KITTY_PLACE_INVALID;
    uint64_t sequence=p ? p->sequence : 0;
    if (p) {
        s->cell_insert_count=0;
        *link=p->next;
        if (p->virtual) virtual_remove(s,p);
    }
    else {
        if (s->count-s->cells>=NEMO_KITTY_PLACEMENT_MAX || s->sequence==UINT64_MAX ||
            sizeof(*p)>s->budget-s->used ||
            (s->admit && !s->admit(s->ctx,s->used,sizeof(*p)))) return NEMO_KITTY_PLACE_LIMIT;
        p=malloc(sizeof(*p));
        if (!p) return NEMO_KITTY_PLACE_NOMEM;
        if (!nemo_kitty_image_reference(s->cache,image,true)) { free(p); return NEMO_KITTY_PLACE_NOT_FOUND; }
        s->used+=sizeof(*p); s->count++;
        sequence=++s->sequence;
    }
    *p=(NemoKittyPlacement){NULL,image,column,row,g.z,id,
        nemo_kitty_get(command,'c'),nemo_kitty_get(command,'r'),g.offset_x,g.offset_y,
        g.source_x,g.source_y,g.source_width,g.source_height,sequence,s,
        parent ? parent->sequence : 0,nemo_kitty_signed(command,'H'),nemo_kitty_signed(command,'V'),0,virtual};
    if (virtual) { p->column=p->row=0;virtual_insert(s,p); }
    insert(s,p); s->generation++;
    int64_t resolved_x,resolved_y;
    if (resolve(p,&resolved_x,&resolved_y)) {
        double dx=((double)resolved_x-column)*cw,dy=((double)resolved_y-row)*ch;
        g.left+=dx;g.right+=dx;g.top+=dy;g.bottom+=dy;
    }
    collect_orphans(s);
    *out=g;
    return NEMO_KITTY_PLACE_OK;
}

NemoKittyPlacementStatus nemo_kitty_placements_delete(
    NemoKittyPlacements *s, const NemoKittyCommand *c, int32_t cursor_column,
    int32_t cursor_row, uint32_t columns, uint32_t rows, uint32_t cw, uint32_t ch,
    unsigned *deleted)
{
    if (!s || !c || !deleted || !columns || !rows || !cw || !ch ||
        cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX ||
        (nemo_kitty_get(c,'i') && nemo_kitty_get(c,'I'))) return NEMO_KITTY_PLACE_INVALID;
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
    NemoKittyPlacement *selected[NEMO_KITTY_PLACEMENT_MAX+NEMO_KITTY_CELL_RUN_MAX];unsigned selection=0;
    /* Uppercase id/number also frees a matching image with no placements. */
    if (release && target && !id) candidates[count++]=target;
    for (NemoKittyPlacement *p=s->first;p;p=p->next) {
        bool match=false;
        uint32_t cell_columns,cell_rows;
        if (action=='i' || action=='n') match=p->image==target && (!id || p->id==id);
        else if (action=='r') {
            uint32_t image_id=nemo_kitty_image_id(p->image);
            match=image_id && image_id>=x && image_id<=y;
        } else if (!p->virtual && !p->prototype && footprint(p,cw,ch,&cell_columns,&cell_rows)) {
            double px=action=='c' ? cursor_column : (double)x-1;
            double py=action=='c' ? cursor_row : (double)y-1;
            bool inx=px>=p->column && px<(double)p->column+cell_columns;
            bool iny=py>=p->row && py<(double)p->row+cell_rows;
            switch (action) {
              /* The pinned model clears all non-history placements, including
               * those currently below or to the right of the viewport. */
              case 'a': match=(int64_t)p->row+cell_rows>0; break;
              case 'c': case 'p': match=inx && iny; break;
              case 'q': match=inx && iny && p->z==nemo_kitty_signed(c,'z'); break;
              case 'x': match=inx; break;
              case 'y': match=iny; break;
              case 'z': match=p->z==nemo_kitty_signed(c,'z'); break;
            }
        }
        if (match) selected[selection++]=p;
    }
    /* Select the entire direct deletion before orphan retirement. A child
     * explicitly selected in the same command follows ordinary data-retention
     * rules rather than the rules for a lost parent. */
    for (unsigned n=0;n<selection;n++) {
        NemoKittyPlacement *p=selected[n];
        NemoKittyPlacement **link=&s->first;
        while (*link!=p) link=&(*link)->next;
        NemoKittyImage *image=p->image;
        if (release || !nemo_kitty_image_id(image)) {
            unsigned i=0; while (i<count && candidates[i]!=image) i++;
            if (i==count && count<NEMO_KITTY_IMAGE_MAX) candidates[count++]=image;
        }
        remove_view(s,link,false); removed++;
    }
    collect_orphans(s);
    for (unsigned i=0;i<count;i++)
        nemo_kitty_cache_remove_unreferenced(s->cache,candidates[i]);
    if (release && action=='r' && !id) nemo_kitty_cache_prune_range(s->cache,x,y);
    *deleted=removed; return NEMO_KITTY_PLACE_OK;
}

void nemo_kitty_placements_scroll(NemoKittyPlacements *s, int32_t top, int32_t bottom,
    int32_t lines, bool margins, uint32_t history_rows, uint32_t cw, uint32_t ch)
{
    if (!s || !lines || top<0 || bottom<top || !cw || !ch ||
        cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX) return;
    NemoKittyImage *unused[NEMO_KITTY_IMAGE_MAX];unsigned unused_count=0;
    NemoKittyPlacement **link=&s->first;
    while (*link) {
        NemoKittyPlacement *p=*link; NemoKittyView v;uint32_t cols,rows;
        if (p->virtual || !placement_view_at(p,cw,ch,p->column,p->row,&v) || !footprint(p,cw,ch,&cols,&rows) ||
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
            if (!nemo_kitty_image_id(image) && !nemo_kitty_image_references(image))
                unused[unused_count++]=image;
            continue;
        }
        p->row=(int32_t)row;
        p->source_y=source_y;p->source_height=source_height;p->offset_y=offset_y;
        if (p->rows) p->rows-=clipped;
        s->generation++; link=&p->next;
    }
    collect_orphans(s);
    for (unsigned i=0;i<unused_count;i++) nemo_kitty_cache_remove_unreferenced(s->cache,unused[i]);
}

void nemo_kitty_placements_rescale(NemoKittyPlacements *s, uint32_t cw, uint32_t ch)
{
    if (!s || !cw || !ch || cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX) return;
    nemo_kitty_placements_remove_cells(s,INT32_MIN,INT32_MAX);
    for (NemoKittyPlacement *p=s->first; p; p=p->next) {
        if (p->offset_x>=cw) p->offset_x=cw-1;
        if (p->offset_y>=ch) p->offset_y=ch-1;
    }
    s->generation++;
}

void nemo_kitty_placements_rows(NemoKittyPlacements *s, int32_t delta,
                                int32_t first, uint32_t cw, uint32_t ch)
{
    if (!s || !cw || !ch || cw>NEMO_KITTY_AXIS_MAX || ch>NEMO_KITTY_AXIS_MAX) return;
    NemoKittyImage *unused[NEMO_KITTY_IMAGE_MAX];unsigned unused_count=0;
    NemoKittyPlacement **link=&s->first;
    while (*link) {
        NemoKittyPlacement *p=*link;
        if (p->virtual) { link=&p->next;continue; }
        uint32_t cols,rows;
        int64_t row=(int64_t)p->row+delta;
        if (!footprint(p,cw,ch,&cols,&rows) || row<INT32_MIN || row>INT32_MAX ||
            row+rows<=first) {
            NemoKittyImage *image=p->image;
            remove_view(s,link,false);
            if (!nemo_kitty_image_id(image) && !nemo_kitty_image_references(image))
                unused[unused_count++]=image;
        } else {
            p->row=(int32_t)row;
            if (delta) s->generation++;
            link=&p->next;
        }
    }
    collect_orphans(s);
    for (unsigned i=0;i<unused_count;i++) nemo_kitty_cache_remove_unreferenced(s->cache,unused[i]);
}
