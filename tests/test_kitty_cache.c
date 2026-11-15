/* SPDX-License-Identifier: MIT */
#include "nemo_kitty_cache.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define BUDGET (4u*1024u*1024u)
static unsigned checks;
#define CHECK(x) do { checks++; assert(x); } while (0)

typedef struct Fixture {
    NemoKittyCache *cache;
    size_t limit, other, peak;
    unsigned admitted, readonly, removed, png_calls, png_mode;
    uint32_t last_removed_id;
    unsigned last_removed_references;
    uint32_t orphan_source[2];
    NemoKittyImage *orphan_target[2];
    unsigned callback_depth, max_callback_depth;
} Fixture;

static NemoKittyPacket command(const char *header, const void *data, size_t length)
{
    NemoKitty *transport = nemo_kitty_new(BUDGET, NULL, NULL);
    CHECK(transport && nemo_kitty_begin(transport));
    CHECK(nemo_kitty_feed(transport, header, strlen(header)));
    NemoKittyPacket p;
    CHECK(nemo_kitty_finish(transport, &p) == NEMO_KITTY_PACKET);
    p.data = data; p.length = length;
    nemo_kitty_free(transport);
    return p;
}

static bool admission(void *ctx, size_t current, size_t extra, bool evict)
{
    Fixture *f = ctx;
    f->admitted++; f->readonly += !evict;
    CHECK(current <= BUDGET && extra <= BUDGET - current);
    if (current + extra + f->other > f->limit) return false;
    if (current + extra + f->other > f->peak) f->peak = current + extra + f->other;
    return true;
}

static void removed(void *ctx, const NemoKittyImage *im)
{
    Fixture *f = ctx;
    f->callback_depth++;
    if (f->callback_depth>f->max_callback_depth) f->max_callback_depth=f->callback_depth;
    f->removed++; f->last_removed_id = nemo_kitty_image_id(im);
    f->last_removed_references = nemo_kitty_image_references(im);
    CHECK(nemo_kitty_image_raster(im)->pixels != NULL);
    /* The owner may inspect the old image, but cannot reenter mutation. */
    CHECK(!nemo_kitty_cache_remove(f->cache, (NemoKittyImage *)im));
    CHECK(!nemo_kitty_image_reference(f->cache, (NemoKittyImage *)im, false));
    CHECK(!nemo_kitty_cache_release_orphan(f->cache, (NemoKittyImage *)im));
    for (unsigned i=0;i<2;i++) if (f->orphan_source[i]==nemo_kitty_image_id(im) && f->orphan_target[i]) {
        unsigned count=nemo_kitty_cache_count(f->cache);
        NemoKittyImage *target=f->orphan_target[i];f->orphan_target[i]=NULL;
        CHECK(!nemo_kitty_image_reference(f->cache,target,false));
        CHECK(nemo_kitty_cache_release_orphan(f->cache,target));
        CHECK(!nemo_kitty_cache_prune_orphans(f->cache));
        CHECK(nemo_kitty_cache_count(f->cache)==count);
        CHECK(nemo_kitty_image_raster(target)->pixels);
    }
    f->callback_depth--;
}

static bool png(void *ctx, const void *bytes, size_t length, NemoRaster *r,
                NemoRasterAdmission allow, void *allow_ctx)
{
    Fixture *f = ctx;
    f->png_calls++;
    for (unsigned i=0;i<2;i++) if (f->orphan_target[i])
        CHECK(!nemo_kitty_cache_release_orphan(f->cache,f->orphan_target[i]));
    CHECK(bytes && length >= 8);
    if (f->png_mode == 1) return false;
    if (!allow(allow_ctx, 2, 1, 8)) return false;
    if (f->png_mode == 2) {
        CHECK(!allow(allow_ctx, 2, 1, 8));
        return false;
    }
    if (f->png_mode == 5) CHECK(!allow(allow_ctx, 2, 1, 8));
    r->pixels = malloc(8);
    CHECK(r->pixels);
    r->pixels[0] = 0xff123456; r->pixels[1] = 0x80789abc;
    r->width = 2; r->height = 1; r->bytes = 8; r->partial_alpha = true;
    if (f->png_mode == 3) return false;
    if (f->png_mode == 4) r->width = 1;
    NemoKittyPacket p = command("i=99,f=24,s=1,v=1", "abc", 3);
    CHECK(nemo_kitty_cache_load(f->cache, &p).status == NEMO_KITTY_IMAGE_BUSY);
    return true;
}

