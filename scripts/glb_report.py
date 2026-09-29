#!/usr/bin/env python3
"""Parse a .glb (glTF binary) and emit a skeleton/mesh report as Markdown.

Dependency-free: reads the JSON chunk directly. Reports the joint hierarchy + bind-pose TRS,
a cross-check against Tribe's EReadyPlayerMeBone set, mesh/material/UV stats, and morph targets.

Usage: python scripts/glb_report.py IN.glb OUT.md
"""
import json
import struct
import sys

# Tribe's EReadyPlayerMeBone enum (from libUnreal.so, phase 3) — the bones the loader references.
RPM_BONES = [
    "AvatarRoot", "Hips", "Spine", "Neck", "Head", "LeftEye", "RightEye",
    "LeftHand", "LeftHandThumb1", "LeftHandThumb2", "LeftHandThumb3",
    "LeftHandIndex1", "LeftHandIndex2", "LeftHandIndex3",
    "LeftHandMiddle1", "LeftHandMiddle2", "LeftHandMiddle3",
    "LeftHandRing1", "LeftHandRing2", "LeftHandRing3",
    "LeftHandPinky1", "LeftHandPinky2", "LeftHandPinky3",
    "RightHand", "RightHandThumb1", "RightHandThumb2", "RightHandThumb3",
    "RightHandIndex1", "RightHandIndex2", "RightHandIndex3",
    "RightHandMiddle1", "RightHandMiddle2", "RightHandMiddle3",
    "RightHandRing1", "RightHandRing2", "RightHandRing3",
    "RightHandPinky1", "RightHandPinky2", "RightHandPinky3",
]


