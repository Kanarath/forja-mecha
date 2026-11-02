"""
Forja Mecha - generador de imágenes y modelos para la web.

Construye en Blender (sin interfaz) las piezas de cada lección paso a paso,
las renderiza y exporta cada paso a .glb para el visor 3D de la web.

Uso (desde la raíz del repo):
  blender -b --factory-startup --python tools/forja_build.py -- [workbench|eevee|all]
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG = os.path.join(ROOT, "assets", "img")
GLB = os.path.join(ROOT, "assets", "models")
BLEND = os.path.join(ROOT, "assets", "blend")
for d in (IMG, GLB, BLEND):
    os.makedirs(d, exist_ok=True)

MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "all"


# ---------------------------------------------------------------- utilidades

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.world = bpy.data.worlds.new("World")
    return s


def mat(name, color, metal=0.0, rough=0.5, emit=None, strength=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = (*(emit or color), 1)
    return m


def MATS():
    return {
        "armor": mat("Blindaje", (0.62, 0.64, 0.68), 0.35, 0.38),
        "dark": mat("Metal oscuro", (0.06, 0.065, 0.075), 0.7, 0.32),
        "core": mat("Nucleo", (0.2, 0.6, 1.0), 0, 0.2, (0.08, 0.45, 1.0), 9),
        "red": mat("Linea roja", (0.8, 0.05, 0.05), 0, 0.3, (1.0, 0.05, 0.04), 6),
        "wire": mat("Wire", (0.02, 0.02, 0.025)),
        "floor": mat("Estudio", (0.17, 0.175, 0.185), 0, 0.5),
    }


def obj_from_bm(name, bm, material=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    if material:
        me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = smooth
    return o


def wire_overlay(o, thickness=0.006, evaluated=False):
    """Copia con modificador Wireframe: así se ve la topología en el render."""
    if evaluated:
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    else:
        me = o.data.copy()
    w = bpy.data.objects.new(o.name + "_wireR", me)
    bpy.context.scene.collection.objects.link(w)
    w.matrix_world = o.matrix_world.copy()
    me.materials.clear()
    me.materials.append(MATS()["wire"])
    m = w.modifiers.new("wire", "WIREFRAME")
    m.thickness = thickness
    m.use_even_offset = True
    m.offset = 0
    return w


def edge_object(o, evaluated=False):
    """Objeto solo-aristas para exportar al .glb (el visor lo pinta como líneas)."""
    if evaluated:
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    else:
        me = o.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=list(bm.faces), context="FACES_ONLY")
    bm.to_mesh(me)
    e = bpy.data.objects.new(o.name + "_wire", me)
    bpy.context.scene.collection.objects.link(e)
    e.matrix_world = o.matrix_world.copy()
    return e


def camera(loc, target, lens=35):
    s = bpy.context.scene
    cam = s.camera
    if not cam:
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        s.collection.objects.link(cam)
        s.camera = cam
    cam.data.lens = lens
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def workbench(light="STUDIO", cavity=True, bg=(0.19, 0.195, 0.21)):
    s = bpy.context.scene
    s.render.engine = "BLENDER_WORKBENCH"
    sh = s.display.shading
    sh.light = light
    if light == "MATCAP":
        sh.studio_light = "basic_1.exr"
    sh.color_type = "MATERIAL"
    sh.show_cavity = cavity
    sh.cavity_type = "BOTH"
    sh.cavity_ridge_factor = 1.2
    sh.cavity_valley_factor = 1.0
    sh.show_specular_highlight = True
    sh.show_object_outline = False
    sh.show_shadows = False
    s.display.render_aa = "16"
    s.world.color = bg
    s.render.film_transparent = False
    s.view_settings.view_transform = "Standard"


def render(name, w=1280, h=720):
    s = bpy.context.scene
    s.render.resolution_x, s.render.resolution_y = w, h
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "WEBP"
    s.render.image_settings.quality = 86
    s.render.filepath = os.path.join(IMG, name + ".webp")
    bpy.ops.render.render(write_still=True)
    print("RENDER", name)


def export_glb(name, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.hide_render = False
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(GLB, name + ".glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        use_mesh_edges=True,
        export_cameras=False,
        export_lights=False,
    )
    print("GLB", name)


def hide(objs, state=True):
    for o in objs:
        o.hide_render = state
        o.hide_set(state)


def faces_where(bm, fn):
    return [f for f in bm.faces if fn(f)]


# ------------------------------------------------- Lección 1: celda de energía

def cell_steps():
    """Devuelve una lista de (bmesh, extras) con cada paso de la celda."""
    steps = []

    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16,
                          radius1=0.5, radius2=0.5, depth=2.0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 1))
    steps.append(bm.copy())  # 1: cilindro de 16 lados

    # 2: tapas con Inset (I) repetido: borde, hueco y terminal
    def cap(top):
        def key(f):
            c = f.calc_center_median()
            return (round(c.z * (1 if top else -1), 4), -c.xy.length)
        return max(faces_where(bm, lambda f: abs(f.normal.z) > 0.99), key=key)
    for top in (True, False):
        f = cap(top)  # la cara original sigue siendo la del centro tras cada Inset
        bmesh.ops.inset_individual(bm, faces=[f], thickness=0.06, depth=0)
        bmesh.ops.inset_individual(bm, faces=[f], thickness=0.06, depth=-0.07)
        bmesh.ops.inset_individual(bm, faces=[f], thickness=0.12, depth=0.12 if top else 0)
        bm.normal_update()
    steps.append(bm.copy())

    # 3: Loop Cuts (Ctrl+R) para preparar las ranuras y las ventanas
    for z in (0.38, 0.48, 0.58, 1.42, 1.52, 1.62):
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z), plane_no=(0, 0, 1))
    bm.normal_update()
    steps.append(bm.copy())

    # 4: ranuras: extruir los anillos y escalarlos hacia dentro (E + S + Shift Z)
    side = lambda f: abs(f.normal.z) < 0.01
    for lo, hi in ((0.38, 0.48), (1.52, 1.62)):
        ring = faces_where(bm, lambda f: side(f) and lo < f.calc_center_median().z < hi)
        r = bmesh.ops.extrude_face_region(bm, geom=ring)
        vs = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
        for v in vs:
            v.co.x *= 0.9
            v.co.y *= 0.9
        bmesh.ops.delete(bm, geom=ring, context="FACES")
    bm.normal_update()
    steps.append(bm.copy())

    # 5: ventanas: Inset individual (I I) + extruir hacia dentro + borrar la cara
    band = faces_where(bm, lambda f: side(f) and 0.58 < f.calc_center_median().z < 1.42
                       and abs(f.calc_center_median().length) > 0.3)
    band.sort(key=lambda f: math.atan2(f.calc_center_median().y, f.calc_center_median().x))
    windows = band[::2]
    bmesh.ops.inset_individual(bm, faces=windows, thickness=0.035, depth=0)
    bm.normal_update()
    holes = []
    for f in windows:
        n = f.normal.copy()
        r = bmesh.ops.extrude_discrete_faces(bm, faces=[f])
        nf = r["faces"][0]
        bmesh.ops.translate(bm, verts=nf.verts, vec=-n * 0.09)
        holes.append(nf)
    bmesh.ops.delete(bm, geom=holes, context="FACES")
    bm.normal_update()
    steps.append(bm.copy())
    return steps


def build_cell(step_bm, idx, M, final=False):
    o = obj_from_bm(f"Celda_{idx:02d}", step_bm, M["armor"], smooth=final)
    extras = []
    if idx >= 5:
        b = bmesh.new()
        bmesh.ops.create_cone(b, cap_ends=True, segments=24, radius1=0.34, radius2=0.34, depth=0.9)
        bmesh.ops.translate(b, verts=b.verts, vec=(0, 0, 1))
        extras.append(obj_from_bm(f"Nucleo_{idx:02d}", b, M["core"], smooth=True))
    if final:
        bev = o.modifiers.new("Bevel", "BEVEL")
        bev.width = 0.02
        bev.segments = 3
        bev.limit_method = "ANGLE"
        bev.angle_limit = math.radians(30)
        bev.harden_normals = True
        wn = o.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
        wn.keep_sharp = True
    return o, extras


def lesson1_workbench():
    reset()
    M = MATS()
    workbench()
    camera((2.7, -3.6, 3.3), (0, 0, 0.95), 40)
    steps = cell_steps()
    names = ["cilindro", "tapas", "loopcuts", "ranuras", "ventanas", "final"]
    for i, bmx in enumerate(steps + [steps[-1]], start=1):
        final = i == 6
        o, extras = build_cell(bmx.copy(), i, M, final)
        w = wire_overlay(o, 0.005 if not final else 0.003, evaluated=final)
        render(f"l1_{i:02d}_{names[i-1]}")
        hide([w])
        if final:
            render(f"l1_{i:02d}_{names[i-1]}_limpio")
        e = edge_object(o, evaluated=final)
        export_glb(f"celda_{i:02d}", [o, e] + extras)
        hide([o, e] + extras)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "celda_energia.blend"))


# --------------------------------------------- Lección 2: sombreado limpio

def module_mesh():
    """Bloque tipo 'cargador' con chaflán y un agujero booleano aplicado (n-gons)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(1.1, 0.6, 1.5), verts=bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.75))
    e = [e for e in bm.edges if all(v.co.y < -0.29 and v.co.z > 1.49 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=e + list({v for x in e for v in x.verts}), offset=0.28,
                    segments=1, affect="EDGES", profile=0.5)
    me = bpy.data.meshes.new("Modulo")
    bm.to_mesh(me)
    o = bpy.data.objects.new("Modulo", me)
    bpy.context.scene.collection.objects.link(o)
    # agujero con booleano (como harías con Bool Tool o el modificador)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.22, depth=2,
                                        location=(-0.18, 0, 0.65), rotation=(math.pi / 2, 0, 0))
    cut = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.33, -0.3, 0.5), scale=(0.16, 0.2, 0.5))
    slot = bpy.context.object
    for c in (cut, slot):
        m = o.modifiers.new("Bool", "BOOLEAN")
        m.object = c
        m.solver = "EXACT"
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cut)
    bpy.data.objects.remove(slot)
    return o


