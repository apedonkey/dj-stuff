// freeze.cpp: a freeze recorder (the Halloween session, 2026-10-27). dumper.cpp includes it after stream.cpp, calls
// freeze_beat() from both game-thread tick lines and freeze_poll() from the poll loop. On by default; the file
// tribemod/freeze_off keeps it off (read once, when it would start). Logs [FREEZE] and appends to tribemod/freeze_log.txt.
//
// Why: Tribe's picture froze for good while the music played on (10-18 on RED EYE, twice on 10-19 on Graveyard, 10-27
// 18:18:29 on Graveyard 0.2 s after a click in the song list). The game and render threads were asleep (0 % CPU), but
// nothing outside the app can say where they wait: debuggerd needs root, run-as needs a debuggable APK, and Tribe writes
// no log file. From inside the process it can be done: a watchdog thread notices that the game thread stopped ticking,
// signals the threads that matter, and the handler (on each of them) walks its own frame-pointer chain. libUnreal.so
// keeps frame records (stp x29,x30 / add x29,sp in every prologue read so far), so the chain names the Tribe function
// that waits and its callers.
//
// When: 4 s without a game-thread tick (sample 1), again at 30 s (sample 2: still in the same place?), then nothing until
// it ticks again ("ticking again after N s": a headset-off pause also stops the ticks, and it comes back). Plus one
// self-test of the game thread 20 s after the first tick, so every launch shows that the recorder works.
// Which threads: the game thread, every RenderThread / RHIThread / TribeXR.TribeXR thread, and the 3 busiest of the rest
// (CPU over 1 s); at most 12.
// The handler reads its own registers, reads the stack through process_vm_readv (the kernel copies or fails, so a bad
// frame pointer can't fault), takes no lock and fills one slot; a thread that doesn't answer in 300 ms is skipped. The
// signal is a real-time one that was free (SIG_DFL) when the recorder started, re-checked before every send (an RT
// signal's default action ends the process).
#include <sys/ucontext.h>
#include <sys/uio.h>
#include <sys/prctl.h>

#define FRZ_MAXF 48                                   // frames per thread
#define FRZ_MAXT 12                                   // threads per sample
struct FrzSlot { pid_t tid; int n; uintptr_t pc, lr, sp, fp; uintptr_t f[FRZ_MAXF]; };
static FrzSlot g_frzSlot; static volatile sig_atomic_t g_frzBusy=0, g_frzSeq=0, g_frzDone=0;
static volatile uint32_t g_frzBeat=0; static volatile pid_t g_frzGameTid=0; static int g_frzSig=0;

// ---- GAME thread, every frame (both tick lines)
static void freeze_beat(){ if(!g_frzGameTid) g_frzGameTid=my_tid(); g_frzBeat=g_frzBeat+1; }

// ---- the signal handler, on the sampled thread
static bool frz_read(uintptr_t a,void* out,size_t n){              // never faults: the kernel copies or refuses
    struct iovec l={out,n}, r={(void*)a,n}; return process_vm_readv(getpid(),&l,1,&r,1,0)==(ssize_t)n; }
static void frz_handler(int,siginfo_t*,void* ucv){
    if(__sync_lock_test_and_set(&g_frzBusy,1)) return;             // a late answer is still being written: skip this one
    const ucontext_t* uc=(const ucontext_t*)ucv; FrzSlot* s=&g_frzSlot;
    s->tid=(pid_t)syscall(SYS_gettid); s->pc=uc->uc_mcontext.pc; s->lr=uc->uc_mcontext.regs[30];
    s->sp=uc->uc_mcontext.sp; s->fp=uc->uc_mcontext.regs[29];
    int n=0; uintptr_t fp=s->fp;                                    // frame record: [fp] = the caller's fp, [fp+8] = return address
    while(n<FRZ_MAXF&&fp>=s->sp&&fp<s->sp+(8u<<20)&&!(fp&7)){
        uintptr_t rec[2]; if(!frz_read(fp,rec,16)) break;
        s->f[n++]=rec[1]; if(rec[0]<=fp) break; fp=rec[0]; }
    s->n=n; __sync_synchronize(); g_frzDone=g_frzSeq; __sync_lock_release(&g_frzBusy); }

