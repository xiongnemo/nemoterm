# UI translation drafts

These UTF-8 JSON catalogs are **not wired into the executable yet**. Their `draft-not-integrated` status is intentional. The current preview remains English. See [the integration design](../docs/I18N.md) for code touchpoints and acceptance criteria.

`en.json` is the source language; `zh-CN.json` is the Simplified Chinese draft. Both contain the same 289 semantic IDs. They cover the principal menu and settings surfaces, not every runtime message or dropdown option. The language-selection page is proposed new UI, and parameterized entries require corresponding call-site integration.

Translator rules:

- Keep IDs and named `{parameters}` unchanged; reorder parameters when grammar needs it.
- Preserve protocol names, key names, application names and command-line switches.
- Preserve menu access keys, e.g. `&Copy` becomes `复制(&C)`. Settings-control access keys remain separate metadata and are appended by the future adapter.
- Do not translate user-entered profile names, paths or shell output. `profile.default_display` is only a display label; stored profile identity stays `Default`.
- Use 配置方案 for Profile, 响铃 for Bell, 回滚历史 for Scrollback, 标签页 for Tab, and 字符编码 for the existing Translation page.
- Keep technical negatives exact: “Disable …” options remain “禁用/禁止 …”, so checkbox semantics cannot reverse.

Before runtime integration, validate duplicate IDs, matching key sets, nonempty strings and matching placeholder/access-key sets. Completeness also requires auditing call sites and actual rendered UI; catalog validation alone cannot prove it.
