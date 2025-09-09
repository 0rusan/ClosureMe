# assemble_worker.py
# 以 Blender 背景模式執行：匯入頭/身 → 縮放/對齊/就座/右移 → 裁殘 → 合併 → Mixamo 清理 → 匯出 FBX
# 已拿掉：自動開瀏覽器／檔案總管。可用 --print_json 在結尾輸出結果 JSON。

import bpy, os, sys, math, bmesh, addon_utils, json, argparse, shutil, re
import numpy as np
from mathutils import Vector
from datetime import datetime

# ----------------- args -----------------
def parse_args():
    # 只解析 '--' 之後的參數（Blender 自己的參數會在 '--' 之前）
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []  # 沒有傳入腳本參數時

    ap = argparse.ArgumentParser()
    # 允許手動或自動二選一：手動傳 head/body；或只給 auto_base/auto_dir 由腳本自動抓 001/002
    ap.add_argument("--head", required=False, help="頭 OBJ/FBX/GLB/PLY/STL 路徑")
    ap.add_argument("--body", required=False, help="身體 OBJ/FBX/GLB/PLY/STL 路徑")
    ap.add_argument("--auto_base", default=None,
                    help=r"父資料夾（例：C:\...\Hunyuan3D-2\demo\output）。會自動挑選『資料夾名為純數字且最大的』、且含 001/002.obj 的子資料夾；若無，退回以 mtime 最新者。")
    ap.add_argument("--auto_dir", default=None,
                    help=r"直接指定場景資料夾（例：C:\...\output\036），資料夾內需有 001/002.obj")
    ap.add_argument("--outdir", default=None, help="輸出資料夾(預設=head 所在資料夾或 auto_dir)")
    ap.add_argument("--case",   default=None, help="案例名(預設=head 上層資料夾名或 auto_dir 名稱)")
    ap.add_argument("--export_assembled", action="store_true", help="另存未整理版 FBX")
    ap.add_argument("--target_tris", type=int, default=80000)
    ap.add_argument("--weld_dist", type=float, default=0.0010)
    ap.add_argument("--auto_smooth_deg", type=float, default=60.0)
    ap.add_argument("--right_bias", type=float, default=0.014)
    ap.add_argument("--extra_right", type=float, default=0.006)
    ap.add_argument("--shrink_bias", type=float, default=0.92)
    ap.add_argument("--print_json", action="store_true", help="結尾印出 JSON 給外部程式解析")
    args = ap.parse_args(argv)

    # 參數合法性：必須滿足 (head & body) 或 (auto_base|auto_dir) 其一
    if not ((args.head and args.body) or args.auto_base or args.auto_dir):
        ap.error("請提供 --head 與 --body，或改用 --auto_base / --auto_dir 讓腳本自動抓 001/002")

    return args

ARGS = parse_args()

# ----------------- 自動尋檔（不影響任何組裝參數） -----------------
def _has_required_files(scene_dir: str) -> bool:
    return os.path.isfile(os.path.join(scene_dir, "001.obj")) and \
           os.path.isfile(os.path.join(scene_dir, "002.obj"))

def _pick_scene_by_numeric(base_dir: str):
    """優先挑選資料夾名稱為純數字且最大的；需同時含 001/002.obj。"""
    cand = []
    try:
        for name in os.listdir(base_dir):
            path = os.path.join(base_dir, name)
            if not os.path.isdir(path):
                continue
            if not re.fullmatch(r"\d+", name):
                continue
            if not _has_required_files(path):
                continue
            cand.append((int(name), os.path.getmtime(path), path))
    except FileNotFoundError:
        return None
    if not cand:
        return None
    cand.sort(key=lambda t: (t[0], t[1]), reverse=True)  # 數字大優先；再比 mtime
    return cand[0][2]

def _pick_scene_by_mtime(base_dir: str):
    """備援：沒有數字夾就選 mtime 最新、且含 001/002.obj 的資料夾。"""
    cand = []
    try:
        for name in os.listdir(base_dir):
            path = os.path.join(base_dir, name)
            if not os.path.isdir(path):
                continue
            if not _has_required_files(path):
                continue
            cand.append((os.path.getmtime(path), path))
    except FileNotFoundError:
        return None
    if not cand:
        return None
    cand.sort(key=lambda t: t[0], reverse=True)
    return cand[0][1]