// ---- WATCHDOG thread
struct FrzMap { uintptr_t lo, hi, off; char name[64]; };
static FrzMap* g_frzMaps=0; static int g_frzNMaps=0;
static void frz_load_maps(){                                         // the executable mappings, for naming addresses
    if(!g_frzMaps) g_frzMaps=(FrzMap*)malloc(sizeof(FrzMap)*2048);
    if(!g_frzMaps) return;
    g_frzNMaps=0; FILE* f=fopen("/proc/self/maps","r"); if(!f) return; char line[700];
    while(fgets(line,sizeof line,f)&&g_frzNMaps<2048){ unsigned long lo,hi,off; char perm[8], path[512]; path[0]=0;
        if(sscanf(line,"%lx-%lx %7s %lx %*s %*s %511[^\n]",&lo,&hi,perm,&off,path)<4||perm[2]!='x') continue;
        FrzMap* m=&g_frzMaps[g_frzNMaps++]; m->lo=lo; m->hi=hi; m->off=off;
        const char* b=strrchr(path,'/'); snprintf(m->name,sizeof m->name,"%s",b?b+1:(path[0]?path:"[anon]")); }
    fclose(f); }
// an address as the Ghidra project sees it: libUnreal = "UE <Ghidra address>" (vaddr + 0xFF000), others = lib+file offset
static void frz_where(uintptr_t a,char* out,size_t cap){
    a&=0x00FFFFFFFFFFFFFFull;
    for(int i=0;i<g_frzNMaps;i++){ const FrzMap* m=&g_frzMaps[i]; if(a<m->lo||a>=m->hi) continue;
        if(g_base&&strstr(m->name,"libUnreal.so")) snprintf(out,cap,"UE %08lx",(unsigned long)(a-g_base+0xFF000));
        else snprintf(out,cap,"%s+%lx",m->name,(unsigned long)(a-m->lo+m->off));
        return; }
    snprintf(out,cap,"?%lx",(unsigned long)a); }
static bool frz_task(pid_t tid,char* comm,size_t cap,char* state,unsigned long* cpu){   // name, state, utime+stime
    char p[64], b[600]; snprintf(p,sizeof p,"/proc/self/task/%d/stat",(int)tid); int fd=open(p,O_RDONLY); if(fd<0) return false;
    int n=(int)read(fd,b,sizeof b-1); close(fd); if(n<=0) return false; b[n]=0;
    char* l=strchr(b,'('); char* r=strrchr(b,')'); if(!l||!r||r<l) return false;
    size_t k=(size_t)(r-l-1); if(k>=cap) k=cap-1; memcpy(comm,l+1,k); comm[k]=0;
    char st=0; unsigned long ut=0, kt=0;                             // after the name: state ppid pgrp session tty tpgid flags
    if(sscanf(r+2,"%c %*d %*d %*d %*d %*d %*u %*u %*u %*u %*u %lu %lu",&st,&ut,&kt)!=3) return false;   // ... utime stime
    *state=st; *cpu=ut+kt; return true; }
static int frz_capture(pid_t tid,FrzSlot* out){                     // 1 answered, 0 no answer, -1 the signal isn't ours now
    struct sigaction cur; if(sigaction(g_frzSig,0,&cur)!=0||!(cur.sa_flags&SA_SIGINFO)||(void*)cur.sa_sigaction!=(void*)frz_handler) return -1;
    int k=g_frzSeq+1; g_frzSeq=k; __sync_synchronize();
    if(syscall(SYS_tgkill,getpid(),tid,g_frzSig)!=0) return 0;
    for(int i=0;i<60;i++){ usleep(5000); if(g_frzDone==k&&g_frzSlot.tid==tid&&!g_frzBusy){ __sync_synchronize(); *out=g_frzSlot; return 1; } }
    return 0; }