static void create(Fixture *f, size_t budget, bool callback)
{
    memset(f, 0, sizeof(*f)); f->limit = BUDGET;
    f->cache = nemo_kitty_cache_new(budget, admission, png, callback ? removed : NULL, f);
    CHECK(f->cache);
}

static NemoKittyImageResult load(Fixture *f, const char *header, const void *data, size_t length)
{
    NemoKittyPacket p = command(header, data, length);
    NemoKittyImageResult r = nemo_kitty_cache_load(f->cache, &p);
    CHECK(nemo_kitty_cache_memory(f->cache) <= BUDGET);
    return r;
}

static void pixels_and_identity(void)
{
    Fixture f; create(&f, BUDGET, true);
    size_t empty = nemo_kitty_cache_memory(f.cache);
    const unsigned char rgb[] = {255,0,0, 0,255,0, 0,0,255, 255,255,255};
    NemoKittyImageResult r = load(&f, "a=T,i=7,f=24,s=2,v=2", rgb, sizeof(rgb));
    CHECK(r.status == NEMO_KITTY_IMAGE_OK && r.image && r.changed && !r.query);
    CHECK(r.id == 7 && !r.number && r.width == 2 && r.height == 2);
    const NemoRaster *pixels = nemo_kitty_image_raster(r.image);
    CHECK(pixels->pixels[0] == 0xffff0000 && pixels->pixels[1] == 0xff00ff00);
    CHECK(pixels->pixels[2] == 0xff0000ff && pixels->pixels[3] == 0xffffffff);
    CHECK(!pixels->partial_alpha && pixels->bytes == 16);
    CHECK(nemo_kitty_image_reference(f.cache, r.image, true));
    CHECK(nemo_kitty_image_reference(f.cache, r.image, true));
    NemoKittyImage *original = r.image;
    uint64_t sequence = nemo_kitty_image_sequence(original);
    CHECK(sequence != 0);
    size_t memory = nemo_kitty_cache_memory(f.cache);
    uint64_t generation = nemo_kitty_cache_generation(f.cache);
    const unsigned char rgba[] = {10,20,30,128, 1,2,3,0};
    r = load(&f, "a=q,i=7,f=32,s=2,v=1", rgba, sizeof(rgba));
    CHECK(r.status == NEMO_KITTY_IMAGE_OK && r.query && !r.image && !r.changed);
    CHECK(r.width == 2 && r.height == 1 && f.readonly);
    CHECK(nemo_kitty_cache_generation(f.cache) == generation && nemo_kitty_cache_memory(f.cache) == memory);
    CHECK(nemo_kitty_cache_find(f.cache, 7, 0) == original && !f.removed);
    CHECK(nemo_kitty_image_sequence(original) == sequence);
    r = load(&f, "i=7,f=32,s=2,v=2", rgba, sizeof(rgba));
    CHECK(r.status == NEMO_KITTY_IMAGE_INVALID && !r.changed);
    CHECK(nemo_kitty_cache_find(f.cache, 7, 0) == original && !f.removed);
    r = load(&f, "i=7,f=32,s=2,v=1", rgba, sizeof(rgba));
    CHECK(r.status == NEMO_KITTY_IMAGE_OK && r.changed && r.image != original);
    CHECK(nemo_kitty_image_sequence(r.image) == sequence);
    CHECK(f.removed == 1 && f.last_removed_id == 7 && f.last_removed_references == 2);
    pixels = nemo_kitty_image_raster(r.image);
    CHECK(pixels->pixels[0] == 0x800a141e && pixels->pixels[1] == 0x00010203 && pixels->partial_alpha);
    CHECK(nemo_kitty_cache_count(f.cache) == 1);
    CHECK(!nemo_kitty_image_reference(f.cache, r.image, false));
    nemo_kitty_cache_clear(f.cache);
    CHECK(!nemo_kitty_cache_count(f.cache) && nemo_kitty_cache_memory(f.cache) == empty);
    nemo_kitty_cache_free(f.cache);
}

