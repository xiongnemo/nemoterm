/* SPDX-License-Identifier: MIT */
#include "nemo_kitty_layout.h"
#include <stdio.h>
#include <string.h>
/* Keep checks active even in a release build. */
static unsigned checks;
#define CHECK(x) do { checks++; if (!(x)) { \
    fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x); return 1; } } while (0)

typedef struct Reference {
    const char *name, *header;
    uint32_t width, height;
    int32_t column, row;
    uint32_t cursor_column, cursor_row;
    double dest[4], source[4];
} Reference;
#include "kitty_layout_reference.h"

static bool parse(const char *header, NemoKittyCommand *command)
{
    NemoKitty *s=nemo_kitty_new(4u*1024u*1024u,NULL,NULL);
    NemoKittyPacket packet={0};
    bool ok=s && nemo_kitty_begin(s) && nemo_kitty_feed(s,header,strlen(header)) &&
        nemo_kitty_finish(s,&packet)==NEMO_KITTY_PACKET;
    if (ok) *command=packet.command;
    nemo_kitty_free(s);return ok;
}
static bool close_to(double a,double b) { return a-b<0.00002 && a-b> -0.00002; }

int main(void)
{
    NemoKittyCommand command;
    NemoKittyLayout g, sentinel;
    unsigned i;
    for (i=0;i<sizeof(references)/sizeof(*references);i++) {
        const Reference *r=references+i;
        uint64_t x,y;
        CHECK(parse(r->header,&command));
        CHECK(nemo_kitty_layout(&command,r->width,r->height,r->column,r->row,10,20,&g)==NEMO_KITTY_LAYOUT_OK);
        CHECK(close_to(g.left,r->dest[0]) && close_to(g.top,r->dest[1]) &&
              close_to(g.right,r->dest[2]) && close_to(g.bottom,r->dest[3]));
        CHECK(close_to((double)g.source_x/r->width,r->source[0]));
        CHECK(close_to((double)g.source_y/r->height,r->source[1]));
        CHECK(close_to((double)(g.source_x+g.source_width)/r->width,r->source[2]));
        CHECK(close_to((double)(g.source_y+g.source_height)/r->height,r->source[3]));
        /* Convert the deltas to the captured screen's basic right-edge wrap.
         * This is comparison bookkeeping, not a Nemoterm terminal integration
         * or evidence of scrolling/margins/alternate-screen behavior. */
        x=(uint64_t)r->column+g.advance_columns;y=(uint64_t)r->row+g.advance_rows;
        if (x>=12) {x=0;y++;}
        CHECK(x==r->cursor_column && y==r->cursor_row);
        printf("Pinned kitty geometry matched: %s\n",r->name);
    }
    CHECK(parse("a=p,x=19,y=29,w=4294967295,h=4294967295,X=4294967295,Y=4294967295,z=-2147483648",&command));
    CHECK(nemo_kitty_layout(&command,20,30,-4,-3,10,20,&g)==NEMO_KITTY_LAYOUT_OK);
    CHECK(g.source_width==1 && g.source_height==1 && g.offset_x==9 && g.offset_y==19);
    CHECK(g.z==INT32_MIN && g.left==-31 && g.top==-41 && g.right==-30 && g.bottom==-40);
    CHECK(g.advance_columns==1 && g.advance_rows==0);
    /* Same immutable command re-evaluates geometry against changed font cells. */
    CHECK(parse("a=p,c=3,r=2,X=3,Y=5",&command));
    CHECK(nemo_kitty_layout(&command,40,20,1,1,20,40,&g)==NEMO_KITTY_LAYOUT_OK);
    CHECK(g.left==23 && g.top==45 && g.right==80 && g.bottom==120);
    memset(&sentinel,0xa5,sizeof(sentinel));
    {
        const char *headers[]={"a=p,x=20","a=p,y=30","a=p,C=2","a=p,U=1",
            "a=p,P=1","a=p,Q=1","a=p,H=-1","a=p,V=1","a=p,c=4294967295"};
        const NemoKittyLayoutStatus status[]={NEMO_KITTY_LAYOUT_INVALID,NEMO_KITTY_LAYOUT_INVALID,
            NEMO_KITTY_LAYOUT_INVALID,NEMO_KITTY_LAYOUT_UNSUPPORTED,NEMO_KITTY_LAYOUT_UNSUPPORTED,
            NEMO_KITTY_LAYOUT_UNSUPPORTED,NEMO_KITTY_LAYOUT_UNSUPPORTED,NEMO_KITTY_LAYOUT_UNSUPPORTED,
            NEMO_KITTY_LAYOUT_LIMIT};
        for (i=0;i<sizeof(headers)/sizeof(*headers);i++) {
            CHECK(parse(headers[i],&command));g=sentinel;
            CHECK(nemo_kitty_layout(&command,20,30,0,0,8192,1,&g)==status[i]);
            CHECK(!memcmp(&g,&sentinel,sizeof(g)));
        }
    }
    CHECK(parse("a=p",&command));g=sentinel;
    CHECK(nemo_kitty_layout(&command,0,30,0,0,10,20,&g)==NEMO_KITTY_LAYOUT_INVALID);
    CHECK(nemo_kitty_layout(&command,20,30,0,0,0,20,&g)==NEMO_KITTY_LAYOUT_INVALID);
    CHECK(nemo_kitty_layout(&command,20,30,0,0,10,0,&g)==NEMO_KITTY_LAYOUT_INVALID);
    CHECK(nemo_kitty_layout(NULL,20,30,0,0,10,20,&g)==NEMO_KITTY_LAYOUT_INVALID);
    CHECK(nemo_kitty_layout(&command,20,30,0,0,10,20,NULL)==NEMO_KITTY_LAYOUT_INVALID);
    CHECK(nemo_kitty_layout(&command,8193,30,0,0,10,20,&g)==NEMO_KITTY_LAYOUT_LIMIT);
    CHECK(nemo_kitty_layout(&command,20,8193,0,0,10,20,&g)==NEMO_KITTY_LAYOUT_LIMIT);
    CHECK(nemo_kitty_layout(&command,20,30,0,0,8193,20,&g)==NEMO_KITTY_LAYOUT_LIMIT);
    CHECK(nemo_kitty_layout(&command,20,30,0,0,10,8193,&g)==NEMO_KITTY_LAYOUT_LIMIT);
    CHECK(!memcmp(&g,&sentinel,sizeof(g)));
    CHECK(nemo_kitty_layout(&command,8192,8192,INT32_MIN,INT32_MAX,1,1,&g)==NEMO_KITTY_LAYOUT_OK);
    CHECK(g.advance_columns==8192 && g.advance_rows==8191);
    CHECK(g.left==INT32_MIN && g.top==INT32_MAX && g.right>g.left && g.bottom>g.top);
    printf("Kitty ordinary layout: %u checks passed\n",checks);
    return 0;
}
