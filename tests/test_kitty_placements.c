/* SPDX-License-Identifier: MIT */
#include "nemo_kitty_placements.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define BUDGET (4u*1024u*1024u)
static unsigned checks;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x); exit(1); } } while (0)
typedef struct Fixture {
    NemoKittyCache *cache;
    NemoKittyPlacements *places;
    size_t limit,peak;
    unsigned removals;
    bool deny_placement;
} Fixture;
typedef struct Reference {
    const char *name,*header;
    unsigned reset,operation,width,height,column,row,images,placements;
    unsigned top,bottom,margins,scrollback;
    double layers[2][9];
} Reference;
#include "kitty_placement_reference.h"

static NemoKittyCommand parse(const char *header)
{
    NemoKitty *s=nemo_kitty_new(BUDGET,NULL,NULL); NemoKittyPacket p={0};
    CHECK(s && nemo_kitty_begin(s) && nemo_kitty_feed(s,header,strlen(header)));
    CHECK(nemo_kitty_finish(s,&p)==NEMO_KITTY_PACKET);
    NemoKittyCommand c=p.command; nemo_kitty_free(s); return c;
}
static void removed(void *ctx,const NemoKittyImage *image)
{
    Fixture *f=ctx; f->removals++;
    nemo_kitty_placements_image_removed(f->places,image);
}
static bool cache_admit(void *ctx,size_t current,size_t extra,bool evict)
{
    Fixture *f=ctx; (void)evict;
    size_t total=current+extra+nemo_kitty_placements_memory(f->places);
    if (total>f->limit) return false;
    if (total>f->peak) f->peak=total;
    return true;
}
static bool place_admit(void *ctx,size_t current,size_t extra)
{
    Fixture *f=ctx;
    size_t total=current+extra+nemo_kitty_cache_memory(f->cache);
    if (f->deny_placement || total>f->limit) return false;
    if (total>f->peak) f->peak=total;
    return true;
}
static void create(Fixture *f)
{
    memset(f,0,sizeof(*f)); f->limit=BUDGET;
    f->cache=nemo_kitty_cache_new(BUDGET,cache_admit,NULL,removed,f);CHECK(f->cache);
    f->places=nemo_kitty_placements_new(f->cache,BUDGET,place_admit,f);CHECK(f->places);
}
static void destroy(Fixture *f)
{
    nemo_kitty_cache_clear(f->cache);
    CHECK(!nemo_kitty_placements_count(f->places));
    nemo_kitty_placements_free(f->places); f->places=NULL;
    nemo_kitty_cache_free(f->cache); f->cache=NULL;
}
static NemoKittyImage *load(Fixture *f,NemoKittyCommand c,unsigned width,unsigned height)
{
    size_t n=(size_t)width*height*3; unsigned char *data=malloc(n);CHECK(data);
    memset(data,127,n); NemoKittyPacket p={c,data,n};
    NemoKittyImageResult result=nemo_kitty_cache_load(f->cache,&p);free(data);
    CHECK(result.status==NEMO_KITTY_IMAGE_OK && result.image);return result.image;
}
static void put(Fixture *f,NemoKittyImage *image,const char *header,int32_t x,int32_t y)
{
    NemoKittyCommand c=parse(header);NemoKittyLayout g;
    CHECK(nemo_kitty_placements_put(f->places,image,&c,x,y,10,20,&g)==NEMO_KITTY_PLACE_OK);
}
static unsigned delete(Fixture *f,const char *header)
{
    NemoKittyCommand c=parse(header);unsigned count=UINT32_MAX;
    CHECK(nemo_kitty_placements_delete(f->places,&c,1,2,12,8,10,20,&count)==NEMO_KITTY_PLACE_OK);
    return count;
}
static NemoKittyView first(Fixture *f)
{
    NemoKittyView v;CHECK(nemo_kitty_placement_view(nemo_kitty_placements_first(f->places),10,20,&v));return v;
}
static bool near(double a,double b) { return a-b<0.00002 && a-b> -0.00002; }