static void numbers_and_anonymous(void)
{
    Fixture f; create(&f, BUDGET, true);
    NemoKittyImageResult a = load(&f, "I=17,f=24,s=1,v=1", "abc", 3);
    NemoKittyImageResult b = load(&f, "I=17,f=24,s=1,v=1", "def", 3);
    CHECK(a.status == NEMO_KITTY_IMAGE_OK && b.status == NEMO_KITTY_IMAGE_OK);
    CHECK(a.id && b.id && a.id != b.id && a.number == 17 && b.number == 17);
    CHECK(nemo_kitty_cache_find(f.cache, 0, 17) == b.image);
    CHECK(nemo_kitty_cache_find(f.cache, a.id, 0) == a.image);
    CHECK(nemo_kitty_cache_remove(f.cache, b.image));
    CHECK(nemo_kitty_cache_find(f.cache, 0, 17) == a.image);
    a = load(&f, "a=T,f=24,s=1,v=1", "abc", 3);
    b = load(&f, "a=T,i=0,I=0,f=24,s=1,v=1", "def", 3);
    CHECK(a.image && b.image && a.image != b.image && !a.id && !b.id);
    CHECK(nemo_kitty_image_sequence(a.image) < nemo_kitty_image_sequence(b.image));
    CHECK(nemo_kitty_cache_count(f.cache) == 3 && !nemo_kitty_cache_find(f.cache, 0, 0));
    CHECK(!nemo_kitty_cache_find(f.cache, 1, 17));
    NemoKittyImageResult high = load(&f, "i=4294967295,f=24,s=1,v=1", "xyz", 3);
    CHECK(high.status == NEMO_KITTY_IMAGE_OK && high.id == UINT32_MAX);
    CHECK(nemo_kitty_cache_find(f.cache, UINT32_MAX, 0) == high.image);
    nemo_kitty_cache_free(f.cache);
}

static void malformed_and_codecs(void)
{
    Fixture f; create(&f, BUDGET, true);
    static const char *unsupported[] = {"f=8,s=1,v=1", "f=16,s=1,v=1", "f=24,s=1,v=1,o=x",
        "t=f,s=1,v=1", "t=t,s=1,v=1", "t=s,s=1,v=1", "a=f,i=1", "a=q,i=1,e=T"};
    for (size_t i = 0; i < sizeof(unsupported)/sizeof(*unsupported); i++)
        CHECK(load(&f, unsupported[i], "abc", 3).status == NEMO_KITTY_IMAGE_UNSUPPORTED);
    static const char *invalid[] = {"s=0,v=1", "s=1,v=0", "s=4294967295,v=1", "s=1,v=8193",
        "s=1,v=1,f=24", "a=q,f=24,s=1,v=1"};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(*invalid); i++)
        CHECK(load(&f, invalid[i], "a", 1).status == NEMO_KITTY_IMAGE_INVALID);
    CHECK(load(&f, "f=100,i=1", "not a png", 9).status == NEMO_KITTY_IMAGE_DECODE && !f.png_calls);
    const unsigned char wire[] = {137,80,78,71,13,10,26,10};
    for (unsigned mode = 1; mode <= 5; mode++) {
        f.png_mode = mode;
        CHECK(load(&f, "f=100,i=1", wire, sizeof(wire)).status == NEMO_KITTY_IMAGE_DECODE);
        CHECK(!nemo_kitty_cache_count(f.cache));
    }
    f.png_mode = 0;
    NemoKittyImageResult result = load(&f, "f=100,i=1", wire, sizeof(wire));
    CHECK(result.status == NEMO_KITTY_IMAGE_OK && result.width == 2 && result.height == 1);
    CHECK(nemo_kitty_image_raster(result.image)->pixels[1] == 0x80789abc);
    f.limit = nemo_kitty_cache_memory(f.cache);
    unsigned before = f.removed;
    CHECK(load(&f, "a=q,f=100,i=1", wire, sizeof(wire)).status == NEMO_KITTY_IMAGE_LIMIT);
    CHECK(f.removed == before && nemo_kitty_cache_count(f.cache) == 1);
    CHECK(load(&f, "i=3,f=24,s=1,v=1", "abc", NEMO_KITTY_DATA_MAX+1).status == NEMO_KITTY_IMAGE_LIMIT);
    CHECK(load(&f, "i=3,f=24,s=1,v=1", NULL, 3).status == NEMO_KITTY_IMAGE_INVALID);
    nemo_kitty_cache_free(f.cache);
    /* The mock above verifies decoder admission and ownership only. It is not
     * evidence that a PNG file has been decoded by a real platform codec. */
}

