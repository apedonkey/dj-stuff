// club_collide.h: the REACTOR walking rules, engine-free. Used by hook/club.cpp; tests/club_collide_test.cpp runs them
// on the headset against Scripts/Blender/club/club_collide.py (which states the rules and writes club_collide.txt).
// World cm, doubles (the Python check uses doubles, so both agree to the last grid cell).
#pragma once
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

// CC_MAXP 4608 (the Dino Stage's 4,446 dancers) with a person grid: CC_GRID^2 cells of 1 m (larger if the crowd is
// wider than CC_GRID m), so a query visits only the people near it. CC_CAND: the most people one query may visit before
// it falls back to a full scan.
enum { CC_MAXF=128, CC_MAXB=512, CC_MAXC=512, CC_MAXP=4608, CC_MAXS=8, CC_GRID=128, CC_CAND=1024 };
struct CCFloor { double x0,y0,x1,y1,top,bot; };                 // walkable top of a solid reaching down to bot
struct CCBox   { double x0,y0,x1,y1,z0,z1; int gate; };         // gate: while shut, blocks only moves toward +Y
struct CCCirc  { double x,y,r,z0,z1; };
struct CCPerson{ double x,y,r,z0,z1; };                        // a dancer: soft, solid only within core of the spine
struct CCSpot  { char name[24]; double x,y,z,yaw; };
struct CCMap   { double step,head,knee,radius,core; int nf,nb,nc,np,ns,bad; CCFloor f[CC_MAXF]; CCBox b[CC_MAXB];
                 CCCirc c[CC_MAXC]; CCPerson p[CC_MAXP]; CCSpot s[CC_MAXS];
                 double pmaxr,gox,goy,gcell; int gnx,gny; int gstart[CC_GRID*CC_GRID+1]; int gidx[CC_MAXP]; };   // the grid

// the people grid (cc_parse builds it): cells of gcell cm from (gox, goy), each cell's people in ascending index order
// in gidx[gstart[c] .. gstart[c+1]). A query collects the cells it touches, in ascending index order, so the person loops
// see exactly the people a full scan would have kept, in the same order: same results, bit for bit.
static int cc_gcell(const CCMap* m,double v,double o,int n){ double c=floor((v-o)/m->gcell); return !(c>=0)?-1:c>=n?n:(int)c; }
static void cc_grid(CCMap* m){
    m->gnx=m->gny=0; m->pmaxr=0; if(m->np<=0) return;
    double x0=m->p[0].x, y0=m->p[0].y, x1=x0, y1=y0;
    for(int i=0;i<m->np;i++){ const CCPerson* q=&m->p[i]; x0=fmin(x0,q->x); y0=fmin(y0,q->y); x1=fmax(x1,q->x); y1=fmax(y1,q->y);
        m->pmaxr=fmax(m->pmaxr,q->r); }
    m->gox=x0; m->goy=y0; m->gcell=fmax(100.0,fmax(x1-x0,y1-y0)/(CC_GRID-1));
    m->gnx=(int)floor((x1-x0)/m->gcell)+1; m->gny=(int)floor((y1-y0)/m->gcell)+1;          // <= CC_GRID each
    int n=m->gnx*m->gny; for(int c=0;c<=n;c++) m->gstart[c]=0;
    for(int i=0;i<m->np;i++) m->gstart[cc_gcell(m,m->p[i].y,m->goy,m->gny)*m->gnx+cc_gcell(m,m->p[i].x,m->gox,m->gnx)+1]++;
    for(int c=0;c<n;c++) m->gstart[c+1]+=m->gstart[c];
    static int fill[CC_GRID*CC_GRID]; for(int c=0;c<n;c++) fill[c]=m->gstart[c];             // (cc_parse's thread only)
    for(int i=0;i<m->np;i++) m->gidx[fill[cc_gcell(m,m->p[i].y,m->goy,m->gny)*m->gnx+cc_gcell(m,m->p[i].x,m->gox,m->gnx)]++]=i; }
// the people in the cells that meet the square (x +- r, y +- r), ascending into out[CC_CAND]; -1 = more than that
// (the caller scans everyone)
static int cc_near(const CCMap* m,double x,double y,double r,int* out){
    if(m->gnx<=0) return 0;
    int cx0=cc_gcell(m,x-r,m->gox,m->gnx), cx1=cc_gcell(m,x+r,m->gox,m->gnx), cy0=cc_gcell(m,y-r,m->goy,m->gny), cy1=cc_gcell(m,y+r,m->goy,m->gny);
    if(cx0<0) cx0=0; if(cy0<0) cy0=0; if(cx1>m->gnx-1) cx1=m->gnx-1; if(cy1>m->gny-1) cy1=m->gny-1;
    int n=0;
    for(int cy=cy0;cy<=cy1;cy++) for(int cx=cx0;cx<=cx1;cx++){ int c=cy*m->gnx+cx;
        for(int k=m->gstart[c];k<m->gstart[c+1];k++){ if(n>=CC_CAND) return -1;
            int v=m->gidx[k], j=n++; while(j>0&&out[j-1]>v){ out[j]=out[j-1]; j--; } out[j]=v; } }
    return n; }

