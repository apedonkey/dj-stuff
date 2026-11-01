// club_collide_test.cpp: runs hook/club_collide.h's walking rules on the headset, as the same 10 cm flood fill that
// Scripts/Blender/club/club_collide.py runs offline, and prints the same state counts. Equal counts = the C++ rules match
// the Python ones (which the check image and the reachability checks were judged on).
//   build:  aarch64-linux-android32-clang++ -O2 -fPIE -pie -nostdlib++ -o out/club_collide_test tests/club_collide_test.cpp -lm
//   host:   any C++ compiler, e.g. MSVC: cl /O2 /EHsc tests\club_collide_test.cpp (the rules are plain doubles)
//   run:    adb push out/club_collide_test /data/local/tmp/cct && adb push club_collide.txt /data/local/tmp/
//           adb shell "chmod 755 /data/local/tmp/cct && /data/local/tmp/cct /data/local/tmp/club_collide.txt"
#include "../hook/club_collide.h"
#include <stdlib.h>

static const double GRID=10.0;
static double g_tops[64]; static int g_ntops=0;
static int top_idx(double t){ for(int i=0;i<g_ntops;i++) if(fabs(g_tops[i]-t)<1e-9) return i; g_tops[g_ntops]=t; return g_ntops++; }

enum { HSZ=1<<21, MAXST=HSZ/2, MAXE=4*MAXST };   // 1M states: the Dino field (62 x 91 m) at 10 cm
struct State { int16_t ix,iy,fi; };
static uint64_t g_key[HSZ]; static int32_t g_val[HSZ];
static State g_st[MAXST]; static int g_n=0;
static int32_t g_ef[MAXE], g_et[MAXE]; static int g_ne=0;
static int32_t g_cnt[MAXST+1], g_rev[MAXE]; static uint8_t g_back[MAXST];

static int find_or_add(int ix,int iy,int fi){
    uint64_t k=(((uint64_t)(uint16_t)ix<<32)|((uint64_t)(uint16_t)iy<<16)|(uint64_t)(uint16_t)fi)+1;
    uint32_t h=(uint32_t)((k*0x9E3779B97F4A7C15ull)>>40)&(HSZ-1);
    while(g_key[h]){ if(g_key[h]==k) return g_val[h]; h=(h+1)&(HSZ-1); }
    if(g_n>=MAXST){ printf("state table full\n"); exit(2); }
    g_key[h]=k; g_val[h]=g_n; g_st[g_n].ix=(int16_t)ix; g_st[g_n].iy=(int16_t)iy; g_st[g_n].fi=(int16_t)fi; return g_n++; }
// breadth-first from (sx, sy) on floor sz; g_st[0..g_n) are the states reached, g_ef/g_et the moves between them
static void walk(const CCMap* m,double sx,double sy,double sz,int gateOpen){
    memset(g_key,0,sizeof g_key); g_n=0; g_ne=0;
    find_or_add((int)lround(sx/GRID),(int)lround(sy/GRID),top_idx(sz));
    static const int D[4][2]={{1,0},{-1,0},{0,1},{0,-1}};
    for(int qi=0;qi<g_n;qi++){
        State st=g_st[qi]; double px=st.ix*GRID, py=st.iy*GRID, cur=g_tops[st.fi];
        for(int d=0;d<4;d++){ double nf; int hit;
            if(!cc_try(m,px,py,px+D[d][0]*GRID,py+D[d][1]*GRID,cur,gateOpen,&nf,&hit)) continue;
            int to=find_or_add(st.ix+D[d][0],st.iy+D[d][1],top_idx(nf));
            if(g_ne<MAXE){ g_ef[g_ne]=qi; g_et[g_ne]=to; g_ne++; } } } }
// how many reached states can't walk back to the start (state 0)
static int stuck(){
    memset(g_cnt,0,sizeof(int32_t)*(g_n+1));
    for(int e=0;e<g_ne;e++) g_cnt[g_et[e]+1]++;
    for(int i=0;i<g_n;i++) g_cnt[i+1]+=g_cnt[i];
    static int32_t fill[MAXST]; memcpy(fill,g_cnt,sizeof(int32_t)*g_n);
    for(int e=0;e<g_ne;e++) g_rev[fill[g_et[e]]++]=g_ef[e];
    memset(g_back,0,g_n); static int32_t q[MAXST]; int qh=0,qt=0; q[qt++]=0; g_back[0]=1;
    while(qh<qt){ int s=q[qh++]; for(int k=g_cnt[s];k<g_cnt[s+1];k++){ int p=g_rev[k]; if(!g_back[p]){ g_back[p]=1; q[qt++]=p; } } }
    return g_n-qt; }