def load_glb(path):
    d = open(path, "rb").read()
    assert d[:4] == b"glTF", "not a glb"
    ver, length = struct.unpack_from("<II", d, 4)
    off = 12
    gltf = None
    while off < length:
        clen, ctype = struct.unpack_from("<II", d, off)
        chunk = d[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:      # 'JSON'
            gltf = json.loads(chunk.decode("utf-8"))
        off += 8 + clen
    return gltf, len(d)


def fmt_vec(v, n=4):
    if v is None:
        return None
    return "[" + ", ".join(f"{x:.{n}g}" for x in v) + "]"


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    inp, outp = argv
    g, total = load_glb(inp)
    nodes = g.get("nodes", [])
    L = []
    def w(s=""):
        L.append(s)

    w(f"# Skeleton report — `{inp.split('/')[-1]}`")
    w()
    asset = g.get("asset", {})
    w(f"- glTF {asset.get('version')}, generator: `{asset.get('generator')}`")
    w(f"- file size: {total:,} bytes; nodes: {len(nodes)}; meshes: {len(g.get('meshes', []))}; "
      f"skins: {len(g.get('skins', []))}; materials: {len(g.get('materials', []))}; "
      f"animations: {len(g.get('animations', []))}")
    w()

    # parent map
    parent = {i: None for i in range(len(nodes))}
    for i, nd in enumerate(nodes):
        for c in nd.get("children", []):
            parent[c] = i
    def nname(i):
        return nodes[i].get("name", f"node{i}")

    # ---- skins / skeleton ----
    skins = g.get("skins", [])
    accessors = g.get("accessors", [])
    for si, sk in enumerate(skins):
        joints = sk.get("joints", [])
        ibm = sk.get("inverseBindMatrices")
        ibm_count = accessors[ibm]["count"] if ibm is not None else None
        w(f"## Skin {si}: {len(joints)} joints; inverseBindMatrices count = {ibm_count}; "
          f"skeleton root node = {sk.get('skeleton')}")
        w()
        jset = set(joints)
        # roots within this skin = joints whose parent is not a joint
        roots = [j for j in joints if parent[j] not in jset]
        w("### Hierarchy (indented tree; bind-pose local TRS)")
        w("```")
        def rec(i, depth):
            nd = nodes[i]
            t = nd.get("translation"); r = nd.get("rotation"); s = nd.get("scale")
            trs = []
            if t: trs.append("T" + fmt_vec(t, 4))
            if r: trs.append("R" + fmt_vec(r, 4))
            if s and [round(x, 4) for x in s] != [1, 1, 1]: trs.append("S" + fmt_vec(s, 4))
            L.append("  " * depth + f"{nname(i)} (node {i})" + ("  " + " ".join(trs) if trs else ""))
            for c in nd.get("children", []):
                if c in jset:
                    rec(c, depth + 1)
        for rt in roots:
            rec(rt, 0)
        w("```")
        w()
        # ordered joint list with parent index (index = position in skin.joints)
        w("### Joint list (skin index → name, parent skin-index)")
        w("```")
        jpos = {j: k for k, j in enumerate(joints)}
        for k, j in enumerate(joints):
            p = parent[j]
            pk = jpos.get(p, -1)
            L.append(f"{k:3d}  {nname(j):28s} parent={pk:>3}")
        w("```")
        w()
        # RPM cross-check
        names = {nname(j) for j in joints}
        present = [b for b in RPM_BONES if b in names]
        missing = [b for b in RPM_BONES if b not in names]
        extra = sorted(names - set(RPM_BONES))
        w("### Cross-check vs EReadyPlayerMeBone")
        w(f"- present ({len(present)}/{len(RPM_BONES)}): {', '.join(present) if present else '(none)'}")
        w(f"- MISSING from GLB: {', '.join(missing) if missing else '(none)'}")
        w(f"- extra joints in GLB not in enum ({len(extra)}): {', '.join(extra) if extra else '(none)'}")
        w()

    # ---- meshes ----
    materials = g.get("materials", [])
    textures = g.get("textures", [])
    images = g.get("images", [])
    w("## Meshes")
    for mi, m in enumerate(g.get("meshes", [])):
        prims = m.get("primitives", [])
        tnames = m.get("extras", {}).get("targetNames")
        w(f"### mesh {mi}: `{m.get('name','')}` — {len(prims)} primitive(s)"
          + (f"; morph targetNames: {len(tnames)}" if tnames else ""))
        for pi, p in enumerate(prims):
            attrs = p.get("attributes", {})
            pos = attrs.get("POSITION")
            vcount = accessors[pos]["count"] if pos is not None else "?"
            uvs = sorted(a for a in attrs if a.startswith("TEXCOORD_"))
            joints_attr = [a for a in attrs if a.startswith("JOINTS_")]
            mat = p.get("material")
            matname = materials[mat].get("name", f"material{mat}") if mat is not None else "(none)"
            ntargets = len(p.get("targets", []))
            w(f"  - prim {pi}: verts={vcount}; UV channels={len(uvs)} {uvs}; "
              f"skinned={'yes' if joints_attr else 'no'} {joints_attr}; material=`{matname}`; "
              f"morph targets={ntargets}")
        if tnames:
            w(f"  - morph target names: {', '.join(tnames)}")
        w()

    # ---- materials / textures ----
    w("## Materials & textures")
    for mi, m in enumerate(materials):
        pbr = m.get("pbrMetallicRoughness", {})
        texrefs = []
        for key, slot in [("baseColorTexture", pbr.get("baseColorTexture")),
                          ("metallicRoughnessTexture", pbr.get("metallicRoughnessTexture")),
                          ("normalTexture", m.get("normalTexture")),
                          ("emissiveTexture", m.get("emissiveTexture")),
                          ("occlusionTexture", m.get("occlusionTexture"))]:
            if slot is not None:
                ti = slot.get("index")
                img = textures[ti].get("source") if ti is not None and ti < len(textures) else None
                iname = images[img].get("name", images[img].get("mimeType", "")) if img is not None and img < len(images) else "?"
                texrefs.append(f"{key}->img{img}({iname})")
        w(f"- material {mi}: `{m.get('name','')}` alphaMode={m.get('alphaMode','OPAQUE')} "
          f"doubleSided={m.get('doubleSided', False)}; textures: {', '.join(texrefs) if texrefs else '(none)'}")
    w(f"\n- total images: {len(images)} "
      f"({', '.join(sorted({im.get('mimeType','?') for im in images}))})")
    w()

    open(outp, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print(f"wrote {outp} ({len(L)} lines)")
    # console summary
    if skins:
        j = skins[0].get("joints", [])
        print(f"skin0 joints={len(j)}  meshes={len(g.get('meshes', []))}  "
              f"materials={len(materials)}  images={len(images)}")


if __name__ == "__main__":
    main(sys.argv[1:])
