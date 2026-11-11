#include "putty.h"
#include "storage.h"

const unsigned cmdline_tooltype =
    TOOLTYPE_NONNETWORK |
    TOOLTYPE_NO_VERBOSE_OPTION;

void gui_term_process_cmdline(Conf *conf, char *cmdline)
{
    bool show_settings = false;
    char *exec_command = NULL;
    do_defaults(NULL, conf);
    conf_set_str(conf, CONF_remote_cmd, "");

    cmdline = handle_restrict_acl_cmdline_prefix(cmdline);
    if (handle_special_sessionname_cmdline(cmdline, conf) ||
        handle_special_filemapping_cmdline(cmdline, conf))
        return;

    CmdlineArgList *arglist = cmdline_arg_list_from_GetCommandLineW();
    size_t arglistpos = 0;
    while (arglist->args[arglistpos]) {
        CmdlineArg *arg = arglist->args[arglistpos++];
        CmdlineArg *nextarg = arglist->args[arglistpos];
        const char *argstr = cmdline_arg_to_str(arg);
        if (!strcmp(argstr, "--settings")) {
            show_settings = true;
            continue;
        }
        if (!strcmp(argstr, "--font") || !strcmp(argstr, "--font-size") ||
            !strcmp(argstr, "--cols") || !strcmp(argstr, "--rows") ||
            !strcmp(argstr, "--scrollback") || !strcmp(argstr, "--right-click")) {
            if (!nextarg)
                cmdline_error("option %s requires an argument", argstr);
            const char *value = cmdline_arg_to_str(nextarg);
            arglistpos++;
            if (!strcmp(argstr, "--right-click")) {
                if (strcmp(value, "copy") && strcmp(value, "copy-paste"))
                    cmdline_error("--right-click expects copy or copy-paste");
                conf_set_bool(conf, CONF_nemo_right_click_paste,
                              !strcmp(value, "copy-paste"));
            } else if (!strcmp(argstr, "--font")) {
                FontSpec *old = conf_get_fontspec(conf, CONF_font);
                FontSpec *font = fontspec_new(value, old->isbold,
                                              old->height, DEFAULT_CHARSET);
                conf_set_fontspec(conf, CONF_font, font);
                fontspec_free(font);
            } else {
                char *end;
                long n = strtol(value, &end, 10);
                long minval = !strcmp(argstr, "--scrollback") ? 0 : 1;
                long maxval = !strcmp(argstr, "--scrollback") ? 100000 :
                              !strcmp(argstr, "--font-size") ? 96 : 1000;
                if (!*value || *end || n < minval || n > maxval)
                    cmdline_error("%s must be between %ld and %ld", argstr, minval, maxval);
                if (!strcmp(argstr, "--font-size")) {
                    FontSpec *old = conf_get_fontspec(conf, CONF_font);
                    FontSpec *font = fontspec_new(old->name, old->isbold, n, old->charset);
                    conf_set_fontspec(conf, CONF_font, font);
                    fontspec_free(font);
                } else {
                    int key = !strcmp(argstr, "--cols") ? CONF_width :
                              !strcmp(argstr, "--rows") ? CONF_height : CONF_savelines;
                    conf_set_int(conf, key, n);
                }
            }
            continue;
        }
        int retd = cmdline_process_param(arg, nextarg, 1, conf);
        if (retd == -2) {
            cmdline_error("option \"%s\" requires an argument", argstr);
        } else if (retd == 2) {
            arglistpos++;              /* skip next argument */
        } else if (retd == 1) {
            continue;          /* nothing further needs doing */
        } else if (!strcmp(argstr, "-e")) {
            if (nextarg) {
                /* The command to execute is taken to be the unparsed
                 * version of the whole remainder of the command line. */
                exec_command = cmdline_arg_remainder_utf8(nextarg);
                break;
            } else {
                cmdline_error("option \"%s\" requires an argument", argstr);
            }
        } else if (argstr[0] == '-') {
            cmdline_error("unrecognised option \"%s\"", argstr);
        } else {
            cmdline_error("unexpected non-option argument \"%s\"", argstr);
        }
    }

    cmdline_run_saved(conf);
    if (exec_command) {
        conf_set_utf8(conf, CONF_remote_cmd, exec_command);
        sfree(exec_command);
    }
    if (show_settings && !do_config(conf))
        cleanup_exit(0);

    conf_set_int(conf, CONF_sharrow_type, SHARROW_BITMAP);
    SetEnvironmentVariableA("TERM", "xterm-256color");
    SetEnvironmentVariableA("COLORTERM", "truecolor");
    SetEnvironmentVariableA("TERM_PROGRAM", "nemoterm");
}

const struct BackendVtable *backend_vt_from_conf(Conf *conf)
{
    return &conpty_backend;
}

const wchar_t *get_app_user_model_id(void)
{
    return L"Nemo.Nemoterm";
}

void gui_terminal_ready(HWND hwnd, Seat *seat, Backend *backend)
{
}
