# UI translations

These UTF-8 JSON catalogs are compiled into the single executable. Choose the interface language under **Window → Interface language**, save, and restart Nemoterm. See [language settings and integration](../docs/I18N.md) for persistence, scope and acceptance evidence.

`en.json` is the source language; `zh-CN.json` is Simplified Chinese. They cover the principal menu and settings surfaces, including Terminfo keyboard selection, but not every inherited runtime message or dropdown option. Keep the same semantic IDs in both catalogs.

Translator rules:

- Keep IDs and named `{parameters}` unchanged; reorder parameters when grammar needs it.
- Preserve protocol names, key names, application names and command-line switches.
- Preserve menu access keys, e.g. `&Copy` becomes `复制(&C)`. Settings-control access keys remain separate metadata and are appended by the Win32 adapter.
- Do not translate user-entered profile names, paths or shell output. `profile.default_display` is only a display label; stored profile identity stays `Default`.
- Use 配置方案 for Profile, 响铃 for Bell, 回滚历史 for Scrollback, 标签页 for Tab, and 字符编码 for the existing Translation page.
- Keep technical negatives exact: “Disable …” options remain “禁用/禁止 …”, so checkbox semantics cannot reverse.

Regenerate the embedded catalog with `scripts/generate-ui-catalog.py` after editing. GitHub-hosted Actions checks duplicate IDs, matching keys, placeholders and generated-file freshness, then tests the actual bilingual UI at multiple DPI scales. Catalog validation alone cannot prove visual completeness. All builds and tests run remotely.
