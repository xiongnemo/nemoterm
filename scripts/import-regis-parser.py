"""Generate the native parser adaptation from retained, pinned XTerm sources.

This is source generation, not a runtime test. The generated parser remains a
component until terminal ownership, rendering and native replay are connected.
"""
from pathlib import Path
import hashlib
import re

root = Path(__file__).resolve().parents[1]
source = root/'vendor/xterm-regis'
target = root/'vendor/putty-0.85/terminal'
text = (source/'graphics_regis.c').read_text()

def replace(old, new, count=1):
    global text
    actual = text.count(old)
    if actual != count:
        raise ValueError(f'Expected {count} occurrences, got {actual}: {old[:70]}')
    text = text.replace(old,new)

text = re.sub(r'^#include [^\n]+\n', '', text, flags=re.M)
replace('static RegisGraphicsContext persistent_context;\nstatic RegisParseState persistent_state;',
        '#include "nemo_regis_runtime.inc"')
replace('    char const  *start;\n', '    NemoRegis   *owner;\n    char const  *start;\n')
replace('static RegisGraphicsContext *global_context;\n','')
text = text.replace('global_context','context')
text = re.sub(r'^\s*context = context;[^\n]*\n','\n',text,flags=re.M)
for name in ('setPixel','plotLine','plotQuadBezierSeg','plotQuadBezier',
             'plotCubicBezierSeg','plotCubicBezier','plotQuadSpline','plotCubicSpline'):
    text = re.sub(r'\b'+name+r'\(', name+'(context, ',text)
    text = re.sub(r'\n'+name+r'\(context, ',
                  '\n'+name+'(RegisGraphicsContext *context, ',text)
# All X11 font loading is replaced by a caller-owned native bitmap callback.
start = text.index('#if OPT_RENDERFONT && defined(HAVE_TYPE_FCCHAR32)')
end = text.index('static unsigned\nfind_best_alphabet_index',start)
text = text[:start]+'''static int
get_xft_bitmap_of_character(RegisGraphicsContext const *context,
    char const *fontname, int ch, unsigned maxw, unsigned maxh, Char *pixels,
    unsigned max_pixels, unsigned *w, unsigned *h)
{
    NemoRegis *owner = context->current_widget;
    return owner->config.glyph && owner->config.glyph(owner->config.user,
        fontname, (unsigned char) ch, maxw, maxh, pixels, max_pixels, w, h);
}

'''+text[end:]
replace('init_fragment(RegisDataFragment *fragment, char const *str)',
        'init_fragment(RegisDataFragment *fragment, NemoRegis *owner, char const *str)')
replace('    fragment->start = str;', '    fragment->owner = owner;\n    fragment->start = str;')
replace('    dst->start = src->start;', '    dst->owner = src->owner;\n    dst->start = src->start;')
replace('    output->start = &input->start[input->pos];',
        '    output->owner = input->owner;\n    output->start = &input->start[input->pos];',5)
replace('    static char tempstr[MAX_FRAG];','    char *tempstr = fragment->owner->tempstr;')
replace('    *out = atoi(fragment_to_tempstr(input));', '''    char *end;
    errno = 0;
    long number = strtol(fragment_to_tempstr(input), &end, 10);
    if (errno || number < -32768 || number > 32767)
        regis_abort(input->owner, NEMO_REGIS_LIMIT);
    *out = (int) number;''')
replace('    whole = strtoul(num, &end, 10);','''    errno = 0;
    whole = strtoul(num, &end, 10);
    if (errno || whole > 32767 || scale < 1 || scale > 1000)
        return 0;''')
# Windows long is 32 bits. Preserve the wider intermediates used on Linux.
text = re.sub(r'\blong\b','int64_t',text)
replace('    unsigned int64_t whole, frac;', '    uint64_t whole, frac;')
replace('\tcontext->alphabets[alphabet_index].bytes = NULL;',
        '\tregis_deallocate(context->alphabets[alphabet_index].bytes);\n\tcontext->alphabets[alphabet_index].bytes = NULL;')