static void unicode_lifetime_boundaries(void)
{
    Fixture f;create(&f);
    size_t baseline=nemo_kitty_placements_memory(f.places);
    CHECK(!nemo_kitty_placements_have_cells(f.places));
    NemoKittyImage *image=load(&f,parse("i=42,f=24,s=10,v=20"),10,20);
    NemoKittyImage *child=load(&f,parse("i=43,f=24,s=10,v=20"),10,20);
    put(&f,image,"a=p,p=7,U=1,c=4,r=4",6,7);
    put(&f,child,"a=p,p=9,P=42,Q=7,H=1,V=2",0,0);
    NemoKittyView v;
    const NemoKittyPlacement *parent=nemo_kitty_placements_first(f.places);
    CHECK(!nemo_kitty_placement_view(parent,10,20,&v));
    const NemoKittyPlacement *relative=nemo_kitty_placement_next(parent);
    CHECK(!nemo_kitty_placement_view(relative,10,20,&v));
    CHECK(nemo_kitty_placements_have_cells(f.places));
    uint64_t generation=nemo_kitty_placements_generation(f.places);
    f.deny_placement=true;
    CHECK(!nemo_kitty_placements_cell(f.places,42,7,0,0,1,2,3,10,20));
    CHECK(nemo_kitty_placements_generation(f.places)==generation);
    CHECK(nemo_kitty_image_references(image)==1);f.deny_placement=false;
    CHECK(!nemo_kitty_placements_cell(f.places,42,99,0,0,1,2,3,10,20));
    CHECK(nemo_kitty_placements_cell(f.places,42,7,0,0,1,2,3,10,20));
    CHECK(nemo_kitty_placements_cell(f.places,42,7,0,1,1,1,5,10,20));
    CHECK(nemo_kitty_placement_view(relative,10,20,&v) && v.left==20 && v.top==100);
    nemo_kitty_placements_remove_cells(f.places,INT32_MIN,INT32_MAX);
    CHECK(!nemo_kitty_placement_view(relative,10,20,&v));
    CHECK(nemo_kitty_image_references(child)==1 && nemo_kitty_cache_count(f.cache)==2);
    CHECK(nemo_kitty_placements_cell(f.places,42,7,0,0,2,0,0,10,20));
    CHECK(delete(&f,"a=d,d=I,i=42,p=7")==1);
    /* An explicitly deleted template does not prematurely free data retained
     * by derived runs. Refresh drops those runs without deleting named data. */
    CHECK(nemo_kitty_cache_count(f.cache)==1);
    nemo_kitty_placements_remove_cells(f.places,INT32_MIN,INT32_MAX);
    CHECK(!nemo_kitty_placements_count(f.places) && !nemo_kitty_image_references(image));
    CHECK(nemo_kitty_cache_count(f.cache)==1);
    CHECK(delete(&f,"a=d,d=I,i=42")==0 && !nemo_kitty_cache_count(f.cache));
    CHECK(nemo_kitty_placements_memory(f.places)==baseline);

    image=load(&f,parse("i=42,f=24,s=10,v=20"),10,20);
    put(&f,image,"a=p,p=7,U=1,c=1,r=1",0,0);
    for (unsigned i=0;i<NEMO_KITTY_CELL_RUN_MAX;i++)
        CHECK(nemo_kitty_placements_cell(f.places,42,7,0,0,1,0,(int32_t)i,10,20));
    generation=nemo_kitty_placements_generation(f.places);
    CHECK(!nemo_kitty_placements_cell(f.places,42,7,0,0,1,0,0,10,20));
    CHECK(nemo_kitty_placements_generation(f.places)==generation);
    CHECK(nemo_kitty_image_references(image)==NEMO_KITTY_CELL_RUN_MAX+1);
    for (unsigned i=1;i<NEMO_KITTY_PLACEMENT_MAX;i++) put(&f,image,"a=p",0,0);
    CHECK(nemo_kitty_placements_count(f.places)==NEMO_KITTY_CELL_RUN_MAX+NEMO_KITTY_PLACEMENT_MAX);
    CHECK(f.peak<=BUDGET);
    nemo_kitty_placements_erase_all(f.places);
    CHECK(nemo_kitty_placements_count(f.places)==1 && nemo_kitty_image_references(image)==1);
    CHECK(nemo_kitty_placements_cell(f.places,42,7,0,0,1,0,0,10,20));
    nemo_kitty_placements_rescale(f.places,5,10);
    CHECK(nemo_kitty_placements_count(f.places)==1 && nemo_kitty_image_references(image)==1);
    nemo_kitty_cache_clear(f.cache);
    CHECK(nemo_kitty_placements_memory(f.places)==baseline);
    CHECK(!nemo_kitty_placements_have_cells(f.places));
    image=load(&f,parse("f=24,s=10,v=20"),10,20);put(&f,image,"a=p",0,0);
    nemo_kitty_placements_erase_all(f.places);
    CHECK(!nemo_kitty_cache_count(f.cache));
    CHECK(nemo_kitty_placements_memory(f.places)==baseline);
    destroy(&f);
}

