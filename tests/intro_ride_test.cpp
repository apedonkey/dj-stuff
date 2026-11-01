// intro_ride_test.cpp: hook/intro_ride.h on the PC, to check the mod's ride against the stage's own preview math.
//   host:  MSVC  cl /O2 /EHsc tests\intro_ride_test.cpp     then  intro_ride_test <intro.txt> [ride.csv]
// Prints the parse, the keys' yaw against the spline's heading and the speed range, and writes the ride at 72 Hz to the
// csv: once round the loop, then the exit (as after a press 2 during that lap), with the stream camera unfrozen:
// t,exiting,x,y,z,yaw,cam_x,cam_y,cam_z,aim_x,aim_y,aim_z (world cm, deg).
#define _USE_MATH_DEFINES
#ifdef _MSC_VER
#define _CRT_SECURE_NO_WARNINGS
#define strtok_r strtok_s
#endif
#include "../hook/intro_ride.h"

int main(int argc,char** argv){
    if(argc<2){ printf("usage: %s intro.txt [ride.csv]\n",argv[0]); return 2; }
    FILE* f=fopen(argv[1],"rb"); if(!f){ printf("can't open %s\n",argv[1]); return 2; }
    static char buf[1<<17]; size_t n=fread(buf,1,sizeof buf-1,f); fclose(f); buf[n]=0;
    static IRide r; bool ok=ir_parse(&r,buf);
    printf("parse %s: %s, %d keys (seam key %d), loop %.2f..%.2f s, exit to %.2f s, camhold %.2f s, %d lines not understood\n",
           argv[1],ok?"ok":"FAILED",r.nk,r.iL,r.loop0,r.loop1,r.exit1,r.camhold,r.bad);
    if(!ok) return 1;
    printf("button (%.0f, %.0f, %.0f) r %.0f cm | rider %s | woods %d (%s ...) | step %s | door %s %.1f s | hold %.1f s | back %.0f s | "
           "fov ride %.0f wide %.0f\n",r.btn[0],r.btn[1],r.btn[2],r.btnR,r.rider,r.nwoods,r.nwoods?r.woods[0]:"-",r.step,r.doorName,r.door,
           r.hold,r.back,r.fovRide,r.fovWide);
    double worst=0; int wk=-1;
    for(int i=0;i<r.nk;i++){ double P[3],V[3],fw[2]={0,1}; ir_pose(&r,r.t[i],i>=r.iL,P,V); ir_forward(V,fw);
        double d=fabs(fmod(ir_actor_yaw(fw)-r.yaw[i]+540.0,360.0)-180.0); if(d>worst){ worst=d; wk=i; } }
    printf("keys' yaw vs the spline's heading: worst %.2f deg (key %d at %.2f s)\n",worst,wk,wk>=0?r.t[wk]:0.0);
    FILE* o=argc>2?fopen(argv[2],"w"):0;
    if(o) fprintf(o,"t,exiting,x,y,z,yaw,cam_x,cam_y,cam_z,aim_x,aim_y,aim_z\n");
    double vmin[2]={1e9,1e9}, vmax[2]={0,0}, fw[2]={0,1};
    for(int pass=0;pass<2;pass++){
        double t0=pass?r.loop1:r.loop0, t1=pass?r.camhold:r.loop1;
        for(double t=t0; t<t1-1e-9; t+=1.0/72.0){
            double P[3],V[3],C[3],A[3]; ir_pose(&r,t,pass,P,V); ir_forward(V,fw);
            double sp=hypot(V[0],V[1])/100.0; if(sp<vmin[pass]) vmin[pass]=sp; if(sp>vmax[pass]) vmax[pass]=sp;
            ir_camera(&r,t,pass,P,fw,C,A);
            if(o) fprintf(o,"%.5f,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f\n",t,pass,P[0],P[1],P[2],ir_actor_yaw(fw),
                          C[0],C[1],C[2],A[0],A[1],A[2]); } }
    if(o) fclose(o);
    printf("speed: loop %.2f..%.2f m/s, exit to camhold %.2f..%.2f m/s%s\n",vmin[0],vmax[0],vmin[1],vmax[1],o?" (csv written)":"");
    return 0; }
