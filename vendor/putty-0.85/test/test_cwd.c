/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static bool update(NemoCwd *cwd,unsigned osc,const char *s)
{ return nemo_cwd_update(cwd,osc,s,strlen(s)); }
static void expect_path(Mock *mk,NemoCwd *cwd,const char *path,const char *host)
{
    SEQUAL(cwd->path?cwd->path:"",path);SEQUAL(cwd->host?cwd->host:"",host);
    IEQUAL(nemo_cwd_memory(cwd)<=NEMO_CWD_PATH_MAX+NEMO_CWD_HOST_MAX+2,true);
}
static void test_metadata(Mock *mk)
{
    test_context(mk,"directory formats, escapes and host provenance");
    NemoCwd d={0};IEQUAL(nemo_cwd_memory(&d),0);
    IEQUAL(update(&d,7,"file://Workstation/C:/a%20b/%E4%B8%AD/%2525"),true);
    expect_path(mk,&d,"/C:/a b/\xe4\xb8\xad/%25","Workstation");
    char *s=nemo_cwd_uri(&d);SEQUAL(s,"file://Workstation/C:/a%20b/%E4%B8%AD/%2525");sfree(s);
    s=nemo_cwd_native(&d,"workstation","workstation.example",false);SEQUAL(s,"C:\\a b\\\xe4\xb8\xad\\%25");sfree(s);
    IEQUAL(nemo_cwd_native(&d,"other","other.example",false)==NULL,true);
    IEQUAL(update(&d,9,"9;\"D:\\a b\\foo;bar\""),true);
    expect_path(mk,&d,"D:\\a b\\foo;bar","");
    s=nemo_cwd_uri(&d);SEQUAL(s,"file:///D:/a%20b/foo%3Bbar");sfree(s);
    IEQUAL(update(&d,633,"P;Cwd=C:\\x5cA\\x3bB\\\\tail;opaque-nonce"),true);
    expect_path(mk,&d,"C:\\A;B\\tail","");
    IEQUAL(update(&d,633,"P;Cwd=C:\\X5CA\\X3BB"),true);
    expect_path(mk,&d,"C:\\A;B","");
    IEQUAL(update(&d,1337,"RemoteHost=user@remote.example"),true);
    IEQUAL(update(&d,1337,"CurrentDir=/home/user/a b"),true);
    expect_path(mk,&d,"/home/user/a b","remote.example");
    s=nemo_cwd_uri(&d);SEQUAL(s,"file://remote.example/home/user/a%20b");sfree(s);
    IEQUAL(nemo_cwd_native(&d,"local","local.example",true)==NULL,true);
    IEQUAL(update(&d,7,"file://localhost/c/Users/me"),true);
    IEQUAL(nemo_cwd_native(&d,"local","local.example",false)==NULL,true);
    s=nemo_cwd_native(&d,"local","local.example",true);SEQUAL(s,"c:\\Users\\me");sfree(s);
    IEQUAL(update(&d,7,"file://[::1]/C:/work"),true);IEQUAL(nemo_cwd_local(&d,"x","y"),true);
    IEQUAL(update(&d,7,"file://host.example/C:/work"),true);IEQUAL(nemo_cwd_local(&d,"host","HOST.EXAMPLE"),true);
    IEQUAL(update(&d,633,"P;Cwd="),true);IEQUAL(nemo_cwd_uri(&d)==NULL,true);
    nemo_cwd_clear(&d);IEQUAL(nemo_cwd_memory(&d),0);
}
static void test_rejection(Mock *mk)
{
    test_context(mk,"malformed metadata is atomic and never becomes a local path");
    NemoCwd d={0};update(&d,7,"file://localhost/C:/keep");
    struct { unsigned osc;const char *text; } cases[]={
        {7,""},{7,"http://host/C:/bad"},{7,"file://host"},{7,"file://user@host/C:/bad"},
        {7,"file://host:22/C:/bad"},{7,"file:///C:/a#fragment"},{7,"file:///C:/a?query"},
        {7,"file:///C:/\\bad"},{7,"file:///C:/%"},{7,"file:///C:/%x1"},{7,"file:///C:/%00bad"},
        {7,"file:///C:/%0abad"},{7,"file:///C:/%C0%AF"},{7,"file:///C:/%ED%A0%80"},
        {7,"file:///C:/%F4%90%80%80"},{7,"file:///C:/%E2%82"},
        {9,"4;1;50"},{9,"9;relative"},{9,"9;\"C:\\bad"},{9,"9;\\\\server\\share"},
        {633,"P;Cwd=relative"},{633,"P;Cwd=C:\\xGGbad"},{633,"P;Cwd=C:\\x00bad"},
        {633,"P;Other=/tmp"},{633,"A"},{1337,"CurrentDir=relative"},{1337,"RemoteHost=bad/host"},
        {1337,"RemoteHost=user@host@other"},{1337,"SetMark"},{8,";file:///C:/not-cwd"},
    };
    for (size_t i=0;i<lenof(cases);i++) {
        test_context(mk,"reject OSC %u %s",cases[i].osc,cases[i].text);
        IEQUAL(update(&d,cases[i].osc,cases[i].text),false);
        expect_path(mk,&d,"/C:/keep","localhost");
    }
    const char embedded[]="file:///C:/ok\0hidden";
    IEQUAL(nemo_cwd_update(&d,7,embedded,sizeof(embedded)-1),false);
    IEQUAL(update(&d,7,"file:///C:/bad%3Astream"),true);
    IEQUAL(nemo_cwd_native(&d,"local","",false)==NULL,true);
    IEQUAL(update(&d,7,"file:///C:/bad%3Fname"),true);
    IEQUAL(nemo_cwd_native(&d,"local","",false)==NULL,true);
    IEQUAL(update(&d,7,"file:////server/share"),true);
    IEQUAL(nemo_cwd_native(&d,"local","",false)==NULL,true);
    nemo_cwd_clear(&d);
}
static void test_limits(Mock *mk)
{
    test_context(mk,"bounded paths and repeated replacement");
    NemoCwd d={0};char *s=snewn(NEMO_CWD_OSC_MAX+2,char);
    memcpy(s,"file:///",8);memset(s+8,'a',NEMO_CWD_PATH_MAX-1);s[NEMO_CWD_PATH_MAX+7]=0;
    IEQUAL(update(&d,7,s),true);IEQUAL(strlen(d.path),NEMO_CWD_PATH_MAX);
    s[NEMO_CWD_PATH_MAX+7]='a';s[NEMO_CWD_PATH_MAX+8]=0;
    IEQUAL(update(&d,7,s),false);IEQUAL(strlen(d.path),NEMO_CWD_PATH_MAX);
    memset(s,'a',NEMO_CWD_OSC_MAX+1);s[NEMO_CWD_OSC_MAX+1]=0;
    IEQUAL(update(&d,1337,s),false);
    for (unsigned i=0;i<10000;i++) {
        char sequence[128];snprintf(sequence,sizeof(sequence),"file://localhost/C:/cwd-%u",i);
        IEQUAL(update(&d,7,sequence),true);
        IEQUAL(nemo_cwd_memory(&d)<128,true);
    }
    sfree(s);nemo_cwd_clear(&d);IEQUAL(nemo_cwd_memory(&d),0);
}
static void test_terminal_metadata(Mock *mk)
{
    test_context(mk,"OSC dispatch, fragmentation, cancellation and metadata lifetime");
    Terminal *t=mk->term;NemoCwd *d=&t->working_directory;nemo_cwd_clear(d);
    term_size(t,12,40,100);
    term_data_fragmented(t,"\033]7;file://localhost/C:/one%20two\a");expect_path(mk,d,"/C:/one two","localhost");
    term_data_fragmented(t,"\033]9;9;\"D:\\unicode \xe4\xb8\xad\"\033\\");expect_path(mk,d,"D:\\unicode \xe4\xb8\xad","");
    term_data_fragmented(t,"\033]633;P;Cwd=C:\\x5cnew\\x3bname\a");expect_path(mk,d,"C:\\new;name","");
    term_data_fragmented(t,"\033]1337;RemoteHost=user@other\a\033]1337;CurrentDir=/remote/path\033\\");
    expect_path(mk,d,"/remote/path","other");
    term_data_fragmented(t,"\033]7;file:///C:/cancel\030\033]7;file:///C:/cancel\032");
    term_data_fragmented(t,"\033P7;file:///C:/dcs\033\\\033_7;file:///C:/apc\033\\");
    expect_path(mk,d,"/remote/path","other");
    term_data_fragmented(t,"\033[?1049h\033[?1049l\033[!p\033c");term_size(t,18,60,200);term_clrsb(t);
    expect_path(mk,d,"/remote/path","other");
    char *large=snewn(NEMO_CWD_OSC_MAX+100,char);strcpy(large,"\033]7;file:///C:/");
    size_t prefix=strlen(large);
    memset(large+prefix,'a',NEMO_CWD_OSC_MAX);large[NEMO_CWD_OSC_MAX+prefix]=0;
    char *overflow=dupcat(large,"\aZ");term_data_fragmented(t,overflow);sfree(large);sfree(overflow);
    expect_path(mk,d,"/remote/path","other");
    term_data_fragmented(t,"\033]7;file:///C:/recovered\033\\");expect_path(mk,d,"/C:/recovered","");
    nemo_cwd_clear(d);IEQUAL(nemo_cwd_memory(d),0);
}
int main(void)
{
    Mock *mk=mock_new();mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    test_metadata(mk);test_rejection(mk);test_limits(mk);test_terminal_metadata(mk);
    bool failed=mk->any_test_failed;mock_free(mk);
    puts(failed?"Directory metadata suite FAILED":"Directory metadata suite passed");return failed?1:0;
}
