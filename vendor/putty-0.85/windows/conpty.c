/*
 * Backend to run a Windows console session using ConPTY.
 */

#include <stdio.h>
#include <stdlib.h>
#include <limits.h>

#include "putty.h"

#include <windows.h>
#include <consoleapi.h>

typedef struct ConPTY ConPTY;
struct ConPTY {
    HPCON pseudoconsole;
    HANDLE outpipe, inpipe, hprocess;
    struct handle *out, *in;
    HandleWait *subprocess;
    bool exited;
    DWORD exitstatus;
    Seat *seat;
    LogContext *logctx;
    int bufsize;
    Backend backend;
};

DECL_WINDOWS_FUNCTION(static, HRESULT, CreatePseudoConsole,
                      (COORD, HANDLE, HANDLE, DWORD, HPCON *));
DECL_WINDOWS_FUNCTION(static, void, ClosePseudoConsole, (HPCON));
DECL_WINDOWS_FUNCTION(static, HRESULT, ResizePseudoConsole, (HPCON, COORD));

static const char *conpty_api_info;
static const char *conpty_api_error;
static DWORD conpty_api_winerror;

#ifdef NEMOTERM_SINGLE_EXE
HRESULT WINAPI ConptyCreatePseudoConsole(COORD, HANDLE, HANDLE, DWORD, HPCON *);
HRESULT WINAPI ConptyResizePseudoConsole(HPCON, COORD);
void WINAPI ConptyClosePseudoConsole(HPCON);
#endif

/* The NuGet conpty.h exports the same ABI with a Conpty prefix. Never
 * mix functions from that DLL and kernel32 for a single HPCON. */
static int load_bundled_conpty(void)
{
#ifdef NEMOTERM_SINGLE_EXE
    p_CreatePseudoConsole = ConptyCreatePseudoConsole;
    p_ResizePseudoConsole = ConptyResizePseudoConsole;
    p_ClosePseudoConsole = ConptyClosePseudoConsole;
    conpty_api_info = "ConPTY runtime: statically linked; same executable hosts console";
    return 1;
#else
    wchar_t *path = snewn(32768, wchar_t);
    DWORD len = GetModuleFileNameW(NULL, path, 32768);
    if (!len || len >= 32768 - 32) {
        conpty_api_error = "Cannot resolve executable directory for ConPTY";
        sfree(path);
        return -1;
    }
    wchar_t *name = wcsrchr(path, L'\\');
    if (!name) {
        conpty_api_error = "Executable path has no directory for ConPTY";
        sfree(path);
        return -1;
    }
    name++;
    wcscpy(name, L"conpty.dll");
    DWORD attrs = GetFileAttributesW(path);
    if (attrs == INVALID_FILE_ATTRIBUTES) {
        DWORD error = GetLastError();
        sfree(path);
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND)
            return 0;
        conpty_api_error = "Cannot inspect bundled conpty.dll";
        conpty_api_winerror = error;
        return -1;
    }
    /* Microsoft's DLL itself silently falls back to inbox conhost if its
     * host is absent. Reject an incomplete bundle rather than losing VT
     * features silently (notably Sixel on older Windows 10 releases). */
    wcscpy(name, L"OpenConsole.exe");
    attrs = GetFileAttributesW(path);
    if (attrs == INVALID_FILE_ATTRIBUTES || (attrs & FILE_ATTRIBUTE_DIRECTORY)) {
        conpty_api_error = "Bundled ConPTY requires OpenConsole.exe beside nemoterm.exe";
        sfree(path);
        return -1;
    }
    wcscpy(name, L"conpty.dll");
    HMODULE module = LoadLibraryExW(
        path, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    DWORD load_error = module ? ERROR_SUCCESS : GetLastError();
    sfree(path);
    if (!module) {
        conpty_api_error = "Cannot load bundled conpty.dll";
        conpty_api_winerror = load_error;
        return -1;
    }
    t_CreatePseudoConsole create = (t_CreatePseudoConsole)
        GetProcAddress(module, "ConptyCreatePseudoConsole");
    t_ResizePseudoConsole resize = (t_ResizePseudoConsole)
        GetProcAddress(module, "ConptyResizePseudoConsole");
    t_ClosePseudoConsole close = (t_ClosePseudoConsole)
        GetProcAddress(module, "ConptyClosePseudoConsole");
    if (!create || !resize || !close) {
        conpty_api_error = "Bundled conpty.dll lacks required Conpty exports";
        FreeLibrary(module);
        return -1;
    }
    p_CreatePseudoConsole = create;
    p_ResizePseudoConsole = resize;
    p_ClosePseudoConsole = close;
    conpty_api_info = "ConPTY runtime: bundled conpty.dll and OpenConsole.exe";
    /* Keep the module loaded for the lifetime of all pseudoconsole handles. */
    return 1;
#endif
}

