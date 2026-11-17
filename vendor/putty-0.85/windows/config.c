/*
 * config.c - the Windows-specific parts of the PuTTY configuration
 * box.
 */

#include <assert.h>
#include <stdlib.h>

#include "putty.h"
#include "dialog.h"
#include "storage.h"
#include "nemo_shell.h"
#include "nemo_ui.h"

static void ui_language_handler(dlgcontrol *ctrl, dlgparam *dlg, void *data, int event)
{
    (void)data;
    if (event == EVENT_REFRESH) {
        if (dlg->ui_language_pending < 0)
            dlg->ui_language_original = dlg->ui_language_pending = nemo_ui_read_preference();
        dlg_update_start(ctrl, dlg);
        dlg_listbox_clear(ctrl, dlg);
        dlg_listbox_addwithid(ctrl, dlg, nemo_ui_text("language.system"), NEMO_UI_SYSTEM);
        dlg_listbox_addwithid(ctrl, dlg, nemo_ui_text("language.english"), NEMO_UI_EN);
        dlg_listbox_addwithid(ctrl, dlg, nemo_ui_text("language.simplified_chinese"), NEMO_UI_ZH_CN);
        dlg_listbox_select(ctrl, dlg, dlg->ui_language_pending);
        dlg_update_done(ctrl, dlg);
    } else if (event == EVENT_SELCHANGE) {
        int index = dlg_listbox_index(ctrl, dlg);
        if (index >= 0) dlg->ui_language_pending = dlg_listbox_getid(ctrl, dlg, index);
    }
}

static void shell_list_free(void *v)
{
    nemo_shell_free(v);
}
static void shell_handler(dlgcontrol *ctrl, dlgparam *dlg, void *data, int event)
{
    Conf *conf = data;
    NemoShellList *list = ctrl->context.p;
    if (event == EVENT_REFRESH) {
        char *id = dupstr(conf_get_str(conf, CONF_nemo_shell));
        int selected = 0;
        dlg_update_start(ctrl, dlg);
        dlg_listbox_clear(ctrl, dlg);
        dlg_listbox_addwithid(ctrl, dlg, nemo_ui_text("shell.automatic"), 0);
        for (int i = 0; i < NEMO_SHELL_COUNT; i++) {
            char *label = list->paths[i] ? dupstr(nemo_shell_names[i]) : nemo_ui_format("shell.not_installed", "shell", nemo_shell_names[i], NULL, NULL);
            dlg_listbox_addwithid(ctrl, dlg, label, i + 1);
            sfree(label);
            if (!strcmp(id, nemo_shell_ids[i])) selected = i + 1;
        }
        dlg_listbox_addwithid(ctrl, dlg, nemo_ui_text("shell.custom_choice"), NEMO_SHELL_COUNT + 1);
        if (!strcmp(id, "custom")) selected = NEMO_SHELL_COUNT + 1;
        if (strcmp(id, "auto") && strcmp(id, "custom") && nemo_shell_index(id) < 0) {
            char *label = nemo_ui_format("shell.unavailable", "shell", id, NULL, NULL);
            selected = NEMO_SHELL_COUNT + 2;
            dlg_listbox_addwithid(ctrl, dlg, label, selected);
            sfree(label);
        }
        dlg_listbox_select(ctrl, dlg, selected);
        dlg_update_done(ctrl, dlg);
        conf_set_str(conf, CONF_nemo_shell, id);
        sfree(id);
    } else if (event == EVENT_SELCHANGE) {
        int row = dlg_listbox_index(ctrl, dlg);
        if (row < 0) return;
        int id = dlg_listbox_getid(ctrl, dlg, row);
        if (id < 0 || id > NEMO_SHELL_COUNT + 1) return;
        conf_set_str(conf, CONF_nemo_shell, id == 0 ? "auto" :
                     id == NEMO_SHELL_COUNT + 1 ? "custom" : nemo_shell_ids[id - 1]);
    }
}

static void about_handler(dlgcontrol *ctrl, dlgparam *dlg,
                          void *data, int event)
{
    HWND *hwndp = (HWND *)ctrl->context.p;

    if (event == EVENT_ACTION) {
        modal_about_box(*hwndp);
    }
}

static void help_handler(dlgcontrol *ctrl, dlgparam *dlg,
                         void *data, int event)
{
    HWND *hwndp = (HWND *)ctrl->context.p;

    if (event == EVENT_ACTION) {
        show_help(*hwndp);
    }
}

