# Kitty image data cache

This component follows the bounded transport checkpoint. It is not yet connected
to the terminal's APC handler or renderer, so the terminal still does not report
kitty graphics support. The user has resumed local native testing.

`nemo_kitty_cache.c` owns immutable decoded image data separately from future
placements. It implements actual RGB/RGBA-to-straight-BGRA conversion, an admitted
PNG decoder callback, client image ids, generated ids for image numbers, anonymous
images, reference counts, replacement/removal notifications and quota eviction.
Image-number lookup selects the newest image with that number. Replacing a named
image invalidates its previous placement references through the owner callback;
failed decoding preserves that particular old image. Queries validate a decoder
without retaining data, allocating ids, changing existing images or evicting any
images. Unknown formats, compressed data and non-direct media return an explicit
unsupported result; this component performs no filesystem access.

The owner supplies admission for the shared image budget and must include
transport/Sixel/iTerm allocations. Reservations include old retained data, new
decoded pixels and new metadata simultaneously. PNG decoders must obtain approval
before allocating and return the approved dimensions and byte count. The cache
tracks transient reservations, rejects reentrant mutation during callbacks, and
frees partially returned decoder data on failure. Images without placement
references are evicted before referenced images. Eviction of referenced data
requires an owner callback to discard the placements before pixels are freed.
There are at most 128 cached image objects and each source axis is bounded to
8,192 pixels; the shared byte budget remains the tighter limit for large images.

Evicting unrelated old data may be necessary before a new decoder can allocate.
If that decoding subsequently fails, the result still reports that visible state
changed. The future terminal adapter must repaint even though the command failed.
Queries disable this eviction behavior entirely. Accounting covers owned buffers
and structures, not allocator overhead or whole-process working set.

The cache test exercises channel/alpha values, unsigned ids, duplicate image
numbers, anonymous images, query isolation, protected replacements, reference
callbacks, invalid sizes/lengths, admission denial, shared-budget pressure,
unplaced-first eviction, image-count limits and decoder failure cleanup. Its
injected PNG decoder tests the callback/ownership contract only; those checks are
**not evidence of real PNG decoding**. Existing platform WIC decoding still needs
to be wired and tested through this new path. The [focused remote workflow](https://github.com/xiongnemo/nemoterm/actions/runs/43611847711)
at `400486d02ed9d181ceeb63e0641673b0d197757a` passed GCC, Clang and MSVC.
Each run passes 1,564 cache assertions, with additional ASan/UBSan runs on both
Linux compilers. All three source manifests match this checkout. Twenty raw
logs/manifests are retained with hashes in the [validation record](kitty-image-cache-validation.json).
The complete [core](https://github.com/xiongnemo/nemoterm/actions/runs/43611847687)
and [single-executable](https://github.com/xiongnemo/nemoterm/actions/runs/43611847731)
workflows also passed at this exact source. The single image is 4,486,144 bytes,
SHA-256 `5a22c46d3b7a86050aa7c808ff12f81acac789579df8b357d12f19acf91ce74e`.
All 122 mandatory application checks passed; the downloaded executable hash
matches the manifest and the single-image, zoom, bell and tab-profile records.
Fourteen additional raw records are retained in the validation record. This
candidate has not replaced the accepted local executable. These checks do not
establish runtime kitty graphics or local memory acceptance.

## Layout questions found during source inspection

The pinned kitty source and protocol text do not agree in two places relevant
to the next stage:

* `handle_put_command` advances the row by effective rows minus one, while the
  documentation describes advancing by the number of rows.
* Ordinary placements with both row and column counts use the whole requested
  rectangle in `update_layers`; the documentation describes preserving aspect
  ratio with letterboxing. The source explicitly performs that fitting for
  Unicode placeholder placements, a separate path.

These observations come from kitty commit
`8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f`,
[`graphics.c`](https://github.com/kovidgoyal/kitty/blob/8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f/kitty/graphics.c)
and [`graphics.py`](https://github.com/kovidgoyal/kitty/blob/8e5487e9d4a1dd79c3a769e0ba82326b8ad7c37f/kitty_tests/graphics.py).
The subsequent [independent native-model capture](kitty-graphics-reference.md)
confirms rows-minus-one cursor advancement and stretching when both axes are
specified, for this pinned ordinary-placement path. It captures actual compiled
upstream model output, not visible GPU pixels. Also preserve the explicit distinction between
clearing the screen and other text erases: the latter must not erase kitty
placements, unlike the existing Sixel cell-mask path.

The [ordinary layout component](kitty-layout.md) now calculates crop, offsets,
scale and cursor deltas against 13 retained upstream observations. It remains
separate from placement ownership and actual rendering.

Remaining work includes placement identity/deletion and scroll lifetimes,
rendering order around text/backgrounds, terminal framing and
replies, real PNG decoding, indexed/compressed formats, relative/Unicode placements,
animation, independent pixel reference evidence and full local acceptance.
The complete modern-terminal objective remains open.
