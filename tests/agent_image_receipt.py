"""Read one real client conversation from a completed loopback provider log."""
import re


def chat_attachment(requests, client, binding):
    marker = 'NEMOTERM_' + client.upper() + '_IMAGE_' + binding.upper().replace('-', '_')
    endpoint = {'codex': '/v1/responses', 'opencode': '/v1/chat/completions'}[client]
    turns = []
    title_images = 0
    for r in requests:
        if r['path'] != endpoint:
            raise ValueError('Unexpected provider endpoint')
        if client == 'opencode':
            title = r['has_opencode_title_instruction']
            if type(title) is not bool:
                raise ValueError('Unknown OpenCode request purpose')
            if title:
                title_images += len(r['images'])
                continue
        if marker in r['text']:
            turns.append(r)
        elif r['images']:
            raise ValueError('Image on an unrelated conversation turn')
    # Codex can also send a later text-only request with the same marker.
    # A later retry with an image cannot repair a missing first attachment.
    if (not turns or turns[0]['text'].count(marker) != 1 or len(turns[0]['images']) != 1
            or any(r['images'] for r in turns[1:])):
        raise ValueError('Expected one image on the first marked chat request')
    image = turns[0]['images'][0]
    if not (image['generated_pixels_match'] is True and image['png_size'] == [32, 16]
            and image['mime'] == 'image/png' and re.fullmatch('[a-f0-9]{64}', image['sha256'])):
        raise ValueError('Chat attachment does not match the generated 32 x 16 PNG')
    return dict(chat_image_sha256=image['sha256'], title_images=title_images)
