/* SPDX-License-Identifier: MIT */
#include "nemo_iterm.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BUDGET (4u*1024u*1024u)
static void feed(NemoIterm *s, const char *p)
{ assert(nemo_iterm_feed(s, p, strlen(p))); }
static void file(NemoIterm *s, const char *p)
{ assert(nemo_iterm_begin(s,NEMO_ITERM_FILE)); feed(s,p); }
static void equal(NemoIterm *s, const void *data, size_t size)
{
    NemoItermPacket p;
    assert(nemo_iterm_finish(s,&p));
    assert(p.length == size && !memcmp(p.data,data,size));
    assert(!nemo_iterm_finish(s,&p));
    assert(!p.data && !p.length);
}

static void vectors(NemoIterm *s)
{
    static const char *encoded[] = {"Zg==","Zm8=","Zm9v","Zm9vYg==","Zm9vYmE=","Zm9vYmFy"};
    static const char *plain[] = {"f","fo","foo","foob","fooba","foobar"};
    for (size_t i=0;i<6;i++) {
        size_t n=strlen(encoded[i]);
        for (size_t cut=0;cut<=n;cut++) {
            file(s,"inline=1:");
            assert(nemo_iterm_feed(s,encoded[i],cut));
            assert(nemo_iterm_feed(s,encoded[i]+cut,n-cut));
            equal(s,plain[i],strlen(plain[i]));
        }
    }
    file(s,"inline=1:AP8A/w==");
    const unsigned char binary[]={0,255,0,255}; equal(s,binary,sizeof(binary));
    file(s,"inline=1:Zg"); equal(s,"f",1);
    file(s,"inline=1:Zm8"); equal(s,"fo",2);
}

static void metadata(NemoIterm *s)
{
    const char *wire="name=Zm9vPQ==;size=9999999999999999999999;inline=1;"
        "width=80;height=50%;width=00123px;preserveAspectRatio=0;unknown=bar:YWJj";
    assert(nemo_iterm_begin(s,NEMO_ITERM_FILE));
    for (const char *p=wire;*p;p++) assert(nemo_iterm_feed(s,p,1));
    NemoItermPacket p;
    assert(nemo_iterm_finish(s,&p));
    assert(p.width.unit==NEMO_ITERM_PIXELS && p.width.value==123);
    assert(p.height.unit==NEMO_ITERM_PERCENT && p.height.value==50);
    assert(!p.preserve_aspect && p.length==3 && !memcmp(p.data,"abc",3));
    file(s,"inline=1;width=auto;height=4294967295:YWJj");
    assert(nemo_iterm_finish(s,&p));
    assert(p.width.unit==NEMO_ITERM_AUTO && p.height.unit==NEMO_ITERM_CELLS &&
           p.height.value==UINT32_MAX && p.preserve_aspect);
    file(s,"inline=1;width=0;height=1px:YWJj");
    assert(nemo_iterm_finish(s,&p));
    assert(p.width.unit==NEMO_ITERM_CELLS && !p.width.value);
    static const char *bad[]={"width=4294967296","width=-1","width=1.5", "height=", "width=12pxjunk","height=nan","inline=2","preserveAspectRatio=no"};
    for (size_t i=0;i<sizeof(bad)/sizeof(*bad);i++) {
        file(s,"inline=1;");feed(s,bad[i]);
        assert(!nemo_iterm_feed(s,":",1));
        assert(nemo_iterm_status(s)==NEMO_ITERM_MALFORMED);
    }
    assert(nemo_iterm_begin(s,NEMO_ITERM_FILE));
    assert(!nemo_iterm_feed(s,"name=foo:",9));
    assert(nemo_iterm_status(s)==NEMO_ITERM_NOT_INLINE);
    assert(nemo_iterm_begin(s,NEMO_ITERM_FILE));
    assert(!nemo_iterm_feed(s,"inline=0:",9));
    assert(nemo_iterm_status(s)==NEMO_ITERM_NOT_INLINE);
}