static bool init_conpty_api(void)
{
    static bool tried = false;
    if (!tried) {
        tried = true;
        char selection[16];
        DWORD n = GetEnvironmentVariableA("NEMOTERM_CONPTY", selection, sizeof(selection));
        if (n >= sizeof(selection) ||
            (n && strcmp(selection, "auto") && strcmp(selection, "bundled") &&
             strcmp(selection, "system"))) {
            conpty_api_error = "NEMOTERM_CONPTY must be auto, bundled or system";
            return false;
        }
        if (!n || strcmp(selection, "system")) {
            int bundled = load_bundled_conpty();
            if (bundled < 0)
                return false;
            if (bundled > 0)
                return true;
            if (n && !strcmp(selection, "bundled")) {
                conpty_api_error = "NEMOTERM_CONPTY=bundled requires conpty.dll beside nemoterm.exe";
                return false;
            }
            conpty_api_info = "ConPTY runtime: system API fallback (bundled conpty.dll absent)";
        } else {
            conpty_api_info = "ConPTY runtime: system API explicitly selected by NEMOTERM_CONPTY=system";
        }
        HMODULE kernel32_module = load_system32_dll("kernel32.dll");
        GET_WINDOWS_FUNCTION(kernel32_module, CreatePseudoConsole);
        GET_WINDOWS_FUNCTION(kernel32_module, ClosePseudoConsole);
        GET_WINDOWS_FUNCTION(kernel32_module, ResizePseudoConsole);
    }

    return (p_CreatePseudoConsole != NULL &&
            p_ClosePseudoConsole != NULL &&
            p_ResizePseudoConsole != NULL);
}

static void conpty_terminate(ConPTY *conpty)
{
    if (conpty->out) {
        handle_free(conpty->out);
        conpty->out = NULL;
    }
    if (conpty->outpipe != INVALID_HANDLE_VALUE) {
        CloseHandle(conpty->outpipe);
        conpty->outpipe = INVALID_HANDLE_VALUE;
    }
    if (conpty->in) {
        handle_free(conpty->in);
        conpty->in = NULL;
    }
    if (conpty->inpipe != INVALID_HANDLE_VALUE) {
        CloseHandle(conpty->inpipe);
        conpty->inpipe = INVALID_HANDLE_VALUE;
    }
    if (conpty->subprocess) {
        delete_handle_wait(conpty->subprocess);
        conpty->subprocess = NULL;
        conpty->hprocess = INVALID_HANDLE_VALUE;
    }
    if (conpty->pseudoconsole != INVALID_HANDLE_VALUE) {
        p_ClosePseudoConsole(conpty->pseudoconsole);
        conpty->pseudoconsole = INVALID_HANDLE_VALUE;
    }
}

static void conpty_process_wait_callback(void *vctx)
{
    ConPTY *conpty = (ConPTY *)vctx;

    if (!GetExitCodeProcess(conpty->hprocess, &conpty->exitstatus))
        return;
    conpty->exited = true;

    /*
     * We can stop waiting for the process now.
     */
    if (conpty->subprocess) {
        delete_handle_wait(conpty->subprocess);
        conpty->subprocess = NULL;
        conpty->hprocess = INVALID_HANDLE_VALUE;
    }

    /*
     * Once the contained process exits, close the pseudo-console as
     * well. But don't close the pipes yet, since apparently
     * ClosePseudoConsole can trigger a final bout of terminal output
     * as things clean themselves up.
     */
    if (conpty->pseudoconsole != INVALID_HANDLE_VALUE) {
        p_ClosePseudoConsole(conpty->pseudoconsole);
        conpty->pseudoconsole = INVALID_HANDLE_VALUE;
    }
}

static size_t conpty_gotdata(
    struct handle *h, const void *data, size_t len, int err)
{
    ConPTY *conpty = (ConPTY *)handle_get_privdata(h);
    if (err || len == 0) {
        char *error_msg;

        conpty_terminate(conpty);

        seat_notify_remote_exit(conpty->seat);

        if (!err && conpty->exited) {
            /*
             * The clean-exit case: our subprocess terminated, we
             * deleted the PseudoConsole ourself, and now we got the
             * expected EOF on the pipe.
             */
            return 0;
        }

        if (err)
            error_msg = dupprintf("Error reading from console pty: %s",
                                  win_strerror(err));
        else
            error_msg = dupprintf(
                "Unexpected end of file reading from console pty");

        logevent(conpty->logctx, error_msg);
        seat_connection_fatal(conpty->seat, "%s", error_msg);
        sfree(error_msg);

        return 0;
    } else {
        return seat_stdout(conpty->seat, data, len);
    }
}

