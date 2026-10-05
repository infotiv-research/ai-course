"""INFOTIV — collaborative robot arm with glass letters, seamless infinite loop.

Variant of robotarm.py: the word is made of clear glass letters with glowing
orange cores (as in glass.py), lit by glass.py's softbox + orbiting rig of
coloured caustic spots (Cycles), with no safety ring on the floor.


A clean white/orange cobot stands behind a studio pedestal carrying the word
INFOTIV. Each cycle it wakes up (status ring turns from teal to orange), reaches
over, pinches the "O", lifts it towards the camera, gives it a precise 360° turn,
sets it back exactly in its slot and returns to its rest pose.

All joint angles come from an analytic IK solve of a periodic tool path and are
baked as per-frame linear keys; everything is a function of u = ((f-1) mod LOOP)/LOOP,
so frame LOOP+1 is identical to frame 1.

Standalone copy of the "liftlow" variant: the arm shows the O low, in front of its own
slot. Run through ./build.sh, or directly inside the container:

    blender -b -P scene.py -- [--preview] [--frames 1,60] [--samples 32] [--save]
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW = "--preview" in ARGS
SAVE = "--save" in ARGS
FRAMES = [int(f) for f in ARGS[ARGS.index("--frames") + 1].split(",")] if "--frames" in ARGS else None
SAMPLES = int(ARGS[ARGS.index("--samples") + 1]) if "--samples" in ARGS else None

ASSETS = "/work/assets/"
SLUG = "robotarm_glass_liftlow"
VARIANT = "liftlow"
OUT = "/work/out/"
FPS, LOOP = 30, 240                      # 8-second loop
TAU = 2 * math.pi
ORANGE = (1.0, 0.147, 0.0003)            # #FF6B00 linear
NAVY = (0.019, 0.042, 0.1)
TEAL = (0.02, 0.6, 0.45)

# pedestal / letters
PED_H = 0.34
TEXT_SIZE = 1.18
HALF_T = 0.12                            # half thickness of the letters (extrude+bevel)
BEVEL = 0.02
TUBE = 0.044                             # glowing core radius (glass.py's 0.075 scaled to this text size)
CORE = (1.0, 0.075, 0.0)                 # pushed redder: the tone-mapper warms it back to #FF6B00

# robot geometry
BASE = Vector((3.1, 0.95, 0.0))
SH_H = 1.2                              # shoulder pivot height
L1, L2 = 2.3, 2.1                       # upper arm / forearm
L3 = 0.62                                # wrist pivot -> tool point (between fingertips)
FINGER_OPEN = 0.30
FINGER_CLOSED = HALF_T + 0.035


# ---------------------------------------------------------------- helpers
def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (x * 6 - 15) + 10)   # smootherstep


def lerp(a, b, t):
    return a + (b - a) * t


def mat_principled(name, color, rough=0.35, metal=0.0, coat=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.05
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def mat_emission(name, color, strength):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    return m, em


def finish(ob, mat, parent=None, loc=(0, 0, 0), smooth_angle=40, bevel=0.0):
    """Apply the primitive's transform into its mesh, then hang it under `parent`."""
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(smooth_angle))
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = "ANGLE"
    ob.data.materials.append(mat)
    if parent:
        ob.parent = parent
    ob.location = loc
    return ob


