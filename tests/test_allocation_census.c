/* Diagnostic collector regressions: no windows or instrumentation here. */
#include <assert.h>
#include <stdio.h>
#include "allocation_census.h"

static void validate(ACState *s, ACValue count, ACValue bytes)
{
    ACValue actual_count=0,actual_bytes=0;
    unsigned i;
    for (i=0;i<s->capacity;i++) if (s->entries[i].address>1) {
        actual_count++;actual_bytes+=s->entries[i].bytes;
    }
    assert(s->live_count==count && s->live_bytes==bytes);
    assert(actual_count==count && actual_bytes==bytes);
}

static void lifetime_and_reallocation(void)
{
    ACEntry entries[16];ACState s;ACValue old;
    ac_init(&s,entries,16);
    assert(!ac_record(&s,0,100,200,300));validate(&s,0,0);
    assert(ac_record(&s,0x1000,100,64,300));
    old=ac_generation(&s,0x1000);
    ac_free_done(&s,0x1000,old,0);validate(&s,1,64);
    ac_realloc_done(&s,0x1000,old,0,100,128,301);validate(&s,1,64);
    assert(ac_generation(&s,0x1000)==old);
    ac_realloc_done(&s,0x1000,old,0x1000,100,16,301);validate(&s,1,16);
    old=ac_generation(&s,0x1000);
    ac_realloc_done(&s,0x1000,old,0x2000,100,256,302);validate(&s,1,256);
    assert(!ac_generation(&s,0x1000));
    assert(ac_slot(&s,0x2000,0)->caller==302);
    old=ac_generation(&s,0x2000);
    ac_free_done(&s,0x2000,old,1);validate(&s,0,0);
    assert(!s.errors);
}

static void address_reuse_and_nested_hooks(void)
{
    ACEntry entries[16];ACState s;ACValue old;
    ac_init(&s,entries,16);
    ac_record(&s,0x1000,100,64,300);old=ac_generation(&s,0x1000);
    /* Heap release has happened, but its leave callback is delayed. */
    ac_record(&s,0x1000,100,32,400);
    ac_free_done(&s,0x1000,old,1);validate(&s,1,32);
    assert(ac_slot(&s,0x1000,0)->caller==400);
    /* The old realloc moved; its old address was reused before onLeave. */
    ac_realloc_done(&s,0x1000,old,0x2000,100,128,500);validate(&s,2,160);
    old=ac_generation(&s,0x2000);
    ac_record(&s,0x3000,100,256,501); /* Nested RtlAllocateHeap callback. */
    ac_realloc_done(&s,0x2000,old,0x3000,100,256,502);validate(&s,2,288);
    assert(ac_slot(&s,0x3000,0)->caller==502);
    old=ac_generation(&s,0x3000);
    ac_record(&s,0x3000,100,512,503);
    ac_realloc_done(&s,0x3000,old,0x3000,100,512,504);validate(&s,2,544);
    assert(!s.errors);
}

static void heap_handle_reuse_and_freeze(void)
{
    ACEntry entries[8];ACState s;ACValue cutoff;
    ac_init(&s,entries,8);
    ac_record(&s,0x1000,100,64,1);ac_record(&s,0x2000,100,32,1);
    ac_record(&s,0x3000,200,16,2);cutoff=s.generation;
    ac_destroy_done(&s,100,cutoff,0);validate(&s,3,112);
    ac_record(&s,0x1000,100,128,3); /* New heap reuses handle and address. */
    ac_record(&s,0x4000,100,256,3);
    ac_destroy_done(&s,100,cutoff,1);validate(&s,3,400);
    assert(!ac_generation(&s,0x2000));
    ac_freeze(&s);
    ac_record(&s,0x5000,100,64,1);
    ac_free_done(&s,0x1000,ac_generation(&s,0x1000),1);
    ac_realloc_done(&s,0x3000,ac_generation(&s,0x3000),0x6000,200,200,1);
    ac_destroy_done(&s,100,s.generation,1);validate(&s,3,400);
    assert(!s.errors);
}

static void collisions_and_exhaustion(void)
{
    ACEntry entries[8];ACState s;unsigned i;
    ac_init(&s,entries,8);
    /* Several distinct addresses have the same low alignment/hash bits. */
    for (i=0;i<8;i++) assert(ac_record(&s,0x1000+256*i,100,i+1,1));
    validate(&s,8,36);
    ac_free_done(&s,0x1000,ac_generation(&s,0x1000),1);
    assert(ac_slot(&s,0x1700,0)->bytes==8);
    assert(ac_record(&s,0x2000,100,20,1));validate(&s,8,55);
    assert(!ac_record(&s,0x3000,100,99,1));
    assert(s.errors==AC_TABLE_FULL);validate(&s,8,55);
    for (i=0;i<8;i++) if (entries[i].address>1)
        ac_free_done(&s,entries[i].address,entries[i].generation,1);
    validate(&s,0,0);
    assert(ac_record(&s,0x4000,100,44,1));validate(&s,1,44);
    assert(s.errors==AC_TABLE_FULL); /* Lost observations remain explicit. */
}

static void counter_boundaries(void)
{
    ACEntry entries[4];ACState s;
    ac_init(&s,entries,3);assert(s.errors==AC_BAD_CAPACITY && !s.active);
    ac_init(&s,entries,4);s.generation=~(ACValue)0;
    assert(!ac_record(&s,0x1000,100,1,1));
    assert(s.errors==AC_GENERATION_OVERFLOW);validate(&s,0,0);
    ac_init(&s,entries,4);
    assert(ac_record(&s,0x1000,100,~(ACValue)0,1));
    assert(!ac_record(&s,0x2000,100,1,1));
    assert(s.errors==AC_BYTES_OVERFLOW);validate(&s,1,~(ACValue)0);
    assert(ac_record(&s,0x1000,100,4,1));validate(&s,1,4);
}

int main(void)
{
    lifetime_and_reallocation();address_reuse_and_nested_hooks();
    heap_handle_reuse_and_freeze();collisions_and_exhaustion();counter_boundaries();
    puts("Allocation census lifetimes, address/heap reuse, nested hooks and bounds passed");
    return 0;
}
