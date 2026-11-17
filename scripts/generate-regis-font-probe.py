"""Extract only pinned upstream Xft font operations for a hosted input fixture.

This probe cannot read a reference screenshot, terminal stream or Nemoterm
decoder. Its output is the platform-dependent glyph input to the parser, not
an expected final image. Original comparison PNGs and streams stay unchanged.
"""
import argparse
import hashlib
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
source = Path('vendor/xterm-regis/graphics_regis.c').read_bytes()
assert hashlib.sha256(source).hexdigest() == 'a14512193dccdf25fb230da82698ceb7b522c45dc6fd892842dfcbb026af8109'
text = source.decode()
begin = text.index('#if OPT_RENDERFONT && defined(HAVE_TYPE_FCCHAR32)')
end = text.index('static unsigned\nfind_best_alphabet_index', begin)
license = text[:text.index('#include')]
preamble = r'''
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xft/Xft.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define OPT_RENDERFONT 1
#define HAVE_TYPE_FCCHAR32 1
#define XRENDERFONT 1
#define REGIS_FONTNAME_LEN 256
#define TRACE(args) ((void)0)
#define TypeMallocN(type, n) ((type *)malloc(sizeof(type)*(n)))
#define CharOf(ch) ((unsigned char)(ch))
#define CopyFontname(dst, src) snprintf(dst, sizeof(dst), "%s", src)
#define XtDisplay(xw) ((xw)->display)
#define XtScreen(xw) ((xw)->screen)
#define getVisualDepth(xw) DefaultDepthOfScreen((xw)->screen)
#define maybeXftCache(xw, font) ((void)0)
typedef unsigned char Char;
typedef struct ProbeWidget { Display *display; Screen *screen; XVisualInfo *visInfo; } *XtermWidget;
typedef struct { XtermWidget xw; } Graphic;
typedef struct { Graphic *destination_graphic; } RegisGraphicsContext;
'''
main = r'''
int main(void)
{
    const char *actions = getenv("GITHUB_ACTIONS"), *hosted = getenv("RUNNER_ENVIRONMENT");
    if (!actions || strcmp(actions,"true") || !hosted || strcmp(hosted,"github-hosted"))
        return 2;
    Display *display = XOpenDisplay(NULL);
    if (!display) return 3;
    XVisualInfo visual = {0}; visual.visual = DefaultVisual(display, DefaultScreen(display));
    struct ProbeWidget widget =
        {display, DefaultScreenOfDisplay(display), &visual};
    Graphic graphic = {&widget};
    RegisGraphicsContext context = {&graphic};
    const unsigned sizes[][2] = {{8,10},{8,20},{16,30},{24,45},{32,60}};
    fputs("NREGF1\n", stdout);
    for (size_t i=0; i<sizeof(sizes)/sizeof(sizes[0]); i++) {
        unsigned width=0,height=0; Char pixels[8192];
        if (!get_xft_bitmap_of_character(&context,"",'A',sizes[i][0],sizes[i][1],
                                         pixels,sizeof(pixels),&width,&height) || !width || !height)
            return 4;
        printf("F %u %u 8192 %u %u\n",sizes[i][0],sizes[i][1],width,height);
        for (unsigned ch=0;ch<256;ch++) {
            unsigned w=0,h=0;
            if (!get_xft_bitmap_of_character(&context,"",(int)ch,sizes[i][0],sizes[i][1],
                                             pixels,sizeof(pixels),&w,&h) || w!=width || h!=height)
                return 5;
            if (fwrite(pixels,1,w*h,stdout)!=w*h) return 6;
        }
    }
    for (unsigned i=0;i<FONT_SIZE_CACHE_SIZE;i++) {
        if (!font_cache[i].font_data) continue;
        FcChar8 *file=NULL; char pattern[2048];
        if (XftNameUnparse(font_cache[i].font_data->pattern,pattern,sizeof(pattern)))
            fprintf(stderr,"font-pattern: %s\n",pattern);
        if (FcPatternGetString(font_cache[i].font_data->pattern,FC_FILE,0,&file)==FcResultMatch)
            fprintf(stderr,"font-file: %s\n",file);
        close_xft_font(&widget,font_cache[i].font_data);
    }
    XCloseDisplay(display);
    return ferror(stdout) ? 7 : 0;
}
'''
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(license+preamble+text[begin:end]+main, encoding='utf-8', newline='\n')