def cyl(r, depth, axis, mat, parent=None, loc=(0, 0, 0), offset=(0, 0, 0), verts=48, bevel=0.0):
    rot = {"X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=offset, rotation=rot)
    return finish(bpy.context.active_object, mat, parent, loc, bevel=bevel)


def box(size, mat, parent=None, loc=(0, 0, 0), offset=(0, 0, 0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=offset)
    ob = bpy.context.active_object
    ob.scale = size
    return finish(ob, mat, parent, loc, bevel=bevel)


def empty(name, parent=None, loc=(0, 0, 0)):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.2
    bpy.context.collection.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    return ob


def light(name, kind, loc, energy, color, target, size=1.0, spot=50):
    ob = bpy.data.objects.new(name, bpy.data.lights.new(name, kind))
    ob.data.energy = energy
    ob.data.color = color
    if kind == "AREA":
        ob.data.size = size
    if kind == "SPOT":
        ob.data.spot_size = math.radians(spot)
        ob.data.spot_blend = 1.0
        ob.data.shadow_soft_size = size
    ob.location = loc
    bpy.context.collection.objects.link(ob)
    ob.constraints.new("TRACK_TO").target = target
    return ob


# ---------------------------------------------------------------- scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, LOOP
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.resolution_percentage = 50 if PREVIEW else 100
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
scene.cycles.device = "GPU"
cy = scene.cycles
cy.samples = SAMPLES or 16          # OIDN cleans this up
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.02
cy.use_denoising = True
cy.denoiser = "OPENIMAGEDENOISE"
cy.denoising_use_gpu = True
cy.seed = 7
cy.use_animated_seed = False
cy.max_bounces = 10
cy.transmission_bounces = 10
cy.glossy_bounces = 4
cy.diffuse_bounces = 2
cy.transparent_max_bounces = 8
cy.caustics_refractive = True
cy.caustics_reflective = False
cy.blur_glossy = 0.5
cy.sample_clamp_indirect = 8.0
scene.render.use_persistent_data = True
scene.view_settings.view_transform = "Filmic"
scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = 0.3

world = bpy.data.worlds.new("World")
scene.world = world
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.9, 0.92, 0.95, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.2

# ---- cyclorama: floor sweeping up into a back wall
bm = bmesh.new()
R, WALL_Y = 4.0, 9.0
prof = [(-30.0, 0.0), (WALL_Y - R, 0.0)]
for i in range(1, 17):
    a = i / 16 * math.pi / 2
    prof.append((WALL_Y - R + R * math.sin(a), R - R * math.cos(a)))
prof.append((WALL_Y, 45.0))
W = 90
rows = []
for (y, z) in prof:
    rows.append((bm.verts.new((-W, y, z)), bm.verts.new((W, y, z))))
for (a0, a1), (b0, b1) in zip(rows, rows[1:]):
    bm.faces.new((a0, a1, b1, b0))
me = bpy.data.meshes.new("cyc")
bm.to_mesh(me)
for p in me.polygons:
    p.use_smooth = True
cyc = bpy.data.objects.new("cyc", me)
bpy.context.collection.objects.link(cyc)
m_cyc = mat_principled("studio", (0.86, 0.865, 0.875), rough=0.32)
cyc.data.materials.append(m_cyc)
cyc.cycles.is_caustics_receiver = True

# ---- materials
m_white = mat_principled("robot_white", (0.82, 0.82, 0.8), rough=0.28, coat=0.4)
m_grey = mat_principled("robot_grey", (0.035, 0.037, 0.042), rough=0.4, metal=0.2)
m_steel = mat_principled("steel", (0.6, 0.6, 0.62), rough=0.25, metal=1.0)
m_orange = mat_principled("robot_orange", ORANGE, rough=0.3, coat=0.5)
m_glass = bpy.data.materials.new("glass")
gb = m_glass.node_tree.nodes["Principled BSDF"]
gb.inputs["Base Color"].default_value = (0.97, 0.98, 1.0, 1)
gb.inputs["Roughness"].default_value = 0.0
gb.inputs["IOR"].default_value = 1.5
gb.inputs["Transmission Weight"].default_value = 1.0
m_core = mat_principled("core", CORE, rough=0.3, emit=CORE, strength=6.0)
kb = m_core.node_tree.nodes["Principled BSDF"]
m_ped = mat_principled("pedestal", (0.9, 0.89, 0.87), rough=0.4)
m_ped_dark = mat_principled("pedestal_dark", NAVY, rough=0.35, coat=0.3)
m_led, _ = mat_emission("led", (1.0, 0.25, 0.02), 6.0)
m_status, em_status = mat_emission("status", TEAL, 8.0)

# ---- pedestal
ped = box((5.3, 1.2, PED_H), m_ped, loc=(0, 0, PED_H / 2), bevel=0.04)
ped.cycles.is_caustics_receiver = True
box((5.36, 1.26, 0.06), m_ped_dark, loc=(0, 0, 0.03), bevel=0.01)          # plinth kick
box((5.1, 0.02, 0.035), m_led, loc=(0, -0.61, PED_H - 0.07))              # front LED strip

# ---- the word, one object per letter
cu = bpy.data.curves.new("word", "FONT")
cu.body = "INFOTIV"
cu.font = bpy.data.fonts.load(ASSETS + "Montserrat-800.ttf")
cu.size = TEXT_SIZE
cu.extrude = HALF_T - BEVEL
cu.bevel_depth = BEVEL
cu.bevel_resolution = 5
cu.space_character = 1.06
cu.align_x = "CENTER"
cu.align_y = "BOTTOM"
cu.resolution_u = 10
word = bpy.data.objects.new("word", cu)
bpy.context.collection.objects.link(word)
word.rotation_euler = (math.radians(90), 0, 0)
word.location = (0, 0, PED_H)
bpy.ops.object.select_all(action="DESELECT")
word.select_set(True)
bpy.context.view_layer.objects.active = word
bpy.ops.object.convert(target="MESH")
bpy.ops.object.transform_apply(location=True, rotation=True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.separate(type="LOOSE")
bpy.ops.object.mode_set(mode="OBJECT")


def x_range(o):
    xs = [(o.matrix_world @ v.co).x for v in o.data.vertices]
    return min(xs), max(xs)


pieces = sorted(bpy.context.selected_objects, key=lambda o: x_range(o)[0])
groups, hi = [], -1e9
for p in pieces:
    lo, phi = x_range(p)
    if lo > hi - 0.02:
        groups.append([])
        hi = phi
    else:
        hi = max(hi, phi)
    groups[-1].append(p)
letters = []
for g in groups:
    bpy.ops.object.select_all(action="DESELECT")
    for p in g:
        p.select_set(True)
    bpy.context.view_layer.objects.active = g[0]
    bpy.ops.object.join()
    letters.append(bpy.context.active_object)
assert len(letters) == 7, len(letters)
bpy.ops.object.select_all(action="DESELECT")
for o in letters:
    o.select_set(True)
bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
# font BOTTOM alignment leaves room for descenders: stand the letters on the pedestal
z_min = min(min((o.matrix_world @ v.co).z for v in o.data.vertices) for o in letters)
for o in letters:
    o.location.z += PED_H - z_min
bpy.context.view_layer.update()
for k, ob in enumerate(letters):
    ob.name = f"letter_{'INFOTIV'[k]}{k}"
    ob.data.materials.clear()
    ob.data.materials.append(m_glass)
    ob.cycles.is_caustics_caster = True
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(35))


def bounds(o):
    xs = [v.co.x for v in o.data.vertices]
    zs = [v.co.z for v in o.data.vertices]
    return min(xs), max(xs), min(zs), max(zs)


# Stroke width of the glyphs, measured from the "I" (minus the outward bevel).
_x0, _x1, _, _ = bounds(letters[0])
W = _x1 - _x0 - 2 * BEVEL


def neon_strokes(letter, b):
    """Centre-lines of each glyph's strokes, in the letter's local XZ coords."""
    xa, xb, za, zb = b
    h = W / 2 + BEVEL
    L, R, B, T_ = xa + h, xb - h, za + h, zb - h
    if letter == "I":
        return [[(0, B), (0, T_)]]
    if letter == "N":
        return [[(L, B), (L, T_), (R, B), (R, T_)]]
    if letter == "F":
        zm = za + (zb - za) * 0.44
        return [[(xb - h * 0.6, T_), (L, T_), (L, B)], [(L, zm), (xb - h * 1.1, zm)]]
    if letter == "O":
        rx, rz = (xb - xa) / 2 - h, (zb - za) / 2 - h
        return [[(rx * math.cos(TAU * i / 64), rz * math.sin(TAU * i / 64)) for i in range(64)]]
    if letter == "T":
        return [[(xa + h * 0.6, T_), (xb - h * 0.6, T_)], [(0, T_), (0, B)]]
    if letter == "V":
        return [[(xa + h * 1.25, zb - h * 0.6), (0, za + h * 1.3), (xb - h * 1.25, zb - h * 0.6)]]
    raise ValueError(letter)


for k, (ch, g) in enumerate(zip("INFOTIV", letters)):
    ccu = bpy.data.curves.new(f"neon_{k}", "CURVE")
    ccu.dimensions = "3D"
    ccu.bevel_depth = TUBE
    ccu.bevel_resolution = 3
    ccu.use_fill_caps = True
    for pts in neon_strokes(ch, bounds(g)):
        sp = ccu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for pt, (px, pz) in zip(sp.points, pts):
            pt.co = (px, 0, pz, 1)
        sp.use_cyclic_u = ch == "O"
    c = bpy.data.objects.new(f"core_{k}", ccu)
    bpy.context.collection.objects.link(c)
    ccu.materials.append(m_core)
    c.parent = g                       # rides along with its letter (the O when lifted)

O = letters[3]
O_HOME = O.location.copy()
O_TOP = max((O.matrix_world @ v.co).z for v in O.data.vertices)
O_BOT = min((O.matrix_world @ v.co).z for v in O.data.vertices)
print('O_HOME', O_HOME, 'top', O_TOP, 'bot', O_BOT, [round(v,3) for v in x_range(letters[0])+x_range(letters[6])])
# orange slot mark on the pedestal under the O
box((0.8, 0.44, 0.004), m_ped_dark, loc=(O_HOME.x, 0, PED_H + 0.002))

# ---- robot: base -> yaw -> shoulder -> elbow -> wrist pitch -> wrist roll -> fingers
cyl(0.62, 0.08, "Z", m_grey, loc=(BASE.x, BASE.y, 0.04), bevel=0.02)            # floor plate
cyl(0.48, 0.42, "Z", m_white, loc=(BASE.x, BASE.y, 0.29), bevel=0.03)          # base drum
ring = cyl(0.485, 0.05, "Z", m_status, loc=(BASE.x, BASE.y, 0.44))             # status light ring
yaw = empty("yaw", loc=(BASE.x, BASE.y, 0.5))
cyl(0.42, 0.34, "Z", m_white, yaw, (0, 0, 0.17), bevel=0.03)                    # turret
cyl(0.43, 0.04, "Z", m_orange, yaw, (0, 0, 0.02))
box((0.46, 0.5, 0.5), m_white, yaw, (0, 0, SH_H - 0.5 - 0.22), bevel=0.08)     # riser
shoulder = empty("shoulder", yaw, (0, 0, SH_H - 0.5))
cyl(0.3, 0.62, "Y", m_white, shoulder, bevel=0.03)                             # shoulder housing
cyl(0.2, 0.64, "Y", m_orange, shoulder)                                        # orange hub caps
cyl(0.18, L1, "X", m_white, shoulder, offset=(L1 / 2, 0, 0), bevel=0.0)        # upper arm tube
cyl(0.21, 0.2, "X", m_grey, shoulder, offset=(0.4, 0, 0))                       # collar
elbow = empty("elbow", shoulder, (L1, 0, 0))
cyl(0.25, 0.5, "Y", m_white, elbow, bevel=0.03)
cyl(0.16, 0.52, "Y", m_orange, elbow)
cyl(0.14, L2, "X", m_white, elbow, offset=(L2 / 2, 0, 0))
cyl(0.165, 0.14, "X", m_grey, elbow, offset=(L2 - 0.35, 0, 0))
wrist = empty("wrist", elbow, (L2, 0, 0))
cyl(0.17, 0.38, "Y", m_white, wrist, bevel=0.02)
cyl(0.11, 0.4, "Y", m_orange, wrist)
roll = empty("roll", wrist, (0, 0, 0))
cyl(0.13, 0.16, "X", m_grey, roll, offset=(0.2, 0, 0))                          # roll flange
cyl(0.135, 0.03, "X", m_orange, roll, offset=(0.29, 0, 0))
box((0.1, 0.42, 0.2), m_grey, roll, offset=(0.36, 0, 0), bevel=0.02)           # gripper palm
fingers = []
for s in (1, -1):
    f = empty(f"finger{s}", roll, (0, s * FINGER_OPEN, 0))
    box((0.32, 0.05, 0.14), m_steel, f, offset=(L3 - 0.07, 0, 0), bevel=0.012)
    box((0.1, 0.03, 0.12), m_orange, f, offset=(L3 - 0.07, -s * 0.035, 0))       # grip pads
    fingers.append((f, s))

# ---- course placard (as glass.py): a frosted-glass plate hung on two fine wires,
#      centred behind the pedestal, "AI COURSE" glowing in the core orange. Static, and it
#      casts no shadow. Its bottom edge sits just above the letter tops in frame.
#      Each loop it drops in from above the frame, is caught by its strings, bounces and
#      dangles until it settles, and is hoisted back out before the loop ends.
PLQ_X, PLQ_Y, PLQ_Z, PLQ_W, PLQ_H, PLQ_D = 0.0, 2.5, 1.95, 3.4, 1.3, 0.06
if VARIANT == "signleft":
    PLQ_X = -2.75                    # right edge stays left of the lifted O for any camera drift
PLQ_ROT = 0.0
HANG_Z = PLQ_Z + PLQ_H / 2                               # strings attach on the top edge
hang = empty("course_hang", loc=(PLQ_X, PLQ_Y, HANG_Z))  # pivot the sign dangles from
plq = empty("course_placard", hang, (0, 0, -HANG_Z))
plq.rotation_euler = (0, 0, PLQ_ROT)

m_frost = bpy.data.materials.new("frost")
fb_ = m_frost.node_tree.nodes["Principled BSDF"]
fb_.inputs["Base Color"].default_value = (0.96, 0.97, 1.0, 1)
fb_.inputs["Roughness"].default_value = 0.35
fb_.inputs["IOR"].default_value = 1.5
fb_.inputs["Transmission Weight"].default_value = 1.0
m_sign = mat_principled("sign_glow", CORE, emit=CORE, strength=2.6)
m_ink = mat_principled("sign_ink", NAVY, rough=0.35)

plate = box((PLQ_W, PLQ_D, PLQ_H), m_frost, plq, (0, 0, PLQ_Z), bevel=0.015)
plate.visible_shadow = False
font_b = bpy.data.fonts.load(ASSETS + "Montserrat-800.ttf", check_existing=True)
font_m = bpy.data.fonts.load(ASSETS + "Montserrat-500.ttf")


def sign_text(name, body, font, size, z, mat):
    c = bpy.data.curves.new(name, "FONT")
    c.body = body
    c.font = font
    c.size = size
    c.extrude = 0.012
    c.space_character = 1.06
    c.align_x = "CENTER"
    c.align_y = "CENTER"
    c.resolution_u = 8
    c.materials.append(mat)
    ob = bpy.data.objects.new(name, c)
    bpy.context.collection.objects.link(ob)
    ob.parent = plq
    ob.rotation_euler = (math.radians(90), 0, 0)
    ob.location = (0, -PLQ_D / 2 - 0.016, z)
    ob.visible_shadow = False
    return ob


sign_text("course_title", "AI COURSE", font_b, 0.48, PLQ_Z + 0.2, m_sign)
sign_text("course_by", "Hamid Ebadi", font_m, 0.31, PLQ_Z - 0.31, m_ink)
for sx in (-1, 1):
    top = PLQ_Z + PLQ_H / 2
    w_ = cyl(0.01, 12.0 - top, "Z", m_steel, plq, (sx * (PLQ_W / 2 - 0.3), 0, (top + 12.0) / 2), verts=8)
    w_.visible_shadow = False

DROP_H = 3.5                         # start/end height above the hanging pose: out of frame
DROP_U, HOIST_U = 0.06, 0.88         # fall lasts DROP_U; hoist runs HOIST_U -> 1


def sign_pose(f):
    """(dz, swing about X, tilt about Y) of the sign at frame f; periodic in LOOP."""
    u = ((f - 1) % LOOP) / LOOP
    if u < DROP_U:                                   # free fall
        return DROP_H * (1 - (u / DROP_U) ** 2), 0.0, 0.0
    t = (u - DROP_U) * LOOP / FPS                    # seconds since the strings caught it
    up = smooth((u - HOIST_U) / (1 - HOIST_U))       # 0 -> 1 while hoisting
    damp = 1 - up
    bounce = -0.32 * math.exp(-1.6 * t) * math.sin(TAU * 1.9 * t)
    swing = 0.10 * math.exp(-0.8 * t) * math.sin(TAU * 0.55 * t)
    tilt = 0.14 * math.exp(-0.9 * t) * math.sin(TAU * 0.8 * t)
    return DROP_H * up + damp * bounce, damp * swing, damp * tilt


bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
for f in range(1, LOOP + 2):
    dz, sw, tl = sign_pose(f)
    hang.location = (PLQ_X, PLQ_Y, HANG_Z + dz)
    hang.rotation_euler = (sw, tl, 0)
    hang.keyframe_insert("location", frame=f)
    hang.keyframe_insert("rotation_euler", frame=f)


# ---------------------------------------------------------------- motion
def ik(p):
    dx, dy = p.x - BASE.x, p.y - BASE.y
    th0 = math.atan2(dy, dx)
    r = math.hypot(dx, dy)
    wz = p.z + L3 - SH_H
    d = min(math.hypot(r, wz), L1 + L2 - 1e-4)
    b = math.acos(max(-1.0, min(1.0, (d * d - L1 * L1 - L2 * L2) / (2 * L1 * L2))))
    a1 = math.atan2(wz, r) + math.atan2(L2 * math.sin(b), L1 + L2 * math.cos(b))
    a2 = a1 - b
    return th0, a1, a2, b


GRASP = Vector((O_HOME.x, O_HOME.y, O_TOP - 0.16))
ABOVE = GRASP + Vector((0, 0, 0.55))
LIFT = GRASP + Vector({"liftright": (2.2, -0.9, 1.05),      # off to the right of the sign
                       "liftlow": (0, -1.3, 0.15)}.get(VARIANT, (0, -0.45, 1.05)))
HOME = Vector((BASE.x - 1.3, BASE.y - 1.1, 2.35))
O_OFF = O_HOME - GRASP                    # O centre relative to the tool point
TH_GRASP = ik(GRASP)[0]
# fingers separate along the wrist's local Y (world angle th+90° - roll); roll by the
# grasp yaw so they pinch the letter's thickness along world Y
ROLL0 = TH_GRASP

# keyed timeline: (u_start, u_end, from, to)
PATH = [(0.10, 0.28, HOME, ABOVE), (0.28, 0.36, ABOVE, GRASP), (0.41, 0.53, GRASP, LIFT),
        (0.70, 0.82, LIFT, GRASP), (0.87, 0.93, GRASP, ABOVE), (0.93, 1.00, ABOVE, HOME)]


def tool_at(u):
    p = HOME
    for a, b, p0, p1 in PATH:
        if u >= a:
            t = smooth((u - a) / (b - a))
            p = p0.lerp(p1, t)
    # a gentle arc on the lift / return so it swings rather than slides
    for a, b, p0, p1 in PATH[2:4]:
        if a < u < b:
            p = p + Vector((0, 0, 0.18 * math.sin(math.pi * (u - a) / (b - a))))
    # soft hover bob while showing off the O
    if 0.53 < u < 0.70:
        p = p + Vector((0, 0, 0.06 * math.sin(TAU * (u - 0.53) / 0.17)))
    return p


def state(f):
    u = ((f - 1) % LOOP) / LOOP
    p = tool_at(u)
    th0, a1, a2, b = ik(p)
    spin = TAU * smooth((u - 0.535) / 0.16)
    grip = smooth((u - 0.36) / 0.05) * (1 - smooth((u - 0.82) / 0.05))
    holding = 0.37 < u < 0.86
    busy = smooth((u - 0.04) / 0.06) * (1 - smooth((u - 0.94) / 0.05))
    return dict(u=u, p=p, th0=th0, a1=a1, a2=a2, b=b, spin=spin, grip=grip,
                holding=holding, busy=busy)


bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
for f in range(1, LOOP + 2):
    s = state(f)
    yaw.rotation_euler = (0, 0, s["th0"])
    shoulder.rotation_euler = (0, -s["a1"], 0)
    elbow.rotation_euler = (0, s["b"], 0)
    wrist.rotation_euler = (0, math.pi / 2 + s["a2"], 0)
    rl = ROLL0 + s["spin"]
    roll.rotation_euler = (rl, 0, 0)
    for ob in (yaw, shoulder, elbow, wrist, roll):
        ob.keyframe_insert("rotation_euler", frame=f)
    for fo, sg in fingers:
        fo.location = (0, sg * lerp(FINGER_OPEN, FINGER_CLOSED, s["grip"]), 0)
        fo.keyframe_insert("location", frame=f)
    if s["holding"]:
        # the O hangs rigidly from the tool point; the vertical tool axis spins it
        dth = -(s["th0"] - TH_GRASP) + s["spin"]
        c, sn = math.cos(-dth), math.sin(-dth)
        off = Vector((c * O_OFF.x - sn * O_OFF.y, sn * O_OFF.x + c * O_OFF.y, O_OFF.z))
        O.location = s["p"] + off
        O.rotation_euler = (0, 0, -dth)
    else:
        O.location = O_HOME
        O.rotation_euler = (0, 0, 0)
    O.keyframe_insert("location", frame=f)
    O.keyframe_insert("rotation_euler", frame=f)
    col = Vector(TEAL).lerp(Vector(ORANGE), s["busy"])
    em_status.inputs["Color"].default_value = (*col, 1)
    em_status.inputs["Color"].keyframe_insert("default_value", frame=f)

aim = empty("aim", loc=(0.75, 0.4, 1.55))

# ---- camera: slow periodic drift
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.lens = 40
cam.data.dof.use_dof = True
cam.data.dof.focus_object = aim
cam.data.dof.aperture_fstop = 5.6
bpy.context.collection.objects.link(cam)
scene.camera = cam
cam.constraints.new("TRACK_TO").target = aim


def phase_driver(target, path, expr, index=-1):
    fc = target.driver_add(path, index) if index >= 0 else target.driver_add(path)
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = expr.replace("T", f"((frame-1)*{TAU / LOOP:.10f})")
    assert fc.driver.is_simple_expression, expr
    return fc


phase_driver(cam, "location", "0.1 + 0.7*sin(T)", 0)
phase_driver(cam, "location", "-9.6 + 0.3*cos(T)", 1)
phase_driver(cam, "location", "2.7 + 0.2*sin(2*T)", 2)

# ---- lights (as glass.py): soft overhead softbox, a broad wall wash, and an
#      orbiting rig of coloured spots throwing refracted caustics from the glass word
key = bpy.data.objects.new("key", bpy.data.lights.new("key", "AREA"))
key.data.shape = "RECTANGLE"
key.data.size, key.data.size_y = 14, 6
key.data.energy = 450
key.location = (0, -3, 12)
key.rotation_euler = (math.radians(-15), 0, 0)
key.visible_camera = False
bpy.context.collection.objects.link(key)

wash = bpy.data.objects.new("wash", bpy.data.lights.new("wash", "AREA"))
wash.data.size = 20
wash.data.energy = 700
wash.location = (0, -2, 14)
wash.visible_camera = False
bpy.context.collection.objects.link(wash)
wash.constraints.new("TRACK_TO").target = empty("wall_aim", loc=(0, 11, 7))

word_aim = empty("word_aim", loc=(0, 0, PED_H + 0.5))
RIG = [((1.0, 0.95, 0.9), 4500, 0.0),
       (ORANGE, 9000, TAU / 3),
       ((0.25, 0.55, 1.0), 7000, 2 * TAU / 3)]
for i, (col, e, ph) in enumerate(RIG):
    sp_ = bpy.data.objects.new(f"rig_{i}", bpy.data.lights.new(f"rig_{i}", "SPOT"))
    sp_.data.energy = e
    sp_.data.color = col
    sp_.data.spot_size = math.radians(40)
    sp_.data.spot_blend = 0.6
    sp_.data.shadow_soft_size = 0.05
    sp_.data.cycles.is_caustics_light = True
    sp_.visible_camera = False
    bpy.context.collection.objects.link(sp_)
    phase_driver(sp_, "location", f"9.0*sin(T + {ph:.5f})", 0)
    phase_driver(sp_, "location", f"2.0 + 7.0*cos(T + {ph:.5f})", 1)
    phase_driver(sp_, "location", f"4.2 + 0.8*sin(2*T + {ph:.5f})", 2)
    sp_.constraints.new("TRACK_TO").target = word_aim
# the cores pulse softly, as in glass.py
phase_driver(kb.inputs["Emission Strength"], "default_value", "3.2 + 1.0*sin(2*T)")

# ---- compositor: gentle bloom
tree = bpy.data.node_groups.new("comp", "CompositorNodeTree")
tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
scene.compositing_node_group = tree
rln = tree.nodes.new("CompositorNodeRLayers")
glare = tree.nodes.new("CompositorNodeGlare")
glare.inputs["Type"].default_value = "Bloom"
glare.inputs["Quality"].default_value = "High"
glare.inputs["Threshold"].default_value = 1.2
glare.inputs["Strength"].default_value = 0.2
glare.inputs["Size"].default_value = 0.6
out = tree.nodes.new("NodeGroupOutput")
tree.links.new(rln.outputs["Image"], glare.inputs["Image"])
tree.links.new(glare.outputs[0], out.inputs[0])

# ---------------------------------------------------------------- render
if SAVE:
    bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}{SLUG}.blend")

scene.render.image_settings.file_format = "PNG"
if FRAMES:
    for f in FRAMES:
        scene.frame_set(f)
        scene.render.filepath = f"{OUT}preview_{f:04d}.png"
        bpy.ops.render.render(write_still=True)
else:
    scene.render.filepath = f"{OUT}frames/f_"
    bpy.ops.render.render(animation=True)
