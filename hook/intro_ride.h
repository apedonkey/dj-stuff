// intro_ride.h: a stage's stream-intro file (tribemod/intro.<folder>.txt) and the ride's sampling, engine-free. The stage's
// own script writes the file (Graveyard Shift: Scripts/Blender/halloween/intro/hw_intro_path.py); hook/intro.cpp runs it;
// tests/intro_ride_test.cpp prints the same samples on the PC to check them against that script's preview path.
// World cm, degrees, seconds.
//
// The ride: "key t x,y,z yaw" lines, through which a Hermite spline with Catmull-Rom tangents on the time knots runs.
// "loop t0 t1" closes on its first key (the key at t1 repeats t0's) and "exit t1 t2" branches off at that seam, leaving
// along the loop's own tangent there. The rider faces along the spline (his mesh's local +Y forward, so
// actor yaw = atan2(-f.x, f.y)); the keys' own yaw is only a check. "cam loop|exit f,l,u look=f,l,u": the stream camera
// and its aim, forward / left / up (cm) from the ground under him, left = (f.y, -f.x) in Unreal's left-handed world.
#pragma once
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { IR_MAXK=512, IR_MAXN=4 };
struct IRide {
    int nk, iL, bad;                          // keys; the seam key (t == loop1); lines not understood
    double t[IR_MAXK], p[IR_MAXK][3], yaw[IR_MAXK];
    double loop0, loop1, exit1, camhold;      // the loop t0..t1, the exit t1..exit1, the camera holds still from camhold
    double cam[2][3], look[2][3];             // [0] loop, [1] exit: forward, left, up (cm)
    double wide[3], wideLook[3];              // showtime's wide shot (world cm) and its aim
    double btn[3], btnR;                      // the backstage button (world cm) and the press radius (cm)
    double fovRide, fovWide;                  // the capture's horizontal FOV (deg) for the ride and the wide shot; 0 = Tribe's
    double door, hold, back;                  // the door's ease (s), showtime's dark hold (s), the camera's hand-back timeout (s)
    double shut;                              // door ... shut=s: it closes again s after you reach the decks (-1: stays open)
    char rider[64], woods[IR_MAXN][64], step[64], doorName[64]; int nwoods;
    char screen[64];                          // screen <actor>: a mesh that shows the stream (the selfie preview's material)
    // HARVEST MOON 2026-10-20 (opt-in; files without these lines behave as before): the showtime camera follows a descent
    int hasDesc, hasWide2;
    double descA[3], descB[3];                // descent <from x,y,z> <to x,y,z>: what the wide shot tracks as the door rises
    double wide2[3], wide2Look[3];            // wide2 x,y,z look=x,y,z: where the wide shot settles once the door is up
    int autoShow;                             // autoshow: press 2 also queues showtime (it plays once the camera holds)
    char btnActor[64]; double btnTravel;      // buttonactor <name> [travel=cm]: the cap the hand pushes down (3 cm)
};

