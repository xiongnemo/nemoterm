"""Read-only menu checks for the explicitly owned tab-host HWND.

Read IDs, types and handles only, never saved-session labels. The host already
created its system menu before these checks; no menu is opened or reset here.
"""
from native_test_utils import c, w, u

u.GetSystemMenu.argtypes, u.GetSystemMenu.restype = [w.HWND, w.BOOL], w.HMENU
u.GetMenuItemCount.argtypes, u.GetMenuItemCount.restype = [w.HMENU], c.c_int
u.GetMenuItemID.argtypes, u.GetMenuItemID.restype = [w.HMENU, c.c_int], w.UINT
u.GetMenuState.argtypes, u.GetMenuState.restype = [w.HMENU, w.UINT, w.UINT], w.UINT
u.GetSubMenu.argtypes, u.GetSubMenu.restype = [w.HMENU, c.c_int], w.HMENU
u.IsMenu.argtypes, u.IsMenu.restype = [w.HMENU], w.BOOL


class TabMenuChecks:
    def __init__(self, host, evidence):
        self.host, self.evidence = host, evidence
        self.menu, self.prefix, self.children = None, None, {}
        evidence['system_menus'] = []

    def observe(self, child):
        menu = u.GetSystemMenu(self.host, False)
        count = u.GetMenuItemCount(menu)
        assert menu and 0 < count < 128, (menu, count)
        entries = []
        for index in range(count):
            state = u.GetMenuState(menu, index, 0x400)
            assert state != 0xffffffff
            entries.append(dict(command=u.GetMenuItemID(menu, index),
                                separator=bool(state & 0x800),
                                submenu=u.GetSubMenu(menu, index)))
        boundary = next(i for i, item in enumerate(entries)
                        if item['command'] < 0xf000 and not item['separator'])
        prefix = entries[:boundary]
        assert {0xf000, 0xf010, 0xf020, 0xf030, 0xf060, 0xf120} <= {
            item['command'] for item in prefix}
        assert any(item['separator'] for item in prefix)
        children = [item['submenu'] for item in entries[boundary:] if item['submenu']]
        assert children and all(u.IsMenu(sub) for sub in children)
        record = dict(child=child, menu=menu, native=prefix, submenus=children,
                      app_commands=[item['command'] for item in entries[boundary:]])
        self.evidence['system_menus'].append(record)
        if self.menu is None:
            self.menu, self.prefix = menu, prefix
        assert menu == self.menu, 'Tab switch recreated the host system menu'
        assert prefix == self.prefix, 'Native system-menu items or separators changed'
        if child in self.children:
            assert children == self.children[child], 'Active tab borrowed another seat menu'
        self.children[child] = children

    def retired(self, child):
        children = self.children.pop(child)
        states = [bool(u.IsMenu(sub)) for sub in children]
        self.evidence.setdefault('retired_tab_menus', []).append(
            dict(child=child, submenus=children, valid_after_close=states))
        assert not any(states), 'Closed tab retained a submenu'
        assert all(u.IsMenu(sub) for menus in self.children.values() for sub in menus), \
            'Closing a tab destroyed another seat menu'
