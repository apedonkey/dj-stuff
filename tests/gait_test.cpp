// gait_test.cpp: hook/gait.h on the PC. A two-leg chain (hips 100 cm, thigh and shin 45 cm, foot 15 cm forward) walked by
// the stick the way a2_drive feeds it, checking what the eye would: the thigh swings toward the walking direction, the
// planted foot stays on the ground and doesn't slide, the swinging foot clears it, walking backwards runs the cycle in
// reverse, a teleport and a snap turn don't count as steps, and the legs come back to the tracked pose when you stop.
//   host:  MSVC  cl /O2 /EHsc tests\gait_test.cpp   then  gait_test
// The math helpers are copied from hook/dumper.cpp (lines "struct V3" .. "qrot"); keep them the same.
#define _USE_MATH_DEFINES
#include <math.h>
#include <stdio.h>
struct V3{ double x,y,z; };
struct Q4{ double x,y,z,w; };
static inline V3 V(double x,double y,double z){ V3 r={x,y,z}; return r; }
static inline V3 vadd(V3 a,V3 b){ return V(a.x+b.x,a.y+b.y,a.z+b.z); }
static inline V3 vsub(V3 a,V3 b){ return V(a.x-b.x,a.y-b.y,a.z-b.z); }
static inline V3 vmul(V3 a,double s){ return V(a.x*s,a.y*s,a.z*s); }
static inline double vdot(V3 a,V3 b){ return a.x*b.x+a.y*b.y+a.z*b.z; }
static inline V3 vcross(V3 a,V3 b){ return V(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x); }
static inline double vlen(V3 a){ return sqrt(vdot(a,a)); }
static inline V3 vnorm(V3 a){ double l=vlen(a); return l>1e-9?vmul(a,1.0/l):V(0,0,0); }
static inline Q4 Qm(double x,double y,double z,double w){ Q4 q={x,y,z,w}; return q; }
static const Q4 QI={0,0,0,1};
static inline Q4 qmul(Q4 a,Q4 b){ return Qm(a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y, a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,
                                            a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w, a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z); }
static inline Q4 qinv(Q4 q){ return Qm(-q.x,-q.y,-q.z,q.w); }
static inline Q4 qnorm(Q4 q){ double l=sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w); return l>1e-12?Qm(q.x/l,q.y/l,q.z/l,q.w/l):QI; }
static inline V3 qrot(Q4 q,V3 v){ V3 u=V(q.x,q.y,q.z), t=vmul(vcross(u,v),2.0); return vadd(vadd(v,vmul(t,q.w)),vcross(u,t)); }
#include "../hook/gait.h"

static const V3 F={-1,0,0};                                        // the avatar faces 180 deg (component space = world here)
static const double THIGH=45, SHIN=45, HIPZ=100, ANKZ=HIPZ-THIGH-SHIN;
struct Leg { V3 knee, ankle, toe; };
static Leg pose(const Gait* g,double side,double ph){              // FK of one leg, rest rotations = identity
    Q4 up=QI, lo=QI, ft=QI, toe=QI; gait_leg(&up,&lo,&ft,&toe,gait_lateral(F),ph,g->w);
    V3 hip=V(0,side*10,HIPZ+gait_dip(g,THIGH+SHIN)); Leg l;
    l.knee=vadd(hip,qrot(up,V(0,0,-THIGH))); l.ankle=vadd(l.knee,qrot(lo,V(0,0,-SHIN))); l.toe=vadd(l.ankle,qrot(ft,V(-15,0,-8)));
    return l; }