static bool ir_xyz(const char* s,double o[3]){ return s&&sscanf(s,"%lf,%lf,%lf",&o[0],&o[1],&o[2])==3; }
// the whole file (NUL-terminated) -> r. False unless the keys, the loop and the exit make a ride.
static bool ir_parse(IRide* r,const char* text){
    memset(r,0,sizeof *r); r->btnR=14; r->door=4; r->hold=2; r->back=20; r->camhold=-1; r->shut=-1;
    for(const char* q=text; *q; ){
        const char* e=strchr(q,'\n'); size_t n=e?(size_t)(e-q):strlen(q); char ln[256]; if(n>=sizeof ln) n=sizeof ln-1;
        memcpy(ln,q,n); ln[n]=0; q=e?e+1:q+n;
        char* hash=strchr(ln,'#'); if(hash) *hash=0;
        char* tk[8]; int nt=0; char* save=0;
        for(char* t=strtok_r(ln," \t\r",&save); t&&nt<8; t=strtok_r(0," \t\r",&save)) tk[nt++]=t;
        if(!nt) continue;
        const char* w=tk[0]; const char* lk=0; for(int i=2;i<nt;i++) if(!strncmp(tk[i],"look=",5)) lk=tk[i]+5;
        if(!strcmp(w,"key")&&nt>=4&&r->nk<IR_MAXK&&ir_xyz(tk[2],r->p[r->nk])){
            r->t[r->nk]=atof(tk[1]); r->yaw[r->nk]=nt>=4?atof(tk[3]):0; r->nk++; }
        else if(!strcmp(w,"loop")&&nt>=3){ r->loop0=atof(tk[1]); r->loop1=atof(tk[2]); }
        else if(!strcmp(w,"exit")&&nt>=3){ if(fabs(atof(tk[1])-r->loop1)>1e-3) r->bad++; r->exit1=atof(tk[2]); }
        else if(!strcmp(w,"camhold")&&nt>=2) r->camhold=atof(tk[1]);
        else if(!strcmp(w,"cam")&&nt>=4&&(!strcmp(tk[1],"loop")||!strcmp(tk[1],"exit"))&&ir_xyz(tk[2],r->cam[tk[1][0]=='e'])&&ir_xyz(lk,r->look[tk[1][0]=='e'])){}
        else if(!strcmp(w,"wide")&&nt>=3&&ir_xyz(tk[1],r->wide)&&ir_xyz(lk,r->wideLook)){}
        else if(!strcmp(w,"descent")&&nt>=3&&ir_xyz(tk[1],r->descA)&&ir_xyz(tk[2],r->descB)) r->hasDesc=1;
        else if(!strcmp(w,"wide2")&&nt>=3&&ir_xyz(tk[1],r->wide2)&&ir_xyz(lk,r->wide2Look)) r->hasWide2=1;
        else if(!strcmp(w,"autoshow")) r->autoShow=1;
        else if(!strcmp(w,"buttonactor")&&nt>=2){ snprintf(r->btnActor,sizeof r->btnActor,"%s",tk[1]); r->btnTravel=3;
            for(int i=2;i<nt;i++) if(!strncmp(tk[i],"travel=",7)) r->btnTravel=fmin(fmax(atof(tk[i]+7),0.0),10.0); }
        else if(!strcmp(w,"button")&&nt>=2&&ir_xyz(tk[1],r->btn)){ for(int i=2;i<nt;i++) if(!strncmp(tk[i],"r=",2)) r->btnR=atof(tk[i]+2); }
        else if(!strcmp(w,"fov")&&nt>=3){ double v=atof(tk[2]); if(v<20||v>140) r->bad++; else if(!strcmp(tk[1],"wide")) r->fovWide=v; else r->fovRide=v; }
        else if(!strcmp(w,"rider")&&nt>=2) snprintf(r->rider,sizeof r->rider,"%s",tk[1]);
        else if(!strcmp(w,"woods")) for(int i=1;i<nt&&r->nwoods<IR_MAXN;i++) snprintf(r->woods[r->nwoods++],64,"%s",tk[i]);
        else if(!strcmp(w,"step")&&nt>=2) snprintf(r->step,sizeof r->step,"%s",tk[1]);
        else if(!strcmp(w,"screen")&&nt>=2) snprintf(r->screen,sizeof r->screen,"%s",tk[1]);
        else if(!strcmp(w,"door")&&nt>=2){ snprintf(r->doorName,sizeof r->doorName,"%s",tk[1]); if(nt>=3) r->door=fmax(0.1,atof(tk[2]));
            for(int i=3;i<nt;i++) if(!strncmp(tk[i],"shut=",5)) r->shut=fmin(fmax(atof(tk[i]+5),0.0),600.0); }
        else if(!strcmp(w,"hold")&&nt>=2) r->hold=fmin(fmax(atof(tk[1]),0.0),10.0);
        else if(!strcmp(w,"back")&&nt>=2) r->back=fmin(fmax(atof(tk[1]),3.0),120.0);
        else if(!strcmp(w,"spot")||!strcmp(w,"presses")){}                       // the stage's notes: not the mod's business
        else r->bad++; }
    for(int i=1;i<r->nk;i++) if(!(r->t[i]>r->t[i-1])) return false;
    r->iL=-1; for(int i=0;i<r->nk;i++) if(fabs(r->t[i]-r->loop1)<1e-3) r->iL=i;
    if(r->nk<4||r->iL<3||fabs(r->t[0]-r->loop0)>1e-3||r->exit1<=r->loop1||fabs(r->t[r->nk-1]-r->exit1)>1e-3||r->iL>r->nk-2) return false;
    double d=0; for(int k=0;k<3;k++) d+=fabs(r->p[r->iL][k]-r->p[0][k]);
    if(d>3.0) return false;                                                   // the loop must close on its first key
    if(r->camhold<r->loop1||r->camhold>r->exit1) r->camhold=r->exit1;
    return true; }

