/* SPDX-License-Identifier: MIT
 * Test-only input adapter for separately captured, pinned upstream Xft glyphs.
 * This does not supply expected image output and is never linked to production.
 */
typedef struct RegisFontInput {
    unsigned maxw, maxh, capacity, width, height;
    unsigned char *pixels;
} RegisFontInput;
typedef struct RegisFontInputs {
    RegisFontInput entries[16];
    unsigned count, calls, misses;
} RegisFontInputs;

static void font_inputs_free(RegisFontInputs *inputs)
{
    for (unsigned i=0;i<inputs->count;i++) free(inputs->entries[i].pixels);
    inputs->count=0;
}

static bool font_inputs_load(RegisFontInputs *inputs, const char *path)
{
    FILE *file=fopen(path,"rb");
    if (!file) return false;
    char line[128];
    bool ok=fgets(line,sizeof(line),file) && !strcmp(line,"NREGF1\n");
    while (ok && fgets(line,sizeof(line),file)) {
        if (inputs->count==16) { ok=false; break; }
        RegisFontInput *e=&inputs->entries[inputs->count];
        if (sscanf(line,"F %u %u %u %u %u",&e->maxw,&e->maxh,&e->capacity,&e->width,&e->height)!=5 ||
            !e->width || !e->height || e->width>e->maxw || e->height>e->maxh ||
            e->capacity!=8192 || e->width>e->capacity/e->height) { ok=false; break; }
        size_t size=(size_t)e->width*e->height*256;
        e->pixels=malloc(size);
        if (!e->pixels) { ok=false; break; }
        inputs->count++;
        if (fread(e->pixels,1,size,file)!=size) { ok=false; break; }
        for (size_t i=0;i<size;i++)
            if (e->pixels[i]>1) { ok=false; break; }
    }
    ok=ok && !ferror(file) && inputs->count>0;
    fclose(file);
    if (!ok) font_inputs_free(inputs);
    return ok;
}

static bool font_input_glyph(RegisFontInputs *inputs, const char *font, unsigned ch,
                              unsigned maxw, unsigned maxh, unsigned char *pixels,
                              size_t capacity, unsigned *width, unsigned *height)
{
    inputs->calls++;
    if (!*font && ch<256) {
        for (unsigned i=0;i<inputs->count;i++) {
            RegisFontInput *e=&inputs->entries[i];
            if (maxw!=e->maxw || maxh!=e->maxh || capacity!=e->capacity) continue;
            size_t size=(size_t)e->width*e->height;
            memcpy(pixels,e->pixels+ch*size,size);
            *width=e->width; *height=e->height;
            return true;
        }
    }
    inputs->misses++;
    return false;
}