static void check_cell_order(Fixture *f,unsigned first_row)
{
    unsigned seen=0,hidden=0;
    for (const NemoKittyPlacement *p=nemo_kitty_placements_first(f->places);p;
         p=nemo_kitty_placement_next(p)) {
        NemoKittyView v;
        if (!nemo_kitty_placement_view(p,10,20,&v)) { hidden++;continue; }
        unsigned image=seen/4,row=first_row+seen%4;
        CHECK(v.id==100+image && v.z==-1 && !v.placement);
        CHECK(v.left==image*10 && v.right==(image+1)*10 && v.top==row*20 && v.bottom==(row+1)*20);
        seen++;
    }
    CHECK(seen==4*NEMO_KITTY_IMAGE_MAX && hidden==NEMO_KITTY_PLACEMENT_MAX);
}

static void unicode_index_lifetime(void)
{
    Fixture f;create(&f);
    size_t baseline=nemo_kitty_placements_memory(f.places);
    NemoKittyImage *images[NEMO_KITTY_IMAGE_MAX];
    CHECK(NEMO_KITTY_PLACEMENT_MAX==4*NEMO_KITTY_IMAGE_MAX);
    for (unsigned i=0;i<NEMO_KITTY_IMAGE_MAX;i++) {
        char header[64];
        int n=snprintf(header,sizeof(header),"i=%u,f=24,s=10,v=20",100+i);
        CHECK(n>0 && (size_t)n<sizeof(header));
        images[i]=load(&f,parse(header),10,20);
        put(&f,images[i],"a=p,p=7,U=1,c=1,r=1,z=2",0,0);
        put(&f,images[i],"a=p,p=8,U=1,c=1,r=1,z=1",0,0);
        put(&f,images[i],"a=p,p=9,U=1,c=1,r=1,z=0",0,0);
        put(&f,images[i],"a=p,p=10,U=1,c=1,r=1,z=-2",0,0);
    }
    NemoKittyCommand command=parse("a=p,p=11,U=1,c=1,r=1");NemoKittyLayout out;
    CHECK(nemo_kitty_placements_put(f.places,images[0],&command,0,0,10,20,&out)==NEMO_KITTY_PLACE_LIMIT);
    /* Alternate image order between passes. Each image must still be sorted
     * by creation order, with its own cells in placement-creation order. */
    for (unsigned row=0;row<4;row++)
        for (unsigned i=0;i<NEMO_KITTY_IMAGE_MAX;i++) {
            unsigned index=row%2 ? i : NEMO_KITTY_IMAGE_MAX-1-i;
            CHECK(nemo_kitty_placements_cell(f.places,100+index,0,0,0,1,(int32_t)index,(int32_t)row,10,20));
        }
    check_cell_order(&f,0);
    /* Replacement changes sorting without changing the prototype identity. */
    put(&f,images[0],"a=p,p=7,U=1,c=1,r=1,z=-3",0,0);
    check_cell_order(&f,0);
    /* An ordinary replacement must disappear from the prototype index. */
    put(&f,images[0],"a=p,p=7,c=1,r=1",0,0);
    put(&f,images[0],"a=p,p=7,U=1,c=1,r=1,z=2",0,0);
    check_cell_order(&f,0);
    nemo_kitty_placements_remove_cells(f.places,0,0);
    for (unsigned i=NEMO_KITTY_IMAGE_MAX;i--;)
        CHECK(nemo_kitty_placements_cell(f.places,100+i,7,0,0,1,(int32_t)i,4,10,20));
    check_cell_order(&f,1);
    CHECK(delete(&f,"a=d,d=I,i=100,p=7")==1);
    /* Reusing a client ID creates a new identity; stale cells stay hidden. */
    put(&f,images[0],"a=p,p=7,U=1,c=1,r=1",0,0);
    CHECK(nemo_kitty_placements_cell(f.places,100,7,0,0,1,0,5,10,20));
    nemo_kitty_placements_remove_cells(f.places,INT32_MIN,INT32_MAX);
    CHECK(nemo_kitty_placements_count(f.places)==NEMO_KITTY_PLACEMENT_MAX);
    for (unsigned i=0;i<NEMO_KITTY_IMAGE_MAX;i++) CHECK(nemo_kitty_image_references(images[i])==4);
    nemo_kitty_cache_clear(f.cache);
    CHECK(nemo_kitty_placements_memory(f.places)==baseline);
    CHECK(!nemo_kitty_placements_have_cells(f.places));
    CHECK(f.peak<=BUDGET);destroy(&f);
}