static void multipart(NemoIterm *s)
{
    for (unsigned chunk=1;chunk<=8;chunk++) {
        assert(nemo_iterm_begin(s,NEMO_ITERM_MULTIPART));
        feed(s,"inline=1;width=8;height=6px");
        assert(!nemo_iterm_finish(s,NULL) && nemo_iterm_status(s)==NEMO_ITERM_OK);
        const char *payload="Zm9vYmFyAP8=";size_t length=strlen(payload);
        for (size_t at=0;at<length;at+=chunk) {
            assert(nemo_iterm_begin(s,NEMO_ITERM_PART));
            size_t n=length-at;if(n>chunk)n=chunk;
            assert(nemo_iterm_feed(s,payload+at,n));
            assert(!nemo_iterm_finish(s,NULL) && nemo_iterm_status(s)==NEMO_ITERM_OK);
        }
        assert(nemo_iterm_begin(s,NEMO_ITERM_PART));
        assert(nemo_iterm_feed(s,NULL,0));
        assert(!nemo_iterm_finish(s,NULL));
        assert(nemo_iterm_begin(s,NEMO_ITERM_END));
        assert(nemo_iterm_feed(s,NULL,0));
        const unsigned char data[]={'f','o','o','b','a','r',0,255};
        equal(s,data,sizeof(data));
        assert(!nemo_iterm_begin(s,NEMO_ITERM_END));
    }
    assert(nemo_iterm_begin(s,NEMO_ITERM_MULTIPART));feed(s,"inline=1");
    assert(!nemo_iterm_begin(s,NEMO_ITERM_PART));
    assert(nemo_iterm_status(s)==NEMO_ITERM_MALFORMED);
    file(s,"inline=1:YWJj");
    nemo_iterm_cancel(s);
    assert(!nemo_iterm_finish(s,NULL));
    assert(!nemo_iterm_begin(s,NEMO_ITERM_PART));
    file(s,"inline=1:YWJj");
    file(s,"inline=1:Zg==");equal(s,"f",1);
}

static void malformed(NemoIterm *s)
{
    static const char *bad[]={"A","=AAA","A=AA","AA=A","Zg=","Zh==","Zm9=","Zg==A","AA!A","AA AA","AA\nAA",""};
    for(size_t i=0;i<sizeof(bad)/sizeof(*bad);i++) {
        file(s,"inline=1:");
        (void)nemo_iterm_feed(s,bad[i],strlen(bad[i]));
        assert(!nemo_iterm_finish(s,NULL));
        assert(nemo_iterm_status(s)==NEMO_ITERM_MALFORMED);
        file(s,"inline=1:YWJj");equal(s,"abc",3);
    }
    file(s,"inline=1");assert(!nemo_iterm_finish(s,NULL));
    assert(nemo_iterm_status(s)==NEMO_ITERM_MALFORMED);
    file(s,"inline=1:");assert(!nemo_iterm_feed(s,NULL,1));
    assert(nemo_iterm_status(s)==NEMO_ITERM_MALFORMED);
    assert(!nemo_iterm_begin(s,(NemoItermCommand)123));
}

typedef struct Guard {size_t limit, peak, calls;} Guard;
static bool admit(void *ctx,size_t current,size_t extra)
{
    Guard *g=ctx;g->calls++;
    assert(current <= SIZE_MAX-extra);
    if(current+extra > g->limit)return false;
    if(current+extra > g->peak)g->peak=current+extra;
    return true;
}

static void limits(NemoIterm *s)
{
    nemo_iterm_cancel(s);size_t base=nemo_iterm_memory(s);
    assert(!nemo_iterm_new(base-1,NULL,NULL));
    Guard g={0,0,0};assert(!nemo_iterm_new(BUDGET,admit,&g) && g.calls==1);
    g=(Guard){BUDGET,0,0};NemoIterm *owned=nemo_iterm_new(BUDGET,admit,&g);assert(owned);
    file(owned,"inline=1:");
    char block[4096];memset(block,'A',sizeof(block));
    for(unsigned i=0;i<4;i++)assert(nemo_iterm_feed(owned,block,sizeof(block)));
    assert(g.peak==base+8192+16384); /* includes old buffer during growth */
    g.limit=base+16384;
    for(unsigned i=0;nemo_iterm_status(owned)==NEMO_ITERM_OK && i<8;i++)
        (void)nemo_iterm_feed(owned,block,sizeof(block));
    assert(nemo_iterm_status(owned)==NEMO_ITERM_LIMIT && nemo_iterm_memory(owned)==base);
    nemo_iterm_free(owned);

    file(s,"inline=1;name=");
    size_t prefix=strlen("inline=1;name=");
    for(size_t i=prefix;i<NEMO_ITERM_HEADER_MAX;i++)feed(s,"x");
    feed(s,":YWJj");equal(s,"abc",3);
    file(s,"inline=1;name=");
    for(size_t i=prefix;i<NEMO_ITERM_HEADER_MAX;i++)feed(s,"x");
    assert(!nemo_iterm_feed(s,"x",1) && nemo_iterm_status(s)==NEMO_ITERM_LIMIT);

    assert(nemo_iterm_begin(s,NEMO_ITERM_MULTIPART));feed(s,"inline=1");
    assert(!nemo_iterm_finish(s,NULL));assert(nemo_iterm_begin(s,NEMO_ITERM_PART));
    for(size_t i=0;i<NEMO_ITERM_PART_MAX/sizeof(block);i++)
        assert(nemo_iterm_feed(s,block,sizeof(block)));
    assert(!nemo_iterm_feed(s,"A",1) && nemo_iterm_status(s)==NEMO_ITERM_LIMIT);
    assert(nemo_iterm_memory(s)==base);

    file(s,"inline=1:");
    for(size_t i=0;i<NEMO_ITERM_FILE_MAX/3;i++)feed(s,"AAAA");
    feed(s,"AAA=");
    NemoItermPacket packet;
    assert(nemo_iterm_finish(s,&packet) && packet.length==NEMO_ITERM_FILE_MAX);
    for(size_t i=0;i<packet.length;i++)assert(!packet.data[i]);
    file(s,"inline=1:");
    for(size_t i=0;i<NEMO_ITERM_FILE_MAX/3;i++)feed(s,"AAAA");
    assert(!nemo_iterm_feed(s,"AAAA",4) && nemo_iterm_status(s)==NEMO_ITERM_LIMIT);
    assert(nemo_iterm_memory(s)==base);
}