static FILE* frz_open(){                                             // tribemod/freeze_log.txt, rotated at 512 KB
    char p[600], q[600]; snprintf(p,sizeof p,"%s/freeze_log.txt",OUTDIR); struct stat st;
    if(stat(p,&st)==0&&st.st_size>512*1024){ snprintf(q,sizeof q,"%s/freeze_log.1.txt",OUTDIR); rename(p,q); }
    return fopen(p,"a"); }
static void frz_stamp(char* b,size_t cap){ time_t t=time(0); struct tm tm; localtime_r(&t,&tm); strftime(b,cap,"%Y-%m-%d %H:%M:%S",&tm); }
static void frz_report(double still,int sample){                    // sample 0 = the self-test (the game thread only)
    frz_load_maps();
    struct T { pid_t tid; char comm[20]; char st; unsigned long c0, c1; } *ts=(T*)malloc(sizeof(T)*512); if(!ts) return;
    int nt=0; DIR* d=opendir("/proc/self/task");
    if(d){ struct dirent* e; while((e=readdir(d))&&nt<512){ int tid=atoi(e->d_name); if(tid<=0) continue;
            T* t=&ts[nt]; t->tid=tid; if(frz_task(tid,t->comm,sizeof t->comm,&t->st,&t->c0)){ t->c1=t->c0; nt++; } }
        closedir(d); }
    if(sample>0){ usleep(1000000); for(int i=0;i<nt;i++){ char c[20], s; unsigned long v; if(frz_task(ts[i].tid,c,sizeof c,&s,&v)){ ts[i].c1=v; ts[i].st=s; } } }
    pid_t pick[FRZ_MAXT]; int np=0, gi=-1; pid_t gt=g_frzGameTid;
    for(int i=0;i<nt;i++) if(ts[i].tid==gt) gi=i;
    if(gt) pick[np++]=gt;
    for(int i=0;i<nt&&np<FRZ_MAXT-3&&sample>0;i++){ const char* c=ts[i].comm; if(ts[i].tid==gt) continue;
        if(!strncmp(c,"RenderThread",12)||!strncmp(c,"RHIThread",9)||!strcmp(c,"TribeXR.TribeXR")) pick[np++]=ts[i].tid; }
    for(int r=0;r<3&&sample>0;r++){ int best=-1; unsigned long bd=4;  // the busiest others (over 4 % of a core)
        for(int i=0;i<nt;i++){ bool had=false; for(int j=0;j<np;j++) if(pick[j]==ts[i].tid) had=true;
            unsigned long dd=ts[i].c1-ts[i].c0; if(!had&&dd>bd){ bd=dd; best=i; } }
        if(best>=0&&np<FRZ_MAXT) pick[np++]=ts[best].tid; }
    char when[32]; frz_stamp(when,sizeof when); FILE* f=frz_open();
    if(sample>0){ LOGI("[FREEZE] sample %d: the game thread (%d) hasn't ticked for %.1f s; %d thread(s)",sample,(int)gt,still,np);
        if(f) fprintf(f,"\n== %s sample %d: the game thread (%d) hasn't ticked for %.1f s (a headset-off pause also does this)\n",when,sample,(int)gt,still); }
    else if(f) fprintf(f,"\n== %s self-test: the game thread (%d) while it ticks\n",when,(int)gt);
    for(int j=0;j<np;j++){
        char comm[20]="?", st='?'; unsigned long dc=0; for(int i=0;i<nt;i++) if(ts[i].tid==pick[j]){ snprintf(comm,sizeof comm,"%s",ts[i].comm); st=ts[i].st; dc=ts[i].c1-ts[i].c0; }
        static FrzSlot s; int rc=frz_capture(pick[j],&s);
        if(rc!=1){ LOGI("[FREEZE] %s %d (%c): %s",comm,(int)pick[j],st,rc<0?"the signal isn't ours any more: stopped":"no answer in 300 ms");
            if(f) fprintf(f,"-- %s %d (%c): %s\n",comm,(int)pick[j],st,rc<0?"the signal isn't ours any more":"no answer in 300 ms");
            if(rc<0) break; continue; }
        uintptr_t fr[FRZ_MAXF+2]; int nf=0; fr[nf++]=s.pc; if(s.n==0||s.lr!=s.f[0]) fr[nf++]=s.lr;
        for(int i=0;i<s.n;i++) fr[nf++]=s.f[i];
        static char line[3600]; int k=snprintf(line,sizeof line,"%s %d (%c, %lu%% CPU): ",comm,(int)pick[j],st,sample>0?dc:0);
        if(f) fprintf(f,"-- %s %d (%c, %lu%% CPU): pc %lx lr %lx sp %lx fp %lx, %d frame(s)\n",comm,(int)pick[j],st,sample>0?dc:0,
                      (unsigned long)s.pc,(unsigned long)s.lr,(unsigned long)s.sp,(unsigned long)s.fp,s.n);
        for(int i=0;i<nf;i++){ char w[96]; frz_where(fr[i],w,sizeof w);
            if(f) fprintf(f,"   %s %s\n",i==0?"pc":(i==1&&nf>s.n+1)?"lr":"  ",w);
            if(k<(int)sizeof line-100) k+=snprintf(line+k,sizeof line-k,"%s%s",i?" < ":"",w); }
        LOGI("[FREEZE] %s%s",sample>0?"":"self-test: ",line); }
    if(f) fclose(f);
    if(gi<0&&gt) LOGI("[FREEZE] the game thread %d isn't in /proc/self/task any more",(int)gt);
    free(ts); }
