/* Independent ncurses database lifetime observation; no terminal input/UI. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <term.h>

static void snapshot(const char *phase)
{
    static const char *names[] = {"kf1", "kf5", "kf12", "kcuu1", "khome", "kent"};
    printf("{\"phase\":\"%s\",\"current_database\":%s,\"strings\":{",
           phase, cur_term ? "true" : "false");
    for (size_t i=0; i<sizeof(names)/sizeof(*names); i++) {
        char *value=tigetstr((char *)names[i]);
        printf("%s\"%s\":", i ? "," : "", names[i]);
        if (!value || value==(char *)-1) {
            printf("null");
        } else {
            putchar('"');
            for (const unsigned char *p=(const unsigned char *)value; *p; p++)
                printf("%02x", (unsigned)*p);
            putchar('"');
        }
    }
    printf("}}\n");
}

int main(int argc, char **argv)
{
    int status;
    if (argc!=2) return 2;
    if (setupterm("xterm",1,&status)!=0 || status!=1) return 3;
    TERMINAL *initial=cur_term;
    snapshot("initial-xterm");
    if (setupterm(argv[1],1,&status)!=0 || status!=1) return 4;
    snapshot("after-setup-selected");
    if (del_curterm(cur_term)!=0) return 5;
    snapshot("after-delete-current");
    if (setupterm(argv[1],1,&status)!=0 || status!=1) return 6;
    snapshot("after-setup-again");
    if (del_curterm(cur_term)!=0) return 7;
    if (del_curterm(initial)!=0) return 8;
    return 0;
}
