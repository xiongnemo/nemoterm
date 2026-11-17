/* Independent X11 fixed-grid font input; no terminal parser or golden images. */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xatom.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc,char **argv)
{
    const char *actions=getenv("GITHUB_ACTIONS"),*hosted=getenv("RUNNER_ENVIRONMENT");
    if (!actions || strcmp(actions,"true") || !hosted || strcmp(hosted,"github-hosted") || argc!=2) return 2;
    Display *d=XOpenDisplay(NULL);
    if (!d) return 3;
    XFontStruct *font=XLoadQueryFont(d,"fixed");
    if (!font || font->max_bounds.width!=6 || font->ascent+font->descent!=13) return 4;
    XFontStruct *unicode=XLoadQueryFont(d,"-misc-fixed-medium-r-semicondensed--13-120-75-75-c-60-iso10646-1");
    if (!unicode || unicode->max_bounds.width!=6 || unicode->ascent+unicode->descent!=13) return 4;
    int screen=DefaultScreen(d);
    Pixmap surface=XCreatePixmap(d,RootWindow(d,screen),6,13,(unsigned)DefaultDepth(d,screen));
    GC gc=XCreateGC(d,surface,0,NULL);
    XSetFont(d,gc,font->fid);
    FILE *out=fopen(argv[1],"wb");
    if (!out) return 5;
    fwrite("NEMOFIX2",1,8,out);
    for (unsigned code=0;code<257;code++) {
        XSetForeground(d,gc,BlackPixel(d,screen)); XFillRectangle(d,surface,gc,0,0,6,13);
        XSetForeground(d,gc,WhitePixel(d,screen));
        if (code<256) {
            char byte=(char)code;
            XDrawString(d,surface,gc,0,font->ascent,&byte,1);
        } else {
            XChar2b sub={0x24,0x26};
            XSetFont(d,gc,unicode->fid);
            XDrawString16(d,surface,gc,0,unicode->ascent,&sub,1);
        }
        XImage *image=XGetImage(d,surface,0,0,6,13,AllPlanes,ZPixmap);
        if (!image) return 6;
        for (int y=0;y<13;y++) for (int x=0;x<6;x++)
            if (fputc(XGetPixel(image,x,y)==WhitePixel(d,screen),out)==EOF) return 7;
        XDestroyImage(image);
    }
    if (fclose(out)) return 8;
    unsigned long atom=0;
    if (XGetFontProperty(font,XA_FONT,&atom)) {
        char *name=XGetAtomName(d,(Atom)atom);
        if (name) { printf("fixed-font: %s\n",name); XFree(name); }
    }
    if (XGetFontProperty(unicode,XA_FONT,&atom)) {
        char *name=XGetAtomName(d,(Atom)atom);
        if (name) { printf("unicode-font: %s\n",name); XFree(name); }
    }
    printf("cell: 6x13 ascent=%d descent=%d codes=256 plus U+2426\n",font->ascent,font->descent);
    XFreeGC(d,gc); XFreePixmap(d,surface); XFreeFont(d,font); XFreeFont(d,unicode); XCloseDisplay(d);
    return 0;
}
