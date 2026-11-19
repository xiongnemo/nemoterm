/* Nemoterm's Linux side of a redirected WSL PTY. No network or persistent
 * state. The caller owns stdin/stdout, supplying the initial grid and argv.
 * Terminal output is an unmodified byte stream. See README.md for input. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pty.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

enum { DATA = 1, RESIZE = 2, CAPACITY = 16384, BAD = 125 };

typedef struct {
    unsigned char header[3], data[CAPACITY];
    size_t header_used, used, length, offset;
} Frame;

static unsigned number(const unsigned char *p) { return ((unsigned)p[0] << 8) | p[1]; }
static bool dimension(unsigned value) { return value > 0 && value <= 32767; }
static int grid_arg(const char *s)
{
    unsigned n = 0;
    if (!*s) return 0;
    for (; *s; s++) {
        if (*s < '0' || *s > '9') return 0;
        n = n*10 + (unsigned)(*s-'0');
        if (n > 32767) return 0;
    }
    return (int)n;
}
static int nonblock(int fd)
{
    int f = fcntl(fd, F_GETFL);
    return f == -1 ? -1 : fcntl(fd,F_SETFL,f|O_NONBLOCK);
}
static bool transient(void) { return errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK; }
static bool ready(const Frame *f) { return f->length && f->used == f->length; }
static void clear_frame(Frame *f) { f->header_used = f->length = f->used = f->offset = 0; }

/* Read only the missing part. Never wait for a partial header/payload while
 * the slave has output. Never read through the previous frame's write. */
static int read_frame(Frame *f)
{
    bool header = f->header_used < sizeof(f->header);
    unsigned char *buffer = header ? f->header : f->data;
    size_t *used = header ? &f->header_used : &f->used;
    size_t limit = header ? sizeof(f->header) : f->length;
    ssize_t n = read(STDIN_FILENO,buffer+*used,limit-*used);
    if (n < 0) return transient() ? 1 : -1;
    if (!n) {
        if (!f->header_used) return 0;
        errno = EPROTO; return -1;
    }
    *used += (size_t)n;
    if (header && *used == sizeof(f->header)) {
        f->length = number(f->header+1);
        if (!(f->header[0] == DATA && f->length && f->length <= CAPACITY) &&
            !(f->header[0] == RESIZE && f->length == 4)) {
            errno = EPROTO; return -1;
        }
    }
    return 1;
}

enum end { SLAVE_EOF, OWNER_CLOSED, FAILED };
static enum end pump(int master)
{
    Frame f = {0};
    unsigned char output[CAPACITY];
    size_t out_at = 0, out_end = 0;
    bool eof = false;
    if (nonblock(master) < 0 || nonblock(STDIN_FILENO) < 0 || nonblock(STDOUT_FILENO) < 0)
        return FAILED;
    for (;;) {
        if (eof && out_at == out_end) return SLAVE_EOF;
        if (!eof && ready(&f) && f.header[0] == RESIZE) {
            struct winsize ws = {.ws_col=number(f.data), .ws_row=number(f.data+2)};
            if (!dimension(ws.ws_col) || !dimension(ws.ws_row)) { errno=EPROTO; return FAILED; }
            if (ioctl(master,TIOCSWINSZ,&ws) < 0) { if (errno==EINTR) continue; return FAILED; }
            clear_frame(&f);
        }
        const bool input = !eof && !ready(&f);
        const short io = (out_at == out_end && !eof ? POLLIN : 0) |
                         (!eof && ready(&f) ? POLLOUT : 0);
        /* A zero event mask still watches peer closure. Removing these fds
         * while a slave blocks our writes can strand its owner on tab close. */
        struct pollfd fd[] = {{eof ? -1 : STDIN_FILENO,input ? POLLIN : 0,0},
                             {io ? master : -1,io,0},
                             {STDOUT_FILENO,out_at != out_end ? POLLOUT : 0,0}};
        if (poll(fd,3,-1) < 0) { if (errno == EINTR) continue; return FAILED; }
        if ((fd[0].revents|fd[1].revents|fd[2].revents) & POLLNVAL) { errno=EBADF; return FAILED; }
        if ((fd[2].revents & (POLLHUP|POLLERR)) ||
            (!input && (fd[0].revents & (POLLHUP|POLLERR)))) return OWNER_CLOSED;
        if (fd[2].revents & POLLOUT) {
            ssize_t n=write(STDOUT_FILENO,output+out_at,out_end-out_at);
            if (n>0) out_at+=(size_t)n;
            else if (n<0 && errno==EPIPE) return OWNER_CLOSED;
            else if (!n || !transient()) return FAILED;
        }
        if (out_at==out_end && (fd[1].revents & (POLLIN|POLLHUP|POLLERR))) {
            ssize_t n=read(master,output,sizeof(output));
            if (n>0) { out_at=0; out_end=(size_t)n; }
            else if (!n || errno==EIO) eof=true; /* Linux PTY's last slave closed. */
            else if (!transient()) return FAILED;
        }
        if (!eof && ready(&f) && (fd[1].revents&POLLOUT)) {
            ssize_t n=write(master,f.data+f.offset,f.length-f.offset);
            if (n>0) { f.offset+=(size_t)n; if (f.offset==f.length) clear_frame(&f); }
            else if (n<0 && errno==EIO) clear_frame(&f); /* drain the last slave output */
            else if (!n || !transient()) return FAILED;
        }
        if (input && fd[0].revents && !eof) {
            int r=read_frame(&f);
            if (r<=0) return r==0 ? OWNER_CLOSED : FAILED;
        }
    }
}

