/* SPDX-License-Identifier: MIT */
#include "nemo_charset.h"
#include <string.h>
#include "nemo_charset_data.h"

enum { DIRECT, BRITISH, TABLE, UPSS, LINE };
#define ROW(text,table,minimum,maximum,nrc,sized,kind) \
    {text,table,minimum,maximum,kind,nrc,sized}
#define NRC(text,name,minimum) ROW(text,charset_NRCS_##name,minimum,5,true,false,TABLE)
#define DEC(text,name,minimum) ROW(text,charset_DEC_##name,minimum,5,false,false,TABLE)
#define ISO(text,name) ROW(text,charset_ISO_##name,5,5,false,true,TABLE)
static const NemoCharset charsets[] = {
    ROW("B",NULL,1,5,false,false,DIRECT),
    ROW("A",NULL,1,5,false,false,BRITISH),
    ROW("0",charset_DEC_Spec_Graphic,1,5,false,false,LINE),
    ROW("1",NULL,1,1,false,false,DIRECT),
    ROW("2",charset_DEC_Spec_Graphic,1,1,false,false,LINE),
    ROW("<",charset_DEC_Supp_Graphic,2,2,false,false,TABLE),
    NRC("4",Dutch,2), NRC("5",Finnish,2), NRC("C",Finnish,2),
    NRC("R",French,2), NRC("f",French,2), NRC("Q",French_Canadian,2),
    NRC("K",German,2), NRC("Y",Italian,2), NRC("E",Norwegian_Danish,2),
    NRC("6",Norwegian_Danish,2), NRC("Z",Spanish,2), NRC("7",Swedish,2),
    NRC("H",Swedish,2), NRC("=",Swiss,2),
    /* UPSS is initially Latin-1; assigning another UPSS belongs to the parser. */
    ROW("<",NULL,3,5,false,true,UPSS),
    ROW("A",NULL,3,5,true,false,BRITISH),
    DEC("%5",Supp_Graphic,3), DEC(">",Technical,3),
    NRC("9",French_Canadian,3), NRC("`",Norwegian_Danish,3), NRC("%6",Portuguese,3),
    ROW("A",NULL,3,5,false,true,DIRECT),
    ROW("I",charset_JIS_Katakana,3,3,false,false,TABLE),
    ROW("J",charset_JIS_Roman,3,3,false,false,TABLE),
    NRC("\">",Greek,5), NRC("%=",Hebrew,5), NRC("&5",Russian,5),
    NRC("%3",Serbo_Croatian,5), NRC("%2",Turkish,5),
    DEC("&4",Cyrillic,5), DEC("\"?",Greek_Supp,5),
    DEC("\"4",Hebrew_Supp,5), DEC("%0",Turkish_Supp,5),
    ISO("F",Greek_Supp), ISO("H",Hebrew), ISO("B",Latin_2),
    ISO("M",Latin_5), ISO("L",Latin_Cyrillic),
};
#undef ISO
#undef DEC
#undef NRC
#undef ROW

unsigned nemo_charset_id(const NemoCharset *charset)
{
    for (unsigned i=0; i<sizeof(charsets)/sizeof(*charsets); i++)
        if (charset == &charsets[i]) return i+1;
    return 0;
}

const NemoCharset *nemo_charset_by_id(unsigned id)
{
    return id && id<=sizeof(charsets)/sizeof(*charsets) ? &charsets[id-1] : NULL;
}

const NemoCharset *nemo_charset_designate(unsigned group, unsigned level,
    bool national, const char *designation, size_t length)
{
    if ((group!=1 && group!=3) || level<1 || level>5 || !designation ||
        length<1 || length>2) return NULL;
    for (size_t i=0;i<sizeof(charsets)/sizeof(*charsets);i++) {
        const NemoCharset *entry=&charsets[i];
        if (group<=entry->minimum_level && level>=entry->minimum_level &&
            level<=entry->maximum_level && (!entry->national || national) &&
            strlen(entry->designation)==length && !memcmp(entry->designation,designation,length))
            return entry;
    }
    return NULL;
}

uint32_t nemo_charset_map(const NemoCharset *charset, unsigned byte,
                         unsigned level, bool national)
{
    if (!charset || byte>255 || byte<0x20 || (byte>=0x80 && byte<0xa0))
        return NEMO_CHARSET_NOCHAR;
    unsigned seven=byte&0x7f;
    if (!charset->size96 && byte==0x7f) return NEMO_CHARSET_NOCHAR;
    if (!charset->size96 && byte==0x20) return 0x20;
    uint32_t result=byte;
    if (charset->kind==TABLE) {
        result=charset->mapping[seven-0x20];
        if (result==UINT16_MAX) result=byte;
    } else if (charset->kind==LINE) {
        result=seven>=0x60 && seven<=0x7e ? charset->mapping[seven-0x20] :
            byte==0x5f ? 0 : seven;
    }
    else if (charset->kind==BRITISH && (national || level==1)) {
        result=national ? seven : byte;
        if (result==0x23) result=0x00a3;
    }
    if (!charset->size96 && result==0x7f) return NEMO_CHARSET_NOCHAR;
    if (byte>=0x80 && result>0x20 && result<0x80) result|=0x80;
    return result;
}

unsigned nemo_charset_input(const NemoCharset *charset, uint32_t scalar,
                            bool unicode_nrc)
{
    if (charset) {
        if (charset->kind==BRITISH && charset->minimum_level==1 && scalar==0xa3)
            return 0x23;
        /* French-Canadian alias 9 and DEC line graphics have no reverse
         * conversion in XTerm; the latter is not a national input layout. */
        if (charset->kind==TABLE && strcmp(charset->designation,"9")) {
            for (size_t i=0;i<sizeof(charset_input_masks)/sizeof(*charset_input_masks);i++) {
                if (charset_input_masks[i].mapping!=charset->mapping) continue;
                for (unsigned p=0;p<96;p++) {
                    uint32_t bits=charset_input_masks[i].direct[p/32] |
                        (unicode_nrc ? charset_input_masks[i].unicode[p/32] : 0);
                    if ((bits & (UINT32_C(1)<<(p%32))) && charset->mapping[p]==scalar)
                        return p+0x20;
                }
                break;
            }
        }
    }
    return scalar & 0x7f;
}