static void conpty_sentdata(struct handle *h, size_t new_backlog, int err,
                            bool close)
{
    ConPTY *conpty = (ConPTY *)handle_get_privdata(h);
    if (err) {
        const char *error_msg = "Error writing to conpty device";

        conpty_terminate(conpty);

        seat_notify_remote_exit(conpty->seat);

        logevent(conpty->logctx, error_msg);

        seat_connection_fatal(conpty->seat, "%s", error_msg);
    } else {
        conpty->bufsize = new_backlog;
    }
}

static char *conpty_init(const BackendVtable *vt, Seat *seat,
                         Backend **backend_handle, LogContext *logctx,
                         Conf *conf, const char *host, int port,
                         char **realhost, bool nodelay, bool keepalive)
{
    ConPTY *conpty;
    char *err = NULL;

    HANDLE in_r = INVALID_HANDLE_VALUE;
    HANDLE in_w = INVALID_HANDLE_VALUE;
    HANDLE out_r = INVALID_HANDLE_VALUE;
    HANDLE out_w = INVALID_HANDLE_VALUE;

    HPCON pcon;
    bool pcon_needs_cleanup = false;

    STARTUPINFOEXW si;
    memset(&si, 0, sizeof(si));

    if (!init_conpty_api()) {
        const char *message = conpty_api_error ? conpty_api_error :
            "Pseudo-console API is not available on this Windows system";
        err = conpty_api_winerror ?
            dupprintf("%s: %s", message, win_strerror(conpty_api_winerror)) :
            dupstr(message);
        goto out;
    }
    logevent(logctx, conpty_api_info);

    if (!CreatePipe(&in_r, &in_w, NULL, 0)) {
        err = dupprintf("CreatePipe: %s", win_strerror(GetLastError()));
        goto out;
    }
    if (!CreatePipe(&out_r, &out_w, NULL, 0)) {
        err = dupprintf("CreatePipe: %s", win_strerror(GetLastError()));
        goto out;
    }

    COORD size;
    size.X = conf_get_int(conf, CONF_width);
    size.Y = conf_get_int(conf, CONF_height);

    HRESULT result = p_CreatePseudoConsole(size, in_r, out_w, 0, &pcon);
    if (FAILED(result)) {
        if (HRESULT_FACILITY(result) == FACILITY_WIN32)
            err = dupprintf("CreatePseudoConsole: %s",
                            win_strerror(HRESULT_CODE(result)));
        else
            err = dupprintf("CreatePseudoConsole failed: HRESULT=0x%08x",
                            (unsigned)result);
        goto out;
    }
    pcon_needs_cleanup = true;

    CloseHandle(in_r);
    in_r = INVALID_HANDLE_VALUE;
    CloseHandle(out_w);
    out_w = INVALID_HANDLE_VALUE;

    si.StartupInfo.cb = sizeof(si);

    SIZE_T attrsize = 0;
    InitializeProcThreadAttributeList(NULL, 1, 0, &attrsize);
    si.lpAttributeList = smalloc(attrsize);
    if (!InitializeProcThreadAttributeList(
            si.lpAttributeList, 1, 0, &attrsize)) {
        err = dupprintf("InitializeProcThreadAttributeList: %s",
                        win_strerror(GetLastError()));
        goto out;
    }
    if (!UpdateProcThreadAttribute(
            si.lpAttributeList,
            0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
            pcon, sizeof(pcon), NULL, NULL)) {
        err = dupprintf("UpdateProcThreadAttribute: %s",
                        win_strerror(GetLastError()));
        goto out;
    }

    PROCESS_INFORMATION pi;
    memset(&pi, 0, sizeof(pi));

    wchar_t *command;
    {
        bool utf8;
        const char *conf_cmd = conf_get_str_ambi(conf, CONF_remote_cmd, &utf8);
        if (*conf_cmd) {
            command = dup_mb_to_wc(utf8 ? CP_UTF8 : CP_ACP, conf_cmd);
        } else {
            char *cmd = dupcat(get_system_dir(), "\\cmd.exe");
            command = dup_mb_to_wc(CP_ACP, cmd);
            sfree(cmd);
        }
    }
    bool created_ok = CreateProcessW(NULL, command, NULL, NULL,
                                     false, EXTENDED_STARTUPINFO_PRESENT,
                                     NULL, NULL, &si.StartupInfo, &pi);
    sfree(command);
    if (!created_ok) {
        err = dupprintf("CreateProcess: %s",
                        win_strerror(GetLastError()));
        goto out;
    }

    /* No local authentication phase in this protocol */
    seat_set_trust_status(seat, false);

    conpty = snew(ConPTY);
    memset(conpty, 0, sizeof(ConPTY));
    conpty->pseudoconsole = pcon;
    pcon_needs_cleanup = false;
    conpty->outpipe = in_w;
    conpty->out = handle_output_new(in_w, conpty_sentdata, conpty, 0);
    in_w = INVALID_HANDLE_VALUE;
    conpty->inpipe = out_r;
    conpty->in = handle_input_new(out_r, conpty_gotdata, conpty, 0);
    out_r = INVALID_HANDLE_VALUE;
    conpty->subprocess = add_handle_wait(
        pi.hProcess, conpty_process_wait_callback, conpty);
    conpty->hprocess = pi.hProcess;
    CloseHandle(pi.hThread);
    conpty->exited = false;
    conpty->exitstatus = 0;
    conpty->bufsize = 0;
    conpty->backend.vt = vt;
    *backend_handle = &conpty->backend;

    conpty->seat = seat;
    conpty->logctx = logctx;

    *realhost = dupstr("");

    /*
     * Specials are always available.
     */
    seat_update_specials_menu(conpty->seat);

  out:
    if (in_r != INVALID_HANDLE_VALUE)
        CloseHandle(in_r);
    if (in_w != INVALID_HANDLE_VALUE)
        CloseHandle(in_w);
    if (out_r != INVALID_HANDLE_VALUE)
        CloseHandle(out_r);
    if (out_w != INVALID_HANDLE_VALUE)
        CloseHandle(out_w);
    if (pcon_needs_cleanup)
        p_ClosePseudoConsole(pcon);
    sfree(si.lpAttributeList);
    return err;
}

