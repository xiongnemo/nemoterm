/* $XTermId: graphics.c,v 1.142 2026/10/11 10:00:04 tom Exp $ */

/*
 * Copyright 2013-2025,2026 by Thomas E. Dickey
 * Copyright 2013-2022,2023 by Ross Combs
 *
 *                         All Rights Reserved
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice shall be included
 * in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 * OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE ABOVE LISTED COPYRIGHT HOLDER(S) BE LIABLE FOR ANY
 * CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 * TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * Except as contained in this notice, the name(s) of the above copyright
 * holders shall not be used in advertising or otherwise to promote the
 * sale, use or other dealings in this Software without prior written
 * authorization.
 */


#define MAX_PCT 100.
#define MAX_RGB 100.
static void
hls2rgb(int h, int l, int s, short *r, short *g, short *b)
{
    int hs;
    const double lv = l / MAX_PCT;	/* scale to [0..1] */
    const double sv = s / MAX_PCT;	/* scale to [0..1] */
    double c, x, m, c2;
    double r1, g1, b1;

    if (s == 0) {		/* the achromatic case */
	*r = *g = *b = (short) l;
	return;
    }

    h = h - 120;		/* Rotate so that blue is at 0 degrees  */
    while (h < 0)
	h += 360;		/* Normalize to [0..360) */
    while (h >= 360)
	h -= 360;

    hs = (h % 120) - 60;	/* compute abs((h % 120) - 60) */
    if (hs < 0)
	hs = -hs;

    c2 = (2.0 * lv) - 1.0;	/* compute abs((2 * lv) - 1) */
    if (c2 < 0.0)
	c2 = -c2;

    c = (1.0 - c2) * sv;
    x = ((60 - hs) / 60.) * c;
    m = lv - 0.5 * c;

    switch (h / 60) {		/* result in six intervals */
    case 0:
	r1 = c;
	g1 = x;
	b1 = 0.0;
	break;
    case 1:
	r1 = x;
	g1 = c;
	b1 = 0.0;
	break;
    case 2:
	r1 = 0.0;
	g1 = c;
	b1 = x;
	break;
    case 3:
	r1 = 0.0;
	g1 = x;
	b1 = c;
	break;
    case 4:
	r1 = x;
	g1 = 0.0;
	b1 = c;
	break;
    case 5:
	r1 = c;
	g1 = 0.0;
	b1 = x;
	break;
    default:
	TRACE(("Bad HLS input: [%d,%d,%d], returning white\n", h, l, s));
	*r = (short) 360;
	*g = (short) MAX_PCT;
	*b = (short) MAX_PCT;
	return;
    }

    *r = (short) ((r1 + m) * MAX_PCT + 0.5);
    *g = (short) ((g1 + m) * MAX_PCT + 0.5);
    *b = (short) ((b1 + m) * MAX_PCT + 0.5);

    if (*r < 0)
	*r = 0;
    else if (*r > 100)
	*r = 100;
    if (*g < 0)
	*g = 0;
    else if (*g > 100)
	*g = 100;
    if (*b < 0)
	*b = 0;
    else if (*b > 100)
	*b = 100;
}

static void
rgb2hls(int r, int g, int b, short *h, short *l, short *s)
{
    const double scaled_r = (r / MAX_RGB);
    const double scaled_g = (g / MAX_RGB);
    const double scaled_b = (b / MAX_RGB);

    const double min_scale = Min(Min(scaled_r, scaled_g), scaled_b);
    const double max_scale = Max(Max(scaled_r, scaled_g), scaled_b);
    const double dif_scale = max_scale - min_scale;

    double h_work = 0.;
    double s_work = 0.;
    double l_work = ((max_scale + min_scale) / 2.);

    if (dif_scale != 0.) {
	if (l_work < 0.5f) {
	    s_work = (dif_scale / (max_scale + min_scale));
	} else {
	    s_work = (dif_scale / (2. - max_scale - min_scale));
	}

	if (scaled_r == max_scale) {
	    h_work = (scaled_g - scaled_b) / dif_scale;
	} else if (scaled_g == max_scale) {
	    h_work = 2. + (scaled_b - scaled_r) / dif_scale;
	} else if (scaled_b == max_scale) {
	    h_work = 4. + (scaled_r - scaled_g) / dif_scale;
	}
    }

    h_work *= 60.;
    if (h_work < 0)
	h_work += 360.;

    s_work *= MAX_RGB;
    l_work *= MAX_RGB;

    *h = (short) h_work;
    *s = (short) s_work;
    *l = (short) l_work;
}