static void limits_and_eviction(void)
{
    Fixture f; create(&f, BUDGET, true);
    size_t empty = nemo_kitty_cache_memory(f.cache);
    NemoKittyImageResult a = load(&f, "i=1,f=24,s=1,v=1", "abc", 3);
    CHECK(a.status == NEMO_KITTY_IMAGE_OK);
    size_t image_cost = nemo_kitty_cache_memory(f.cache) - empty;
    nemo_kitty_cache_free(f.cache);
    create(&f, empty + image_cost * 2, true);
    a = load(&f, "i=1,f=24,s=1,v=1", "abc", 3);
    CHECK(nemo_kitty_image_reference(f.cache, a.image, true));
    CHECK(load(&f, "i=2,f=24,s=1,v=1", "abc", 3).status == NEMO_KITTY_IMAGE_OK);
    CHECK(load(&f, "i=3,f=24,s=1,v=1", "abc", 3).status == NEMO_KITTY_IMAGE_OK);
    CHECK(f.last_removed_id == 2 && !nemo_kitty_cache_find(f.cache, 2, 0));
    CHECK(nemo_kitty_cache_find(f.cache, 1, 0) == a.image);
    NemoKittyImage *third = nemo_kitty_cache_find(f.cache, 3, 0);
    CHECK(nemo_kitty_image_reference(f.cache, third, true));
    CHECK(load(&f, "i=4,f=24,s=1,v=1", "abc", 3).status == NEMO_KITTY_IMAGE_OK);
    CHECK(f.last_removed_id == 1 && f.last_removed_references == 1);
    nemo_kitty_cache_free(f.cache);

    create(&f, empty + image_cost, true);
    a = load(&f, "i=1,f=24,s=1,v=1", "abc", 3);
    CHECK(load(&f, "i=1,f=24,s=1,v=1", "def", 3).status == NEMO_KITTY_IMAGE_LIMIT);
    CHECK(nemo_kitty_cache_find(f.cache, 1, 0) == a.image && !f.removed);
    CHECK(nemo_kitty_image_raster(a.image)->pixels[0] == 0xff616263);
    nemo_kitty_cache_free(f.cache);

    create(&f, BUDGET, false);
    a = load(&f, "i=1,f=24,s=1,v=1", "abc", 3);
    CHECK(nemo_kitty_image_reference(f.cache, a.image, true));
    CHECK(!nemo_kitty_cache_remove(f.cache, a.image));
    CHECK(load(&f, "i=1,f=24,s=1,v=1", "def", 3).status == NEMO_KITTY_IMAGE_BUSY);
    CHECK(nemo_kitty_image_reference(f.cache, a.image, false));
    CHECK(nemo_kitty_cache_remove(f.cache, a.image));
    nemo_kitty_cache_free(f.cache);

    create(&f, BUDGET, true);
    for (unsigned i = 1; i <= NEMO_KITTY_IMAGE_MAX + 1; i++) {
        char header[80]; snprintf(header, sizeof(header), "i=%u,f=24,s=1,v=1", i);
        CHECK(load(&f, header, "abc", 3).status == NEMO_KITTY_IMAGE_OK);
    }
    CHECK(nemo_kitty_cache_count(f.cache) == NEMO_KITTY_IMAGE_MAX && f.last_removed_id == 1);
    CHECK(!nemo_kitty_cache_find(f.cache, 1, 0));
    CHECK(nemo_kitty_cache_find(f.cache, NEMO_KITTY_IMAGE_MAX+1, 0));
    nemo_kitty_cache_free(f.cache);

    create(&f, BUDGET, true);
    f.other = BUDGET - empty - image_cost;
    a = load(&f, "i=1,f=24,s=1,v=1", "abc", 3);
    CHECK(a.status == NEMO_KITTY_IMAGE_OK && f.peak == BUDGET);
    CHECK(load(&f, "a=q,i=2,f=24,s=1,v=1", "abc", 3).status == NEMO_KITTY_IMAGE_LIMIT);
    CHECK(!f.removed && nemo_kitty_cache_find(f.cache, 1, 0) == a.image);
    nemo_kitty_cache_free(f.cache);

    create(&f, empty + 2*image_cost, true);
    CHECK(load(&f, "i=1,f=24,s=1,v=1", "abc", 3).status == NEMO_KITTY_IMAGE_OK);
    CHECK(load(&f, "i=2,f=24,s=1,v=1", "def", 3).status == NEMO_KITTY_IMAGE_OK);
    f.png_mode = 3;
    const unsigned char signature[] = {137,80,78,71,13,10,26,10};
    NemoKittyImageResult failure = load(&f, "i=3,f=100", signature, sizeof(signature));
    CHECK(failure.status == NEMO_KITTY_IMAGE_DECODE && failure.changed);
    CHECK(f.removed > 0 && !nemo_kitty_cache_find(f.cache, 3, 0));
    /* Even failed decoding can have evicted other old data to satisfy the
     * quota; the owner must observe changed and repaint those removals. */
    nemo_kitty_cache_free(f.cache);
}

