/* SPDX-License-Identifier: MIT */
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "nemo_raster.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void composition(void)
{
    NemoRaster r;
    assert(nemo_raster_allocate(&r, 3, 2, 5, 4096));
    NemoRasterComposer c = {.background=0xff000000};
    assert(nemo_raster_prepare(&r, 0, &c));
    r.frames[0].pixels[0] = 0xffff0000;
    assert(nemo_raster_dispose(&r, &c, 0, 1, 0, 0, 1, 1));
    assert(nemo_raster_prepare(&r, 1, &c));
    r.frames[1].pixels[1] = 0xff00ff00;
    assert(nemo_raster_dispose(&r, &c, 1, 3, 1, 0, 1, 1));
    assert(nemo_raster_prepare(&r, 2, &c));
    assert(r.frames[2].pixels[0] == 0xffff0000);
    assert(r.frames[2].pixels[1] == 0xff000000); /* previous, not frame 1 */
    r.frames[2].pixels[3] = 0xff0000ff;
    assert(nemo_raster_dispose(&r, &c, 2, 2, 0, 1, 1, 1));
    assert(nemo_raster_prepare(&r, 3, &c));
    assert(r.frames[3].pixels[0] == 0xffff0000);
    assert(r.frames[3].pixels[3] == 0xff000000);
    r.frames[3].pixels[5] = 0xffffffff;
    assert(nemo_raster_dispose(&r, &c, 3, 3, 2, 1, 1, 1));
    assert(nemo_raster_prepare(&r, 4, &c));
    const uint32_t expected[] = {0xffff0000,0xff000000,0xff000000,
                                 0xff000000,0xff000000,0xff000000};
    assert(!memcmp(r.frames[4].pixels, expected, sizeof(expected)));
    assert(!nemo_raster_dispose(&r,&c,4,4,0,0,1,1));
    assert(!nemo_raster_dispose(&r,&c,4,0,UINT32_MAX,0,1,1));
    assert(!nemo_raster_dispose(&r,&c,4,0,2,1,2,1));
    nemo_raster_free(&r);
    assert(!r.frames && !r.pixels && !r.bytes);
    nemo_raster_free(&r);
    assert(!nemo_raster_allocate(&r,8192,8192,256,4*1024*1024));
    assert(!nemo_raster_storage(1,1,257));
    assert(!nemo_raster_storage(UINT32_MAX,UINT32_MAX,256));
    size_t bytes = nemo_raster_storage(2,2,3);
    assert(!nemo_raster_allocate(&r,2,2,3,bytes-1));
    assert(nemo_raster_allocate(&r,2,2,3,bytes));
    assert(r.bytes == bytes);
    nemo_raster_free(&r);
}

static void timing(void)
{
    NemoRaster r;
    bool changed;
    assert(nemo_raster_allocate(&r,1,1,4,4096));
    r.frames[0].delay_ms=0; r.frames[1].delay_ms=20;
    r.frames[2].delay_ms=30; r.frames[3].delay_ms=0;
    r.plays=2;
    assert(nemo_raster_tick(&r,UINT32_MAX-9,&changed)==20 && changed && r.frame_index==1);
    assert(nemo_raster_tick(&r,5,&changed)==5 && !changed);
    assert(nemo_raster_tick(&r,10,&changed)==30 && changed && r.frame_index==2);
    assert(nemo_raster_tick(&r,40,&changed)==20 && changed && r.frame_index==1);
    assert(nemo_raster_tick(&r,90,&changed)==0 && changed && r.frame_index==3 && r.finished);
    assert(nemo_raster_tick(&r,500,&changed)==0 && !changed);
    nemo_raster_free(&r);
    assert(nemo_raster_allocate(&r,1,1,3,4096));
    r.plays=0;
    assert(!nemo_raster_tick(&r,0,&changed) && changed && r.frame_index==2 && r.finished);
    nemo_raster_free(&r);
    /* Finite and infinite catch-up agree with an independent duration oracle,
     * including skipped zero frames and long gaps without callback storms. */
    for (unsigned plays=0;plays<4;plays++) {
        assert(nemo_raster_allocate(&r,1,1,3,4096));
        r.plays=plays;
        r.frames[0].delay_ms=10;r.frames[1].delay_ms=20;r.frames[2].delay_ms=30;
        for (unsigned t=0;t<100000;t+=17) {
            unsigned wait=nemo_raster_tick(&r,t,&changed);
            unsigned phase=t%60, expected=phase<10?0:phase<30?1:2;
            if (plays && t>=60*plays) {expected=2;assert(!wait);}
            else assert(wait==(phase<10?10-phase:phase<30?30-phase:60-phase));
            assert(r.frame_index==expected && r.pixels==r.frames[expected].pixels);
        }
        nemo_raster_free(&r);
    }
}

static uint32_t random_value(uint32_t *seed)
{
    *seed = *seed*1664525u+1013904223u;
    return *seed;
}

static void composition_oracle(void)
{
    /* The oracle copies the full pre-frame canvas, independently of the
     * implementation's deferred base-frame and clear-rectangle representation. */
    for (uint32_t seed0=1; seed0<33; seed0++) {
        uint32_t seed=seed0, state[12], saved[12];
        NemoRaster r;
        assert(nemo_raster_allocate(&r,4,3,64,65536));
        NemoRasterComposer compose={.background=0xff000000};
        for (unsigned i=0;i<12;i++) state[i]=compose.background;
        for (unsigned frame=0;frame<64;frame++) {
            assert(nemo_raster_prepare(&r,frame,&compose));
            assert(!memcmp(r.frames[frame].pixels,state,sizeof(state)));
            memcpy(saved,state,sizeof(state));
            unsigned x=random_value(&seed)%4,y=random_value(&seed)%3;
            unsigned w=1+random_value(&seed)%(4-x),h=1+random_value(&seed)%(3-y);
            unsigned disposal=random_value(&seed)%4;
            for (unsigned yy=y;yy<y+h;yy++) for (unsigned xx=x;xx<x+w;xx++) {
                uint32_t pixel=random_value(&seed);
                if (pixel&256) state[yy*4+xx]=r.frames[frame].pixels[yy*4+xx]=0xff000000|(pixel&0xffffff);
            }
            if (disposal==2) compose.background=(random_value(&seed)&256)?0:0xff101010;
            assert(nemo_raster_dispose(&r,&compose,frame,disposal,x,y,w,h));
            if (disposal==3) memcpy(state,saved,sizeof(state));
            else if (disposal==2)
                for (unsigned yy=y;yy<y+h;yy++) for (unsigned xx=x;xx<x+w;xx++) state[yy*4+xx]=compose.background;
        }
        nemo_raster_free(&r);
    }
}

int main(void)
{
    composition();composition_oracle();timing();puts("Raster composition and animation suite passed");
    return 0;
}