static void relative_lifetime_boundaries(void)
{
    /* Retiring an anonymous image must not call back in the middle of a
     * scroll iterator: that callback can also remove its preceding orphan. */
    for (unsigned resize=0;resize<2;resize++) {
        Fixture f;create(&f);
        size_t baseline=nemo_kitty_placements_memory(f.places);
        NemoKittyImage *root=load(&f,parse("i=1,f=24,s=1,v=1"),1,1);
        NemoKittyImage *child=load(&f,parse("i=2,f=24,s=1,v=1"),1,1);
        NemoKittyImage *anonymous=load(&f,parse("f=24,s=1,v=1"),1,1);
        NemoKittyImage *last=load(&f,parse("i=3,f=24,s=1,v=1"),1,1);
        put(&f,root,"a=p,p=1,z=0",0,0);
        put(&f,child,"a=p,P=1,Q=1,p=2,z=1",0,7);
        put(&f,anonymous,"a=p,z=2",0,0);
        put(&f,last,"a=p,p=3,z=3",0,0);
        if (resize) nemo_kitty_placements_rows(f.places,-1,0,10,20);
        else nemo_kitty_placements_scroll(f.places,0,7,1,false,0,10,20);
        CHECK(!nemo_kitty_placements_count(f.places));
        CHECK(nemo_kitty_placements_memory(f.places)==baseline);
        CHECK(nemo_kitty_cache_count(f.cache)==2);
        CHECK(nemo_kitty_cache_peek(f.cache,1,0) && nemo_kitty_cache_peek(f.cache,3,0));
        CHECK(!nemo_kitty_cache_peek(f.cache,2,0));
        destroy(&f);
    }

    Fixture f;create(&f);
    NemoKittyImage *image=load(&f,parse("i=1,f=24,s=1,v=1"),1,1);
    size_t baseline=nemo_kitty_placements_memory(f.places);
    put(&f,image,"a=p,p=1",INT32_MAX,INT32_MIN);
    size_t per_view=nemo_kitty_placements_memory(f.places)-baseline;
    for (unsigned i=2;i<=NEMO_KITTY_PARENT_DEPTH_MAX+1;i++) {
        char header[160];snprintf(header,sizeof(header),
            "a=p,p=%u,P=1,Q=%u,H=2147483647,V=-2147483648",i,i-1);
        put(&f,image,header,0,0);
    }
    const NemoKittyPlacement *leaf=nemo_kitty_placements_first(f.places);
    while (nemo_kitty_placement_next(leaf)) leaf=nemo_kitty_placement_next(leaf);
    NemoKittyView v;CHECK(nemo_kitty_placement_view(leaf,10,20,&v));
    CHECK(v.left==(double)((int64_t)INT32_MAX*9)*10);
    CHECK(v.top==(double)((int64_t)INT32_MIN*9)*20);
    CHECK(nemo_kitty_placements_memory(f.places)==baseline+9*per_view);
    uint64_t generation=nemo_kitty_placements_generation(f.places);
    NemoKittyLayout out,sentinel;memset(&sentinel,0xa5,sizeof(sentinel));out=sentinel;
    NemoKittyCommand c=parse("a=p,p=10,P=1,Q=9");
    CHECK(nemo_kitty_placements_put(f.places,image,&c,0,0,10,20,&out)==NEMO_KITTY_PLACE_DEPTH);
    CHECK(!memcmp(&out,&sentinel,sizeof(out)));
    CHECK(nemo_kitty_placements_generation(f.places)==generation);
    CHECK(nemo_kitty_image_references(image)==9);
    CHECK(delete(&f,"a=d,d=i,i=1,p=1")==1);
    CHECK(!nemo_kitty_cache_count(f.cache) && !nemo_kitty_placements_count(f.places));
    CHECK(nemo_kitty_placements_memory(f.places)==baseline);
    destroy(&f);
}

