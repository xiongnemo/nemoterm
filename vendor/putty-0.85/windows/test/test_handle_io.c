/* SPDX-License-Identifier: MIT */
#include "putty.h"
#ifdef NDEBUG
#error This lifecycle test requires assertions
#endif

void out_of_memory(void) { fputs("out of memory\n", stderr); exit(1); }
static size_t received;
static unsigned input_calls, output_calls, eof_calls;

static size_t input(struct handle *h, const void *data, size_t len, int error)
{
    (void)h;
    assert(!error); input_calls++;
    if (!len) eof_calls++;
    const unsigned char *bytes = data;
    for (size_t i=0; i<len; i++) assert(bytes[i] == (unsigned char)(received+i));
    received += len;
    return 0;
}

static void output(struct handle *h, size_t backlog, int error, bool close)
{
    (void)h; (void)backlog; (void)close;
    assert(!error); output_calls++;
}

static void pump(void)
{
    HandleWaitList *waits = get_handle_wait_list();
    assert(waits->nhandles > 0);
    DWORD result = WaitForMultipleObjects(waits->nhandles, waits->handles, FALSE, 20);
    if (result != WAIT_TIMEOUT) {
        assert(result < WAIT_OBJECT_0 + (DWORD)waits->nhandles);
        handle_wait_activate(waits, result-WAIT_OBJECT_0);
    }
    handle_wait_list_free(waits);
}

static HandleWaitList *completion_wait(void)
{
    HandleWaitList *waits = get_handle_wait_list();
    /* This private test process registers only handle-io's shared event. */
    assert(waits->nhandles==1);
    assert(WaitForSingleObject(waits->handles[0],2000)==WAIT_OBJECT_0);
    return waits;
}

static void retired(const char *scenario)
{
    ULONGLONG deadline = GetTickCount64()+2000;
    for (;;) {
        HandleIOStats s = handle_io_stats();
        if (!s.input && !s.output && !s.closing) {
            assert(s.created == s.destroyed);
            return;
        }
        if (GetTickCount64() >= deadline) {
            fprintf(stderr,"%s: input=%llu output=%llu closing=%llu created=%llu destroyed=%llu\n",
                scenario,(unsigned long long)s.input,(unsigned long long)s.output,
                (unsigned long long)s.closing,(unsigned long long)s.created,
                (unsigned long long)s.destroyed);
            exit(1);
        }
        pump();
    }
}