static int wait_child(pid_t child, bool cancel)
{
    int status=0; pid_t r;
    /* Apps may close their tty before they exit. Preserve their eventual
     * status as long as the owner is connected; still honor a later close.
     * Probe only in this post-EOF interval, never in the normal pump. */
    while (!cancel) {
        r=waitpid(child,&status,WNOHANG);
        if (r==child) goto done;
        if (r<0) { if (errno==EINTR) continue; return BAD; }
        struct pollfd owner[]={{STDIN_FILENO,0,0},{STDOUT_FILENO,0,0}};
        int n=poll(owner,2,100);
        if (n<0 && errno==EINTR) continue;
        if (n!=0) cancel=true;
    }
    {
        /* Only our direct, unreaped child. Closing the master already gives
         * the terminal's foreground session its normal hangup semantics. */
        kill(child,SIGHUP);
        for (int i=0; i<50; i++) {
            r=waitpid(child,&status,WNOHANG);
            if (r==child) goto done;
            if (r<0 && errno!=EINTR) return BAD;
            struct timespec pause={0,20000000}; nanosleep(&pause,NULL);
        }
        kill(child,SIGKILL);
    }
    do r=waitpid(child,&status,0); while (r<0 && errno==EINTR);
    if (r!=child) return BAD;
  done:
    return WIFEXITED(status) ? WEXITSTATUS(status) : WIFSIGNALED(status) ? 128+WTERMSIG(status) : BAD;
}

int main(int argc, char **argv)
{
    if (argc<4 || isatty(STDIN_FILENO) || isatty(STDOUT_FILENO)) {
        fputs("expected redirected pipes and COLS ROWS PROGRAM [ARG ...]\n",stderr); return BAD;
    }
    struct winsize ws={.ws_col=grid_arg(argv[1]),.ws_row=grid_arg(argv[2])};
    if (!ws.ws_col || !ws.ws_row) { fputs("invalid initial dimensions\n",stderr); return BAD; }
    int master=-1;
    pid_t child=forkpty(&master,NULL,NULL,&ws);
    if (child<0) { perror("forkpty"); return BAD; }
    if (!child) {
        execvp(argv[3],argv+3);
        int code=errno==ENOENT ? 127 : 126; perror("execvp"); _exit(code);
    }
    signal(SIGPIPE,SIG_IGN); /* keep the child's inherited signal policy */
    enum end why=pump(master);
    if (why==FAILED) perror("PTY transport");
    close(master);
    int code=wait_child(child,why!=SLAVE_EOF);
    return why==FAILED ? BAD : code;
}