static void fuzz(NemoIterm *s)
{
    uint32_t rng=0x5e12b38;
    const char alphabet[]="ABCZabcz019+/=:;inlinewidthpxauto%01234";
    for(unsigned i=0;i<200000;i++) {
        rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;
        switch(rng & 31) {
          case 0: (void)nemo_iterm_begin(s,NEMO_ITERM_FILE);break;
          case 1: (void)nemo_iterm_begin(s,NEMO_ITERM_MULTIPART);break;
          case 2: (void)nemo_iterm_begin(s,NEMO_ITERM_PART);break;
          case 3: (void)nemo_iterm_begin(s,NEMO_ITERM_END);break;
          case 4: nemo_iterm_cancel(s);break;
          case 5: {
            NemoItermPacket p;
            if(nemo_iterm_finish(s,&p)) {
                assert(p.data && p.length && p.length<=NEMO_ITERM_FILE_MAX);
                assert(nemo_iterm_status(s)==NEMO_ITERM_OK);
            }
            break;
          }
          default: {
            unsigned char c=(rng & 64) ? alphabet[(rng>>8)%(sizeof(alphabet)-1)] : (unsigned char)(rng>>16);
            (void)nemo_iterm_feed(s,&c,1);break;
          }
        }
        assert(nemo_iterm_memory(s)<=BUDGET);
    }
}

static void layout(void)
{
    NemoItermPacket p = {0};
    p.preserve_aspect = true;
    unsigned w = 0, h = 0;
#define SIZE(nw,nh,ew,eh) do { \
    assert(nemo_iterm_size(&p,nw,nh,8,16,80,24,8192,&w,&h)); \
    assert(w == ew && h == eh); } while (0)
    SIZE(20,10,20,10);
    SIZE(1280,320,640,160);
    p.width = (NemoItermDimension){NEMO_ITERM_CELLS,2};
    SIZE(2,4,16,32);
    p.width = (NemoItermDimension){NEMO_ITERM_AUTO,0};
    p.height = (NemoItermDimension){NEMO_ITERM_PERCENT,50};
    SIZE(2,4,96,192);
    p.width = (NemoItermDimension){NEMO_ITERM_PIXELS,4};
    p.height = (NemoItermDimension){NEMO_ITERM_PIXELS,6};
    SIZE(2,2,4,4);
    p.preserve_aspect = false;
    SIZE(2,2,4,6);
    p.width = (NemoItermDimension){NEMO_ITERM_PERCENT,10};
    p.height = (NemoItermDimension){NEMO_ITERM_PERCENT,25};
    SIZE(2,2,64,96);
    p.width.value = 0;
    assert(!nemo_iterm_size(&p,2,2,8,16,80,24,8192,&w,&h));
    p.width.value = UINT32_MAX;
    assert(!nemo_iterm_size(&p,2,2,UINT32_MAX,16,UINT32_MAX,24,8192,&w,&h));
    p.width = (NemoItermDimension){NEMO_ITERM_PIXELS,1};
    p.height = (NemoItermDimension){NEMO_ITERM_AUTO,0};
    SIZE(8192,1,1,1);
    assert(!nemo_iterm_size(&p,0,2,8,16,80,24,8192,&w,&h));
#undef SIZE
}

int main(void)
{
    NemoIterm *s=nemo_iterm_new(BUDGET,NULL,NULL);assert(s);
    vectors(s);metadata(s);multipart(s);malformed(s);limits(s);fuzz(s);layout();
    nemo_iterm_free(s);
    puts("iTerm transport suite passed");return 0;
}