// club_collide.txt (the whole file, NUL-terminated) -> m. False without a rules line or floors; m->bad counts lines
// that didn't parse or didn't fit.
static bool cc_parse(CCMap* m,const char* buf){
    memset(m,0,sizeof *m); m->step=45; m->head=190; m->knee=25; m->radius=20; m->core=15; bool rules=false;
    for(const char* p=buf; *p; ){
        const char* e=strchr(p,'\n'); size_t n=e?(size_t)(e-p):strlen(p); char ln[256]; if(n>=sizeof ln) n=sizeof ln-1;
        memcpy(ln,p,n); ln[n]=0; p=e?e+1:p+n;
        while(n&&(ln[n-1]=='\r'||ln[n-1]==' ')) ln[--n]=0;
        if(!ln[0]||ln[0]=='#') continue;
        double a[6]; char nm[24];
        int k=sscanf(ln,"rules %lf %lf %lf %lf %lf",&a[0],&a[1],&a[2],&a[3],&a[4]);
        if(k>=4){ m->step=a[0]; m->head=a[1]; m->knee=a[2]; m->radius=a[3]; if(k==5) m->core=a[4]; rules=true; }
        else if(!strncmp(ln,"floor ",6)&&sscanf(ln+6,"%lf %lf %lf %lf %lf %lf",&a[0],&a[1],&a[2],&a[3],&a[4],&a[5])==6){
            if(m->nf<CC_MAXF){ CCFloor* f=&m->f[m->nf++]; f->x0=a[0]; f->y0=a[1]; f->x1=a[2]; f->y1=a[3]; f->top=a[4]; f->bot=a[5]; } else m->bad++; }
        else if((!strncmp(ln,"box ",4)||!strncmp(ln,"gate ",5))&&sscanf(ln+(ln[0]=='g'?5:4),"%lf %lf %lf %lf %lf %lf",&a[0],&a[1],&a[2],&a[3],&a[4],&a[5])==6){
            if(m->nb<CC_MAXB){ CCBox* b=&m->b[m->nb++]; b->x0=a[0]; b->y0=a[1]; b->x1=a[2]; b->y1=a[3]; b->z0=a[4]; b->z1=a[5]; b->gate=ln[0]=='g'; } else m->bad++; }
        else if(!strncmp(ln,"circle ",7)&&sscanf(ln+7,"%lf %lf %lf %lf %lf",&a[0],&a[1],&a[2],&a[3],&a[4])==5){
            if(m->nc<CC_MAXC){ CCCirc* c=&m->c[m->nc++]; c->x=a[0]; c->y=a[1]; c->r=a[2]; c->z0=a[3]; c->z1=a[4]; } else m->bad++; }
        else if(!strncmp(ln,"person ",7)&&sscanf(ln+7,"%lf %lf %lf %lf %lf",&a[0],&a[1],&a[2],&a[3],&a[4])==5){
            if(m->np<CC_MAXP){ CCPerson* q=&m->p[m->np++]; q->x=a[0]; q->y=a[1]; q->r=a[2]; q->z0=a[3]; q->z1=a[4]; } else m->bad++; }
        else if(sscanf(ln,"spot %23s %lf %lf %lf %lf",nm,&a[0],&a[1],&a[2],&a[3])==5){
            if(m->ns<CC_MAXS){ CCSpot* s=&m->s[m->ns++]; snprintf(s->name,sizeof s->name,"%s",nm); s->x=a[0]; s->y=a[1]; s->z=a[2]; s->yaw=a[3]; } else m->bad++; }
        else m->bad++;
    }
    cc_grid(m);
    return rules&&m->nf>0; }
static const CCSpot* cc_spot(const CCMap* m,const char* name){ for(int i=0;i<m->ns;i++) if(!strcmp(m->s[i].name,name)) return &m->s[i]; return 0; }
// signed distance from (x, y) to a rect: positive outside, minus the depth inside
static double cc_sdist(double x0,double y0,double x1,double y1,double x,double y){
    double dx=fmax(fmax(x0-x,0.0),x-x1), dy=fmax(fmax(y0-y,0.0),y-y1);
    if(dx>0.0||dy>0.0) return hypot(dx,dy);
    return -fmin(fmin(x-x0,x1-x),fmin(y-y0,y1-y)); }
// the floor under (x, y) for someone standing on `cur`: the highest floor rect holding the point whose top is within step
static bool cc_floor_at(const CCMap* m,double x,double y,double cur,double* out){
    bool got=false; double best=0;
    for(int i=0;i<m->nf;i++){ const CCFloor* f=&m->f[i];
        if(x<f->x0||x>f->x1||y<f->y0||y>f->y1||f->top<cur-m->step||f->top>cur+m->step) continue;
        if(!got||f->top>best){ best=f->top; got=true; } }
    if(got) *out=best; return got; }