// Catmull-Rom tangents (cm/s) on the time knots: the loop's wrap round its seam, the exit's run on from there. The exit
// leaves along the loop's own tangent at the seam (the stage's path is built that way), so both branches share that
// tangent: the loop's last segment is the same whether the exit is taken or not, and the branch has no kink.
static void ir_tan_loop(const IRide* r,int j,double m[3]){
    int n=r->iL; j%=n; if(j<0) j+=n;
    double tp=j>0?r->t[j-1]:r->t[n-1]-(r->t[n]-r->t[0]); const double* pp=r->p[j>0?j-1:n-1];
    double tn=r->t[j+1]; const double* pn=r->p[j+1];
    for(int k=0;k<3;k++) m[k]=(pn[k]-pp[k])/(tn-tp); }
static void ir_tan_exit(const IRide* r,int i,double m[3]){
    int n=r->nk; if(i<=r->iL){ ir_tan_loop(r,r->iL,m); return; }
    if(i>=n-1){ for(int k=0;k<3;k++) m[k]=(r->p[n-1][k]-r->p[n-2][k])/(r->t[n-1]-r->t[n-2]); return; }
    for(int k=0;k<3;k++) m[k]=(r->p[i+1][k]-r->p[i-1][k])/(r->t[i+1]-r->t[i-1]); }
// the rider at ride time tau: on the loop tau in [loop0, loop1) (the caller wraps it); once the exit is taken (exiting),
// tau runs on from loop1 to exit1 (held there after). P = position (cm), V = velocity (cm/s).
static void ir_pose(const IRide* r,double tau,int exiting,double P[3],double V[3]){
    int n=r->iL, i; double m0[3], m1[3];
    if(tau<r->t[n]||!exiting){ if(tau<r->t[0]) tau=r->t[0]; if(tau>r->t[n]) tau=r->t[n];
        for(i=0;i<n-1&&r->t[i+1]<=tau;i++){}
        ir_tan_loop(r,i,m0); ir_tan_loop(r,i+1,m1); }
    else { if(tau>r->exit1) tau=r->exit1;
        for(i=n;i<r->nk-2&&r->t[i+1]<=tau;i++){}
        ir_tan_exit(r,i,m0); ir_tan_exit(r,i+1,m1); }
    double h=r->t[i+1]-r->t[i], u=(tau-r->t[i])/h; if(u<0) u=0; if(u>1) u=1;
    double u2=u*u, u3=u2*u, h00=2*u3-3*u2+1, h10=u3-2*u2+u, h01=-2*u3+3*u2, h11=u3-u2;
    double d00=6*u2-6*u, d10=3*u2-4*u+1, d01=-6*u2+6*u, d11=3*u2-2*u;
    for(int k=0;k<3;k++){ const double a=r->p[i][k], b=r->p[i+1][k];
        P[k]=h00*a+h10*h*m0[k]+h01*b+h11*h*m1[k];
        V[k]=(d00*a+d10*h*m0[k]+d01*b+d11*h*m1[k])/h; } }
// his forward (unit, horizontal) from a velocity; false if he isn't moving (then f keeps its last value)
static bool ir_forward(const double V[3],double f[2]){
    double l=hypot(V[0],V[1]); if(l<1e-6) return false; f[0]=V[0]/l; f[1]=V[1]/l; return true; }
static double ir_actor_yaw(const double f[2]){ return atan2(-f[0],f[1])*180.0/M_PI; }     // local +Y along f
// a point in his frame: c = forward, left, up (cm) from the ground under him (G)
static void ir_frame(const double G[3],const double f[2],const double c[3],double out[3]){
    out[0]=G[0]+f[0]*c[0]+f[1]*c[1]; out[1]=G[1]+f[1]*c[0]-f[0]*c[1]; out[2]=G[2]+c[2]; }
static double ir_smooth(double x){ if(x<=0) return 0; if(x>=1) return 1; return x*x*(3-2*x); }
// the stream camera (Pc) and its aim (Pa) at ride time tau: the loop's offsets, blended to the exit's over the exit's
// first 5 s (smoothstep, as the preview)
static void ir_camera(const IRide* r,double tau,int exiting,const double G[3],const double f[2],double Pc[3],double Pa[3]){
    double b=(exiting&&tau>=r->loop1)?ir_smooth((tau-r->loop1)/5.0):0.0, c[3], l[3];
    for(int k=0;k<3;k++){ c[k]=r->cam[0][k]+(r->cam[1][k]-r->cam[0][k])*b; l[k]=r->look[0][k]+(r->look[1][k]-r->look[0][k])*b; }
    ir_frame(G,f,c,Pc); ir_frame(G,f,l,Pa); }