static void compressed_budget_and_readonly_peek(void)
{
    static const unsigned char rgb[] = {120,156,75,76,74,6,0,2,77,1,39};
    static const unsigned char png_z[] = {120,156,235,12,240,115,231,229,146,226,2,0,10,71,1,170};
    Fixture f; create(&f, BUDGET, true);
    size_t empty = nemo_kitty_cache_memory(f.cache);
    NemoKittyImageResult a = load(&f, "i=1,f=24,s=1,v=1,o=z", rgb, sizeof(rgb));
    CHECK(a.status == NEMO_KITTY_IMAGE_OK);
    CHECK(nemo_kitty_image_raster(a.image)->pixels[0] == 0xff616263);
    size_t cost = nemo_kitty_cache_memory(f.cache) - empty;
    f.limit = empty + cost + 15; /* PNG encoding (8) and pixels (8) overlap. */
    CHECK(load(&f, "a=q,i=2,f=100,o=z,S=8", png_z, sizeof(png_z)).status == NEMO_KITTY_IMAGE_LIMIT);
    CHECK(nemo_kitty_cache_memory(f.cache) == empty + cost && !f.removed);
    CHECK(nemo_kitty_cache_peek(f.cache, 1, 0) == a.image);
    f.limit++;
    CHECK(load(&f, "a=q,i=2,f=100,o=z,S=8", png_z, sizeof(png_z)).status == NEMO_KITTY_IMAGE_OK);
    CHECK(nemo_kitty_cache_memory(f.cache) == empty + cost && !f.removed);
    CHECK(f.peak == f.limit && nemo_kitty_cache_count(f.cache) == 1);
    nemo_kitty_cache_clear(f.cache);
    f.limit = empty + 8 + cost + 4; /* Encoded PNG, metadata, two RGBA pixels. */
    f.png_mode = 3;
    CHECK(load(&f, "i=1,f=100,o=z,S=8", png_z, sizeof(png_z)).status == NEMO_KITTY_IMAGE_DECODE);
    CHECK(nemo_kitty_cache_memory(f.cache) == empty && !nemo_kitty_cache_count(f.cache));
    f.png_mode = 0;
    CHECK(load(&f, "i=1,f=100,o=z,S=8", png_z, sizeof(png_z)).status == NEMO_KITTY_IMAGE_OK);
    CHECK(nemo_kitty_cache_memory(f.cache) == empty + cost + 4);
    nemo_kitty_cache_free(f.cache);

    create(&f, empty + 2*cost, true);
    CHECK(load(&f, "i=1,f=24,s=1,v=1", "abc", 3).status == NEMO_KITTY_IMAGE_OK);
    CHECK(load(&f, "i=2,f=24,s=1,v=1", "def", 3).status == NEMO_KITTY_IMAGE_OK);
    uint64_t generation = nemo_kitty_cache_generation(f.cache);
    CHECK(nemo_kitty_cache_peek(f.cache, 1, 0));
    CHECK(nemo_kitty_cache_generation(f.cache) == generation);
    CHECK(load(&f, "i=3,f=24,s=1,v=1", "ghi", 3).status == NEMO_KITTY_IMAGE_OK);
    CHECK(f.last_removed_id == 1 && !nemo_kitty_cache_peek(f.cache, 1, 0));
    CHECK(nemo_kitty_cache_peek(f.cache, 2, 0) && nemo_kitty_cache_peek(f.cache, 3, 0));
    nemo_kitty_cache_free(f.cache);
    CHECK(!nemo_kitty_cache_peek(NULL, 1, 0));
}