static bool reached_near(double X,double Y,double top,double tol){
    for(int i=0;i<g_n;i++) if(fabs(g_st[i].ix*GRID-X)<=tol&&fabs(g_st[i].iy*GRID-Y)<=tol&&fabs(g_tops[g_st[i].fi]-top)<1.0) return true;
    return false; }
static char g_buf[1<<19];

int main(int argc,char** argv){
    if(argc<2){ printf("usage: %s club_collide.txt\n",argv[0]); return 2; }
    FILE* f=fopen(argv[1],"rb"); if(!f){ printf("can't open %s\n",argv[1]); return 2; }
    size_t n=fread(g_buf,1,sizeof g_buf-1,f); fclose(f); g_buf[n]=0;
    static CCMap m; bool ok=cc_parse(&m,g_buf);
    printf("parse %s: %d floors, %d boxes, %d circles, %d people, %d spots, %d bad lines; rules step %g head %g knee %g radius %g core %g\n",
           ok?"ok":"FAILED",m.nf,m.nb,m.nc,m.np,m.ns,m.bad,m.step,m.head,m.knee,m.radius,m.core);
    if(!ok||m.bad) return 1;
    const CCSpot *dk=cc_spot(&m,"decks"), *gf=cc_spot(&m,"guest_floor"), *gs=cc_spot(&m,"guest_stage");
    if(!dk){ printf("spot decks missing\n"); return 1; }
    walk(&m,dk->x,dk->y,dk->z,1);
    printf("host: %d grid states reached from the decks, %d with no way back\n",g_n,stuck());
    if(!gf||!gs){ printf("no guest_floor / guest_stage spots: the club-only checks are skipped\n"); return 0; }
    walk(&m,gf->x,gf->y,gf->z,0);
    int onStage=0; for(int i=0;i<g_n;i++) if(fabs(g_tops[g_st[i].fi])<1.0&&g_st[i].iy*GRID>-300.0) onStage++;
    printf("guest from the floor: %d states, %d on the stage\n",g_n,onStage);
    walk(&m,gs->x,gs->y,gs->z,0);
    printf("guest from Tribe's stage spawn: %d states, reaches the dance floor centre: %s\n",g_n,
           reached_near(0.0,-1200.0,-120.0,30.0)?"yes":"no");
    // the slide: a step into the barrier from the dance floor at an angle keeps its X part
    double ax,ay,nf; int hit; int r=cc_move(&m,-300.0,-390.0,6.0,8.0,-120.0,1,&ax,&ay,&nf,&hit);
    printf("slide along the barrier: mode %d, took (%.1f, %.1f), refused by %d\n",r,ax,ay,hit);
    // the gate: a guest walking straight at the shut door is refused by the gate; the host is not
    r=cc_move(&m,gf->x,-610.0,0.0,6.0,-120.0,0,&ax,&ay,&nf,&hit);
    printf("guest at the door: mode %d, gate refused: %s\n",r,cc_is_gate(&m,hit)?"yes":"no");
    r=cc_move(&m,gf->x,-610.0,0.0,6.0,-120.0,1,&ax,&ay,&nf,&hit);
    printf("host at the door: mode %d, took (%.1f, %.1f)\n",r,ax,ay);
    // the soft crowd: right beside the first dancer it is crowded and pushes you away from them; a step at their spine
    // is refused (a person, 3000+i), a step past them is not
    if(m.np>0){ const CCPerson* q=&m.p[0]; double cx,cy,nx,ny, d=cc_crowd(&m,q->x+20.0,q->y,q->z0,&cx,&cy,&nx,&ny);
        printf("crowd beside dancer 0: density %.2f, push (%.2f, %.2f), nearest at (%.0f, %.0f)\n",d,cx,cy,nx,ny);
        r=cc_move(&m,q->x+20.0,q->y,-8.0,0.0,q->z0,1,&ax,&ay,&nf,&hit);
        printf("step into dancer 0's core: mode %d, refused by %d (person: %s)\n",r,hit,hit>=3000?"yes":"no");
        r=cc_move(&m,q->x+20.0,q->y,0.0,8.0,q->z0,1,&ax,&ay,&nf,&hit);
        printf("step past dancer 0: mode %d, took (%.1f, %.1f)\n",r,ax,ay); }
    return 0; }