// what refuses the move p -> q: 0 = nothing, 1+i floor i (a solid too high to step on), 1000+i box/gate i, 2000+i circle
// i, 3000+i person i. A wall refuses a move that ends within radius of it and closer than before, so an overlap can always
// be backed out of; a person only within core of their centre (the crowd is soft: club.cpp slows you and steers you).
static int cc_wall_hit(const CCMap* m,double px,double py,double qx,double qy,double cur,int gateOpen){
    double lo=cur+m->knee, hi=cur+m->head, R=m->radius;
    for(int i=0;i<m->nf;i++){ const CCFloor* f=&m->f[i]; if(!(f->top>cur+m->step&&f->bot<cur+m->head)) continue;
        double dq=cc_sdist(f->x0,f->y0,f->x1,f->y1,qx,qy); if(dq>=R) continue;
        if(dq<cc_sdist(f->x0,f->y0,f->x1,f->y1,px,py)-0.01) return 1+i; }
    for(int i=0;i<m->nb;i++){ const CCBox* b=&m->b[i]; if(b->z1<=lo||b->z0>=hi) continue;
        if(b->gate&&(gateOpen||qy<=py)) continue;
        double dq=cc_sdist(b->x0,b->y0,b->x1,b->y1,qx,qy); if(dq>=R) continue;
        if(dq<cc_sdist(b->x0,b->y0,b->x1,b->y1,px,py)-0.01) return 1000+i; }
    for(int i=0;i<m->nc;i++){ const CCCirc* c=&m->c[i]; if(c->z1<=lo||c->z0>=hi) continue;
        double dq=hypot(qx-c->x,qy-c->y)-c->r; if(dq>=R) continue;
        if(dq<hypot(px-c->x,py-c->y)-c->r-0.01) return 2000+i; }
    int cand[CC_CAND], nc=cc_near(m,qx,qy,m->core+1e-6,cand);                         // the people near q
    for(int k=0;k<(nc<0?m->np:nc);k++){ int i=nc<0?k:cand[k]; const CCPerson* q=&m->p[i]; if(q->z1<=lo||q->z0>=hi) continue;
        double dq=hypot(qx-q->x,qy-q->y); if(dq>=m->core) continue;
        if(dq<hypot(px-q->x,py-q->y)-0.01) return 3000+i; }
    return 0; }
// the soft crowd round (x, y) for someone on `cur`: how crowded it is (0 = nobody within shoulders + radius; about 1 =
// right against one person), the summed push away from those people (*ax, *ay) and the nearest one's offset (*nx, *ny)
static double cc_crowd(const CCMap* m,double x,double y,double cur,double* ax,double* ay,double* nx,double* ny){
    double lo=cur+m->knee, hi=cur+m->head, dens=0, best=1e9; *ax=*ay=*nx=*ny=0;
    int cand[CC_CAND], nc=cc_near(m,x,y,m->pmaxr+m->radius+1e-6,cand);                // the people within reach
    for(int k=0;k<(nc<0?m->np:nc);k++){ int i=nc<0?k:cand[k]; const CCPerson* q=&m->p[i]; if(q->z1<=lo||q->z0>=hi) continue;
        double dx=x-q->x, dy=y-q->y, d=hypot(dx,dy), reach=q->r+m->radius; if(d>=reach) continue;
        double w=1.0-d/reach; dens+=w; if(d>0.01){ *ax+=dx/d*w; *ay+=dy/d*w; }
        if(d<best){ best=d; *nx=-dx; *ny=-dy; } }
    return dens; }
static bool cc_is_gate(const CCMap* m,int hit){ return hit>=1000&&hit<2000&&m->b[hit-1000].gate; }
// p -> q allowed? *nf = the floor at q; *hit = what refused it (0 if allowed, -1 = no floor: a drop or a climb)
static bool cc_try(const CCMap* m,double px,double py,double qx,double qy,double cur,int gateOpen,double* nf,int* hit){
    double f; *hit=-1; if(!cc_floor_at(m,qx,qy,cur,&f)) return false;
    *hit=cc_wall_hit(m,px,py,qx,qy,cur,gateOpen); if(*hit) return false;
    *nf=f; return true; }
// a stick step: the whole delta, else slide along X, else along Y. *ax,*ay = the delta taken; returns 0 if none.
// *hit = what refused the whole step (for the gate's refusal; 0 if it went through whole).
static int cc_move(const CCMap* m,double px,double py,double dx,double dy,double cur,int gateOpen,
                   double* ax,double* ay,double* nf,int* hit){
    int h2;
    if(cc_try(m,px,py,px+dx,py+dy,cur,gateOpen,nf,hit)){ *ax=dx; *ay=dy; return 1; }
    if(dx!=0.0&&cc_try(m,px,py,px+dx,py,cur,gateOpen,nf,&h2)){ *ax=dx; *ay=0; return 2; }
    if(dy!=0.0&&cc_try(m,px,py,px,py+dy,cur,gateOpen,nf,&h2)){ *ax=0; *ay=dy; return 3; }
    *ax=0; *ay=0; return 0; }
