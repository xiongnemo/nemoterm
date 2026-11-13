"""User-approved frontend private-working-set budgets, in decimal bytes.

Use the observed NemotermRenderer property, not the requested setting: a GPU
request that falls back to GDI retains GDI's budget. Instrumented observations
must be excluded by the calling fixture before applying these limits.
"""


def private_ws_policy(actual_renderer):
    if actual_renderer not in (1, 2, 3):
        raise ValueError(f'Unknown actual renderer: {actual_renderer}')
    return dict(memory_limit_bytes={1: 20_000_000, 2: None, 3: 25_000_000}[actual_renderer],
                memory_limit_inclusive=actual_renderer == 3,
                memory_limit_required=actual_renderer != 2)


def private_ws_passes(actual_renderer, peak):
    policy = private_ws_policy(actual_renderer)
    if peak < 0:
        raise ValueError('Private working set cannot be negative')
    limit = policy['memory_limit_bytes']
    if limit is None:
        return None
    return peak <= limit if policy['memory_limit_inclusive'] else peak < limit