static void variable_pitch_handler(dlgcontrol *ctrl, dlgparam *dlg,
                                   void *data, int event)
{
    if (event == EVENT_REFRESH) {
        dlg_checkbox_set(ctrl, dlg, !dlg_get_fixed_pitch_flag(dlg));
    } else if (event == EVENT_VALCHANGE) {
        dlg_set_fixed_pitch_flag(dlg, !dlg_checkbox_get(ctrl, dlg));
    }
}

void win_setup_config_box(struct controlbox *b, HWND *hwndp, bool has_help,
                          bool midsession, int protocol)
{
    const struct BackendVtable *backvt;
    bool resize_forbidden = false;
    struct controlset *s;
    dlgcontrol *c;
    char *str;

    if (protocol < 0) {
        ctrl_settitle(b, "Window/Language", nemo_ui_text("language.title"));
        s = ctrl_getset(b, "Window/Language", "language", nemo_ui_text("language.title"));
        ctrl_droplist(s, nemo_ui_text("language.label"), NO_SHORTCUT, 100,
                      HELPCTX(no_help), ui_language_handler, I(0));
        ctrl_text(s, nemo_ui_text("language.restart_hint"), HELPCTX(no_help));
        ctrl_text(s, nemo_ui_text("language.terminal_hint"), HELPCTX(no_help));
        NemoShellList *list = ctrl_alloc_with_free(b, sizeof(*list), shell_list_free);
        nemo_shell_detect(list);
        s = ctrl_getset(b, "Profile/Shell", "shell", nemo_ui_text("shell.local"));
        ctrl_droplist(s, nemo_ui_text("shell.label"), NO_SHORTCUT, 100, HELPCTX(no_help), shell_handler, P(list));
        ctrl_checkbox(s, nemo_ui_text("shell.choose_on_startup"), NO_SHORTCUT, HELPCTX(no_help),
                      conf_checkbox_handler, I(CONF_nemo_choose_shell));
        ctrl_settitle(b, "Profile/Shell", nemo_ui_text("shell.startup_command"));
        s = ctrl_getset(b, "Profile/Shell", "command", nemo_ui_text("shell.custom"));
        ctrl_editbox(s, nemo_ui_text("shell.command"), 'm', 100, HELPCTX(no_help),
                     conf_editbox_handler, I(CONF_nemo_shell_command), ED_STR);
        ctrl_editbox(s, nemo_ui_text("shell.directory"), NO_SHORTCUT, 100,
                     HELPCTX(no_help), conf_editbox_handler, I(CONF_nemo_starting_directory), ED_STR);
        ctrl_checkbox(s, nemo_ui_text("shell.inherit_directory"), NO_SHORTCUT,
                      HELPCTX(no_help), conf_checkbox_handler, I(CONF_nemo_inherit_directory));
        ctrl_text(s, nemo_ui_text("shell.save_hint"), HELPCTX(no_help));
    }

    if (!midsession) {
        /*
         * Add the About and Help buttons to the standard panel.
         */
        s = ctrl_getset(b, "", "", "");
        c = ctrl_pushbutton(s, nemo_ui_text("common.about"), 'a', HELPCTX(no_help),
                            about_handler, P(hwndp));
        c->column = 0;
        if (has_help) {
            c = ctrl_pushbutton(s, nemo_ui_text("common.help"), 'h', HELPCTX(no_help),
                                help_handler, P(hwndp));
            c->column = 1;
        }
    }

    /*
     * Full-screen mode is a Windows peculiarity; hence
     * scrollbar_in_fullscreen is as well.
     */
    s = ctrl_getset(b, "Window", "scrollback",
                    nemo_ui_text("window.scrollback"));
    ctrl_checkbox(s, nemo_ui_text("window.fullscreen_scrollbar"), 'i',
                  HELPCTX(window_scrollback),
                  conf_checkbox_handler,
                  I(CONF_scrollbar_in_fullscreen));
    /*
     * Really this wants to go just after `Display scrollbar'. See
     * if we can find that control, and do some shuffling.
     */
    {
        int i;
        for (i = 0; i < s->ncontrols; i++) {
            c = s->ctrls[i];
            if (c->type == CTRL_CHECKBOX &&
                c->context.i == CONF_scrollbar) {
                /*
                 * Control i is the scrollbar checkbox.
                 * Control s->ncontrols-1 is the scrollbar-in-FS one.
                 */
                if (i < s->ncontrols-2) {
                    c = s->ctrls[s->ncontrols-1];
                    memmove(s->ctrls+i+2, s->ctrls+i+1,
                            (s->ncontrols-i-2)*sizeof(dlgcontrol *));
                    s->ctrls[i+1] = c;
                }
                break;
            }
        }
    }

    /*
     * Windows has the AltGr key, which has various Windows-
     * specific options.
     */
    s = ctrl_getset(b, "Terminal/Keyboard", "features",
                    nemo_ui_text("keyboard.extra"));
    ctrl_checkbox(s, nemo_ui_text("keyboard.altgr_compose"), 't',
                  HELPCTX(keyboard_compose),
                  conf_checkbox_handler, I(CONF_compose_key));
    ctrl_checkbox(s, nemo_ui_text("keyboard.ctrlalt_distinct"), 'd',
                  HELPCTX(keyboard_ctrlalt),
                  conf_checkbox_handler, I(CONF_ctrlaltkeys));

    /*
     * Windows allows an arbitrary .WAV to be played as a bell, and
     * also the use of the PC speaker. For this we must search the
     * existing controlset for the radio-button set controlling the
     * `beep' option, and add extra buttons to it.
     *
     * Note that although this _looks_ like a hideous hack, it's
     * actually all above board. The well-defined interface to the
     * per-platform dialog box code is the _data structures_ `union
     * control', `struct controlset' and so on; so code like this
     * that reaches into those data structures and changes bits of
     * them is perfectly legitimate and crosses no boundaries. All
     * the ctrl_* routines that create most of the controls are
     * convenient shortcuts provided on the cross-platform side of
     * the interface, and template creation code is under no actual
     * obligation to use them.
     */
    s = ctrl_getset(b, "Terminal/Bell", "style", nemo_ui_text("bell.style"));
    {
        int i;
        for (i = 0; i < s->ncontrols; i++) {
            c = s->ctrls[i];
            if (c->type == CTRL_RADIO &&
                c->context.i == CONF_beep) {
                assert(c->handler == conf_radiobutton_handler);
                c->radio.nbuttons += 2;
                c->radio.buttons =
                    sresize(c->radio.buttons, c->radio.nbuttons, char *);
                c->radio.buttons[c->radio.nbuttons-1] =
                    dupstr(nemo_ui_text("bell.custom"));
                c->radio.buttons[c->radio.nbuttons-2] =
                    dupstr(nemo_ui_text("bell.speaker"));
                c->radio.buttondata =
                    sresize(c->radio.buttondata, c->radio.nbuttons, intorptr);
                c->radio.buttondata[c->radio.nbuttons-1] = I(BELL_WAVEFILE);
                c->radio.buttondata[c->radio.nbuttons-2] = I(BELL_PCSPEAKER);
                if (c->radio.shortcuts) {
                    c->radio.shortcuts =
                        sresize(c->radio.shortcuts, c->radio.nbuttons, char);
                    c->radio.shortcuts[c->radio.nbuttons-1] = NO_SHORTCUT;
                    c->radio.shortcuts[c->radio.nbuttons-2] = NO_SHORTCUT;
                }
                break;
            }
        }
    }
    ctrl_filesel(s, nemo_ui_text("bell.file"), NO_SHORTCUT,
                 FILTER_SOUND_FILES, false, nemo_ui_text("bell.file_picker"),
                 HELPCTX(bell_style),
                 conf_filesel_handler, I(CONF_bell_wavefile));

    /*
     * While we've got this box open, taskbar flashing on a bell is
     * also Windows-specific.
     */
    ctrl_radiobuttons(s, nemo_ui_text("bell.indication"), 'i', 3,
                      HELPCTX(bell_taskbar),
                      conf_radiobutton_handler,
                      I(CONF_beep_ind),
                      nemo_ui_text("common.disabled"), I(B_IND_DISABLED),
                      nemo_ui_text("bell.flashing"), I(B_IND_FLASH),
                      nemo_ui_text("bell.steady"), I(B_IND_STEADY));
    ctrl_checkbox(s, nemo_ui_text("bell.raise"), NO_SHORTCUT,
                  HELPCTX(bell_taskbar),
                  conf_checkbox_handler, I(CONF_nemo_bell_raise));
    ctrl_checkbox(s, nemo_ui_text("bell.on_reset"), NO_SHORTCUT,
                  HELPCTX(bell_style),
                  conf_checkbox_handler, I(CONF_nemo_bell_on_reset));

    /*
     * The sunken-edge border is a Windows GUI feature.
     */
    s = ctrl_getset(b, "Window/Appearance", "border",
                    nemo_ui_text("appearance.border_group"));
    ctrl_checkbox(s, nemo_ui_text("appearance.sunken_border"), 's',
                  HELPCTX(appearance_border),
                  conf_checkbox_handler, I(CONF_sunken_edge));

    /*
     * Configurable font quality settings for Windows.
     */
    s = ctrl_getset(b, "Window/Appearance", "font",
                    nemo_ui_text("appearance.font_group"));
    ctrl_checkbox(s, nemo_ui_text("appearance.variable_pitch"), NO_SHORTCUT,
                  HELPCTX(appearance_font), variable_pitch_handler, I(0));
    ctrl_radiobuttons(s, nemo_ui_text("appearance.font_quality"), 'q', 2,
                      HELPCTX(appearance_font),
                      conf_radiobutton_handler,
                      I(CONF_font_quality),
                      nemo_ui_text("appearance.antialiased"), I(FQ_ANTIALIASED),
                      nemo_ui_text("appearance.non_antialiased"), I(FQ_NONANTIALIASED),
                      "ClearType", I(FQ_CLEARTYPE),
                      nemo_ui_text("profile.default_display"), I(FQ_DEFAULT));

    /*
     * Cyrillic Lock is a horrid misfeature even on Windows, and
     * the least we can do is ensure it never makes it to any other
     * platform (at least unless someone fixes it!).
     */
    s = ctrl_getset(b, "Window/Translation", "tweaks", NULL);
    ctrl_checkbox(s, nemo_ui_text("encoding.cyrillic"), 's',
                  HELPCTX(translation_cyrillic),
                  conf_checkbox_handler,
                  I(CONF_xlat_capslockcyr));

    /*
     * On Windows we can use but not enumerate translation tables
     * from the operating system. Briefly document this.
     */
    s = ctrl_getset(b, "Window/Translation", "trans",
                    nemo_ui_text("encoding.received"));
    ctrl_text(s, nemo_ui_text("encoding.windows_hint"),
              HELPCTX(translation_codepage));

    /*
     * Windows has the weird OEM font mode, which gives us some
     * additional options when working with line-drawing
     * characters.
     */
    str = nemo_ui_format("encoding.line_title", "app", appname, NULL, NULL);
    s = ctrl_getset(b, "Window/Translation/Line drawing", "linedraw", str);
    sfree(str);
    {
        int i;
        for (i = 0; i < s->ncontrols; i++) {
            c = s->ctrls[i];
            if (c->type == CTRL_RADIO &&
                c->context.i == CONF_vtmode) {
                assert(c->handler == conf_radiobutton_handler);
                c->radio.nbuttons += 3;
                c->radio.buttons =
                    sresize(c->radio.buttons, c->radio.nbuttons, char *);
                c->radio.buttons[c->radio.nbuttons-3] =
                    dupstr(nemo_ui_text("encoding.xwindows"));
                c->radio.buttons[c->radio.nbuttons-2] =
                    dupstr(nemo_ui_text("encoding.ansi_oem"));
                c->radio.buttons[c->radio.nbuttons-1] =
                    dupstr(nemo_ui_text("encoding.oem"));
                c->radio.buttondata =
                    sresize(c->radio.buttondata, c->radio.nbuttons, intorptr);
                c->radio.buttondata[c->radio.nbuttons-3] = I(VT_XWINDOWS);
                c->radio.buttondata[c->radio.nbuttons-2] = I(VT_OEMANSI);
                c->radio.buttondata[c->radio.nbuttons-1] = I(VT_OEMONLY);
                if (!c->radio.shortcuts) {
                    int j;
                    c->radio.shortcuts = snewn(c->radio.nbuttons, char);
                    for (j = 0; j < c->radio.nbuttons; j++)
                        c->radio.shortcuts[j] = NO_SHORTCUT;
                } else {
                    c->radio.shortcuts = sresize(c->radio.shortcuts,
                                                 c->radio.nbuttons, char);
                }
                c->radio.shortcuts[c->radio.nbuttons-3] = 'x';
                c->radio.shortcuts[c->radio.nbuttons-2] = 'b';
                c->radio.shortcuts[c->radio.nbuttons-1] = 'e';
                break;
            }
        }
    }

    /*
     * RTF paste is Windows-specific.
     */
    s = ctrl_getset(b, "Window/Selection/Copy", "format",
                    nemo_ui_text("selection.formatting"));
    ctrl_checkbox(s, nemo_ui_text("selection.rtf"), 'f',
                  HELPCTX(copy_rtf),
                  conf_checkbox_handler, I(CONF_rtf_paste));

    /*
     * Windows often has no middle button, so we supply a selection
     * mode in which the more critical Paste action is available on
     * the right button instead.
     */
    s = ctrl_getset(b, "Window/Selection", "mouse",
                    nemo_ui_text("selection.mouse_group"));
    ctrl_radiobuttons(s, nemo_ui_text("selection.buttons"), 'm', 1,
                      HELPCTX(selection_buttons),
                      conf_radiobutton_handler,
                      I(CONF_mouse_is_xterm),
                      nemo_ui_text("selection.windows"), I(2),
                      nemo_ui_text("selection.compromise"), I(0),
                      nemo_ui_text("selection.xterm"), I(1));
    /*
     * This really ought to go at the _top_ of its box, not the
     * bottom, so we'll just do some shuffling now we've set it
     * up...
     */
    c = s->ctrls[s->ncontrols-1];      /* this should be the new control */
    memmove(s->ctrls+1, s->ctrls, (s->ncontrols-1)*sizeof(dlgcontrol *));
    s->ctrls[0] = c;

    /*
     * Logical palettes don't even make sense anywhere except Windows.
     */
    s = ctrl_getset(b, "Window/Colours", "general",
                    nemo_ui_text("colours.general"));
    ctrl_checkbox(s, nemo_ui_text("colours.palette"), 'l',
                  HELPCTX(colours_logpal),
                  conf_checkbox_handler, I(CONF_try_palette));
    ctrl_checkbox(s, nemo_ui_text("colours.system"), 's',
                  HELPCTX(colours_system),
                  conf_checkbox_handler, I(CONF_system_colour));


    /*
     * Resize-by-changing-font is a Windows insanity.
     */

    backvt = backend_vt_from_proto(protocol);
    if (backvt)
        resize_forbidden = (backvt->flags & BACKEND_RESIZE_FORBIDDEN);
    if (!midsession || !resize_forbidden) {
        s = ctrl_getset(b, "Window", "size", nemo_ui_text("window.size"));
        ctrl_radiobuttons(s, nemo_ui_text("window.resize"), 'z', 1,
                          HELPCTX(window_resize),
                          conf_radiobutton_handler,
                          I(CONF_resize_action),
                          nemo_ui_text("window.resize_cells"), I(RESIZE_TERM),
                          nemo_ui_text("window.resize_font"), I(RESIZE_FONT),
                          nemo_ui_text("window.maximise_font"), I(RESIZE_EITHER),
                          nemo_ui_text("window.forbid_resize"), I(RESIZE_DISABLED));
    }

    /*
     * Most of the Window/Behaviour stuff is there to mimic Windows
     * conventions which PuTTY can optionally disregard. Hence,
     * most of these options are Windows-specific.
     */
    s = ctrl_getset(b, "Window/Behaviour", "main", NULL);
    ctrl_checkbox(s, nemo_ui_text("behaviour.alt_f4"), '4',
                  HELPCTX(behaviour_altf4),
                  conf_checkbox_handler, I(CONF_alt_f4));
    ctrl_checkbox(s, nemo_ui_text("behaviour.alt_space"), 'y',
                  HELPCTX(behaviour_altspace),
                  conf_checkbox_handler, I(CONF_alt_space));
    ctrl_checkbox(s, nemo_ui_text("behaviour.alt"), 'l',
                  HELPCTX(behaviour_altonly),
                  conf_checkbox_handler, I(CONF_alt_only));
    ctrl_checkbox(s, nemo_ui_text("behaviour.on_top"), 'e',
                  HELPCTX(behaviour_alwaysontop),
                  conf_checkbox_handler, I(CONF_alwaysontop));
    ctrl_checkbox(s, nemo_ui_text("behaviour.fullscreen"), 'f',
                  HELPCTX(behaviour_altenter),
                  conf_checkbox_handler,
                  I(CONF_fullscreenonaltenter));

    /*
     * Windows supports a local-command proxy.
     */
    if (!midsession && protocol >= 0) {
        int i;
        s = ctrl_getset(b, "Connection/Proxy", "basics", NULL);
        for (i = 0; i < s->ncontrols; i++) {
            c = s->ctrls[i];
            if (c->type == CTRL_LISTBOX &&
                c->handler == proxy_type_handler) {
                c->context.i |= PROXY_UI_FLAG_LOCAL;
                break;
            }
        }
    }

    /*
     * $XAUTHORITY is not reliable on Windows, so we provide a
     * means to override it.
     */
    if (!midsession && backend_vt_from_proto(PROT_SSH)) {
        s = ctrl_getset(b, "Connection/SSH/X11", "x11", "X11 forwarding");
        ctrl_filesel(s, "X authority file for local display", 't',
                     FILTER_ALL_FILES, false, "Select X authority file",
                     HELPCTX(ssh_tunnels_xauthority),
                     conf_filesel_handler, I(CONF_xauthfile));
    }
}
