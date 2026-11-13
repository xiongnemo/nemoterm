/* SPDX-License-Identifier: MIT
 * Allocation-lifetime bookkeeping for a diagnostic observer, never the app.
 * The adapter must serialize every operation, including freeze and snapshots.
 * No allocations, OS calls or target-memory reads occur in these functions.
 * Only allocations observed after attachment are represented. Requested live
 * bytes are not committed/resident bytes and are never a working-set result.
 */
#ifndef NEMOTERM_ALLOCATION_CENSUS_H
#define NEMOTERM_ALLOCATION_CENSUS_H

typedef unsigned long long ACValue;
typedef struct ACEntry {
    ACValue address, heap, caller, bytes, generation;
} ACEntry;
typedef struct ACState {
    ACEntry *entries;
    unsigned capacity, active, errors;
    ACValue generation, live_count, live_bytes;
} ACState;
enum { AC_BAD_CAPACITY=1, AC_TABLE_FULL=2, AC_GENERATION_OVERFLOW=4,
       AC_BYTES_OVERFLOW=8 };

static void ac_init(ACState *s, ACEntry *entries, unsigned capacity)
{
    unsigned i;
    *s=(ACState){0};
    s->entries=entries;
    if (!entries || !capacity || (capacity & (capacity-1))) {
        s->errors=AC_BAD_CAPACITY;return;
    }
    s->capacity=capacity;s->active=1;
    for (i=0;i<capacity;i++) entries[i]=(ACEntry){0};
}

/* 0 is empty and 1 is a tombstone; real heap addresses are aligned. */
static ACEntry *ac_slot(ACState *s, ACValue address, int insert)
{
    ACEntry *vacant=0;
    unsigned n,index;
    if (address<=1 || !s->capacity) return 0;
    index=(unsigned)((address>>4)^(address>>21))&(s->capacity-1);
    for (n=0;n<s->capacity;n++,index=(index+1)&(s->capacity-1)) {
        ACEntry *entry=&s->entries[index];
        if (entry->address==address) return entry;
        if (entry->address==1 && !vacant) vacant=entry;
        if (!entry->address) return insert?(vacant?vacant:entry):0;
    }
    return insert?vacant:0;
}

static ACValue ac_generation(ACState *s, ACValue address)
{
    ACEntry *entry=ac_slot(s,address,0);
    return entry?entry->generation:0;
}

static void ac_remove(ACState *s, ACEntry *entry)
{
    s->live_count--;s->live_bytes-=entry->bytes;
    entry->address=1;
}

static int ac_record(ACState *s, ACValue address, ACValue heap,
                     ACValue bytes, ACValue caller)
{
    ACEntry *entry;
    ACValue previous=0;
    if (!s->active || address<=1) return 0;
    entry=ac_slot(s,address,1);
    if (!entry) {s->errors|=AC_TABLE_FULL;return 0;}
    if (s->generation==~(ACValue)0) {
        s->errors|=AC_GENERATION_OVERFLOW;return 0;
    }
    if (entry->address>1) previous=entry->bytes;
    if (bytes>~(ACValue)0-(s->live_bytes-previous)) {
        s->errors|=AC_BYTES_OVERFLOW;return 0;
    }
    if (entry->address<=1) s->live_count++;
    s->live_bytes=s->live_bytes-previous+bytes;
    *entry=(ACEntry){address,heap,caller,bytes,++s->generation};
    return 1;
}

/* Capture generation on function entry, then apply the successful result on
 * leave. A different thread can reuse the address before this callback runs.
 * The stale free must not remove that new allocation. */
static void ac_free_done(ACState *s, ACValue address, ACValue generation,
                         int succeeded)
{
    ACEntry *entry;
    if (!s->active || !succeeded || !generation) return;
    entry=ac_slot(s,address,0);
    if (entry && entry->generation==generation) ac_remove(s,entry);
}

static void ac_realloc_done(ACState *s, ACValue old_address,
                            ACValue old_generation, ACValue new_address,
                            ACValue heap, ACValue bytes, ACValue caller)
{
    if (!s->active || !new_address) return; /* Failure preserves the old block. */
    if (old_address!=new_address)
        ac_free_done(s,old_address,old_generation,1);
    /* A nested allocation hook may already have recorded new_address. Replace
     * that entry instead of counting the inner/outer observations twice. */
    ac_record(s,new_address,heap,bytes,caller);
}

/* Capture the global generation when heap destruction starts. Allocations in
 * a newly created heap reusing the same handle must survive its late callback. */
static void ac_destroy_done(ACState *s, ACValue heap, ACValue cutoff,
                            int succeeded)
{
    unsigned i;
    if (!s->active || !succeeded) return;
    for (i=0;i<s->capacity;i++) {
        ACEntry *entry=&s->entries[i];
        if (entry->address>1 && entry->heap==heap && entry->generation<=cutoff)
            ac_remove(s,entry);
    }
}

static void ac_freeze(ACState *s) { s->active=0; }

#endif
