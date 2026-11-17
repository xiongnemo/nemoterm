/* SPDX-License-Identifier: MIT
 * Native decoder driver: the Python harness supplies original upstream data.
 */
#include "nemo_regis.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

typedef struct Fixture {
    char reply[8192];
    size_t length, reserved, peak;
    NemoRegis *other;
    int failures;
} Fixture;

#define CHECK(x) do { if (!(x)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x); failures++; } } while (0)

static bool memory(void *ctx,size_t old,size_t bytes)
{
    Fixture *f=ctx;
    if (old!=f->reserved) { f->failures++; return false; }
    f->reserved=bytes;
    if (f->peak<bytes) f->peak=bytes;
    return true;
}

static void reply(void *ctx,const char *data,size_t length)
{
    Fixture *f=ctx;
    if (length>sizeof(f->reply)-f->length) { f->failures++; return; }
    memcpy(f->reply+f->length,data,length);
    f->length+=length;
    if (f->other) {
        const char command[]="P[7,9]R(P)";
        if (nemo_regis_parse(f->other,0,command,sizeof(command)-1)!=NEMO_REGIS_OK)
            f->failures++;
    }
}

static NemoRegisConfig configuration(Fixture *fixture)
{
    NemoRegisConfig c={0};
    c.width=c.max_width=160;
    c.height=c.max_height=120;
    c.colours=16; c.terminal_id=340; c.private_colours=true;
    c.memory_limit=4*1024*1024;
    c.user=fixture; c.resize_memory=memory; c.reply=reply;
    return c;
}

static int self_test(void)
{
    int failures=0;
    Fixture a={0},b={0};
    NemoRegisConfig ca=configuration(&a),cb=configuration(&b);
    NemoRegis *first=nemo_regis_new(&ca),*second=nemo_regis_new(&cb);
    CHECK(first && second);
    if (!first || !second) return 1;
    size_t base=nemo_regis_bytes(first);
    a.other=second;
    const char sample[]="S(E)W(I3)P[20,20]V[120,20]R(P)";
    CHECK(nemo_regis_parse(first,1,sample,sizeof(sample)-1)==NEMO_REGIS_OK);
    CHECK(a.length==9 && !memcmp(a.reply,"[120,20]\r",9));
    CHECK(b.length==6 && !memcmp(b.reply,"[7,9]\r",6));
    uint32_t row[160];
    CHECK(nemo_regis_read_row(first,0,20,0,row,160)==160);
    CHECK(row[19]==0xff000000 && row[20]==0xff33cc33 && row[120]==0xff33cc33 && row[121]==0xff000000);
    a.other=NULL;
    nemo_regis_reset(first);
    CHECK(nemo_regis_bytes(first)==base && a.reserved==base);
    CHECK(nemo_regis_parse(first,0,"x\0y",3)==NEMO_REGIS_INVALID);
    CHECK(nemo_regis_bytes(first)==base);
    char nested[600]; size_t length=0;
    for (unsigned i=0;i<64;i++) { nested[length++]='F'; nested[length++]='('; }
    nested[length++]='P'; nested[length++]='['; nested[length++]='1'; nested[length++]=','; nested[length++]='1'; nested[length++]=']';
    for (unsigned i=0;i<64;i++) nested[length++]=')';
    CHECK(nemo_regis_parse(first,0,nested,length)==NEMO_REGIS_LIMIT);
    CHECK(nemo_regis_bytes(first)==base && a.reserved==base);
    CHECK(nemo_regis_parse(first,1,sample,sizeof(sample)-1)==NEMO_REGIS_OK);
    nemo_regis_free(first); nemo_regis_free(second);
    CHECK(!a.reserved && !b.reserved && !a.failures && !b.failures);
    memset(&a,0,sizeof(a));
    ca=configuration(&a); ca.memory_limit=base+256;
    first=nemo_regis_new(&ca);
    CHECK(first!=NULL);
    if (first) {
        CHECK(nemo_regis_parse(first,0,sample,sizeof(sample)-1)==NEMO_REGIS_LIMIT);
        CHECK(nemo_regis_bytes(first)==base && a.reserved==base);
        nemo_regis_free(first);
    }
    CHECK(!a.reserved && !a.failures);
    memset(&a,0,sizeof(a));
    ca=configuration(&a); ca.work_limit=16;
    first=nemo_regis_new(&ca);
    CHECK(first!=NULL);
    if (first) {
        CHECK(nemo_regis_parse(first,0,sample,sizeof(sample)-1)==NEMO_REGIS_LIMIT);
        CHECK(nemo_regis_bytes(first)==base);
        nemo_regis_free(first);
    }
    CHECK(!a.reserved && !a.failures);
    fprintf(stderr,"ReGIS ownership/budget checks: failures=%d base=%zu\n",failures,base);
    return failures ? 1 : 0;
}

int main(int argc,char **argv)
{
    const char *actions=getenv("GITHUB_ACTIONS"),*hosted=getenv("RUNNER_ENVIRONMENT");
    if (!actions || strcmp(actions,"true") || !hosted || strcmp(hosted,"github-hosted")) {
        fputs("Run ReGIS checks on a GitHub-hosted runner.\n",stderr); return 2;
    }
    if (argc==2 && !strcmp(argv[1],"--self-test")) return self_test();
#ifdef _WIN32
    _setmode(_fileno(stdin),_O_BINARY); _setmode(_fileno(stdout),_O_BINARY);
#endif
    Fixture fixture={0};
    NemoRegisConfig config=configuration(&fixture);
    NemoRegis *decoder=nemo_regis_new(&config);
    if (!decoder) return 3;
    char header[128];
    while (fgets(header,sizeof(header),stdin)) {
        unsigned mode=0; size_t length=0;
        if (sscanf(header,"C %u",&mode)==1) { nemo_regis_private_colours(decoder,mode!=0); continue; }
        if (sscanf(header,"P %u %zu",&mode,&length)!=2 || length>256*1024) return 4;
        char *input=malloc(length ? length : 1);
        if (!input || fread(input,1,length,stdin)!=length) return 5;
        fixture.length=0;
        NemoRegisResult result=nemo_regis_parse(decoder,mode,input,length);
        free(input);
        unsigned page=nemo_regis_display_page(decoder),width=0,height=0;
        nemo_regis_page_size(decoder,page,&width,&height);
        printf("%u %zu %u %u %u %zu\n",(unsigned)result,nemo_regis_bytes(decoder),page,width,height,fixture.length);
        fwrite(fixture.reply,1,fixture.length,stdout);
        for (unsigned y=0;y<120;y++) {
            uint32_t row[160]={0};
            nemo_regis_read_row(decoder,page,y,0,row,160);
            for (unsigned x=0;x<160;x++) {
                unsigned char rgb[3]={(unsigned char)(row[x]>>16),(unsigned char)(row[x]>>8),(unsigned char)row[x]};
                fwrite(rgb,1,3,stdout);
            }
        }
        fflush(stdout);
    }
    nemo_regis_free(decoder);
    return fixture.failures || fixture.reserved ? 6 : 0;
}