/* Opt-in component measurement, separate from correctness-suite timing.
 * This exercises the real placement owner without a window or renderer.
 * clock() units are retained; compare only matched compiler/runtime runs. */
static int benchmark_cells(void)
{
    const unsigned sizes[]={256,512,1024,2048,4096,7268,8192};
    const unsigned templates[]={1,16};
    for (unsigned mode=0;mode<sizeof(templates)/sizeof(*templates);mode++) {
        Fixture f;create(&f);
        NemoKittyImage *image=load(&f,parse("i=42,f=24,s=512,v=288"),512,288);
        for (unsigned i=0;i<templates[mode];i++) {
            char header[64];
            int n=snprintf(header,sizeof(header),"a=p,p=%u,U=1,c=1,r=1",i+1);
            CHECK(n>0 && (size_t)n<sizeof(header));
            put(&f,image,header,0,0);
        }
        size_t baseline=nemo_kitty_placements_memory(f.places);
        for (unsigned size=0;size<sizeof(sizes)/sizeof(*sizes);size++) {
            unsigned count=sizes[size];
            for (unsigned repeat=0;repeat<3;repeat++) {
                clock_t before=clock();CHECK(before!=(clock_t)-1);
                for (unsigned i=0;i<count;i++)
                    CHECK(nemo_kitty_placements_cell(f.places,42,i%templates[mode]+1,
                        0,0,1,(int32_t)(i%158),(int32_t)(i/158),10,20));
                clock_t created=clock();CHECK(created!=(clock_t)-1 && created>=before);
                CHECK(nemo_kitty_placements_count(f.places)==count+templates[mode]);
                CHECK(nemo_kitty_image_references(image)==count+templates[mode]);
                size_t bytes=nemo_kitty_placements_memory(f.places);
                for (unsigned pass=0;pass<4;pass++) {
                    unsigned visible=0,hidden=0;
                    for (const NemoKittyPlacement *p=nemo_kitty_placements_first(f.places);p;
                         p=nemo_kitty_placement_next(p)) {
                        NemoKittyView v;
                        if (!nemo_kitty_placement_view(p,10,20,&v)) { hidden++;continue; }
                        CHECK(v.id==42 && !v.placement && v.z==-1 && v.image==image);
                        CHECK(v.left==(double)(visible%158)*10 && v.right==v.left+10);
                        CHECK(v.top>=(double)(visible/158)*20 && v.bottom>v.top &&
                              v.bottom<=(double)(visible/158+1)*20);
                        visible++;
                    }
                    CHECK(visible==count && hidden==templates[mode]);
                }
                clock_t viewed=clock();CHECK(viewed!=(clock_t)-1 && viewed>=created);
                nemo_kitty_placements_remove_cells(f.places,INT32_MIN,INT32_MAX);
                clock_t cleared=clock();CHECK(cleared!=(clock_t)-1 && cleared>=viewed);
                CHECK(nemo_kitty_placements_count(f.places)==templates[mode]);
                CHECK(nemo_kitty_placements_memory(f.places)==baseline);
                CHECK(nemo_kitty_image_references(image)==templates[mode]);
                CHECK(f.peak<=BUDGET);
                printf("{\"cells\":%u,\"templates\":%u,\"repeat\":%u,\"view_passes\":4,"
                    "\"clock_hz\":%.0f,\"create_ticks\":%.0f,\"view_ticks\":%.0f,"
                    "\"clear_ticks\":%.0f,\"placement_bytes\":%zu,\"baseline_bytes\":%zu,"
                    "\"owner_peak_bytes\":%zu}\n",
                    count,templates[mode],repeat,(double)CLOCKS_PER_SEC,
                    (double)(created-before),(double)(viewed-created),(double)(cleared-viewed),
                    bytes,baseline,f.peak);
                fflush(stdout);
            }
        }
        destroy(&f);
    }
    return 0;
}