static double frz_now(){ struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec+t.tv_nsec*1e-9; }
static void* frz_thread(void*){
    prctl(PR_SET_NAME,"tribemod_frz",0,0,0);
    uint32_t last=g_frzBeat; double lastT=frz_now(), start=lastT; int sampled=0; bool tested=false;
    for(;;){ usleep(500000); double now=frz_now(); uint32_t b=g_frzBeat;
        if(b!=last){ last=b;
            if(sampled){ LOGI("[FREEZE] the game thread is ticking again after %.1f s (a pause, not a freeze)",now-lastT);
                FILE* f=frz_open(); if(f){ char w[32]; frz_stamp(w,sizeof w); fprintf(f,"== %s ticking again after %.1f s\n",w,now-lastT); fclose(f); } }
            lastT=now; sampled=0;
            if(!tested&&now-start>=20.0){ tested=true; frz_report(0,0); }
            continue; }
        double still=now-lastT;
        if((sampled==0&&still>=4.0)||(sampled==1&&still>=30.0)){ sampled++; frz_report(still,sampled); } }
    return 0; }

// ---- POLL thread: start the recorder once the game thread has ticked
static void freeze_poll(){
    static bool done=false; if(done||!g_frzGameTid) return; done=true;
    char p[600]; snprintf(p,sizeof p,"%s/freeze_off",OUTDIR);
    if(access(p,F_OK)==0){ LOGI("[FREEZE] tribemod/freeze_off is there: the recorder stays off"); return; }
    for(int s=SIGRTMIN+6;s<=SIGRTMAX-2&&!g_frzSig;s++){ struct sigaction cur; if(sigaction(s,0,&cur)!=0) continue;
        if(cur.sa_handler!=SIG_DFL||(cur.sa_flags&SA_SIGINFO)) continue;   // somebody's signal
        struct sigaction sa; memset(&sa,0,sizeof sa); sa.sa_sigaction=frz_handler; sa.sa_flags=SA_SIGINFO|SA_RESTART; sigemptyset(&sa.sa_mask);
        if(sigaction(s,&sa,0)==0) g_frzSig=s; }
    if(!g_frzSig){ LOGI("[FREEZE] no free real-time signal: the recorder stays off"); return; }
    pthread_attr_t a; pthread_attr_init(&a); pthread_attr_setstacksize(&a,256*1024); pthread_attr_setdetachstate(&a,PTHREAD_CREATE_DETACHED);
    pthread_t th; int rc=pthread_create(&th,&a,frz_thread,nullptr); pthread_attr_destroy(&a);
    LOGI("[FREEZE] recorder %s: signal %d, game thread %d; a sample after 4 s and 30 s without a tick, a self-test in 20 s (tribemod/freeze_log.txt)",
         rc==0?"on":"FAILED to start",g_frzSig,(int)g_frzGameTid); }