static void run(const char *scenario)
{
    HandleIOStats before = handle_io_stats();
    assert(!before.input && !before.output && !before.closing);
    /* A dispatcher can consume several completions while a later SetEvent
     * remains signalled. Drain that empty notification before creating the
     * next scenario, so completion_wait observes this scenario's operation. */
    HandleWaitList *previous = get_handle_wait_list();
    if (previous->nhandles) {
        assert(previous->nhandles == 1);
        DWORD result = WaitForSingleObject(previous->handles[0], 0);
        if (result == WAIT_OBJECT_0) handle_wait_activate(previous, 0);
        else assert(result == WAIT_TIMEOUT);
    }
    handle_wait_list_free(previous);
    HANDLE reader, writer;
    assert(CreatePipe(&reader,&writer,NULL,4096));
    received=0; input_calls=output_calls=eof_calls=0;
    if (!strcmp(scenario,"idle-output")) {
        struct handle *out = handle_output_new(writer,output,NULL,0);
        handle_free(out);
        assert(handle_io_stats().closing == 1);
        retired(scenario);
        assert(!output_calls);
    } else if (!strcmp(scenario,"input-eof-close")) {
        struct handle *in = handle_input_new(reader,input,NULL,0);
        handle_free(in); /* Read is pending; callback must remain suppressed. */
        assert(handle_io_stats().closing == 1);
        assert(CloseHandle(writer)); writer=INVALID_HANDLE_VALUE;
        retired(scenario);
        assert(!input_calls);
    } else if (!strcmp(scenario,"input-error-close")) {
        /* Reading the write-only end fails instead of reporting pipe EOF. */
        struct handle *in = handle_input_new(writer,input,NULL,0);
        handle_free(in);
        retired(scenario);
        assert(!input_calls);
    } else if (!strcmp(scenario,"output-error-close")) {
        struct handle *out = handle_output_new(writer,output,NULL,0);
        assert(CloseHandle(reader)); reader=INVALID_HANDLE_VALUE;
        handle_write(out,"broken-pipe",11);
        handle_free(out); /* Worker reports an error and exits without an ACK. */
        assert(handle_io_stats().closing == 1);
        retired(scenario);
        assert(!output_calls);
    } else if (!strcmp(scenario,"completed-read-close")) {
        struct handle *in = handle_input_new(reader,input,NULL,0);
        DWORD written;
        assert(WriteFile(writer,"x",1,&written,NULL) && written==1);
        HandleWaitList *waits = completion_wait();
        handle_free(in); /* Successful read still requires a shutdown ACK. */
        handle_wait_activate(waits,0); handle_wait_list_free(waits);
        retired(scenario);
        assert(!input_calls);
    } else if (!strcmp(scenario,"completed-write-close")) {
        struct handle *out = handle_output_new(writer,output,NULL,0);
        handle_write(out,"abc",3);
        HandleWaitList *waits = completion_wait();
        handle_free(out); /* Successful write also leaves a live worker. */
        handle_wait_activate(waits,0); handle_wait_list_free(waits);
        retired(scenario);
        char data[3]; DWORD count;
        assert(ReadFile(reader,data,sizeof(data),&count,NULL) && count==3);
        assert(!memcmp(data,"abc",3) && !output_calls);
    } else if (!strcmp(scenario,"transfer")) {
        struct handle *in = handle_input_new(reader,input,NULL,0);
        struct handle *out = handle_output_new(writer,output,NULL,0);
        unsigned char data[65536];
        for (size_t i=0; i<sizeof(data); i++) data[i]=(unsigned char)i;
        handle_write(out,data,sizeof(data));
        ULONGLONG deadline = GetTickCount64()+2000;
        while (received!=sizeof(data) || handle_backlog(out)) {
            assert(GetTickCount64()<deadline); pump();
        }
        assert(input_calls && output_calls);
        handle_free(out);
        assert(CloseHandle(writer)); writer=INVALID_HANDLE_VALUE;
        while (!eof_calls) { assert(GetTickCount64()<deadline); pump(); }
        handle_free(in); /* Already defunct: retirement is synchronous. */
        retired(scenario);
        assert(eof_calls==1 && received==sizeof(data));
    } else {
        fprintf(stderr,"Unknown scenario: %s\n",scenario); exit(2);
    }
    if (reader!=INVALID_HANDLE_VALUE) assert(CloseHandle(reader));
    if (writer!=INVALID_HANDLE_VALUE) assert(CloseHandle(writer));
    retired(scenario);
}

int main(int argc, char **argv)
{
    /* Warm the retained ready event and Windows' first-pipe initialization
     * before measuring exact OS handle balance across repeated lifetimes. */
    run("idle-output");
    DWORD baseline,after;
    assert(GetProcessHandleCount(GetCurrentProcess(),&baseline));
    static const char *const scenarios[]={"idle-output","input-eof-close","input-error-close","output-error-close",
        "completed-read-close","completed-write-close","transfer"};
    for (unsigned iteration=0; iteration<40; iteration++) {
        if (argc==2) run(argv[1]);
        else for (size_t i=0; i<lenof(scenarios); i++) run(scenarios[i]);
        assert(GetProcessHandleCount(GetCurrentProcess(),&after));
        assert(after==baseline);
    }
    puts("Handle I/O lifecycle and exact handle balance passed");
    return 0;
}