def lesson2_workbench():
    reset()
    M = MATS()
    workbench(light="MATCAP", cavity=False)
    camera((2.6, -3.4, 2.4), (0, 0, 0.7), 40)

    variants = {}
    for key in ("plano", "suave", "angulo", "bevel"):
        o = module_mesh()
        o.name = "Modulo_" + key
        o.data.materials.append(M["armor"])
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        if key == "plano":
            bpy.ops.object.shade_flat()
        elif key == "suave":
            bpy.ops.object.shade_smooth()
        else:
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
        if key == "bevel":
            bev = o.modifiers.new("Bevel", "BEVEL")
            bev.width = 0.02
            bev.segments = 3
            bev.limit_method = "ANGLE"
            bev.angle_limit = math.radians(30)
            bev.harden_normals = True
            wn = o.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
            wn.keep_sharp = True
        variants[key] = o
    for key, o in variants.items():
        hide(list(variants.values()))
        hide([o], False)
        render(f"l2_{key}")
        e = edge_object(o, evaluated=(key == "bevel"))
        export_glb(f"modulo_{key}", [o, e])
        bpy.data.objects.remove(e)
    # topología: el booleano deja n-gons
    hide(list(variants.values()))
    hide([variants["plano"]], False)
    workbench(light="STUDIO", cavity=True)
    w = wire_overlay(variants["plano"], 0.005)
    render("l2_ngons")
    bpy.data.objects.remove(w)
    hide([variants["plano"]])
    hide([variants["bevel"]], False)
    w = wire_overlay(variants["bevel"], 0.0025, evaluated=True)
    render("l2_bevel_wire")
    bpy.data.objects.remove(w)
    hide(list(variants.values()))
    hide([variants["bevel"]], False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "modulo_sombreado.blend"))

    # escala sin aplicar vs aplicada (bevel deformado)
    reset()
    M = MATS()
    workbench()
    camera((0, -7.6, 2.6), (0, 0, 0.35), 35)
    for x, applied in ((-1.6, False), (1.6, True)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 0.4))
        c = bpy.context.object
        c.scale = (2.2, 0.8, 0.8)
        if applied:
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        c.data.materials.append(M["armor"])
        b = c.modifiers.new("Bevel", "BEVEL")
        b.width = 0.12
        b.segments = 1
        wire_overlay(c, 0.006, evaluated=True)
    render("l2_escala")

    # bevel vs sin bevel: los bordes que atrapan la luz
    reset()
    M = MATS()
    workbench(cavity=False)
    camera((0, -6.2, 2.6), (0, 0, 0.45), 40)
    for x, bevel in ((-1.1, False), (1.1, True)):
        bpy.ops.mesh.primitive_cube_add(size=1.3, location=(x, 0, 0.65), rotation=(0, 0, math.radians(30)))
        c = bpy.context.object
        c.data.materials.append(M["armor"])
        if bevel:
            b = c.modifiers.new("Bevel", "BEVEL")
            b.width = 0.05
            b.segments = 3
            b.harden_normals = True
            bpy.ops.object.shade_smooth()
    render("l2_bevel_vs")