int main(){
    int fails=0; Gait g={0,0,0,0,{0,0,0},0,0}; double dt=1.0/72, x=0;
    auto check=[&](bool ok,const char* what){ printf("%s  %s\n",ok?"PASS":"FAIL",what); if(!ok) fails++; };
    // 1) walk forward (along F) at the club's default 180 cm/s for 4 s
    double plantMax=0, liftMax=0, slideMax=0, kneeFwd=0, t=0, adv=0, lastPh=0;
    double lo[2]={1e9,1e9}, hi[2]={-1e9,-1e9}; bool inSt[2]={false,false};
    for(int i=0;i<72*4;i++,t+=dt){ x+=-180*dt; gait_update(&g,V(x,0,0),0,F,THIGH+SHIN,dt);
        double d=g.phase-lastPh; if(d<-0.5) d+=1; if(d>0.5) d-=1; lastPh=g.phase; if(t<2.0) continue; adv+=d;
        double ph[2]={g.phase,g.phase+0.5}; Leg L[2]={pose(&g,1,ph[0]),pose(&g,-1,ph[1])};
        double low=fmin(L[0].ankle.z,L[1].ankle.z); plantMax=fmax(plantMax,fabs(low-ANKZ));
        liftMax=fmax(liftMax,fmax(L[0].ankle.z,L[1].ankle.z)-ANKZ);
        if(fabs(ph[0]-floor(ph[0])-0.0)<0.02) kneeFwd=vdot(vsub(L[0].knee,V(0,10,HIPZ)),F);   // stance start: thigh forward
        for(int s=0;s<2;s++){ double p=ph[s]-floor(ph[s]); bool st=p>0.03&&p<0.47;   // its stance half (ends trimmed)
            double wx=x+L[s].ankle.x;                                                    // the ankle in the world
            if(st){ lo[s]=fmin(lo[s],wx); hi[s]=fmax(hi[s],wx); }
            else if(inSt[s]){ slideMax=fmax(slideMax,hi[s]-lo[s]); lo[s]=1e9; hi[s]=-1e9; }
            inSt[s]=st; } }
    double rate=adv/2.0, want=180.0/fmax(4.0*(THIGH+SHIN)*sin(GAIT_HIP*M_PI/180.0),30.0);
    printf("walking 180 cm/s: weight %.2f, %.2f cycles/s (stride says %.2f), knee %.1f cm ahead of the hip at full forward swing\n",
           g.w,rate,want,kneeFwd);
    printf("  the lower ankle stays within %.1f cm of the floor; the swing ankle lifts up to %.1f cm; a planted ankle slides %.1f cm\n",
           plantMax,liftMax,slideMax);
    check(g.w>0.99,"full swing at walking speed");
    check(kneeFwd>10,"the thigh swings toward the walking direction");
    check(fabs(rate-want)<0.15*want,"the cycle keeps pace with the stride");
    check(plantMax<4.0,"the planted foot stays near the floor (hips dip)");
    check(liftMax>5.0,"the swinging foot clears the floor");
    check(slideMax<5.0,"a planted foot doesn't skate (stride matches the ground)");
    // 2) walk backwards: the phase runs the other way
    double p0=g.phase, back=0; for(int i=0;i<72;i++){ x+=180*dt; double before=g.phase; gait_update(&g,V(x,0,0),0,F,THIGH+SHIN,dt);
        double d=g.phase-before; if(d>0.5) d-=1; if(d<-0.5) d+=1; back+=d; }
    printf("walking backwards 1 s: the phase moved %+.2f cycles (from %.2f)\n",back,p0);
    check(back<-0.5,"backwards runs the cycle in reverse");
    // 3) a teleport (3 m in one frame) and a snap turn (30 deg, the origin swinging 26 cm): no step
    Gait h=g; double s0=h.speed; gait_update(&h,V(x+300,0,0),0,F,THIGH+SHIN,dt); double tp=h.speed-s0;
    Gait r=g; s0=r.speed; gait_update(&r,V(x+26,0,0),30,F,THIGH+SHIN,dt); double st=r.speed-s0;
    printf("teleport: speed %+.1f cm/s; snap turn: speed %+.1f cm/s (both should only decay)\n",tp,st);
    check(tp<=0&&st<=0,"teleports and snap turns aren't steps");
    // 4) stop: back to the tracked legs
    double w03=0; for(int i=0;i<72;i++){ gait_update(&g,V(x,0,0),0,F,THIGH+SHIN,dt); if(i==21) w03=g.w; }
    Leg L=pose(&g,1,g.phase); double off=vlen(vsub(L.ankle,V(0,10,ANKZ)));
    printf("stopped: weight %.2f after 0.3 s, %.3f after 1 s; the ankle %.2f cm off its tracked spot\n",w03,g.w,off);
    check(w03<0.15&&g.w<0.01&&off<1.0,"the legs blend back to tracking (~0.3 s)");
    // 5) the lift: VROrigin rising 150 cm/s doesn't walk
    Gait z={0,0,0,0,{0,0,0},0,0}; for(int i=0;i<72;i++) gait_update(&z,V(0,0,i*150*dt),0,F,THIGH+SHIN,dt);
    check(z.w<0.01,"a vertical move (the lift) isn't walking");
    printf("%s\n",fails?"SOME CHECKS FAILED":"ALL CHECKS PASS");
    return fails?1:0; }