static void deferred_orphan_retirement(void)
{
    Fixture f;create(&f,BUDGET,true);
    size_t empty=nemo_kitty_cache_memory(f.cache);
    NemoKittyImage *root=load(&f,"i=1,f=24,s=1,v=1","abc",3).image;
    size_t cost=nemo_kitty_cache_memory(f.cache)-empty;
    NemoKittyImage *child=load(&f,"i=2,f=24,s=1,v=1","abc",3).image;
    NemoKittyImage *grandchild=load(&f,"i=3,f=24,s=1,v=1","abc",3).image;
    CHECK(nemo_kitty_image_reference(f.cache,child,true));
    CHECK(nemo_kitty_image_reference(f.cache,grandchild,true));
    f.orphan_source[0]=1;f.orphan_target[0]=child;
    f.orphan_source[1]=2;f.orphan_target[1]=grandchild;
    CHECK(nemo_kitty_cache_remove(f.cache,root));
    CHECK(f.removed==3 && f.max_callback_depth==1);
    CHECK(!nemo_kitty_cache_count(f.cache) && nemo_kitty_cache_memory(f.cache)==empty);
    CHECK(!nemo_kitty_cache_remove_unreferenced(f.cache,child));
    CHECK(!nemo_kitty_cache_release_orphan(f.cache,grandchild));
    nemo_kitty_cache_free(f.cache);

    /* A remaining independent placement retains data. Reacquiring an orphan
     * before the deferred drain also cancels its pending retirement. */
    create(&f,BUDGET,true);
    child=load(&f,"i=2,f=24,s=1,v=1","abc",3).image;
    CHECK(nemo_kitty_image_reference(f.cache,child,true));
    CHECK(nemo_kitty_image_reference(f.cache,child,true));
    CHECK(nemo_kitty_cache_release_orphan(f.cache,child));
    CHECK(nemo_kitty_image_reference(f.cache,child,false));
    CHECK(!nemo_kitty_cache_prune_orphans(f.cache));
    CHECK(nemo_kitty_cache_count(f.cache)==1);
    CHECK(nemo_kitty_image_reference(f.cache,child,true));
    CHECK(nemo_kitty_cache_release_orphan(f.cache,child));
    /* A read-only query cannot drain even a previously pending retirement. */
    NemoKittyImageResult query=load(&f,"a=q,i=99,f=24,s=1,v=1","abc",3);
    CHECK(query.status==NEMO_KITTY_IMAGE_OK && query.query && !query.changed);
    CHECK(nemo_kitty_cache_count(f.cache)==1 && nemo_kitty_cache_peek(f.cache,2,0)==child);
    CHECK(nemo_kitty_image_reference(f.cache,child,true));
    CHECK(!nemo_kitty_cache_prune_orphans(f.cache));
    CHECK(nemo_kitty_cache_release_orphan(f.cache,child));
    CHECK(nemo_kitty_cache_prune_orphans(f.cache)==1);
    nemo_kitty_cache_free(f.cache);

    /* Replacing a child can evict its parent while decoding. Its old identity
     * must survive until the transaction commits or unwinds, even though the
     * callback has already dropped the final placement reference. */
    const unsigned char signature[]={137,80,78,71,13,10,26,10};
    for (unsigned fail=0;fail<2;fail++) {
        create(&f,empty+2*cost+4,true);
        root=load(&f,"i=1,f=24,s=1,v=1","abc",3).image;
        child=load(&f,"i=2,f=24,s=1,v=1","abc",3).image;
        CHECK(nemo_kitty_image_reference(f.cache,root,true));
        CHECK(nemo_kitty_image_reference(f.cache,child,true));
        uint64_t sequence=nemo_kitty_image_sequence(child);
        f.orphan_source[0]=1;f.orphan_target[0]=child;
        f.png_mode=fail ? 3 : 0;
        NemoKittyImageResult r=load(&f,"i=2,f=100",signature,sizeof(signature));
        CHECK(r.status==(fail ? NEMO_KITTY_IMAGE_DECODE : NEMO_KITTY_IMAGE_OK));
        CHECK(r.changed && f.removed==2 && f.max_callback_depth==1);
        CHECK(!nemo_kitty_cache_peek(f.cache,1,0));
        CHECK(nemo_kitty_cache_count(f.cache)==(fail ? 0u : 1u));
        if (!fail) {
            CHECK(nemo_kitty_image_sequence(r.image)==sequence);
            CHECK(nemo_kitty_image_raster(r.image)->pixels[0]==0xff123456);
        }
        nemo_kitty_cache_free(f.cache);
    }
}

int main(void)
{
    pixels_and_identity(); numbers_and_anonymous(); malformed_and_codecs(); limits_and_eviction();
    compressed_budget_and_readonly_peek();
    deferred_orphan_retirement();
    CHECK(!nemo_kitty_cache_new(1, NULL, NULL, NULL, NULL));
    CHECK(!nemo_kitty_cache_memory(NULL) && !nemo_kitty_cache_count(NULL));
    CHECK(!nemo_kitty_cache_generation(NULL) && !nemo_kitty_image_raster(NULL));
    CHECK(!nemo_kitty_image_sequence(NULL));
    nemo_kitty_cache_clear(NULL); nemo_kitty_cache_free(NULL);
    printf("Kitty image cache: %u checks passed\n", checks);
    return 0;
}