# ------------------------------------------------------- renders bonitos Eevee

def studio(M):
    """Fondo curvo de estudio (ciclorama) + luces de tres puntos."""
    bm = bmesh.new()
    prof = [(-12, 0)]
    for i in range(13):
        a = math.radians(-90 + i * 7.5)
        prof.append((4 + 4 * math.cos(a), 4 + 4 * math.sin(a)))
    prof.append((8, 12))
    row = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in (-15, 15)]
    for i in range(len(prof) - 1):
        bm.faces.new((row[0][i], row[1][i], row[1][i + 1], row[0][i + 1]))
    o = obj_from_bm("Ciclorama", bm, M["floor"], smooth=True)

    def area(name, loc, power, size, color=(1, 1, 1)):
        l = bpy.data.lights.new(name, "AREA")
        l.energy, l.size, l.color = power, size, color
        ob = bpy.data.objects.new(name, l)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector((0, 0, 1)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    area("Clave", (-4, -4, 6), 380, 3)
    area("Relleno", (5, -3, 2.5), 70, 6, (0.85, 0.9, 1))
    area("Contra", (2, 5, 5), 650, 2, (0.6, 0.75, 1))
    return o


def eevee():
    s = bpy.context.scene
    s.render.engine = "BLENDER_EEVEE_NEXT"
    s.eevee.taa_render_samples = 48
    s.world.color = (0.02, 0.02, 0.025)
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Medium High Contrast"
    s.use_nodes = True
    nt = s.node_tree
    rl, comp = nt.nodes["Render Layers"], nt.nodes["Composite"]
    g = nt.nodes.new("CompositorNodeGlare")
    g.glare_type = "FOG_GLOW"
    g.threshold = 1.2
    g.size = 7
    nt.links.new(rl.outputs["Image"], g.inputs["Image"])
    nt.links.new(g.outputs["Image"], comp.inputs["Image"])


def hero_renders():
    reset()
    M = MATS()
    studio(M)
    eevee()
    steps = cell_steps()
    # celda en pie + celda tumbada, como en una mesa de taller
    o, extras = build_cell(steps[-1], 6, M, final=True)
    o2, extras2 = build_cell(steps[-1].copy(), 7, M, final=True)
    for ob in [o2] + extras2:
        ob.rotation_euler = (0, math.pi / 2, math.radians(-20))
        ob.location = (-2.6, 1.0, 0.5)
    # anillos rojos en las ranuras, como las líneas del arma de referencia
    for z in (0.43, 1.57):
        b = bmesh.new()
        bmesh.ops.create_cone(b, cap_ends=False, segments=16, radius1=0.452, radius2=0.452, depth=0.03)
        bmesh.ops.translate(b, verts=b.verts, vec=(0, 0, z))
        obj_from_bm("Anillo", b, M["red"], smooth=True)
    for ob in [o, o2]:
        ob.data.materials[0] = M["armor"]
    camera((1.6, -6.2, 2.7), (-0.95, 0.4, 0.8), 45)
    render("hero_celda", 1600, 900)
    camera((1.6, -3.2, 1.4), (0, 0, 1.0), 60)
    render("l1_final_eevee", 1280, 720)

    # Lección 0: escena de estudio con primitivas
    reset()
    M = MATS()
    studio(M)
    eevee()
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.4, 0, 0.5))
    c = bpy.context.object
    b = c.modifiers.new("Bevel", "BEVEL")
    b.width, b.segments, b.harden_normals = 0.04, 3, True
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.45, depth=1.2, location=(0, 0.3, 0.6))
    cy = bpy.context.object
    b = cy.modifiers.new("Bevel", "BEVEL")
    b.width, b.segments, b.harden_normals = 0.03, 3, True
    b.limit_method = "ANGLE"
    bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, location=(1.3, -0.1, 0.45))
    bpy.ops.object.shade_smooth()
    sp = bpy.context.object
    for ob, m in ((c, M["armor"]), (cy, M["dark"]), (sp, M["core"])):
        ob.data.materials.append(m)
    camera((0.6, -6.0, 2.2), (0, 0, 0.55), 50)
    render("l0_estudio", 1280, 720)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "estudio_base.blend"))


if MODE in ("workbench", "all"):
    lesson1_workbench()
    lesson2_workbench()
if MODE in ("eevee", "all"):
    hero_renders()
print("FORJA OK")