def _resolve_auto_paths():
    """回傳 (scene_dir, head_path, body_path, case_name)。若未使用自動，回傳 None。"""
    if ARGS.auto_dir:
        scene = os.path.normpath(ARGS.auto_dir)
        if not _has_required_files(scene):
            raise RuntimeError(f"[auto_dir] {scene} 缺少 001/002.obj")
        return scene, os.path.join(scene, "001.obj"), os.path.join(scene, "002.obj"), os.path.basename(scene)

    if ARGS.auto_base:
        base = os.path.normpath(ARGS.auto_base)
        scene = _pick_scene_by_numeric(base) or _pick_scene_by_mtime(base)
        if scene is None:
            raise RuntimeError(f"[auto_base] 在 {base} 找不到同時含 001.obj 與 002.obj 的資料夾")
        return scene, os.path.join(scene, "001.obj"), os.path.join(scene, "002.obj"), os.path.basename(scene)

    return None

_auto = _resolve_auto_paths()

if _auto:
    _scene_dir, _head_auto, _body_auto, _case_auto = _auto
    HEAD_PATH = os.path.normpath(_head_auto)
    BODY_PATH = os.path.normpath(_body_auto)
    EXPORT_DIR = os.path.normpath(ARGS.outdir or _scene_dir)
    CASE_NAME  = (ARGS.case or _case_auto)
else:
    # 維持舊有手動行為
    HEAD_PATH = os.path.normpath(ARGS.head)
    BODY_PATH = os.path.normpath(ARGS.body)
    EXPORT_DIR = os.path.normpath(ARGS.outdir or os.path.dirname(HEAD_PATH))
    CASE_NAME  = (ARGS.case or os.path.basename(os.path.dirname(HEAD_PATH)) or "case")

STAMP      = datetime.now().strftime("%Y%m%d_%H%M%S")
EXPORT_FBX_ASSEMBLED = os.path.join(EXPORT_DIR, f"{CASE_NAME}_assembled_{STAMP}.fbx")
EXPORT_FBX_MIXAMO    = os.path.join(EXPORT_DIR, f"{CASE_NAME}_mixamo_{STAMP}.fbx")

# ===== 幾何/對齊參數（沿用你的設置） =====
GAP_Z, MIN_SAFE_GAP = 0.0005, 0.0002
RING_BAND_RATIO, BODY_TOP_P, HEAD_BASE_P = 0.012, 0.985, 0.14

HEAD_MAX_HFRAC, HEAD_SH_FRAC, MARGIN_RADIUS = 0.072, 0.235, 0.86
SCALE_CLAMP_MIN, SCALE_CLAMP_MAX, FAILSAFE_CAP = 0.28, 0.56, 0.68
SHRINK_BIAS = ARGS.shrink_bias

TORSO_BAND_BELOW_NECK = (0.23, 0.06)
RIGHT_BIAS, RIGHT_MAX, RIGHT_ITERS, RIGHT_STEP, RIGHT_EPS = ARGS.right_bias, 0.080, 8, 0.008, 0.0015
EXTRA_RIGHT = ARGS.extra_right

TRIM_MARGIN = 0.0016
JOIN_AT_END, SHADE_SMOOTH = True, True

# Mixamo 準備
PREP_MIXAMO        = True
WELD_DIST          = ARGS.weld_dist
AUTO_SMOOTH_DEG    = ARGS.auto_smooth_deg
TARGET_TRIS        = ARGS.target_tris
DECIMATE_RATIO_MIN = 0.10
DECIMATE_RATIO_MAX = 0.60
EXPORT_ASSEMBLED   = ARGS.export_assembled
EXPORT_MIXAMO_FBX  = True

# ===== helper =====
def _enable(mod):
    try: addon_utils.enable(mod, default_set=True, persistent=True)
    except: pass

