/* SPDX-License-Identifier: MIT */
#include "nemo_feature_policy.h"
#include <stdio.h>
#include <string.h>

typedef struct FeatureName { const char *name; unsigned code; } FeatureName;
static const FeatureName colors[]={{"SetColor",1},{"GetColor",2},{"GetAnsiColor",3}};
static const FeatureName fonts[]={{"SetFont",1},{"GetFont",2}};
static const FeatureName mouse[]={
    {"X10",1},{"Locator",2},{"VT200Click",3},{"VT200Hilite",4},
    {"AnyButton",5},{"AnyEvent",6},{"FocusEvent",7},{"Extended",8},
    {"SGR",9},{"URXVT",10},{"AlternateScroll",11}};
static const FeatureName paste[]={
    {"NUL",0},{"SOH",1},{"STX",2},{"ETX",3},{"EOT",4},{"ENQ",5},
    {"ACK",6},{"BEL",7},{"BS",8},{"HT",9},{"LF",10},{"VT",11},{"FF",12},
    {"CR",13},{"SO",14},{"SI",15},{"DLE",16},{"DC1",17},{"DC2",18},
    {"DC3",19},{"DC4",20},{"NAK",21},{"SYN",22},{"ETB",23},{"CAN",24},
    {"EM",25},{"SUB",26},{"ESC",27},{"FS",28},{"GS",29},{"RS",30},
    {"US",31},{"NL",10},{"C0",32},{"DEL",33},{"STTY",34}};
static const FeatureName tcap[]={{"SetTcap",1},{"GetTcap",2}};
static const FeatureName window[]={
    {"RestoreWin",1},{"MinimizeWin",2},{"SetWinPosition",3},{"SetWinSizePixels",4},
    {"RaiseWin",5},{"LowerWin",6},{"RefreshWin",7},{"SetWinSizeChars",8},
    {"MaximizeWin",9},{"FullscreenWin",10},{"GetWinState",11},{"GetWinPosition",13},
    {"GetWinSizePixels",14},{"GetWinSizeChars",18},{"GetScreenSizeChars",19},
    {"GetIconTitle",20},{"GetWinTitle",21},{"PushTitle",22},{"PopTitle",23},
    {"SetWinLines",24},{"ColumnMode",25},{"GetChecksum",29},{"SetChecksum",30},
    {"GetSelection",27},{"SetSelection",28},{"SetXprop",26},{"StatusLine",31}};

#define TABLE(a) a,sizeof(a)/sizeof(*(a))
static const struct {
    const char *name;
    const FeatureName *table;
    size_t count;
} categories[NEMO_FEATURE_COUNT]={
    {"allowColorOps",TABLE(colors)},{"allowFontOps",TABLE(fonts)},
    {"allowMouseOps",TABLE(mouse)},{"allowPasteControls",TABLE(paste)},
    {"allowTcapOps",TABLE(tcap)},{"allowTitleOps",NULL,0},
    {"allowWindowOps",TABLE(window)}};
#undef TABLE

static bool equal_name(const char *data, size_t length, const char *name)
{
    if (length!=strlen(name)) return false;
    for (size_t i=0;i<length;i++) {
        unsigned a=(unsigned char)data[i],b=(unsigned char)name[i];
        if (a>='A' && a<='Z') a+='a'-'A';
        if (b>='A' && b<='Z') b+='a'-'A';
        if (a!=b) return false;
    }
    return true;
}

static bool printable(const char *data,size_t length,bool utf8)
{
    for (size_t i=0;i<length;i++) {
        unsigned c=(unsigned char)data[i];
        if (c<32 || (c>=127 && c<160)) return false;
        if (!utf8 || c<128) continue;
        unsigned extra,minimum,value;
        if (c>=0xc2 && c<=0xdf) {extra=1;minimum=0x80;value=c&31;}
        else if (c>=0xe0 && c<=0xef) {extra=2;minimum=0x800;value=c&15;}
        else if (c>=0xf0 && c<=0xf4) {extra=3;minimum=0x10000;value=c&7;}
        else return false;
        if (extra>=length-i) return false;
        while (extra--) {
            c=(unsigned char)data[++i];
            if ((c&0xc0)!=0x80) return false;
            value=(value<<6)|(c&63);
        }
        if (value<minimum || value<0xa0 || value>0x10ffff ||
            (value>=0xd800 && value<=0xdfff)) return false;
    }
    return true;
}

static bool append(char *out,size_t capacity,size_t *used,const char *data,size_t length)
{
    if (*used>capacity || length>capacity-*used) return false;
    memcpy(out+*used,data,length);*used+=length;return true;
}

size_t nemo_feature_policy_reply(const NemoFeaturePolicy *policy,unsigned number,
    const char *payload,size_t length,bool utf8,bool bel,char *reply,size_t capacity)
{
    if (number<60 || number>62) return 0;
    /* XTerm's OSC argument decoder stops at a stored NUL. */
    const char *nul=length ? memchr(payload,0,length) : NULL;
    if (nul) length=(size_t)(nul-payload);
    if (!printable(payload,length,utf8) || (number==60 ? length!=0 : length==0)) return 0;
    char result[NEMO_FEATURE_POLICY_REPLY_MAX];size_t used=4;
    result[0]='\033';result[1]=']';result[2]='6';result[3]=(char)('0'+number-60);
    char separator=';';
#define ADD_NAME(name) do { \
    const char *value_=(name); \
    if (!append(result,sizeof(result),&used,&separator,1) || \
        !append(result,sizeof(result),&used,value_,strlen(value_))) return 0; \
    separator=','; \
} while (0)
    if (number==60) {
        for (unsigned i=0;i<NEMO_FEATURE_COUNT;i++)
            if (policy->enabled&(1u<<i)) ADD_NAME(categories[i].name);
    } else {
        int category=-1;
        for (unsigned i=0;i<NEMO_FEATURE_COUNT;i++)
            if (equal_name(payload,length,categories[i].name)) {category=(int)i;break;}
        if (equal_name(payload,length,"allowWinOps")) category=NEMO_FEATURE_WINDOW;
        if (category>=0) {
            const FeatureName *table=categories[category].table;
            size_t count=categories[category].count;
            uint64_t supported=policy->supported[category];
            if (number==62) {
                for (size_t i=0;i<count;i++)
                    if (supported&NEMO_FEATURE_BIT(table[i].code)) ADD_NAME(table[i].name);
            } else {
                uint64_t restricted=policy->restricted[category]&supported;
                for (unsigned bit=0;bit<64;bit++) {
                    if (!(restricted&NEMO_FEATURE_BIT(bit))) continue;
                    const char *name=NULL;char numeric[4];
                    for (size_t i=0;i<count;i++)
                        if (table[i].code==bit) {name=table[i].name;break;}
                    if (!name) {snprintf(numeric,sizeof(numeric),"%u",bit);name=numeric;}
                    ADD_NAME(name);
                }
            }
        }
    }
#undef ADD_NAME
    if (!append(result,sizeof(result),&used,bel?"\007":"\033\\",bel?1:2) || used>capacity) return 0;
    memcpy(reply,result,used);return used;
}
