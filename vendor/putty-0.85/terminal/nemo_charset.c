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
    /* The parser owns UPSS and resolves this placeholder at invocation. */
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

const NemoCharset *nemo_charset_preferred(unsigned parameter,
    const char *designation, size_t length)
{
    static const struct { unsigned parameter; const char *input, *output; } allowed[] = {
        {0,"%5","%5"}, {0,"A","B"}, {0,"0","0"}, {0,">",">"},
        {0,"\"?","\"?"}, {0,"\"4","\"4"}, {0,"%0","%0"}, {0,"&4","&4"},
        {1,"A","A"}, {1,"B","B"}, {1,"F","F"}, {1,"H","H"},
        {1,"M","M"}, {1,"L","L"},
    };
    if (!designation || !length || length>2) return NULL;
    for (size_t i=0;i<sizeof(allowed)/sizeof(*allowed);i++) {
        const char *name=allowed[i].input;
        size_t n=strlen(name);
        /* XTerm also accepts the final alone, first match winning. */
        if (parameter==allowed[i].parameter &&
            (length==1 ? designation[0]==name[n-1] :
             n==length && !memcmp(name,designation,length)))
            return nemo_charset_designate(parameter ? 3 : 1,5,false,
                allowed[i].output,strlen(allowed[i].output));
    }
    return NULL;
}

const NemoCharset *nemo_charset_resolve(const NemoCharset *charset,
    unsigned preferred_id, unsigned level)
{
    if (!charset || charset->kind!=UPSS) return charset;
    const NemoCharset *preferred=nemo_charset_by_id(preferred_id);
    if (level<2 || !preferred || preferred->kind==UPSS)
        return nemo_charset_designate(1,5,false,"B",1);
    if (level>=3 && level<5 &&
        !(preferred->kind==TABLE && preferred->minimum_level==2 &&
          !strcmp(preferred->designation,"<")))
        return nemo_charset_designate(3,5,false,"A",1);
    return preferred;
}

uint32_t nemo_charset_map(const NemoCharset *charset, unsigned byte,
                         unsigned level, bool national)
{
    return nemo_charset_map_mode(charset, byte, level, national, true);
}

uint32_t nemo_charset_map_mode(const NemoCharset *charset, unsigned byte,
                              unsigned level, bool national, bool unicode_nrc)
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
        else if (!unicode_nrc) {
            for (size_t i=0;i<sizeof(charset_input_masks)/sizeof(*charset_input_masks);i++) {
                if (charset_input_masks[i].mapping!=charset->mapping) continue;
                unsigned p=seven-0x20;
                if (!(charset_input_masks[i].direct[p/32] & (UINT32_C(1)<<(p%32)))) result=seven;
                break;
            }
        }
    } else if (charset->kind==LINE) {
        result=seven>=0x60 && seven<=0x7e ? charset->mapping[seven-0x20] :
            byte==0x5f ? 0 : seven;
    }
    else if ((charset->kind==BRITISH || (charset->kind==DIRECT && charset->size96)) &&
             (national || level==1)) {
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

unsigned nemo_charset_checksum(const NemoCharset *charset, unsigned byte)
{
    if (byte < 0x20 || byte > 0xff) return 0x1b;
    bool seven = !charset || !charset->size96;
    if (seven) {
        if (byte == 0xa0) return 0x1b;
        if (byte == 0x20) return 0x20;
        if (byte == 0x7f || byte == 0xff) return 0;
    }
    unsigned low = byte & 0x7f;
    if (charset && charset->kind == BRITISH)
        return low == 0x23 && charset->minimum_level == 1 ? 0xa3 : low;
    if (charset && charset->mapping) {
        for (size_t i=0; i<sizeof(charset_checksum_maps)/sizeof(*charset_checksum_maps); i++) {
            if (charset_checksum_maps[i].mapping != charset->mapping) continue;
            unsigned mapped = low >= 0x20 ? charset_checksum_maps[i].values[low-0x20] : 0xffff;
            if (mapped != 0xffff) return mapped;
            break;
        }
        if ((!charset->national && charset->minimum_level >= 3 &&
             charset->mapping != charset_DEC_Cyrillic &&
             charset->mapping != charset_JIS_Roman && charset->mapping != charset_JIS_Katakana) ||
            charset->mapping == charset_DEC_Supp_Graphic)
            return byte | 0x80;
    }
    return seven ? low : byte | 0x80;
}