def import_any_mesh(path: str):
    if not os.path.isfile(path): raise RuntimeError(f"找不到檔案：{path}")
    ext = os.path.splitext(path.lower())[1]
    before = set(bpy.data.objects); ok=False
    if ext == ".obj":
        _enable("io_scene_obj")
        try:
            bpy.ops.wm.obj_import(filepath=path); ok=True
        except Exception:
            try:
                bpy.ops.import_scene.obj(filepath=path); ok=True
            except Exception as e:
                raise RuntimeError("OBJ 匯入失敗：請啟用 'OBJ' 擴充或改用 FBX/GLB/PLY/STL。原始錯誤：%r" % e)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path); ok=True
    elif ext in (".gltf",".glb"):
        bpy.ops.import_scene.gltf(filepath=path); ok=True
    elif ext == ".ply":
        _enable("io_mesh_ply"); bpy.ops.import_mesh.ply(filepath=path); ok=True
    elif ext == ".stl":
        _enable("io_mesh_stl"); bpy.ops.import_mesh.stl(filepath=path); ok=True
    else:
        raise RuntimeError(f"不支援副檔名：{ext}")
    new=[o for o in (set(bpy.data.objects)-before) if o.type=="MESH"]
    if not ok or not new: raise RuntimeError(f"匯入失敗或沒有 mesh：{path}")
    return new