text = text.replace('free(context->alphabets[', 'regis_deallocate(context->alphabets[')
replace('TypeCallocN(Char, (size_t) (MAX_GLYPHS * glyph_size))',
        'regis_allocate(context->current_widget, (size_t) MAX_GLYPHS * glyph_size)')
replace('usleep((useconds_t) delay * 10000U);',
        'regis_delay(context->current_widget, (unsigned) delay * 10U);')
# Bound parser recursion before descending; the outer request catches this.
replace('parse_regis_toplevel(RegisParseState *state, RegisGraphicsContext *context)\n{',
        'parse_regis_toplevel_inner(RegisParseState *state, RegisGraphicsContext *context)\n{')
start = text.index('void\nreset_regis(void)')
text = text[:start]+'''static int
parse_regis_toplevel(RegisParseState *state, RegisGraphicsContext *context)
{
    NemoRegis *owner = context->current_widget;
    regis_tick(owner);
    if (++owner->depth > 32) regis_abort(owner, NEMO_REGIS_LIMIT);
    int result = parse_regis_toplevel_inner(state, context);
    owner->depth--;
    return result;
}
'''
replace('static void get_bitmap_of_character(',
        'static int parse_regis_toplevel(RegisParseState *, RegisGraphicsContext *);\n\nstatic void get_bitmap_of_character(')
# A parser/pixel visit always consumes work, including clipped drawing.
replace('    if (fragment->pos < fragment->len) {',
        '    regis_tick(fragment->owner);\n    if (fragment->pos < fragment->len) {',2)
replace('draw_or_save_patterned_pixel(RegisGraphicsContext *context, int x, int y)\n{',
        'draw_or_save_patterned_pixel(RegisGraphicsContext *context, int x, int y)\n{\n    regis_tick(context->current_widget);')
replace('draw_regis_pixel(RegisGraphicsContext *context, int x, int y,\n\t\t unsigned value)\n{',
        'draw_regis_pixel(RegisGraphicsContext *context, int x, int y,\n\t\t unsigned value)\n{\n    regis_tick(context->current_widget);')
# Scan alphabet rows one byte at a time instead of architecture-sized shifts.
begin = text.index('\t\tunsigned unused_bits;')
end = text.index('\n\t\tstate->load_row++;',begin)
text = text[:begin]+'''        glyph = &context->alphabets[state->load_index]
            .bytes[state->load_glyph * glyph_size];
        bytew = GLYPH_WIDTH_BYTES(context->alphabets[state->load_index].pixw);
        for (byte = 0; byte < bytew; byte++) {
            unsigned result = 0;
            for (unsigned bit = 0; bit < 8; bit++) {
                unsigned pixel = byte * 8 + bit, nibble = pixel / 4;
                if (pixel < context->alphabets[state->load_index].pixw && nibble < digit) {
                    unsigned char ch = (unsigned char)state->temp[nibble];
                    unsigned value = ch <= '9' ? ch-'0' : (unsigned)tolower(ch)-'a'+10;
                    if (value & (8U >> (pixel & 3))) result |= 128U >> bit;
                }
            }
            glyph[state->load_row * bytew + byte] = (Char)result;
        }
'''+text[end:]
text = text.replace('unsigned int64_t val;', 'uint64_t val;')
# Include generated provenance and keep the upstream copyright intact.
header = '/* Generated by scripts/import-regis-parser.py.\n * Upstream SHA256: '+hashlib.sha256((source/'graphics_regis.c').read_bytes()).hexdigest()+'\n */\n'
(target/'nemo_regis_parser.inc').write_text(header+text,encoding='utf-8',newline='\n')
# Preserve upstream HLS conversion exactly, without its X11 display code.
graphics = (source/'graphics.c').read_text()
start = graphics.index('void\nhls2rgb(')
end = graphics.index('void\ndump_graphic(',start)
colour = graphics[start:end].replace('void\n','static void\n')
(target/'nemo_regis_colour.inc').write_text(graphics[:graphics.index('#include')]+
    '\n#define MAX_PCT 100.\n#define MAX_RGB 100.\n'+colour,encoding='utf-8',newline='\n')
print('Generated native ReGIS parser and colour adapters from pinned source.')
