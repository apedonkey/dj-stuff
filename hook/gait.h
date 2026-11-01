// gait.h: a procedural walk cycle for the body-tracked avatar's legs while the mod's walking (the stick) carries it. The
// user, 2026-10-10: "my arms are already tracked so we don't need to add that. Im more concerned about the legs moving".
// Body tracking poses the legs from the user's real legs, which stand still while the stick moves VROrigin, so the avatar
// glided. dumper.cpp's a2_drive calls gait_update once a frame with VROrigin's world motion and gait_legs on the leg
// bones' component-space rotations; tests/gait_test.cpp runs the same math on the PC. Engine-free: needs V3 / Q4 and the
// v* / q* helpers declared before it (dumper.cpp's, or the test's copy).
//
// The cycle: a phase advanced by the distance walked / the stride, forward or backward with the walking direction against
// the body's facing. Per leg (the right half a cycle behind the left), about the body's left-right axis: in its stance
// half the thigh turns from forward to back so the foot's horizontal travel is linear in time (L sin(hip) a ramp), which
// with stride = 4 L sin(max hip) keeps the planted foot still on the ground; in its swing half the thigh comes forward
// again on a smooth curve while the knee bends and the foot stays nearer level. The hips dip a little where the legs
// spread so the planted foot stays near the floor. Blended in with speed (full from 60 cm/s) and out in ~0.3 s.
// Ignored: VROrigin jumps over 10 m/s (teleports, a recentre), frames with a snap turn, vertical moves (the giant lift).
// Tuning: GAIT_* below.
#pragma once
#include <math.h>

static const double GAIT_HIP=25.0, GAIT_KNEE=50.0, GAIT_KNEE_STANCE=4.0, GAIT_FOOT=0.4;   // deg; foot = share of the knee undone
static const double GAIT_FULL=60.0, GAIT_TAU_IN=0.1, GAIT_TAU_OUT=0.1, GAIT_DIP=0.6;      // cm/s, s, s, share of the drop
struct Gait { double phase, w, speed, sign; V3 lastP; double lastYaw; int have; };

static Q4 gait_axis(V3 k,double deg){ double h=deg*M_PI/360.0, s=sin(h); return Qm(k.x*s,k.y*s,k.z*s,cos(h)); }
// one frame: P / yaw = VROrigin's world location (cm) and yaw (deg); fwd = the body's facing in the world (horizontal unit);
// legW = the avatar's leg length in world cm (hip to ankle). Returns the swing weight 0..1.
static double gait_update(Gait* g,V3 P,double yaw,V3 fwd,double legW,double dt){
    if(!(dt>0&&dt<0.25)){ g->have=0; return g->w; }
    double v=0, fv=0;
    if(g->have){ V3 d=V(P.x-g->lastP.x,P.y-g->lastP.y,0); double dy=fabs(fmod(yaw-g->lastYaw+540.0,360.0)-180.0);
        v=vlen(d)/dt; fv=vdot(d,fwd)/dt;
        if(v>1000.0||dy>2.0){ v=0; fv=0; } }                          // a teleport or a snap turn, not a step
    g->lastP=P; g->lastYaw=yaw; g->have=1;
    if(g->sign==0) g->sign=1;
    if(v>1e-3&&fabs(fv)>0.3*v) g->sign=fv>0?1:-1;                     // mostly sideways: keep the last direction
    g->speed+=(v-g->speed)*(1.0-exp(-dt/0.05));
    double wt=fmin(1.0,g->speed/GAIT_FULL); g->w+=(wt-g->w)*(1.0-exp(-dt/(wt>g->w?GAIT_TAU_IN:GAIT_TAU_OUT)));
    if(g->w<1e-3) g->w=0;
    double stride=fmax(4.0*legW*sin(GAIT_HIP*g->w*M_PI/180.0),30.0); // two steps; each spans 2 L sin(hip)
    g->phase=fmod(g->phase+g->sign*v*dt/stride+8.0,1.0);
    return g->w; }
// one leg's chain (component-space rotations, each absolute: UpLeg, Leg, Foot, ToeBase; any may be null), at phase ph
// (cycles) and weight w; k = the body's left-right axis (a positive turn about it swings the thigh forward)
static double gait_sin_hip(double ph,double sa,double* swing){      // sin(thigh angle) at phase ph; *swing = 0..1 into the swing
    ph-=floor(ph); if(ph<0.5){ *swing=-1; return sa*(1.0-4.0*ph); }   // stance: forward -> back, the foot still on the ground
    double u=(ph-0.5)*2.0; *swing=u; return -sa*cos(M_PI*u); }       // swing: back -> forward
static void gait_leg(Q4* up,Q4* lo,Q4* ft,Q4* toe,V3 k,double ph,double w){
    double sw, sa=sin(GAIT_HIP*w*M_PI/180.0), sh=gait_sin_hip(ph,sa,&sw);
    double hip=asin(fmax(-1.0,fmin(1.0,sh)))*180.0/M_PI, knee=w*(GAIT_KNEE_STANCE+(sw>=0?GAIT_KNEE*sin(M_PI*sw):0.0)), foot=GAIT_FOOT*knee;
    Q4 Rh=gait_axis(k,hip), Rk=gait_axis(k,-knee), Rf=gait_axis(k,foot), Rhk=qmul(Rh,Rk), Rhkf=qmul(Rhk,Rf);
    if(up) *up=qnorm(qmul(Rh,*up));
    if(lo) *lo=qnorm(qmul(Rhk,*lo));
    if(ft) *ft=qnorm(qmul(Rhkf,*ft));
    if(toe) *toe=qnorm(qmul(Rhkf,*toe)); }
// the hips' drop (avatar cm, <= 0) that keeps the planted foot near the floor: legs of length leg spread by the swing
static double gait_dip(const Gait* g,double leg){                    // the planted leg is the one in its stance half
    double sw, sa=sin(GAIT_HIP*g->w*M_PI/180.0), sh=gait_sin_hip(g->phase,sa,&sw);
    if(sw>=0) sh=gait_sin_hip(g->phase+0.5,sa,&sw);
    return -GAIT_DIP*leg*(1.0-sqrt(fmax(0.0,1.0-sh*sh))); }
// the body's left-right axis for a horizontal facing f: turning "down" toward f about it is positive (Unreal's left)
static V3 gait_lateral(V3 f){ return vnorm(V(f.y,-f.x,0)); }
