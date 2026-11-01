"""preview.py with extra camera views, the "lasers" key and sweep frames, for tuning the atmosphere module
(same command line as preview.py, plus --sweep):

  --sweep 0,0.25,0.5,0.75   pose the lasers at these s = t * rate (atmosphere.laser_pose(), the material's math) and
                            render every view once per value: preview_<module>_<view>_s<100*s>.png; with exactly four
                            values also a 2x2 sheet per view, preview_<module>_<view>_sweep.png (s order: TL TR BL BR)
  Without --sweep the lasers render in their rest pose (the shipped geometry).

  dj_vr      the DJ's eye, level, ~90 x 120 deg: about what the Quest shows (the stock dj view stops at +28 deg)
  dj_turn    the DJ turned around toward the stage and the sky behind it
  crowd_mid  a fan in the middle of the crowd looking at the stage
  laser_src  close on the stage front (laser unit, deck-lip fixtures)
  tracker    close on the back-left sky tracker unit
  horn_l     close on the left horn-tip laser heads; horn_r the same on the right
preview.py itself is not modified: its source is run with these additions.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "preview.py")
CAMS_EXTRA = '''
CAMS.update({
    "dj_vr": ((0, -0.3, 1.65), (0, -60, 1.65), 10),
    "dj_turn": ((0, -0.3, 1.65), (0, 60, 25), 12),
    "crowd_mid": ((3, -30, 0.2), (0, 0, 9), 16),
    "laser_src": ((4, -16, 2.5), (0, -4, 0), 24),
    "tracker": ((-24, -82, 1.5), (-32, -92, 0.5), 35),
    "horn_l": ((-6, -10, 20), (-13.5, -1, 23), 30),
    "horn_r": ((14, -8, 19), (8, 3, 24), 30),
})
'''
LASERS_PLACE = '''
laser_objs = []
for i, bm in enumerate(res.get("lasers", [])):
    ob = place(f"laser{i}", bm, beam_m, "lasers")
    ob.data.uv_layers["UVMap"].active_render = True                  # the texture reads UVMap, not the sweep layers
    lays = [ob.data.uv_layers[n].data for n in ("LaserPivot", "LaserPivotZPhase", "LaserAmp")]   # the sweep inputs
    sweep = {}
    for li, loop in enumerate(ob.data.loops):
        if loop.vertex_index not in sweep:
            (px, py), (pz, ph), (pa, ta) = (tuple(lay[li].uv) for lay in lays)
            sweep[loop.vertex_index] = (Vector((px, py, pz - STAGE_DROP)), ph, pa, ta)
    laser_objs.append((ob, [v.co.copy() for v in ob.data.vertices], sweep))


def pose_lasers(s):
    for ob, rest, sweep in laser_objs:
        for i, v in enumerate(ob.data.vertices):
            pivot, ph, pa, ta = sweep[i]
            v.co = mod.laser_pose(rest[i], pivot, ph, pa, ta, s)
        ob.data.update()

'''
RENDERS = '''# ------------------------------------------------------------------ renders (sweep frames)
import numpy as np  # noqa: E402
SWEEP = [float(v) for v in opt("--sweep", "").split(",") if v]
frames = {}
for s in (SWEEP or [None]):
    if s is not None:
        pose_lasers(s)
    for v in VIEWS:
        if v not in CAMS:
            log(f"unknown view {v}")
            continue
        pos, tgt, lens = CAMS[v]
        cd = bpy.data.cameras.new(v)
        cd.lens, cd.clip_end = lens, 2000
        co = bpy.data.objects.new(v, cd)
        co.location = pos
        co.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        coll.objects.link(co)
        scene.camera = co
        tag = "" if s is None else f"_s{int(round(s * 100)):03d}"
        path = os.path.join(OUT, f"preview_{MODULE}_{v}{tag}.png")
        scene.render.filepath = path
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"render {v}{tag}: {path} ({time.time() - t1:.0f} s)")
        frames.setdefault(v, []).append(path)
if len(SWEEP) == 4:                                    # 2x2 sheet per view (TL, TR, BL, BR = the four s values)
    for v, paths in frames.items():
        tiles = []
        for p in paths:
            img = bpy.data.images.load(p, check_existing=False)
            w, h = img.size
            px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]
            bpy.data.images.remove(img)
            tiles.append(px[: h // 2 * 2, : w // 2 * 2].reshape(h // 2, 2, w // 2, 2, 3).mean(axis=(1, 3)))
        sheet = np.concatenate([np.concatenate(tiles[:2], axis=1), np.concatenate(tiles[2:], axis=1)], axis=0)
        lin = np.where(sheet <= 0.04045, sheet / 12.92, ((sheet + 0.055) / 1.055) ** 2.4)
        path = os.path.join(OUT, f"preview_{MODULE}_{v}_sweep.png")
        kit.write_png(path, lin)
        log(f"sheet {v}: {path}")
log("done")
'''
code = open(SRC, encoding="utf-8").read()
for anchor in ("\n# stage surfaces", 'lights = res.get("lights", [])',
               "# ------------------------------------------------------------------ renders"):
    assert anchor in code, "preview.py changed: update atmosphere_preview.py (" + anchor.strip() + ")"
code = code.replace("\n# stage surfaces", CAMS_EXTRA + "\n# stage surfaces", 1)
code = code.replace('lights = res.get("lights", [])', LASERS_PLACE + 'lights = res.get("lights", [])', 1)
code = code[:code.index("# ------------------------------------------------------------------ renders")] + RENDERS
exec(compile(code, SRC, "exec"), {"__name__": "__main__", "__file__": SRC})
