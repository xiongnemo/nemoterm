/* SPDX-License-Identifier: MIT */
#include "nemo_pointer_glyph.h"
#include <stdio.h>
#include <string.h>
#include <limits.h>

static unsigned checks;
#define CHECK(expr) do { checks++; if (!(expr)) { \
    fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#expr);return 1; } } while (0)

int main(void)
{
    uint8_t a[2050], b[2050], previous[NEMO_POINTER_GLYPH_COUNT][256];
    unsigned custom = 0, cases = 0;
    for (unsigned shape = 0; shape <= NEMO_POINTER_SHAPE_COUNT; shape++) {
        NemoPointerShape value = (NemoPointerShape)shape;
        if (nemo_pointer_glyph_index(value) < 0) {
            unsigned hx = 99, hy = 99;
            memset(a, 0xa5, sizeof(a)); memset(b, 0x5a, sizeof(b));
            CHECK(!nemo_pointer_glyph_masks(value,32,a+1,b+1,2048,&hx,&hy));
            CHECK(hx == 99 && hy == 99 && a[1] == 0xa5 && b[1] == 0x5a);
            continue;
        }
        custom++;
        for (unsigned size = 32; size <= 128; size++) {
            size_t stride = ((size+15)/16)*2, bytes = stride*size;
            unsigned hx = 999, hy = 999;
            memset(a, 0xa5, sizeof(a)); memset(b, 0x5a, sizeof(b));
            CHECK(!nemo_pointer_glyph_masks(value,size,a+1,b+1,bytes-1,&hx,&hy));
            CHECK(hx == 999 && hy == 999 && a[1] == 0xa5 && b[1] == 0x5a);
            CHECK(nemo_pointer_glyph_masks(value,size,a+1,b+1,bytes,&hx,&hy));
            CHECK(hx < size && hy < size);
            CHECK(a[0] == 0xa5 && a[bytes+1] == 0xa5 && b[0] == 0x5a && b[bytes+1] == 0x5a);
            if (a[1+hy*stride+hx/8] & (128u >> (hx%8)))
                fprintf(stderr,"Transparent hotspot: shape=%u size=%u x=%u y=%u\n",shape,size,hx,hy);
            CHECK(!(a[1+hy*stride+hx/8] & (128u >> (hx%8))));
            unsigned white = 0, black = 0, transparent = 0;
            for (unsigned y = 0; y < size; y++) for (unsigned x = 0; x < size; x++) {
                unsigned bit = 128u >> (x%8), offset = 1+y*(unsigned)stride+x/8;
                bool and_bit = (a[offset]&bit) != 0, xor_bit = (b[offset]&bit) != 0;
                CHECK(!(and_bit && xor_bit));
                white += !and_bit && xor_bit;
                black += !and_bit && !xor_bit;
                transparent += and_bit && !xor_bit;
            }
            CHECK(white && black && transparent);
            if (size == 32) {
                unsigned index = (unsigned)nemo_pointer_glyph_index(value);
                memcpy(previous[index],a+1,128); memcpy(previous[index]+128,b+1,128);
                for (unsigned other = 0; other < index; other++)
                    CHECK(memcmp(previous[index],previous[other],256) != 0);
            }
            cases++;
        }
        unsigned hx, hy;
        CHECK(!nemo_pointer_glyph_masks(value,0,a,b,sizeof(a),&hx,&hy));
        CHECK(!nemo_pointer_glyph_masks(value,31,a,b,sizeof(a),&hx,&hy));
        CHECK(!nemo_pointer_glyph_masks(value,129,a,b,sizeof(a),&hx,&hy));
        CHECK(!nemo_pointer_glyph_masks(value,UINT_MAX,a,b,sizeof(a),&hx,&hy));
        CHECK(!nemo_pointer_glyph_masks(value,32,NULL,b,sizeof(b),&hx,&hy));
        CHECK(!nemo_pointer_glyph_masks(value,32,a,NULL,sizeof(a),&hx,&hy));
    }
    CHECK(custom == 8 && cases == 776);
    printf("Pointer glyph masks: %u checks; 776 shape/size cases; bounded buffers and distinct glyphs passed\n",checks);
    return 0;
}