static void conpty_free(Backend *be)
{
    ConPTY *conpty = container_of(be, ConPTY, backend);

    conpty_terminate(conpty);
    expire_timer_context(conpty);
    sfree(conpty);
}

static void conpty_reconfig(Backend *be, Conf *conf)
{
}

static void conpty_send(Backend *be, const char *buf, size_t len)
{
    ConPTY *conpty = container_of(be, ConPTY, backend);

    if (conpty->out == NULL)
        return;

    conpty->bufsize = handle_write(conpty->out, buf, len);
}

static size_t conpty_sendbuffer(Backend *be)
{
    ConPTY *conpty = container_of(be, ConPTY, backend);
    return conpty->bufsize;
}

static void conpty_size(Backend *be, int width, int height)
{
    ConPTY *conpty = container_of(be, ConPTY, backend);
    COORD size;
    size.X = width;
    size.Y = height;
    p_ResizePseudoConsole(conpty->pseudoconsole, size);
}

static void conpty_special(Backend *be, SessionSpecialCode code, int arg)
{
}

static const SessionSpecial *conpty_get_specials(Backend *be)
{
    static const SessionSpecial specials[] = {
        {NULL, SS_EXITMENU}
    };
    return specials;
}

static bool conpty_connected(Backend *be)
{
    return true;                       /* always connected */
}

static bool conpty_sendok(Backend *be)
{
    return true;
}

static void conpty_unthrottle(Backend *be, size_t backlog)
{
    ConPTY *conpty = container_of(be, ConPTY, backend);
    if (conpty->in)
        handle_unthrottle(conpty->in, backlog);
}

static bool conpty_ldisc(Backend *be, int option)
{
    return false;
}

static void conpty_provide_ldisc(Backend *be, Ldisc *ldisc)
{
}

static int conpty_exitcode(Backend *be)
{
    ConPTY *conpty = container_of(be, ConPTY, backend);

    if (conpty->exited) {
        /*
         * PuTTY's representation of exit statuses expects them to be
         * non-negative 'int' values. But Windows exit statuses can
         * include all those exception codes like 0xC000001D which
         * convert to negative 32-bit ints.
         *
         * I don't think there's a great deal of use for returning
         * those in full detail, right now. (Though if we ever
         * connected this system up to a Windows version of psusan or
         * Uppity, perhaps there might be?)
         *
         * So we clip them at INT_MAX-1, since INT_MAX is reserved for
         * 'exit so unclean as to inhibit Close On Clean Exit'.
         */
        return (0 <= conpty->exitstatus && conpty->exitstatus < INT_MAX) ?
            conpty->exitstatus : INT_MAX-1;
    } else {
        return -1;
    }
}

static int conpty_cfg_info(Backend *be)
{
    return 0;
}

const BackendVtable conpty_backend = {
    .init = conpty_init,
    .free = conpty_free,
    .reconfig = conpty_reconfig,
    .send = conpty_send,
    .sendbuffer = conpty_sendbuffer,
    .size = conpty_size,
    .special = conpty_special,
    .get_specials = conpty_get_specials,
    .connected = conpty_connected,
    .exitcode = conpty_exitcode,
    .sendok = conpty_sendok,
    .ldisc_option_state = conpty_ldisc,
    .provide_ldisc = conpty_provide_ldisc,
    .unthrottle = conpty_unthrottle,
    .cfg_info = conpty_cfg_info,
    .id = "conpty",
    .displayname_tc = "ConPTY",
    .displayname_lc = "ConPTY", /* proper name, so capitalise it anyway */
    .protocol = -1,
};