def bounds_world(objs):
    pts=[]
    for o in objs:
        for c in o.bound_box: pts.append(o.matrix_world @ Vector(c))
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def all_world_vertices(objs, cap=None):
    pts=[]
    for o in objs:
        mw=o.matrix_world; me=o.data
        step=1
        if cap and len(me.vertices)>cap: step=max(1, len(me.vertices)//cap)
        for i,v in enumerate(me.vertices):
            if cap and (i%step): continue
            pts.append(mw @ v.co)
    return pts

def quantile(vals, p):
    if not vals: return 0.0
    vs=sorted(vals); i=max(0, min(len(vs)-1, int(round((len(vs)-1)*p))))
    return vs[i]

def ring_points_by_z(objs, z, band, cap=8000):
    pts=[]
    for o in objs:
        mw=o.matrix_world; me=o.data
        step=1
        if cap and len(me.vertices)>cap: step=max(1, len(me.vertices)//cap)
        for i,v in enumerate(me.vertices):
            if cap and (i%step): continue
            w=mw@v.co
            if z-band<=w.z<=z+band: pts.append(w)
    return pts

def fit_plane_pca(pts):
    if len(pts)<3:
        c=sum(pts, Vector((0,0,0)))/max(1,len(pts)); return c, Vector((0,0,1))
    P=np.array([[p.x,p.y,p.z] for p in pts], dtype=np.float64)
    c=P.mean(axis=0); Q=P-c
    C=(Q.T@Q)/max(1,len(P))
    _,V=np.linalg.eigh(C)
    n=Vector((float(V[0,0]),float(V[1,0]),float(V[2,0]))).normalized()
    return Vector((c[0],c[1],c[2])), n

def ring_radius_width(pts, c, n):
    ref=Vector((1,0,0))
    if abs(n.dot(ref))>0.9: ref=Vector((0,1,0))
    u=(ref-n*ref.dot(n)).normalized(); v=n.cross(u).normalized()
    rs=[]; xs=[]; ys=[]
    for p in pts:
        d=p-c; x=d.dot(u); y=d.dot(v)
        xs.append(x); ys.append(y); rs.append(math.hypot(x,y))
    if not rs: return 0.0, 0.0, u, v
    xs=sorted(xs); ys=sorted(ys)
    width = 0.5*((xs[int(0.95*(len(xs)-1))]-xs[int(0.05*(len(xs)-1))])
                 + (ys[int(0.95*(len(ys)-1))]-ys[int(0.05*(len(ys)-1))]))
    return float(np.median(rs)), float(width), u, v

def scale_mesh_vertices_about_world_pivot(objs, s, pivot_world: Vector):
    if abs(s-1.0)<1e-8: return
    for o in objs:
        mw=o.matrix_world; pivot_local = mw.inverted() @ pivot_world
        me=o.data
        bm=bmesh.new(); bm.from_mesh(me)
        for v in bm.verts:
            v.co = pivot_local + s * (v.co - pivot_local)
        bm.to_mesh(me); bm.free(); me.update()

def trim_head_below_world_z(head_objs, z_cut):
    for o in head_objs:
        mw=o.matrix_world; me=o.data
        bm=bmesh.new(); bm.from_mesh(me)
        todel=[v for v in bm.verts if (mw @ v.co).z < z_cut]
        if todel:
            bmesh.ops.delete(bm, geom=todel, context='VERTS')
        bm.to_mesh(me); bm.free(); me.update()

def apply_children_and_clear(container):
    kids = list(container.children)
    if not kids: return []
    bpy.ops.object.select_all(action="DESELECT")
    for k in kids: k.select_set(True)
    bpy.context.view_layer.objects.active = kids[0]
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.select_all(action="DESELECT")
    container.select_set(True); bpy.ops.object.delete()
    return kids

# ---------- bmesh 版焊接/清理/法線 ----------
def bmesh_weld_and_cleanup(obj, merge_dist=0.0010, delete_loose=True, recalc_normals=True):
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
    if delete_loose:
        loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]
        if loose_edges: bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
        loose_verts = [v for v in bm.verts if len(v.link_edges) == 0]
        if loose_verts: bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
    if recalc_normals:
        try: bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        except Exception: bm.normal_update()
    bm.to_mesh(me); bm.free(); me.update()

# ---------- Mixamo 準備 ----------
def mesh_tri_count(obj) -> int:
    me = obj.data
    me.calc_loop_triangles()
    return len(me.loop_triangles)

def set_origin_to_feet_center(obj, band_frac=0.02):
    mw = obj.matrix_world
    zs = [ (mw @ v.co).z for v in obj.data.vertices ]
    if not zs: return
    zmin, zmax = min(zs), max(zs)
    band = max(1e-5, (zmax - zmin) * band_frac)
    foot_pts = [ (mw @ v.co) for v in obj.data.vertices if (zmin <= (mw @ v.co).z <= zmin + band) ]
    if not foot_pts:
        cx = sum((mw @ v.co).x for v in obj.data.vertices)/len(obj.data.vertices)
        cy = sum((mw @ v.co).y for v in obj.data.vertices)/len(obj.data.vertices)
        cz = zmin
    else:
        xs = sorted(p.x for p in foot_pts); ys = sorted(p.y for p in foot_pts)
        cx = xs[len(xs)//2]; cy = ys[len(ys)//2]; cz = zmin
    target_world = Vector((cx, cy, 0.0))
    target_local = obj.matrix_world.inverted() @ Vector((cx, cy, cz))
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    for v in bm.verts: v.co -= target_local
    bm.to_mesh(me); bm.free(); me.update()
    obj.location = target_world

def set_auto_smooth_compat(obj, angle_deg=60.0):
    ang = math.radians(angle_deg)
    me = obj.data
    if hasattr(me, "use_auto_smooth"):
        try:
            me.use_auto_smooth = True
            if hasattr(me, "auto_smooth_angle"): me.auto_smooth_angle = ang
            return
        except Exception:
            pass
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.shade_auto_smooth(angle=ang)
    except Exception:
        pass

def decimate_to_target_tris(obj, target_tris, rmin=0.10, rmax=0.60):
    curr = mesh_tri_count(obj)
    if curr <= target_tris:
        return
    ratio = max(rmin, min(rmax, target_tris / max(1, curr)))
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True); bpy.context.view_layer.objects.active=obj
    dec = obj.modifiers.new("DecimateForMixamo", 'DECIMATE')
    dec.decimate_type = 'COLLAPSE'
    dec.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=dec.name)

