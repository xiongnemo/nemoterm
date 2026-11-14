/* SPDX-License-Identifier: MIT */
#include "nemo_kitty_placements.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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
    double layers[2][8];
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

int main(void)
{
    Fixture f; create(&f);
    size_t baseline=nemo_kitty_placements_memory(f.places);
    for (unsigned i=0;i<sizeof(states)/sizeof(*states);i++) {
        const Reference *r=states+i;
        if (r->reset) nemo_kitty_cache_clear(f.cache);
        if (r->operation==1 || r->operation==2) {
            NemoKittyCommand c=parse(r->header);NemoKittyLayout g;
            NemoKittyImage *image=r->operation==1 ? load(&f,c,r->width,r->height) :
                nemo_kitty_cache_find(f.cache,nemo_kitty_get(&c,'i'),0);
            CHECK(nemo_kitty_placements_put(f.places,image,&c,r->column,r->row,10,20,&g)==NEMO_KITTY_PLACE_OK);
        } else if (r->operation==3) delete(&f,r->header);
        else nemo_kitty_placements_scroll(f.places,1,4,r->operation==4?1:-1,true,0,10,20);
        CHECK(nemo_kitty_cache_count(f.cache)==r->images);
        CHECK(nemo_kitty_placements_count(f.places)==r->placements);
        const NemoKittyPlacement *p=nemo_kitty_placements_first(f.places);
        for (unsigned j=0;j<r->placements;j++,p=nemo_kitty_placement_next(p)) {
            NemoKittyView v;CHECK(nemo_kitty_placement_view(p,10,20,&v));
            double actual[]={v.left,v.top,v.right,v.bottom,v.source_left/r->width,v.source_top/r->height,
                             v.source_right/r->width,v.source_bottom/r->height};
            for (unsigned k=0;k<8;k++) CHECK(near(actual[k],r->layers[j][k]));
        }
        CHECK(!p);printf("Pinned kitty placement matched: %s\n",r->name);
    }
    nemo_kitty_cache_clear(f.cache);CHECK(nemo_kitty_placements_memory(f.places)==baseline);
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
    CHECK(v.id==2);
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
