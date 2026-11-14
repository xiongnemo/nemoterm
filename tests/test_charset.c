/* SPDX-License-Identifier: MIT */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nemo_charset.h"
#include "charset_reference.h"

#define CHECK(test) do { if (!(test)) { \
    fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#test); exit(1); } } while (0)

int main(void)
{
    unsigned compared=0,failures=0;
    for (size_t i=0;i<sizeof(charset_reference)/sizeof(*charset_reference);i++) {
        const NemoCharset *cs=nemo_charset_designate(charset_reference[i].group,5,
            charset_reference[i].national,charset_reference[i].designation,
            strlen(charset_reference[i].designation));
        /* This represents XTerm's explicit unknown-designator reset, not a
         * policy baked into the mapper: a frontend may choose another policy. */
        if (!cs) cs=nemo_charset_designate(1,5,false,"B",1);
        CHECK(cs);
        for (unsigned x=0;x<96;x++) {
            unsigned byte=x+0x20+(charset_reference[i].right ? 0x80 : 0);
            uint32_t actual=nemo_charset_map(cs,byte,5,charset_reference[i].national);
            /* A 94-set introducer makes raw GL DEL a parser control even if
             * the selected set's presentation descriptor says 96. */
            if (byte==0x7f && charset_reference[i].group==1) actual=NEMO_CHARSET_NOCHAR;
            if (actual==NEMO_CHARSET_NOCHAR) actual=0x20; /* untouched blank cell */
            if (actual!=charset_reference[i].cells[x]) {
                if (failures<20) fprintf(stderr,"%s byte %02x: %04x != %04x\n",charset_reference[i].name,
                    byte,(unsigned)actual,charset_reference[i].cells[x]);
                failures++;
            }
            compared++;
        }
    }
    CHECK(!failures);
    CHECK(!nemo_charset_designate(0,5,true,"K",1));
    CHECK(!nemo_charset_designate(2,5,true,"K",1));
    CHECK(!nemo_charset_designate(1,0,true,"K",1));
    CHECK(!nemo_charset_designate(1,6,true,"K",1));
    CHECK(!nemo_charset_designate(1,5,true,NULL,1));
    CHECK(!nemo_charset_designate(1,5,true,"K",0));
    CHECK(!nemo_charset_designate(1,5,true,"%60",3));
    CHECK(!nemo_charset_designate(1,1,true,"K",1));
    CHECK(!nemo_charset_designate(1,5,false,"K",1));
    CHECK(!nemo_charset_designate(3,5,true,"K",1));
    CHECK(!nemo_charset_designate(1,2,true,"%6",2));
    CHECK(nemo_charset_designate(1,3,true,"%6",2));
    CHECK(!nemo_charset_designate(1,4,true,"\">",2));
    CHECK(nemo_charset_designate(1,5,true,"\">",2));
    CHECK(nemo_charset_designate(1,3,false,"I",1));
    CHECK(!nemo_charset_designate(1,4,false,"I",1));
    CHECK(!nemo_charset_designate(3,3,false,"B",1));
    CHECK(nemo_charset_designate(3,5,false,"B",1)->size96);
    CHECK(!nemo_charset_designate(3,5,true,"A",1)->size96);
    const NemoCharset *a=nemo_charset_designate(1,5,true,"C",1);
    const NemoCharset *b=nemo_charset_designate(1,5,true,"5",1);
    CHECK(nemo_charset_by_id(nemo_charset_id(a))==a);
    CHECK(nemo_charset_by_id(nemo_charset_id(b))==b);
    CHECK(nemo_charset_id(NULL)==0);
    NemoCharset external={0};
    CHECK(nemo_charset_id(&external)==0);
    CHECK(!nemo_charset_by_id(0));
    CHECK(!nemo_charset_by_id(256));
    CHECK(!nemo_charset_by_id(UINT32_MAX));
    CHECK(a && b && a!=b && a->mapping==b->mapping);
    CHECK(!strcmp(a->designation,"C") && !strcmp(b->designation,"5"));
    for (unsigned byte=0;byte<0x20;byte++) CHECK(nemo_charset_map(a,byte,5,true)==NEMO_CHARSET_NOCHAR);
    for (unsigned byte=0x80;byte<0xa0;byte++) CHECK(nemo_charset_map(a,byte,5,true)==NEMO_CHARSET_NOCHAR);
    CHECK(nemo_charset_map(a,256,5,true)==NEMO_CHARSET_NOCHAR);
    CHECK(nemo_charset_map(a,~0u,5,true)==NEMO_CHARSET_NOCHAR);
    CHECK(nemo_charset_map(NULL,0x41,5,true)==NEMO_CHARSET_NOCHAR);
    printf("%u independent reference cells and designation/boundary checks passed\n",compared);
    return 0;
}