def prep_for_mixamo(obj, weld_dist=0.0010, auto_smooth_deg=60.0, target_tris=80000):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True); bpy.context.view_layer.objects.active=obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bmesh_weld_and_cleanup(obj, merge_dist=weld_dist, delete_loose=True, recalc_normals=True)
    set_auto_smooth_compat(obj, angle_deg=auto_smooth_deg)
    set_origin_to_feet_center(obj)
    decimate_to_target_tris(obj, target_tris, rmin=DECIMATE_RATIO_MIN, rmax=DECIMATE_RATIO_MAX)

def export_fbx_mixamo(obj, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True); bpy.context.view_layer.objects.active=obj
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        apply_unit_scale=True,
        bake_space_transform=False,
        object_types={'MESH'},
        mesh_smooth_type='FACE',
        use_triangles=True,
        add_leaf_bones=False,
        axis_forward='-Z', axis_up='Y',
        path_mode='COPY', embed_textures=True,
    )

# ----------------- main -----------------
def main():
    # 清場
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False, confirm=False)

    # 匯入
    head_objs = import_any_mesh(HEAD_PATH)
    body_objs = import_any_mesh(BODY_PATH)

    # 分組
    head_grp=bpy.data.objects.new("HEAD_GRP", None); bpy.context.collection.objects.link(head_grp)
    body_grp=bpy.data.objects.new("BODY_GRP", None); bpy.context.collection.objects.link(body_grp)
    for o in head_objs: o.parent=head_grp
    for o in body_objs: o.parent=body_grp

    # 幾何統計
    h_mn,h_mx = bounds_world(head_objs)
    b_mn,b_mx = bounds_world(body_objs)
    Hh=max(1e-6, h_mx.z-h_mn.z)
    Hb=max(1e-6, b_mx.z-b_mn.z)

    head_pts = all_world_vertices(head_objs, cap=60000)
    body_pts = all_world_vertices(body_objs, cap=60000)
    head_base_z = quantile([p.z for p in head_pts], HEAD_BASE_P)
    body_top_z  = quantile([p.z for p in body_pts], BODY_TOP_P)

    # 頸口（掃最小半徑層）
    band_b = RING_BAND_RATIO*Hb
    z0=b_mn.z+0.50*(b_mx-b_mn).z; z1=b_mn.z+0.82*(b_mx-b_mn).z
    zs=[z0+(z1-z0)*i/48 for i in range(49)]
    best=(None,1e9)
    for z in zs:
        ring=ring_points_by_z(body_objs, z, band_b)
        if len(ring)<24: continue
        c,n=fit_plane_pca(ring)
        r,_,_,_ = ring_radius_width(ring, c, n)
        if 0<r<best[1]: best=((z,c,n,r), r)
    if best[0] is None:
        neck_z = body_top_z
        ring = ring_points_by_z(body_objs, neck_z, band_b)
        neck_c = sum(ring, Vector((0,0,0)))/len(ring) if ring else Vector(((b_mn.x+b_mx.x)/2,(b_mn.y+b_mx.y)/2,neck_z))  # 修正 b_mx.y
        neck_r = max(1e-6, np.median([ (p-neck_c).length for p in (ring if ring else [neck_c]) ]))
    else:
        neck_z, neck_c, _n, neck_r = best[0]

    # 頭底（掃最小半徑層）
    band_h = RING_BAND_RATIO * Hh
    zc0 = h_mn.z + 0.05*(h_mx.z - h_mn.z)
    zc1 = h_mn.z + 0.35*(h_mx.z - h_mn.z)
    zs_h = [zc0 + (zc1 - zc0) * i / 36 for i in range(37)]
    best = (None, 1e9)
    for z in zs_h:
        ring = ring_points_by_z(head_objs, z, band_h)
        if len(ring) < 24: continue
        c, n = fit_plane_pca(ring)
        r, w, _, _ = ring_radius_width(ring, c, n)
        if 0 < r < best[1]: best = ((z, c, n, r, w), r)
    if best[0] is None:
        head_ring = ring_points_by_z(head_objs, head_base_z, band_h)
        head_c = sum(head_ring, Vector((0,0,0)))/len(head_ring) if head_ring else Vector(((h_mn.x+h_mx.x)/2,(h_mn.y+h_mx.y)/2,head_base_z))
        head_r = max(1e-6, np.median([ (p-head_c).length for p in (head_ring if head_ring else [head_c]) ]))
        head_w = 2*head_r; ring_z=head_base_z
    else:
        ring_z, head_c, _nh, head_r, head_w = best[0]

    # 肩寬（頸口下方 6% 身高）
    z_sh = neck_z - 0.06*Hb
    sh_ring = ring_points_by_z(body_objs, z_sh, max(band_b*1.5, 0.010))
    if len(sh_ring)<24:
        shoulder_w = 0.5*((b_mx.x-b_mn.x)+(b_mx.y-b_mn.y))
    else:
        c_sh, n_sh = fit_plane_pca(sh_ring)
        shoulder_w = ring_radius_width(sh_ring, c_sh, n_sh)[1]

    # === 縮放（取最嚴格 + 偏置） ===
    s_r = (neck_r*MARGIN_RADIUS) / max(1e-9, head_r)
    s_h = (HEAD_MAX_HFRAC*Hb) / Hh
    s_w = (HEAD_SH_FRAC*shoulder_w) / max(1e-9, head_w)
    s_raw = min(s_r, s_h, s_w)
    s = max(SCALE_CLAMP_MIN, min(SCALE_CLAMP_MAX, s_raw))
    if not np.isfinite(s_raw) or s > FAILSAFE_CAP:
        s = min(FAILSAFE_CAP, SCALE_CLAMP_MAX)
    s *= SHRINK_BIAS
    s = max(SCALE_CLAMP_MIN, min(SCALE_CLAMP_MAX, s))
    # 寫入縮放（繞頸口中心）
    scale_mesh_vertices_about_world_pivot(head_objs, s, neck_c)

    # === XY 對齊到頸口中心 ===
    h_mn2,h_mx2 = bounds_world(head_objs)
    band_h2 = RING_BAND_RATIO * max(1e-6, (h_mx2.z-h_mn2.z))
    head_ring2 = ring_points_by_z(head_objs, ring_z, band_h2)
    if head_ring2:
        c_head2 = sum(head_ring2, Vector((0,0,0)))/len(head_ring2)
        delta_xy = Vector((neck_c.x - c_head2.x, neck_c.y - c_head2.y, 0.0))
        head_grp.location += delta_xy
        bpy.context.view_layer.update()
    else:
        c_head2 = head_c

    # === Z 就座（分位數） ===
    head_pts2 = all_world_vertices(head_objs, cap=60000)
    head_base_z2 = quantile([p.z for p in head_pts2], HEAD_BASE_P)
    dz = (body_top_z + GAP_Z) - head_base_z2
    head_grp.location.z += dz
    bpy.context.view_layer.update()

    # === 自動右移（躯幹中線 X + 偏置） ===
    band_lo = neck_z - TORSO_BAND_BELOW_NECK[0]*Hb
    band_hi = neck_z - TORSO_BAND_BELOW_NECK[1]*Hb
    torso_pts = [p for p in body_pts if (band_lo <= p.z <= band_hi)]
    torso_cx  = quantile([p.x for p in torso_pts], 0.50) if torso_pts else ((b_mn.x+b_mx.x)/2)

    moved = 0.0
    for _ in range(RIGHT_ITERS):
        head_ring3 = ring_points_by_z(head_objs, ring_z, band_h2)
        c_head3 = (sum(head_ring3, Vector((0,0,0)))/len(head_ring3)) if head_ring3 else c_head2
        target_cx = torso_cx + RIGHT_BIAS
        dx_need   = target_cx - c_head3.x
        if dx_need <= RIGHT_EPS: break
        step = min(RIGHT_STEP, dx_need)
        if moved + step > RIGHT_MAX: step = max(0.0, RIGHT_MAX - moved)
        if step <= 0.0: break
        head_grp.location.x += step
        moved += step
        bpy.context.view_layer.update()

    if EXTRA_RIGHT != 0.0:
        head_grp.location.x += EXTRA_RIGHT
        bpy.context.view_layer.update()

    # === 內插保險 ===
    head_pts3 = all_world_vertices(head_objs, cap=60000)
    head_base_z3 = quantile([p.z for p in head_pts3], HEAD_BASE_P)
    gap_now = head_base_z3 - body_top_z
    if gap_now < MIN_SAFE_GAP:
        fix = (MIN_SAFE_GAP - gap_now)
        head_grp.location.z += fix
        bpy.context.view_layer.update()

    # === 裁殘 ===
    trim_head_below_world_z(head_objs, body_top_z + TRIM_MARGIN)

    # === 合併（Ctrl+J） ===
    if JOIN_AT_END:
        head_objs_f = apply_children_and_clear(head_grp)
        body_objs_f = apply_children_and_clear(body_grp)
        sel = head_objs_f + body_objs_f
        bpy.ops.object.select_all(action="DESELECT")
        for o in sel: o.select_set(True)
        bpy.context.view_layer.objects.active = sel[0]
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.join()
        joined = bpy.context.view_layer.objects.active
        if SHADE_SMOOTH:
            try: bpy.ops.object.shade_smooth()
            except: pass
    else:
        head_objs_f = apply_children_and_clear(head_grp)
        body_objs_f = apply_children_and_clear(body_grp)
        bpy.ops.object.select_all(action="DESELECT")
        for o in (head_objs_f + body_objs_f): o.select_set(True)
        bpy.context.view_layer.objects.active = head_objs_f[0]
        bpy.ops.object.duplicate_move()
        dup_sel = [o for o in bpy.context.selected_objects]
        for o in dup_sel: o.select_set(True)
        bpy.ops.object.join()
        joined = bpy.context.view_layer.objects.active

    # === 另存未整理版 FBX（可選） ===
    if EXPORT_ASSEMBLED:
        os.makedirs(os.path.dirname(EXPORT_FBX_ASSEMBLED), exist_ok=True)
        bpy.ops.object.select_all(action="DESELECT"); joined.select_set(True)
        bpy.context.view_layer.objects.active = joined
        bpy.ops.export_scene.fbx(
            filepath=EXPORT_FBX_ASSEMBLED,
            use_selection=True,
            apply_unit_scale=True,
            bake_space_transform=False,
            object_types={'MESH'},
            mesh_smooth_type='FACE',
            use_triangles=True,
            add_leaf_bones=False,
            axis_forward='-Z', axis_up='Y',
            path_mode='COPY', embed_textures=True,
        )

    # === Mixamo 準備（bmesh 清理 + 相容 Auto Smooth） ===
    if PREP_MIXAMO:
        prep_for_mixamo(joined, weld_dist=WELD_DIST, auto_smooth_deg=AUTO_SMOOTH_DEG, target_tris=TARGET_TRIS)

    # === 匯出 Mixamo 版 FBX ===
    export_fbx_mixamo(joined, EXPORT_FBX_MIXAMO)

    # 統計資訊
    tris_final = mesh_tri_count(joined)
    (mn, mx) = bounds_world([joined])
    size = (mx.x-mn.x, mx.y-mn.y, mx.z-mn.z)

    # 印 JSON（給外部 API 讀）
    if ARGS.print_json:
        out = {
            "status": "ok",
            "case": CASE_NAME,
            "stamp": STAMP,
            "assembled_path": EXPORT_FBX_ASSEMBLED if EXPORT_ASSEMBLED else None,
            "mixamo_path": EXPORT_FBX_MIXAMO,
            "triangles": tris_final,
            "bbox_size": {"x": size[0], "y": size[1], "z": size[2]},
            "params": {
                "shrink_bias": SHRINK_BIAS,
                "right_bias": RIGHT_BIAS,
                "extra_right": EXTRA_RIGHT,
                "target_tris": TARGET_TRIS,
                "weld_dist": WELD_DIST,
                "auto_smooth_deg": AUTO_SMOOTH_DEG,
            }
        }
        print("===ASSEMBLE_JSON_BEGIN===")
        print(json.dumps(out, ensure_ascii=False))
        print("===ASSEMBLE_JSON_END===")

if __name__ == "__main__":
    main()