int main(int argc,char **argv)
{
    if (argc==2 && !strcmp(argv[1],"--benchmark-cells")) return benchmark_cells();
    CHECK(argc==1);
    unicode_lifetime_boundaries();
    unicode_index_lifetime();
    relative_lifetime_boundaries();
    Fixture f; create(&f);
    size_t baseline=nemo_kitty_placements_memory(f.places);
    for (unsigned i=0;i<sizeof(states)/sizeof(*states);i++) {
        const Reference *r=states+i;
        if (r->reset) nemo_kitty_cache_clear(f.cache);
        if (r->operation==1 || r->operation==2 || r->operation==6) {
            NemoKittyCommand c=parse(r->header);NemoKittyLayout g;
            NemoKittyImage *image=r->operation!=2 ? load(&f,c,r->width,r->height) :
                nemo_kitty_cache_find(f.cache,nemo_kitty_get(&c,'i'),nemo_kitty_get(&c,'I'));
            if (r->operation!=6) CHECK(nemo_kitty_placements_put(f.places,image,&c,r->column,r->row,10,20,&g)==NEMO_KITTY_PLACE_OK);
        } else if (r->operation==3) delete(&f,r->header);
        else nemo_kitty_placements_scroll(f.places,r->top,r->bottom,r->operation==4?1:-1,r->margins!=0,20,10,20);
        CHECK(nemo_kitty_cache_count(f.cache)==r->images);
        unsigned visible=0;
        for (const NemoKittyPlacement *p=nemo_kitty_placements_first(f.places);p;p=nemo_kitty_placement_next(p)) {
            NemoKittyView v;CHECK(nemo_kitty_placement_view(p,10,20,&v));
            v.top+=r->scrollback*20;v.bottom+=r->scrollback*20;
            if (v.left>=120 || v.right<=0 || v.top>=160 || v.bottom<=0) continue;
            CHECK(visible<r->placements);
            const NemoRaster *raster=nemo_kitty_image_raster(v.image);
            double actual[]={v.left,v.top,v.right,v.bottom,v.source_left/raster->width,v.source_top/raster->height,
                             v.source_right/raster->width,v.source_bottom/raster->height,v.z};
            for (unsigned k=0;k<9;k++) {
                if (!near(actual[k],r->layers[visible][k])) fprintf(stderr,"Reference mismatch %s layer %u field %u: %.9f != %.9f\n",r->name,visible,k,actual[k],r->layers[visible][k]);
                CHECK(near(actual[k],r->layers[visible][k]));
            }
            visible++;
        }
        CHECK(visible==r->placements);printf("Pinned kitty placement matched: %s\n",r->name);
    }
    nemo_kitty_cache_clear(f.cache);CHECK(nemo_kitty_placements_memory(f.places)==baseline);
    /* Internal image/ref identity survives named movement and retransmission;
     * client identifiers and lookup recency cannot reorder an overlap. */
    NemoKittyImage *older=load(&f,parse("a=t,i=9,f=24,s=10,v=20"),10,20);
    put(&f,older,"a=p,p=20",0,0);
    NemoKittyImage *newer=load(&f,parse("a=t,i=2,f=24,s=10,v=20"),10,20);
    put(&f,newer,"a=p,p=1",5,0);put(&f,older,"a=p,p=10",2,0);
    CHECK(nemo_kitty_cache_find(f.cache,9,0)==older);
    put(&f,older,"a=p,p=20",3,0);
    CHECK(first(&f).id==9 && first(&f).placement==20 && first(&f).left==30);
    const NemoKittyPlacement *second=nemo_kitty_placement_next(nemo_kitty_placements_first(f.places));
    NemoKittyView ordered;CHECK(nemo_kitty_placement_view(second,10,20,&ordered));
    CHECK(ordered.id==9 && ordered.placement==10);
    uint64_t original_sequence=nemo_kitty_image_sequence(older);
    older=load(&f,parse("a=t,i=9,f=24,s=20,v=20"),20,20);
    CHECK(nemo_kitty_image_sequence(older)==original_sequence);
    CHECK(nemo_kitty_placements_count(f.places)==1 && first(&f).id==2);
    put(&f,older,"a=p,p=30",1,0);
    CHECK(first(&f).id==9 && first(&f).left==10);
    nemo_kitty_cache_clear(f.cache);
    /* A clipped natural image keeps its source pixels and new cell anchor
     * when the font changes. Keeping a fraction of the old destination would
     * incorrectly move its top into the middle of the preceding text row. */
    NemoKittyImage *clipped=load(&f,parse("a=t,i=9,f=24,s=10,v=40"),10,40);
    put(&f,clipped,"a=p",0,1);
    nemo_kitty_placements_scroll(f.places,1,4,1,true,0,10,20);
    NemoKittyView resized;
    CHECK(nemo_kitty_placement_view(nemo_kitty_placements_first(f.places),20,40,&resized));
    CHECK(resized.top==40 && resized.bottom==60 && resized.source_top==20 && resized.source_bottom==40);
    put(&f,clipped,"a=p,p=7,c=2,r=2",1,3);
    nemo_kitty_placements_scroll(f.places,1,4,-1,true,0,10,20);
    const NemoKittyPlacement *last=nemo_kitty_placement_next(nemo_kitty_placements_first(f.places));
    CHECK(nemo_kitty_placement_view(last,20,40,&resized));
    CHECK(resized.top==160 && resized.bottom==200 && resized.source_top==0 && resized.source_bottom==20);
    nemo_kitty_cache_clear(f.cache);
    NemoKittyImage *image=load(&f,parse("a=t,i=10,f=24,s=20,v=40"),20,40);
    put(&f,image,"a=p,p=1,c=2,r=2",1,1);
    NemoKittyLayout out,sentinel;memset(&sentinel,0xa5,sizeof(sentinel));out=sentinel;
    NemoKittyCommand bad=parse("a=p,p=1,x=20");
    CHECK(nemo_kitty_placements_put(f.places,image,&bad,9,9,10,20,&out)==NEMO_KITTY_PLACE_INVALID);
    CHECK(memcmp(&out,&sentinel,sizeof(out))==0 && first(&f).left==10);
    CHECK(nemo_kitty_image_references(image)==1);
    NemoKittyView enlarged;CHECK(nemo_kitty_placement_view(nemo_kitty_placements_first(f.places),20,40,&enlarged));
    CHECK(enlarged.left==20 && enlarged.top==40 && enlarged.right==60 && enlarged.bottom==120);
    uint64_t generation=nemo_kitty_placements_generation(f.places);
    f.deny_placement=true;
    put(&f,image,"a=p,p=1,c=3",2,2); /* replacement cannot require more metadata */
    NemoKittyCommand command=parse("a=p,p=2");out=sentinel;
    CHECK(nemo_kitty_placements_put(f.places,image,&command,0,0,10,20,&out)==NEMO_KITTY_PLACE_LIMIT);
    CHECK(memcmp(&out,&sentinel,sizeof(out))==0 && nemo_kitty_image_references(image)==1);
    CHECK(nemo_kitty_placements_generation(f.places)==generation+1);f.deny_placement=false;
    CHECK(delete(&f,"a=d,d=i,i=10,p=1")==1 && nemo_kitty_cache_count(f.cache)==1);
    CHECK(delete(&f,"a=d,d=I,i=10")==0 && nemo_kitty_cache_count(f.cache)==0);
    /* Anonymous images cannot be referenced again and release when unplaced. */
    image=load(&f,parse("a=T,f=24,s=1,v=1,p=17"),1,1);
    put(&f,image,"a=p,p=17",0,0);put(&f,image,"a=p,p=17",1,0);
    CHECK(nemo_kitty_placements_count(f.places)==2 && first(&f).placement==0);
    CHECK(delete(&f,"a=d,d=a")==2 && nemo_kitty_cache_count(f.cache)==0);
    /* Number selectors act on the newest image only, even at the same number. */
    NemoKittyImage *old=load(&f,parse("a=t,I=99,f=24,s=1,v=1"),1,1);put(&f,old,"a=p,p=1",0,0);
    image=load(&f,parse("a=t,I=99,f=24,s=1,v=1"),1,1);put(&f,image,"a=p,p=1",1,0);
    CHECK(delete(&f,"a=d,d=N,I=99")==1 && nemo_kitty_cache_count(f.cache)==1);
    CHECK(nemo_kitty_image_references(old)==1);nemo_kitty_cache_clear(f.cache);
    load(&f,parse("a=t,i=2,f=24,s=1,v=1"),1,1);
    load(&f,parse("a=t,i=3,f=24,s=1,v=1"),1,1);
    CHECK(delete(&f,"a=d,d=R,x=1,y=2")==0 && nemo_kitty_cache_count(f.cache)==1);
    CHECK(nemo_kitty_cache_find(f.cache,3,0));nemo_kitty_cache_clear(f.cache);
    /* Shared image replacement and quota eviction invalidate every borrowed view. */
    image=load(&f,parse("a=t,i=10,f=24,s=2,v=2"),2,2);
    put(&f,image,"a=p",0,0);put(&f,image,"a=p",1,0);
    image=load(&f,parse("a=t,i=10,f=24,s=2,v=2"),2,2);
    CHECK(!nemo_kitty_placements_count(f.places) && !nemo_kitty_image_references(image));
    put(&f,image,"a=p",0,0);
    f.limit=nemo_kitty_cache_memory(f.cache)+nemo_kitty_placements_memory(f.places)+16;
    image=load(&f,parse("a=t,i=11,f=24,s=2,v=2"),2,2);
    CHECK(!nemo_kitty_placements_count(f.places) && nemo_kitty_image_id(image)==11);f.limit=BUDGET;
    nemo_kitty_cache_clear(f.cache);
    /* Sorting, selection boundaries, visible-only deletion and retained history. */
    image=load(&f,parse("a=t,i=3,f=24,s=10,v=20"),10,20);put(&f,image,"a=p,z=0",1,2);
    image=load(&f,parse("a=t,i=2,f=24,s=10,v=20"),10,20);put(&f,image,"a=p,z=0",1,2);
    image=load(&f,parse("a=t,i=1,f=24,s=10,v=20"),10,20);put(&f,image,"a=p,z=-2",0,-1);
    CHECK(first(&f).id==1 && first(&f).z==-2);
    NemoKittyView v;CHECK(nemo_kitty_placement_view(nemo_kitty_placement_next(nemo_kitty_placements_first(f.places)),10,20,&v));
    CHECK(v.id==3);
    CHECK(delete(&f,"a=d,d=p,x=1,y=3")==0); /* touching left border is not overlap */
    CHECK(delete(&f,"a=d,d=q,x=2,y=3,z=1")==0);
    CHECK(delete(&f,"a=d,d=c")==2);
    CHECK(delete(&f,"a=d,d=A")==0 && nemo_kitty_placements_count(f.places)==1);
    nemo_kitty_placements_scroll(f.places,0,7,1,false,2,10,20);CHECK(first(&f).top==-40);
    nemo_kitty_placements_scroll(f.places,0,7,1,false,2,10,20);CHECK(!nemo_kitty_placements_count(f.places));
    nemo_kitty_cache_clear(f.cache);
    /* Metadata cap and shared references remain bounded through replacements. */
    image=load(&f,parse("a=t,i=1,f=24,s=1,v=1"),1,1);put(&f,image,"a=p,p=1",0,0);
    for (unsigned i=1;i<NEMO_KITTY_PLACEMENT_MAX;i++) put(&f,image,"a=p",0,0);
    CHECK(nemo_kitty_image_references(image)==NEMO_KITTY_PLACEMENT_MAX);
    command=parse("a=p");
    CHECK(nemo_kitty_placements_put(f.places,image,&command,0,0,10,20,&out)==NEMO_KITTY_PLACE_LIMIT);
    put(&f,image,"a=p,p=1",1,1);
    CHECK(nemo_kitty_placements_count(f.places)==NEMO_KITTY_PLACEMENT_MAX);
    nemo_kitty_cache_clear(f.cache);CHECK(nemo_kitty_placements_memory(f.places)==baseline);
    CHECK(f.peak<=BUDGET);destroy(&f);
    printf("Kitty placements: %u checks passed\n",checks);return 0;
}
