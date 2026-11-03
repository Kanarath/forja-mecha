"""
Forja Mecha - generador de imágenes y modelos para la web.

Construye en Blender (sin interfaz) las piezas de cada lección paso a paso,
las renderiza y exporta cada paso a .glb para el visor 3D de la web.

Uso (desde la raíz del repo):
  blender -b --factory-startup --python tools/forja_build.py -- [workbench|eevee|all]
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

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


def wire_overlay(o, thickness=0.006, evaluated=False, material=None):
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
    me.materials.append(material or MATS()["wire"])
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


# ------------------------------------------- Lección 3: placa de blindaje

def chamfer_rect(x0, x1, y0, y1, c, esquinas=(1, 1, 1, 1)):
    """Rectángulo con esquinas achaflanadas (ab-izq, ab-der, arr-der, arr-izq), sentido antihorario."""
    a, b, cc, d = (c * e for e in esquinas)
    pts = []
    pts += [(x0, y0 + a), (x0 + a, y0)] if a else [(x0, y0)]
    pts += [(x1 - b, y0), (x1, y0 + b)] if b else [(x1, y0)]
    pts += [(x1, y1 - cc), (x1 - cc, y1)] if cc else [(x1, y1)]
    pts += [(x0 + d, y1), (x0, y1 - d)] if d else [(x0, y1)]
    return pts


def prism(name, pts, z0, z1, material=None):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z0)) for x, y in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, material)


def ring_wall(name, pts, z0, z1, thickness, material=None):
    """Pared abierta siguiendo un contorno + Solidify: el cortador de líneas de panel."""
    bm = bmesh.new()
    lo = [bm.verts.new((x, y, z0)) for x, y in pts]
    hi = [bm.verts.new((x, y, z1)) for x, y in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj_from_bm(name, bm, material)
    s = o.modifiers.new("Solidify", "SOLIDIFY")
    s.thickness = thickness
    s.offset = 0
    s.use_even_offset = True
    return o


def plate_base(M):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(2.0, 1.3, 0.16), verts=bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.08))
    vert_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.1]
    bmesh.ops.bevel(bm, geom=vert_edges + list({v for e in vert_edges for v in e.verts}),
                    offset=0.3, segments=1, affect="EDGES", profile=0.5)
    bm.normal_update()
    top = max((f for f in bm.faces if f.normal.z > 0.99), key=lambda f: f.calc_center_median().z)
    bmesh.ops.inset_individual(bm, faces=[top], thickness=0.12, depth=0)
    r = bmesh.ops.extrude_face_region(bm, geom=[top])
    vs = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=vs, vec=(0, 0, 0.04))
    bmesh.ops.delete(bm, geom=[top], context="FACES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm("Placa", bm, M["armor"])


def bolt(name, x, y, M, z=0.16):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=12,
                          radius1=0.035, radius2=0.035, depth=0.025)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(x, y, z + 0.0125))
    bm.normal_update()
    top = max((f for f in bm.faces if f.normal.z > 0.99), key=lambda f: f.calc_center_median().z)
    bmesh.ops.inset_individual(bm, faces=[top], thickness=0.012, depth=-0.008)
    o = obj_from_bm(name, bm, M["dark"], smooth=True)
    b = o.modifiers.new("Bevel", "BEVEL")
    b.width, b.segments, b.harden_normals = 0.003, 2, True
    b.limit_method = "ANGLE"
    return o


def build_plate(M, upto, cambio=False):
    """Construye la placa hasta el paso `upto` (1-7). Devuelve (placa, cortadores, extras)."""
    p = plate_base(M)
    coll = bpy.data.collections.new("Cortadores")
    bpy.context.scene.collection.children.link(coll)
    cut_mat = mat("Cortador", (0.1, 0.6, 1.0))
    cutters, extras = [], []

    def add_cutter(o):
        bpy.context.scene.collection.objects.unlink(o)
        coll.objects.link(o)
        o.display_type = "WIRE"
        o.hide_render = True
        cutters.append(o)

    if upto >= 2:
        sx = 0.8 if cambio else 1.0
        pts = chamfer_rect(-0.72 * sx, -0.08 * sx, -0.36, 0.36, 0.12, (0, 1, 0, 1))
        add_cutter(ring_wall("Cortador_panel", pts, 0.17, 0.3, 0.018, cut_mat))
    if upto >= 3:
        m = p.modifiers.new("Boolean", "BOOLEAN")
        m.operand_type = "COLLECTION"
        m.collection = coll
        m.solver = "EXACT"
    if upto >= 4:
        v = prism("Cortador_rejilla", chamfer_rect(0.18, 0.23, -0.2, 0.2, 0.02), 0.14, 0.3, cut_mat)
        a = v.modifiers.new("Array", "ARRAY")
        a.count = 8 if cambio else 6
        a.use_relative_offset = False
        a.use_constant_offset = True
        a.constant_offset_displace = (0.065 if cambio else 0.09, 0, 0)
        add_cutter(v)
    if upto >= 5:
        def dashes(name, inset, z0, z1, material):
            o = prism(name, chamfer_rect(-0.476 + inset, -0.336 - inset, -0.61 + inset, -0.57 - inset, 0.02),
                      z0, z1, material)
            a = o.modifiers.new("Array", "ARRAY")
            a.count = 5
            a.use_relative_offset = False
            a.use_constant_offset = True
            a.constant_offset_displace = (0.203, 0, 0)
            mi = o.modifiers.new("Mirror", "MIRROR")
            mi.use_axis = (False, True, False)
            return o
        add_cutter(dashes("Cortador_luces", 0, 0.13, 0.25, cut_mat))
        extras.append(dashes("Luces", 0.004, 0.13, 0.15, M["core"]))
    if upto >= 6:
        for i, (x, y) in enumerate([(-0.94, -0.3), (-0.94, 0.3), (0.94, -0.3), (0.94, 0.3)]):
            extras.append(bolt(f"Tornillo_{i}", x, y, M))
    if upto >= 7:
        for poly in p.data.polygons:
            poly.use_smooth = True
        b = p.modifiers.new("Bevel", "BEVEL")
        b.width = 0.006
        b.segments = 2
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(30)
        b.harden_normals = True
        w = p.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
        w.keep_sharp = True
    return p, cutters, extras


def lesson3():
    names = ["base", "cortador", "panel", "rejilla", "luces", "tornillos", "final"]
    for i, nm in enumerate(names, start=1):
        reset()
        M = MATS()
        workbench()
        camera((1.45, -2.35, 2.25), (0.02, -0.05, 0.08), 40)
        p, cutters, extras = build_plate(M, i)
        cmat = bpy.data.materials["Cortador"]
        overlays = [wire_overlay(c, 0.004, evaluated=True, material=cmat) for c in cutters if i <= 5]
        w = wire_overlay(p, 0.0025 if i == 7 else 0.0035, evaluated=True)
        render(f"l3_{i:02d}_{nm}")
        if i == 7:
            hide([w])
            render("l3_07_final_limpio")
        hide([w] + overlays)
        edges = [edge_object(p, evaluated=True)] + [edge_object(c, evaluated=True) for c in cutters if i <= 5]
        export_glb(f"blindaje_{i:02d}", [p] + extras + edges)
        if i == 7:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "placa_blindaje.blend"))

    # no destructivo: mismos cortadores, otros valores
    reset()
    M = MATS()
    workbench()
    camera((1.45, -2.35, 2.25), (0.02, -0.05, 0.08), 40)
    p, cutters, extras = build_plate(M, 5, cambio=True)
    cmat = bpy.data.materials["Cortador"]
    for c in cutters:
        wire_overlay(c, 0.004, evaluated=True, material=cmat)
    wire_overlay(p, 0.0035, evaluated=True)
    render("l3_cambio")


def lesson3_eevee():
    reset()
    M = MATS()
    studio(M)
    eevee()
    p, cutters, extras = build_plate(M, 7)
    pivot = bpy.data.objects.new("Soporte", None)
    bpy.context.scene.collection.objects.link(pivot)
    for o in [p] + extras + cutters:  # los cortadores viajan con la placa
        o.parent = pivot
    pivot.rotation_euler = (math.radians(65), 0, math.radians(-12))
    pivot.location = (0, 0, 0.62)
    # una celda del módulo 1 al lado: las piezas se combinan
    c, cx = build_cell(cell_steps()[-1], 6, M, final=True)
    for o in [c] + cx:
        o.scale = (0.42, 0.42, 0.42)
        o.location = (1.35, -0.1, 0)
    camera((1.1, -4.2, 1.3), (0.3, 0, 0.62), 50)
    render("l3_eevee", 1600, 900)


# --------------------------------------------- Lección 4: cabeza de robot

def subsurf(o, levels=2):
    m = o.modifiers.new("Subdivision", "SUBSURF")
    m.levels = levels
    m.render_levels = levels
    return m


def extrude_move(bm, faces, vec):
    """Extrude de región + mover; devuelve las caras nuevas (como E en Blender)."""
    r = bmesh.ops.extrude_face_region(bm, geom=faces)
    nf = [g for g in r["geom"] if isinstance(g, bmesh.types.BMFace)]
    nv = [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nv, vec=vec)
    bmesh.ops.delete(bm, geom=faces, context="FACES")
    return nf


def concept_cubes():
    """Tres cubos con Subdivision: sin apoyos, con support loops y con crease."""
    out = {}
    for key in ("blob", "loops", "crease"):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        if key == "loops":
            for axis in range(3):
                for d in (-0.42, 0.42):
                    co, no = [0, 0, 0], [0, 0, 0]
                    co[axis], no[axis] = d, 1
                    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
                    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
        o = obj_from_bm("Cubo_" + key, bm, MATS()["armor"], smooth=True)
        if key == "crease":
            a = o.data.attributes.new("crease_edge", "FLOAT", "EDGE")
            for i in range(len(o.data.edges)):
                a.data[i].value = 0.85
        subsurf(o)
        out[key] = o
    return out


def head_bm(paso):
    """Cabeza: cubo subdividido, moldeado, con visor (paso>=4) y support loops (paso>=5)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=2, use_grid_fill=True)
    if paso == 1:
        for v in bm.verts:
            v.co = Vector((v.co.x * 0.8, v.co.y * 0.95, v.co.z * 1.0))
        return bm
    radios = Vector((0.42, 0.5, 0.52))
    for v in bm.verts:
        p = Vector((v.co.x * 0.8, v.co.y * 0.95, v.co.z * 1.0))
        e = Vector((p.x / radios.x, p.y / radios.y, p.z / radios.z)).length
        q = p / e  # el mismo punto llevado a un elipsoide
        t = 0.35 + 0.3 * max(0, min(1, p.z / 0.5)) + 0.25 * max(0, min(1, p.y / 0.475))
        t -= 0.3 * max(0, min(1, -p.y / 0.475))  # la cara se queda más plana
        t = max(0.05, min(0.85, t))
        p = p.lerp(q, t)
        if p.z < 0:  # barbilla más estrecha
            p.x *= 1 - 0.28 * (-p.z / 0.5)
            p.y *= 1 - 0.12 * (-p.z / 0.5)
        v.co = p
    bm.normal_update()
    if paso >= 4:
        visor = [f for f in bm.faces if f.normal.y < -0.5 and abs(f.calc_center_median().z) < 0.15]
        if paso == 4:
            # sin apoyos: extruir directamente, el contorno queda lejos de las aristas vecinas
            fondo = extrude_move(bm, visor, (0, 0.07, 0))
        else:
            bmesh.ops.inset_region(bm, faces=visor, thickness=0.035, depth=0, use_even_offset=True)
            bmesh.ops.inset_region(bm, faces=visor, thickness=0.015, depth=0, use_even_offset=True)
            f = extrude_move(bm, visor, (0, 0.012, 0))
            f = extrude_move(bm, f, (0, 0.046, 0))
            fondo = extrude_move(bm, f, (0, 0.012, 0))
            bmesh.ops.inset_region(bm, faces=fondo, thickness=0.015, depth=0, use_even_offset=True)
        for f in fondo:
            f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def head_extras(M):
    """Piezas duras que flotan sobre la cabeza subdividida: orejeras, cresta en V y cuello."""
    extras = []
    for s in (-1, 1):
        b = bmesh.new()
        bmesh.ops.create_cone(b, cap_ends=True, cap_tris=False, segments=16, radius1=0.15, radius2=0.15, depth=0.1)
        b.normal_update()
        cap = max((f for f in b.faces if f.normal.z > 0.99), key=lambda f: f.calc_center_median().z)
        bmesh.ops.inset_individual(b, faces=[cap], thickness=0.03, depth=0)
        bmesh.ops.inset_individual(b, faces=[cap], thickness=0.03, depth=-0.025)
        bmesh.ops.inset_individual(b, faces=[cap], thickness=0.03, depth=0.04)
        o = obj_from_bm(f"Orejera_{'D' if s > 0 else 'I'}", b, M["dark"], smooth=True)
        o.rotation_euler = (0, math.radians(90 * s), 0)
        o.location = (0.4 * s, 0.03, 0.02)
        bv = o.modifiers.new("Bevel", "BEVEL")
        bv.width, bv.segments, bv.harden_normals, bv.limit_method = 0.008, 2, True, "ANGLE"
        extras.append(o)
    pts = [(0.0, 0.0), (0.045, -0.01), (0.26, 0.17), (0.24, 0.195), (0.02, 0.045)]
    fin = prism("Cresta_V", pts, 0, 0.03, mat("Amarillo", (0.95, 0.62, 0.08), 0.2, 0.35))
    fin.rotation_euler = (math.radians(90), 0, 0)
    fin.location = (0, -0.462, 0.17)
    mi = fin.modifiers.new("Mirror", "MIRROR")
    mi.use_bisect_axis[0] = False
    bv = fin.modifiers.new("Bevel", "BEVEL")
    bv.width, bv.segments, bv.harden_normals = 0.004, 2, True
    for p in fin.data.polygons:
        p.use_smooth = True
    extras.append(fin)
    b = bmesh.new()
    bmesh.ops.create_cone(b, cap_ends=True, cap_tris=False, segments=16, radius1=0.15, radius2=0.17, depth=0.4)
    bmesh.ops.translate(b, verts=b.verts, vec=(0, 0.04, -0.62))
    neck = obj_from_bm("Cuello", b, M["dark"], smooth=True)
    bv = neck.modifiers.new("Bevel", "BEVEL")
    bv.width, bv.segments, bv.harden_normals, bv.limit_method = 0.01, 2, True, "ANGLE"
    extras.append(neck)
    return extras


def build_head(M, paso):
    o = obj_from_bm(f"Cabeza_{paso:02d}", head_bm(paso), M["armor"], smooth=paso >= 3)
    o.data.materials.append(mat("Visor", (0.1, 0.5, 1.0), 0, 0.15, (0.1, 0.55, 1.0), 6))
    if paso >= 3:
        subsurf(o)
    return o


def lesson4():
    reset()
    M = MATS()
    workbench()
    camera((1.9, -2.5, 1.6), (0, 0, 0), 32)
    cubes = concept_cubes()
    for key, o in cubes.items():
        hide(list(cubes.values()))
        hide([o], False)
        w = wire_overlay(o, 0.006)  # la «jaula»: la malla real, sin subdividir
        render(f"l4_cubo_{key}")
        bpy.data.objects.remove(w)
        e = edge_object(o)
        export_glb(f"cubo_{key}", [o, e])
        bpy.data.objects.remove(e)

    names = ["bloque", "forma", "subdivision", "visor", "apoyos", "final"]
    for i, nm in enumerate(names, start=1):
        reset()
        M = MATS()
        workbench()
        camera((1.25, -2.35, 0.75), (0, 0, -0.08 if i == 6 else 0), 40)
        o = build_head(M, min(i, 5))
        extras = head_extras(M) if i == 6 else []
        w = wire_overlay(o, 0.004)
        render(f"l4_{i:02d}_{nm}")
        if i >= 4:
            hide([w])
            render(f"l4_{i:02d}_{nm}_limpio")
        hide([w])
        e = edge_object(o)
        export_glb(f"cabeza_{i:02d}", [o, e] + extras)
        if i == 6:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "cabeza_robot.blend"))


def lesson4_eevee():
    reset()
    M = MATS()
    studio(M)
    eevee()
    o = build_head(M, 5)
    pivot = bpy.data.objects.new("Soporte", None)
    bpy.context.scene.collection.objects.link(pivot)
    for ob in [o] + head_extras(M):
        ob.parent = pivot
    pivot.location = (0, 0, 0.83)
    pivot.rotation_euler = (0, 0, math.radians(-18))
    b = bmesh.new()
    bmesh.ops.create_cone(b, cap_ends=True, segments=48, radius1=0.5, radius2=0.45, depth=0.04)
    bmesh.ops.translate(b, verts=b.verts, vec=(0, 0, 0.02))
    obj_from_bm("Peana", b, M["dark"], smooth=True)
    camera((1.45, -4.3, 1.35), (0, 0, 0.88), 72)
    render("l4_eevee", 1600, 900)


# ------------------------------------------- Lección 5: placa base sci-fi

import random


def prism_bm(pts, z0, z1):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z0)) for x, y in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def top_face(bm):
    bm.normal_update()
    return max((f for f in bm.faces if f.normal.z > 0.99), key=lambda f: f.calc_center_median().z)


def bevel_mod(o, w=0.006, seg=2):
    for p in o.data.polygons:
        p.use_smooth = True
    b = o.modifiers.new("Bevel", "BEVEL")
    b.width, b.segments, b.harden_normals = w, seg, True
    b.limit_method = "ANGLE"
    b.angle_limit = math.radians(30)
    return o


def box_pts(sx, sy, cx=0, cy=0):
    return [(cx - sx / 2, cy - sy / 2), (cx + sx / 2, cy - sy / 2), (cx + sx / 2, cy + sy / 2), (cx - sx / 2, cy + sy / 2)]


def place(objs, loc, rot_z=0, parent_name="Pieza"):
    """Agrupa las partes de una pieza bajo un Empty y la coloca: así se mueve como un todo."""
    e = bpy.data.objects.new(parent_name, None)
    bpy.context.scene.collection.objects.link(e)
    for o in objs:
        o.parent = e
    e.location = loc
    e.rotation_euler = (0, 0, rot_z)
    return e


def kit_mats():
    return {
        "pcb": mat("Placa PCB", (0.075, 0.08, 0.09), 0.5, 0.45),
        "shell": mat("Carcasa", (0.24, 0.25, 0.27), 0.55, 0.35),
        "naranja": mat("Cable naranja", (0.85, 0.3, 0.05), 0, 0.45),
        "azul": mat("Cable azul", (0.05, 0.28, 0.85), 0, 0.45),
        "cobre": mat("Cable cobre", (0.75, 0.42, 0.22), 0.8, 0.35),
        "led": mat("LED", (0.2, 0.7, 1.0), 0, 0.2, (0.15, 0.6, 1.0), 12),
    }


def piece_core(M, K):
    bm = prism_bm(chamfer_rect(-0.5, 0.5, -0.5, 0.5, 0.18), 0, 0.3)
    t = top_face(bm)
    bmesh.ops.inset_individual(bm, faces=[t], thickness=0.08, depth=0)
    extrude_move(bm, [t], (0, 0, -0.04))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    parts = [bevel_mod(obj_from_bm("Nucleo_base", bm, M["armor"]), 0.008)]
    bm = prism_bm(chamfer_rect(-0.2, 0.2, -0.2, 0.2, 0.04), 0.26, 0.3)
    parts.append(bevel_mod(obj_from_bm("Nucleo_chip", bm, K["shell"]), 0.004))
    bm = prism_bm(chamfer_rect(-0.12, 0.12, -0.12, 0.12, 0.02), 0.3, 0.31)
    parts.append(obj_from_bm("Nucleo_luz", bm, K["led"]))
    for i in range(4):  # aletas en cada lado recto: una aleta + Array
        bm = prism_bm(box_pts(0.05, 0.02, 0.525, -0.21), 0.05, 0.23)
        f = bevel_mod(obj_from_bm(f"Nucleo_aletas_{i}", bm, K["shell"]), 0.003)
        a = f.modifiers.new("Array", "ARRAY")
        a.count, a.use_relative_offset, a.use_constant_offset = 7, False, True
        a.constant_offset_displace = (0, 0.07, 0)
        f.modifiers.move(len(f.modifiers) - 1, 0)
        f.rotation_euler = (0, 0, math.radians(90 * i))
        parts.append(f)
    return parts


def piece_module(M, K):
    bm = prism_bm(chamfer_rect(-0.21, 0.21, -0.16, 0.16, 0.05, (0, 1, 0, 1)), 0, 0.14)
    t = top_face(bm)
    bmesh.ops.inset_individual(bm, faces=[t], thickness=0.03, depth=0)
    extrude_move(bm, [t], (0, 0, -0.015))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    parts = [bevel_mod(obj_from_bm("Modulo_caja", bm, K["shell"]), 0.005)]
    parts.append(obj_from_bm("Modulo_led", prism_bm(box_pts(0.05, 0.05, -0.12, 0.08), 0.12, 0.13), K["led"]))
    parts.append(bevel_mod(obj_from_bm("Modulo_puerto", prism_bm(box_pts(0.06, 0.12, 0.24, 0), 0.02, 0.09), M["dark"]), 0.004))
    return parts


def piece_connector(M, K):
    parts = [bevel_mod(obj_from_bm("Conector", prism_bm(chamfer_rect(-0.1, 0.1, -0.06, 0.06, 0.02), 0, 0.06), M["armor"]), 0.004)]
    s = obj_from_bm("Conector_ranuras", prism_bm(box_pts(0.025, 0.07, -0.06, 0), 0.055, 0.07), M["dark"])
    a = s.modifiers.new("Array", "ARRAY")
    a.count, a.use_relative_offset, a.use_constant_offset = 4, False, True
    a.constant_offset_displace = (0.04, 0, 0)
    parts.append(s)
    return parts


def piece_heatsink(M, K):
    parts = [bevel_mod(obj_from_bm("Disipador_base", prism_bm(box_pts(0.3, 0.3), 0, 0.03), M["dark"]), 0.004)]
    f = bevel_mod(obj_from_bm("Disipador_aletas", prism_bm(box_pts(0.012, 0.28, -0.136, 0), 0.03, 0.13), M["armor"]), 0.002)
    a = f.modifiers.new("Array", "ARRAY")
    a.count, a.use_relative_offset, a.use_constant_offset = 9, False, True
    a.constant_offset_displace = (0.034, 0, 0)
    f.modifiers.move(len(f.modifiers) - 1, 0)
    parts.append(f)
    return parts


def cable(name, pts, material, r=0.022):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    cu.materials.append(material)
    return o


# módulos alrededor del núcleo: (posición, giro que apunta su puerto al núcleo, punto de entrada en el núcleo)
SLOTS = [((-1.45, y, 0.1), 0, (-0.5, y * 0.35)) for y in (-0.75, 0, 0.75)] + \
        [((1.45, y, 0.1), math.pi, (0.5, y * 0.35)) for y in (-0.75, 0, 0.75)] + \
        [((x, 1.05, 0.1), -math.pi / 2, (x * 0.35, 0.5)) for x in (-0.75, 0.75)] + \
        [((x, -1.05, 0.1), math.pi / 2, (x * 0.35, -0.5)) for x in (-0.75, 0.75)]


def board(M, K):
    bm = prism_bm(chamfer_rect(-2.0, 2.0, -1.4, 1.4, 0.3), 0, 0.12)
    t = top_face(bm)
    bmesh.ops.inset_individual(bm, faces=[t], thickness=0.1, depth=0)
    extrude_move(bm, [t], (0, 0, -0.02))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bevel_mod(obj_from_bm("Placa_base", bm, K["pcb"]), 0.008)


def build_board(M, K, paso, ruido=False):
    objs = [board(M, K)]
    if paso >= 2:
        objs += piece_core(M, K)
        place(objs[1:], (0, 0, 0.1), 0, "Nucleo")
        for i, (loc, rz, _) in enumerate(SLOTS):
            parts = piece_module(M, K)
            place(parts, loc, rz, f"Modulo_{i}")
            objs += parts
    if paso >= 3:
        colores = [K["naranja"], K["azul"], K["cobre"]]
        for i, (loc, rz, entrada) in enumerate(SLOTS):
            d = Vector((math.cos(rz), math.sin(rz), 0))
            n = Vector((-d.y, d.x, 0))
            tip = Vector(loc) + d * 0.27
            end = Vector((entrada[0], entrada[1], 0)) + d * -0.04  # entra bajo las aletas
            for k in (-1, 0, 1):
                a = Vector((tip.x, tip.y, 0.155)) + n * 0.034 * k
                b = Vector((end.x, end.y, 0.135)) + n * 0.05 * k
                pts = [a, a + d * 0.12 + Vector((0, 0, -0.02)), (a + b) / 2 + Vector((0, 0, -0.012)), b - d * 0.12, b]
                objs.append(cable(f"Cable_{i}_{k + 1}", pts, colores[k + 1]))
            mid = (tip + end) / 2
            clamp = bevel_mod(obj_from_bm(f"Abrazadera_{i}", prism_bm(box_pts(0.05, 0.2), 0.1, 0.18), M["armor"]), 0.004)
            clamp.location = (mid.x, mid.y, 0)
            clamp.rotation_euler = (0, 0, rz)
            objs.append(clamp)
    if paso >= 4 and not ruido:
        for sx in (-1, 1):
            for sy in (-1, 1):
                parts = piece_heatsink(M, K)
                place(parts, (1.6 * sx, 1.12 * sy, 0.1), 0, "Disipador")
                objs += parts
            for sy in (-1, 1):
                objs.append(bolt(f"Tornillo_{sx}{sy}", 1.94 * sx, 0.95 * sy, M, z=0.12))
        for y in (1.12, -1.12):
            parts = piece_connector(M, K)
            place(parts, (0, y, 0.1), 0, "Conector")
            objs += parts
    if ruido:
        rnd = random.Random(7)
        for i in range(46):
            kind = rnd.choice([piece_connector, piece_heatsink, piece_connector])
            parts = kind(M, K)
            z = rnd.choice([0.1, 0.1, 0.24, 0.4])
            place(parts, (rnd.uniform(-1.8, 1.8), rnd.uniform(-1.2, 1.2), z), rnd.uniform(0, 6.3), "Ruido")
            objs += parts
    return objs


def mesh_copies(objs):
    """Copias en malla (las curvas de los cables también) para exportar al .glb."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        if o.type not in ("MESH", "CURVE"):
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        c = bpy.data.objects.new(o.name + "_glb", me)
        bpy.context.scene.collection.objects.link(c)
        c.matrix_world = o.evaluated_get(dg).matrix_world.copy()  # incluye constraints
        out.append(c)
    return out


def label(text, loc, size=0.11):
    cu = bpy.data.curves.new("Etiqueta", "FONT")
    cu.body = text
    cu.size = size
    cu.align_x = "CENTER"
    o = bpy.data.objects.new("Etiqueta", cu)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    cu.materials.append(mat("Texto", (0.85, 0.88, 0.92)))
    return o


def lesson5():
    reset()
    M = MATS()
    K = kit_mats()
    workbench()
    camera((0.15, -4.9, 3.1), (0.15, 0.0, 0.1), 38)
    kit = [(piece_core, "NÚCLEO", -1.55, 1), (piece_module, "MÓDULO", -0.35, 1.4), (piece_connector, "CONECTOR", 0.45, 1.6),
           (piece_heatsink, "DISIPADOR", 1.2, 1.4)]
    allp = []
    for fn, name, x, s in kit:
        parts = fn(M, K)
        e = place(parts, (x, 0.15, 0), 0, name)
        e.scale = (s, s, s)
        allp += parts
        label(name, (x, -0.65, 0))
    t = bolt("Tornillo", 0, 0, M, z=0)
    t.scale = (2.5, 2.5, 2.5)
    t.location = (1.85, 0.15, 0)
    allp.append(t)
    label("TORNILLO", (1.85, -0.65, 0))
    render("l5_01_kit")
    export_glb("kit", mesh_copies(allp))

    names = {1: "base", 2: "colocar", 3: "cables", 4: "final"}
    for paso, nm in names.items():
        reset()
        M = MATS()
        K = kit_mats()
        workbench()
        camera((2.9, -4.1, 3.7), (0, -0.1, 0), 35)
        objs = build_board(M, K, paso)
        render(f"l5_{paso + 1:02d}_{nm}")
        export_glb(f"placabase_{paso:02d}", mesh_copies(objs))
        if paso == 4:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "placa_base_kitbash.blend"))
    reset()
    M = MATS()
    K = kit_mats()
    workbench()
    camera((2.9, -4.1, 3.7), (0, -0.1, 0), 35)
    build_board(M, K, 3, ruido=True)
    render("l5_ruido")


def lesson5_eevee():
    reset()
    M = MATS()
    K = kit_mats()
    studio(M)
    eevee()
    objs = build_board(M, K, 4)
    camera((2.4, -3.6, 3.0), (0.05, -0.05, 0.1), 32)
    render("l5_eevee", 1600, 900)


# ------------------------------------------------ Lección 6: espada-arma

def side_prism_bm(pts, y0, y1):
    """Perfil en el plano XZ (vista lateral) extruido en Y: así se dibujan armas de perfil."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y0, z)) for x, z in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, y1 - y0, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def side_prism(name, pts, y0, y1, material, mirror=False, bevel=0.006):
    o = obj_from_bm(name, side_prism_bm(pts, y0, y1), material)
    if mirror:
        m = o.modifiers.new("Mirror", "MIRROR")
        m.use_axis = (False, True, False)
    if bevel:
        bevel_mod(o, bevel)
    return o


def offset_poly(pts, d):
    """Desplaza un contorno antihorario hacia dentro una distancia d (inglete en las esquinas)."""
    out, n = [], len(pts)
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e1, e2 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n1, n2 = Vector((-e1.y, e1.x)), Vector((-e2.y, e2.x))
        m = (n1 + n2).normalized()
        out.append(tuple(p1 + m * (d / max(0.2, m.dot(n1)))))
    return out


def ribbon(name, pts, d0, d1, y0, y1, material):
    """Cinta fina que sigue un contorno: las líneas rojas de la hoja."""
    a, b = offset_poly(pts, d0), offset_poly(pts, d1)
    bm = bmesh.new()
    va = [bm.verts.new((x, y0, z)) for x, z in a]
    vb = [bm.verts.new((x, y0, z)) for x, z in b]
    n = len(pts)
    faces = [bm.faces.new((va[i], va[(i + 1) % n], vb[(i + 1) % n], vb[i])) for i in range(n)]
    r = bmesh.ops.extrude_face_region(bm, geom=faces)
    top = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, y1 - y0, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj_from_bm(name, bm, material)
    m = o.modifiers.new("Mirror", "MIRROR")
    m.use_axis = (False, True, False)
    return o


def gear_pts(cx, cz, r_in, r_out, teeth):
    pts = []
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        s = 2 * math.pi / teeth
        for frac, r in ((0.0, r_in), (0.18, r_out), (0.5, r_out), (0.68, r_in)):
            pts.append((cx + r * math.cos(a + s * frac), cz + r * math.sin(a + s * frac)))
    return pts


def x_cylinder(name, x0, x1, r, z, material, segs=16, y=0.0):
    b = bmesh.new()
    bmesh.ops.create_cone(b, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r, depth=x1 - x0)
    bmesh.ops.rotate(b, verts=b.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"))
    bmesh.ops.translate(b, verts=b.verts, vec=((x0 + x1) / 2, y, z))
    return bevel_mod(obj_from_bm(name, b, material), 0.004)


def y_cylinder(name, x, z, r, y0, y1, material, segs=16):
    b = bmesh.new()
    bmesh.ops.create_cone(b, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r, depth=y1 - y0)
    bmesh.ops.rotate(b, verts=b.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"))
    bmesh.ops.translate(b, verts=b.verts, vec=(x, (y0 + y1) / 2, z))
    return bevel_mod(obj_from_bm(name, b, material), 0.004)


def weapon_mats():
    return {
        "negro": mat("Arma negro", (0.022, 0.024, 0.028), 0.5, 0.38),
        "gris": mat("Arma grafito", (0.085, 0.09, 0.1), 0.7, 0.3),
        "goma": mat("Goma", (0.03, 0.03, 0.032), 0, 0.7),
        "rojo": mat("Linea roja", (0.8, 0.05, 0.05), 0, 0.3, (1.0, 0.05, 0.04), 6),
        "azul": mat("Nucleo", (0.2, 0.6, 1.0), 0, 0.2, (0.08, 0.45, 1.0), 9),
    }


BLADE = [(-2.6, 0.03), (-2.3, -0.17), (-0.95, -0.17), (-0.8, -0.24), (0.0, -0.24), (0.0, 0.3),
         (-0.75, 0.3), (-0.9, 0.24), (-2.3, 0.24)]
RECEIVER = [(0.0, -0.3), (0.7, -0.3), (0.92, -0.12), (0.92, 0.22), (0.78, 0.38), (0.05, 0.38), (0.0, 0.33)]


def build_weapon(M, W, paso):
    """paso 1-2: blockout de cajas · 3: formas · 4: detalle · 5: acabado."""
    objs = []
    if paso <= 2:
        g = M["armor"]
        objs.append(side_prism("Hoja", box_pts(2.6, 0.54, -1.3, 0.03), -0.05, 0.05, g, bevel=0))
        objs.append(side_prism("Cuerpo", box_pts(0.92, 0.68, 0.46, 0.04), -0.11, 0.11, g, bevel=0))
        objs.append(x_cylinder("Empunadura", 0.92, 1.5, 0.075, 0.02, g, 8))
        objs.append(side_prism("Culata", box_pts(0.45, 0.3, 1.72, 0.0), -0.08, 0.08, g, bevel=0))
        objs.append(side_prism("Bastidor", box_pts(1.25, 0.09, 1.32, -0.2), -0.05, 0.05, g, bevel=0))
        return objs
    bev = 0.006 if paso >= 5 else 0
    hoja = side_prism("Hoja", BLADE, -0.05, 0.05, W["gris"], bevel=bev)
    cuerpo = side_prism("Cuerpo", RECEIVER, -0.11, 0.11, W["negro"], bevel=bev)
    objs += [hoja, cuerpo]
    objs.append(side_prism("Riel", box_pts(0.6, 0.05, 0.4, 0.405), -0.06, 0.06, W["gris"], bevel=bev))
    for i, (x0, x1, r) in enumerate([(0.92, 1.04, 0.08), (1.04, 1.14, 0.072), (1.14, 1.26, 0.08), (1.26, 1.36, 0.072), (1.36, 1.5, 0.08)]):
        objs.append(x_cylinder(f"Empunadura_{i}", x0, x1, r, 0.02, W["goma"]))
    objs.append(side_prism("Bastidor", [(0.7, -0.3), (1.0, -0.24), (1.95, -0.24), (1.95, -0.15), (1.0, -0.15), (0.75, -0.21)],
                           -0.05, 0.05, W["negro"], bevel=bev))
    objs.append(side_prism("Gatillo", [(0.8, -0.3), (0.86, -0.3), (0.9, -0.42), (0.85, -0.42)], -0.015, 0.015, W["gris"], bevel=bev))
    for z in (-0.11, 0.13):
        objs.append(side_prism(f"Barra_{z}", box_pts(0.4, 0.035, 1.7, z), -0.035, 0.035, W["gris"], bevel=bev))
    objs.append(x_cylinder("Tapa", 1.88, 1.96, 0.115, 0.01, W["negro"]))
    if paso < 4:
        return objs
    # -- detalle: placas, líneas rojas, luces, ventana, engranaje, pistón y celda
    placa = side_prism("Placa_hoja", offset_poly(BLADE, 0.06), 0.05, 0.068, W["negro"], mirror=True, bevel=bev)
    objs.append(placa)
    objs.append(ribbon("Linea_roja", BLADE, 0.032, 0.044, 0.05, 0.054, W["rojo"]))
    objs.append(side_prism("Placa_cuerpo", offset_poly(RECEIVER, 0.05), 0.11, 0.125, W["gris"], mirror=True, bevel=bev))
    objs.append(ribbon("Linea_roja_cuerpo", RECEIVER, 0.025, 0.035, 0.11, 0.114, W["rojo"]))
    ventana = side_prism("Cortador_ventana", chamfer_rect(-2.12, -1.38, -0.04, 0.1, 0.06), -0.3, 0.3, W["gris"], bevel=0)
    ventana.display_type = "WIRE"
    ventana.hide_render = True
    objs.append(ventana)  # el cortador viaja con el arma
    for o in (hoja, placa):
        b = o.modifiers.new("Boolean", "BOOLEAN")
        b.object = ventana
        b.solver = "EXACT"
        o.modifiers.move(len(o.modifiers) - 1, 0)
    objs.append(side_prism("Luz_ventana", offset_poly(chamfer_rect(-2.12, -1.38, -0.04, 0.1, 0.06), 0.02), -0.025, 0.025, W["azul"], bevel=0))
    for z in (0.17, -0.11):
        d = side_prism(f"Luces_{z}", chamfer_rect(-2.0, -1.88, z - 0.014, z + 0.014, 0.012), 0.066, 0.072, W["azul"], mirror=True, bevel=0)
        a = d.modifiers.new("Array", "ARRAY")
        a.count, a.use_relative_offset, a.use_constant_offset = 6, False, True
        a.constant_offset_displace = (0.19, 0, 0)
        d.modifiers.move(len(d.modifiers) - 1, 0)
        objs.append(d)
    objs.append(side_prism("Luces_cuerpo", chamfer_rect(0.15, 0.27, 0.2, 0.226, 0.01), 0.123, 0.13, W["azul"], mirror=True, bevel=0))
    objs[-1].modifiers.new("Array", "ARRAY").count = 3
    objs[-1].modifiers["Array"].relative_offset_displace = (1.45, 0, 0)
    objs[-1].modifiers.move(1, 0)
    objs.append(side_prism("Engranaje", gear_pts(0.62, 0.02, 0.13, 0.16, 12), 0.125, 0.16, W["gris"], mirror=True, bevel=bev))
    objs.append(y_cylinder("Eje_engranaje", 0.62, 0.02, 0.05, -0.19, 0.19, W["negro"]))
    objs.append(x_cylinder("Piston_camisa", 0.12, 0.45, 0.04, 0.475, W["negro"]))
    objs.append(x_cylinder("Piston_vastago", 0.45, 0.7, 0.022, 0.475, W["gris"]))
    for x in (0.14, 0.68):
        objs.append(side_prism(f"Soporte_{x}", box_pts(0.05, 0.08, x, 0.45), -0.03, 0.03, W["gris"], bevel=bev))
    c, cx = build_cell(cell_steps()[-1], 6, MATS(), final=True)
    for o in [c] + cx:
        o.scale = (0.16, 0.16, 0.16)
        o.rotation_euler = (0, math.radians(90), 0)
        o.location = (1.555, 0, 0.0)
    objs += [c] + cx
    return objs


def lesson6():
    def scene():
        reset()
        M = MATS()
        W = weapon_mats()
        workbench()
        return M, W
    # siluetas: lo primero que se lee de un diseño
    for paso, nm in ((2, "silueta_bloque"), (5, "silueta_final")):
        M, W = scene()
        s = bpy.context.scene
        s.display.shading.light = "FLAT"
        s.display.shading.color_type = "SINGLE"
        s.display.shading.single_color = (0.02, 0.02, 0.025)
        s.display.shading.show_cavity = False
        s.world.color = (0.8, 0.81, 0.83)
        camera((-0.33, -7.5, 0.0), (-0.33, 0, 0.0), 45)
        build_weapon(M, W, paso)
        render(f"l6_{nm}", 1280, 480)
    names = {2: "blockout", 3: "formas", 4: "detalle", 5: "final"}
    for paso, nm in names.items():
        M, W = scene()
        camera((-0.1, -5.6, 1.5), (-0.33, 0, 0.0), 40)
        objs = build_weapon(M, W, paso)
        render(f"l6_{paso - 1:02d}_{nm}", 1280, 600)
        export_glb(f"arma_{paso - 1:02d}", mesh_copies([o for o in objs if not o.hide_render]))
        if paso == 5:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "espada_arma.blend"))


def lesson6_eevee():
    reset()
    M = MATS()
    W = weapon_mats()
    studio(M)
    eevee()
    objs = build_weapon(M, W, 5)
    pivot = bpy.data.objects.new("Soporte", None)
    bpy.context.scene.collection.objects.link(pivot)
    for o in objs:
        if o.parent is None:
            o.parent = pivot
    pivot.location = (0.2, 0, 1.05)
    pivot.rotation_euler = (0, math.radians(-6), 0)
    camera((-0.1, -6.0, 1.25), (-0.15, 0, 1.0), 42)
    render("l6_eevee", 1600, 800)


# -------------------------------------------- Lección 7: brazo robótico

def rounded_bar(x0, x1, w, seg=10):
    """Perfil de barra con extremos semicirculares (XZ): la forma de toda bisagra."""
    r = w / 2
    pts = []
    for i in range(seg + 1):
        a = math.radians(90 + 180 * i / seg)
        pts.append((x0 + r * math.cos(a), r * math.sin(a)))
    for i in range(seg + 1):
        a = math.radians(-90 + 180 * i / seg)
        pts.append((x1 + r * math.cos(a), r * math.sin(a)))
    return pts


def empty(name, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.parent = parent
    e.location = loc
    e.empty_display_size = 0.15
    return e


def parent_all(objs, parent):
    for o in objs:
        o.parent = parent


def piston(name, a, b, l1, l2, W, M, r=0.045):
    """Camisa en A mirando a B y vástago en B mirando a A: se alargan y encogen solos."""
    parts = []
    for nm, src, dst, length, rad, mt in ((name + "_camisa", a, b, l1, r, W["negro"]), (name + "_vastago", b, a, l2, r * 0.55, M["armor"])):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=rad, radius2=rad, depth=length)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, length / 2))
        o = bevel_mod(obj_from_bm(nm, bm, mt), 0.004)
        o.parent = src
        c = o.constraints.new("DAMPED_TRACK")
        c.target = dst
        c.track_axis = "TRACK_Z"
        parts.append(o)
    return parts


def build_arm(M, W, pose):
    """Brazo con jerarquía de pivotes: Giro → Hombro → Codo → Muñeca."""
    objs = []
    giro = empty("Giro")
    b = bmesh.new()
    bmesh.ops.create_cone(b, cap_ends=True, segments=32, radius1=0.55, radius2=0.5, depth=0.12)
    bmesh.ops.translate(b, verts=b.verts, vec=(0, 0, 0.06))
    objs.append(bevel_mod(obj_from_bm("Base", b, W["negro"]), 0.01))
    b = bmesh.new()
    bmesh.ops.create_cone(b, cap_ends=True, segments=32, radius1=0.35, radius2=0.33, depth=0.26)
    bmesh.ops.translate(b, verts=b.verts, vec=(0, 0, 0.25))
    torreta = bevel_mod(obj_from_bm("Torreta", b, M["armor"]), 0.01)
    lug_pts = [(-0.15, 0.3)] + [(0.15 * math.cos(math.radians(a)), 0.6 + 0.15 * math.sin(math.radians(a))) for a in range(0, 181, 15)]
    lug_pts = [(0.15, 0.3)] + lug_pts[1:] + [(-0.15, 0.3)]
    horquilla = side_prism("Horquilla_hombro", lug_pts, 0.1, 0.15, W["gris"], mirror=True)
    pas1 = y_cylinder("Pasador_hombro", 0, 0.6, 0.05, -0.19, 0.19, W["negro"])
    orejeta = side_prism("Orejeta_piston", rounded_bar(0.28, 0.28, 0.08), -0.06, 0.06, W["gris"])
    orejeta.location = (0, 0, 0.42)
    parent_all([torreta, horquilla, pas1, orejeta], giro)
    objs += [torreta, horquilla, pas1, orejeta]

    hombro = empty("Hombro", giro, (0, 0, 0.6))
    brazo = [side_prism("Brazo_viga", rounded_bar(0, 0.82, 0.22), -0.06, 0.06, W["gris"]),
             side_prism("Brazo_horquilla", rounded_bar(0.72, 1.0, 0.26), 0.085, 0.125, W["gris"], mirror=True),
             side_prism("Brazo_blindaje", chamfer_rect(0.2, 0.72, -0.15, 0.15, 0.06), -0.14, 0.14, M["armor"]),
             y_cylinder("Pasador_codo", 1.0, 0, 0.045, -0.16, 0.16, W["negro"]),
             y_cylinder("Anclaje_codo", 0.35, 0, 0.03, -0.24, -0.14, W["negro"])]
    parent_all(brazo, hombro)
    objs += brazo

    codo = empty("Codo", hombro, (1.0, 0, 0))
    ante = [side_prism("Antebrazo_viga", rounded_bar(0, 0.75, 0.18), -0.07, 0.07, W["gris"]),
            side_prism("Antebrazo_blindaje", chamfer_rect(0.15, 0.6, -0.12, 0.12, 0.05), -0.12, 0.12, M["armor"]),
            x_cylinder("Muneca", 0.75, 0.83, 0.1, 0, W["negro"]),
            y_cylinder("Anclaje_ante", 0.3, 0, 0.03, -0.24, -0.12, W["negro"])]
    parent_all(ante, codo)
    objs += ante

    muneca = empty("Muneca", codo, (0.83, 0, 0))
    dedo = [(0.1, 0.03), (0.26, 0.1), (0.33, 0.07), (0.3, 0.035), (0.12, -0.01)]
    mano = [side_prism("Palma", chamfer_rect(0, 0.13, -0.1, 0.1, 0.03), -0.09, 0.09, W["gris"]),
            side_prism("Dedo_sup", dedo, -0.04, 0.04, W["negro"]),
            side_prism("Dedo_inf", [(x, -z) for x, z in reversed(dedo)], -0.04, 0.04, W["negro"])]
    parent_all(mano, muneca)
    objs += mano

    # pistones con anclajes (empties) en cada pieza
    a1 = empty("A_hombro", giro, (0.28, 0, 0.42))
    b1 = empty("B_hombro", hombro, (0.4, 0, -0.11))
    a2 = empty("A_codo", hombro, (0.35, -0.19, 0))
    b2 = empty("B_codo", codo, (0.3, -0.19, 0))
    objs += piston("Piston_hombro", a1, b1, 0.3, 0.3, W, M)
    objs += piston("Piston_codo", a2, b2, 0.52, 0.47, W, M, r=0.04)

    giro.rotation_euler = (0, 0, math.radians(pose[0]))
    hombro.rotation_euler = (0, math.radians(pose[1]), 0)
    codo.rotation_euler = (0, math.radians(pose[2]), 0)
    muneca.rotation_euler = (0, math.radians(pose[3]), 0)
    bpy.context.view_layer.update()
    return objs, {"Hombro": hombro, "Codo": codo, "Muneca": muneca}


POSES = {"a": (0, -40, 60, 10), "b": (0, -70, 100, 30), "c": (0, -20, 30, -20)}


def lesson7():
    def scene():
        reset()
        M = MATS()
        W = weapon_mats()
        workbench()
        return M, W
    for key, pose in POSES.items():
        M, W = scene()
        camera((1.0, -4.2, 1.5), (0.55, 0, 0.9), 40)
        objs, piv = build_arm(M, W, pose)
        render(f"l7_pose_{key}")
        export_glb(f"brazo_{key}", mesh_copies(objs))
        if key == "a":
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "brazo_robotico.blend"))
    # pivotes: esferas rojas en el centro de cada pasador
    M, W = scene()
    camera((1.0, -4.2, 1.5), (0.55, 0, 0.9), 40)
    objs, piv = build_arm(M, W, POSES["a"])
    rojo = mat("Marcador", (1.0, 0.1, 0.1))
    for e in piv.values():
        b = bmesh.new()
        bmesh.ops.create_uvsphere(b, u_segments=16, v_segments=8, radius=0.06)
        s = obj_from_bm("Marcador", b, rojo, smooth=True)
        s.location = e.matrix_world.translation
        s.location.y = -0.3
    render("l7_pivotes")
    # primeros planos: bisagra y pistón
    M, W = scene()
    objs, piv = build_arm(M, W, POSES["a"])
    camera((0.55, -1.25, 0.95), (0.05, 0, 0.6), 40)
    render("l7_bisagra")
    camera((1.35, -1.6, 1.15), (0.85, -0.19, 0.95), 40)
    render("l7_piston")


def lesson7_eevee():
    reset()
    M = MATS()
    W = weapon_mats()
    studio(M)
    eevee()
    build_arm(M, W, (-20, -45, 75, 15))
    camera((1.9, -3.9, 1.6), (0.4, 0, 0.85), 45)
    render("l7_eevee", 1600, 900)


# -------------------------------------------- Lección 8: materiales y render

def paint_material(name, paint, metal=(0.32, 0.33, 0.35), rough=0.42, wear=True, dirt=True):
    """Pintura con variación de rugosidad, desgaste en bordes (nodo Bevel) y suciedad (AO). Solo Cycles."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    # rugosidad que varía un poco: ninguna superficie real es uniforme
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 4
    rmap = N.new("ShaderNodeMapRange")
    rmap.inputs["To Min"].default_value = rough - 0.1
    rmap.inputs["To Max"].default_value = rough + 0.1
    L.new(nz.outputs["Fac"], rmap.inputs["Value"])
    color_out, rough_out, metal_out = None, rmap.outputs["Result"], None
    base = N.new("ShaderNodeRGB")
    base.outputs[0].default_value = (*paint, 1)
    color_out = base.outputs[0]
    if wear:
        bev = N.new("ShaderNodeBevel")
        bev.inputs["Radius"].default_value = 0.03
        geo = N.new("ShaderNodeNewGeometry")
        dot = N.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        L.new(bev.outputs["Normal"], dot.inputs[0])
        L.new(geo.outputs["Normal"], dot.inputs[1])
        edge = N.new("ShaderNodeMath")
        edge.operation = "SUBTRACT"
        edge.inputs[0].default_value = 1.0
        L.new(dot.outputs["Value"], edge.inputs[1])
        nz2 = N.new("ShaderNodeTexNoise")
        nz2.inputs["Scale"].default_value = 12
        nz2.inputs["Detail"].default_value = 8
        mul = N.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        L.new(edge.outputs["Value"], mul.inputs[0])
        L.new(nz2.outputs["Fac"], mul.inputs[1])
        mask = N.new("ShaderNodeMapRange")
        mask.inputs["From Min"].default_value = 0.01
        mask.inputs["From Max"].default_value = 0.05
        L.new(mul.outputs["Value"], mask.inputs["Value"])
        mix = N.new("ShaderNodeMixRGB")
        mix.inputs["Color2"].default_value = (*metal, 1)
        L.new(mask.outputs["Result"], mix.inputs["Fac"])
        L.new(color_out, mix.inputs["Color1"])
        color_out = mix.outputs["Color"]
        rmix = N.new("ShaderNodeMixRGB")
        rmix.inputs["Color2"].default_value = (0.22, 0.22, 0.22, 1)
        L.new(mask.outputs["Result"], rmix.inputs["Fac"])
        L.new(rough_out, rmix.inputs["Color1"])
        rough_out = rmix.outputs["Color"]
        metal_out = mask.outputs["Result"]
    if dirt:
        ao = N.new("ShaderNodeAmbientOcclusion")
        ao.inputs["Distance"].default_value = 0.08
        amap = N.new("ShaderNodeMapRange")
        amap.inputs["To Min"].default_value = 0.45
        L.new(ao.outputs["AO"], amap.inputs["Value"])
        dmix = N.new("ShaderNodeMixRGB")
        dmix.blend_type = "MULTIPLY"
        dmix.inputs["Fac"].default_value = 1.0
        L.new(color_out, dmix.inputs["Color1"])
        L.new(amap.outputs["Result"], dmix.inputs["Color2"])
        color_out = dmix.outputs["Color"]
    L.new(color_out, bsdf.inputs["Base Color"])
    L.new(rough_out, bsdf.inputs["Roughness"])
    if metal_out:
        L.new(metal_out, bsdf.inputs["Metallic"])
    else:
        bsdf.inputs["Metallic"].default_value = 0.1
    return m


def cycles_setup(samples=64):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.world.color = (0.02, 0.02, 0.025)
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Medium High Contrast"


def glare(on=True):
    s = bpy.context.scene
    s.use_nodes = on
    if not on:
        return
    nt = s.node_tree
    rl, comp = nt.nodes["Render Layers"], nt.nodes["Composite"]
    g = nt.nodes.new("CompositorNodeGlare")
    g.glare_type = "FOG_GLOW"
    g.threshold = 1.2
    g.size = 7
    nt.links.new(rl.outputs["Image"], g.inputs["Image"])
    nt.links.new(g.outputs["Image"], comp.inputs["Image"])


def showcase(M):
    """La placa del módulo 3 y la celda del módulo 1, como en su render."""
    p, cutters, extras = build_plate(M, 7)
    pivot = bpy.data.objects.new("Soporte", None)
    bpy.context.scene.collection.objects.link(pivot)
    for o in [p] + extras + cutters:
        o.parent = pivot
    pivot.rotation_euler = (math.radians(65), 0, math.radians(-12))
    pivot.location = (0, 0, 0.62)
    c, cx = build_cell(cell_steps()[-1], 6, M, final=True)
    for o in [c] + cx:
        o.scale = (0.42, 0.42, 0.42)
        o.location = (1.35, -0.1, 0)
    camera((1.1, -4.2, 1.3), (0.3, 0, 0.62), 50)


def lesson8():
    etapas = ["gris", "pintura", "desgaste", "emision", "luz_plana"]
    for i, nm in enumerate(etapas, start=1):
        reset()
        M = MATS()
        studio(M)
        cycles_setup()
        showcase(M)
        gris = mat("Gris", (0.5, 0.5, 0.5), 0, 0.5)
        apagado = mat("Emisivo apagado", (0.04, 0.05, 0.07), 0.2, 0.2)
        detalle = i >= 3
        naranja = paint_material("Pintura naranja", (0.85, 0.36, 0.08), rough=0.4, wear=detalle, dirt=detalle)
        mats = {
            "Blindaje": paint_material("Pintura blanca", (0.72, 0.73, 0.76), wear=detalle, dirt=detalle),
            "Metal oscuro": paint_material("Pintura grafito", (0.05, 0.055, 0.06), metal=(0.5, 0.5, 0.5), rough=0.35, wear=detalle, dirt=detalle),
        }
        for o in bpy.data.objects:
            if o.type != "MESH" or o.name == "Ciclorama":
                continue
            for slot in o.material_slots:
                n = slot.material.name if slot.material else ""
                if i == 1:
                    slot.material = gris
                elif n == "Blindaje" and o.name.startswith("Celda"):
                    slot.material = naranja
                elif n in mats:
                    slot.material = mats[n]
                elif n in ("Nucleo",) and i < 4:
                    slot.material = apagado
        glare(i >= 4)
        if nm == "luz_plana":
            for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
                bpy.data.objects.remove(o)
            sun = bpy.data.objects.new("Sol", bpy.data.lights.new("Sol", "SUN"))
            bpy.context.scene.collection.objects.link(sun)
            sun.data.energy = 3.5
            sun.rotation_euler = (math.radians(75), 0, math.radians(15))
        render(f"l8_{i:02d}_{nm}", 1100, 620)
        if nm == "emision":
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "materiales_render.blend"))
            # la misma escena en EEVEE: sin nodo Bevel ni AO de Cycles
            eevee()
            render("l8_eevee_mismo", 1100, 620)


# ------------------------------------------------ Lección 9: el androide

def cbox(name, size, center, material, chamfer=0.03, taper=None, rot=None):
    """Caja con todas las aristas achaflanadas: la pieza base del blindaje del androide."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    if taper:  # (factor X abajo, factor Y abajo): estrecha la parte inferior
        for v in bm.verts:
            if v.co.z < 0:
                v.co.x *= taper[0]
                v.co.y *= taper[1]
    if chamfer:
        bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=chamfer, segments=1,
                        affect="EDGES", profile=0.5, clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj_from_bm(name, bm, material)
    o.location = center
    if rot:
        o.rotation_euler = rot
    return bevel_mod(o, 0.006) if chamfer else o


def sphere(name, r, center, material):
    b = bmesh.new()
    bmesh.ops.create_uvsphere(b, u_segments=24, v_segments=12, radius=r)
    o = obj_from_bm(name, b, material, smooth=True)
    o.location = center
    return o


def android_mats():
    return {
        "blanco": mat("Blindaje blanco", (0.74, 0.75, 0.79), 0.2, 0.38),
        "marco": mat("Estructura", (0.1, 0.105, 0.115), 0.6, 0.35),
        "gris": mat("Gris medio", (0.32, 0.33, 0.36), 0.5, 0.35),
        "azul": mat("Luz azul", (0.2, 0.6, 1.0), 0, 0.2, (0.1, 0.5, 1.0), 8),
    }


def build_android(M, A, nivel):
    """nivel 1: blockout de cajas · 2: formas y articulaciones · 3: detalle y piezas de la ruta."""
    o = []
    ch = 0.0 if nivel == 1 else 1.0
    blanco = A["blanco"] if nivel > 1 else M["armor"]
    marco = A["marco"] if nivel > 1 else M["armor"]

    def C(name, size, center, mt, chamfer=0.04, **kw):
        o.append(cbox(name, size, center, mt, chamfer * ch, **kw))
        return o[-1]

    for s in (-1, 1):
        x = 0.17 * s
        C(f"Pie_{s}", (0.18, 0.34, 0.1), (x, -0.04, 0.05), marco, 0.03)
        C(f"Espinilla_{s}", (0.21, 0.25, 0.46), (x, 0, 0.38), blanco, 0.06, taper=(0.82, 0.8))
        C(f"Muslo_{s}", (0.19, 0.21, 0.4), (x, 0.0, 0.86), blanco, 0.05, taper=(0.85, 0.9))
        if nivel > 1:
            o.append(sphere(f"Tobillo_{s}", 0.065, (x, 0, 0.13), marco))
            o.append(x_cylinder(f"Rodilla_{s}", x - 0.11, x + 0.11, 0.07, 0.635, marco))
            C(f"Rodillera_{s}", (0.15, 0.08, 0.15), (x, -0.13, 0.64), blanco, 0.035, rot=(math.radians(-12), 0, 0))
            o.append(sphere(f"Cadera_{s}", 0.08, (0.15 * s, 0, 1.08), marco))
            C(f"Falda_{s}", (0.08, 0.22, 0.24), (0.28 * s, 0, 1.08), blanco, 0.03, rot=(0, math.radians(10 * s), 0))
    C("Pelvis", (0.4, 0.25, 0.18), (0, 0, 1.13), marco, 0.04)
    if nivel > 1:
        C("Placa_pelvis", (0.14, 0.06, 0.17), (0, -0.14, 1.1), blanco, 0.025, taper=(0.6, 1))
        for i, (r, z) in enumerate(((0.15, 1.24), (0.14, 1.29), (0.15, 1.34))):
            b = bmesh.new()
            bmesh.ops.create_cone(b, cap_ends=True, cap_tris=False, segments=24, radius1=r, radius2=r, depth=0.045)
            bmesh.ops.translate(b, verts=b.verts, vec=(0, 0, z))
            o.append(bevel_mod(obj_from_bm(f"Abdomen_{i}", b, marco), 0.006))
    else:
        C("Abdomen", (0.28, 0.22, 0.16), (0, 0, 1.29), marco, 0)
    C("Pecho", (0.62, 0.38, 0.42), (0, 0, 1.57), blanco, 0.07, taper=(0.72, 0.85))
    for s in (-1, 1):
        sx = 0.42 * s
        piv = empty(f"Hombro_{s}", None, (sx, 0, 1.69))
        parts = []
        if nivel > 1:
            parts.append(sphere(f"Hombro_bola_{s}", 0.09, (0, 0, 0), marco))
            parts.append(cbox(f"Hombrera_{s}", (0.25, 0.3, 0.2), (0.05 * s, 0, 0.08), blanco, 0.06,
                              rot=(0, math.radians(-15 * s), 0)))
            parts.append(x_cylinder(f"Codo_{s}", -0.085, 0.085, 0.065, -0.42, marco))
        parts.append(cbox(f"Biceps_{s}", (0.13, 0.14, 0.32), (0, 0, -0.23), blanco if nivel > 1 else blanco, 0.035 * ch))
        parts.append(cbox(f"Antebrazo_{s}", (0.17, 0.18, 0.34), (0.005 * s, 0, -0.6), blanco, 0.05 * ch, taper=(0.8, 0.85)))
        parts.append(cbox(f"Mano_{s}", (0.09, 0.12, 0.12), (0.01 * s, 0, -0.83), marco, 0.025 * ch))
        if nivel > 2:
            for k, y in enumerate((-0.04, -0.013, 0.013, 0.04)):
                parts.append(cbox(f"Dedo_{s}_{k}", (0.022, 0.024, 0.085), (0.01 * s, y, -0.93), marco, 0.006))
            parts.append(cbox(f"Pulgar_{s}", (0.025, 0.025, 0.07), (-0.035 * s, -0.06, -0.86), marco, 0.006,
                              rot=(math.radians(20), 0, 0)))
            d = cbox(f"Luz_antebrazo_{s}", (0.012, 0.06, 0.018), (0.088 * s, 0, -0.52), A["azul"], 0)
            a = d.modifiers.new("Array", "ARRAY")
            a.relative_offset_displace = (0, 0, -1.8)
            a.count = 3
            parts.append(d)
        for p in parts:
            p.parent = piv
        piv.rotation_euler = (0, math.radians(-12 * s), 0)
        o += parts
    if nivel > 1:
        C("Cuello", (0.12, 0.12, 0.12), (0, 0.01, 1.82), marco, 0.02)
    if nivel == 1:
        C("Cabeza", (0.24, 0.28, 0.3), (0, 0, 2.0), blanco, 0)
    elif nivel == 2:
        C("Cabeza", (0.24, 0.28, 0.3), (0, 0, 2.0), blanco, 0.06)
    else:
        head = build_head(M, 5)
        head.data.materials[0] = A["blanco"]
        extras = [e for e in head_extras(M) if e.name != "Cuello"]
        piv = empty("Cabeza_pivote", None, (0, -0.01, 1.99))
        for p in [head] + extras:
            p.parent = piv
        piv.scale = (0.3, 0.3, 0.3)
        o += [head] + extras
        # núcleo en el pecho (la celda del módulo 1 vista de frente) y luces
        ring = y_cylinder("Nucleo_anillo", 0, 1.6, 0.1, -0.215, -0.17, A["marco"], 24)
        core = y_cylinder("Nucleo_pecho", 0, 1.6, 0.065, -0.225, -0.2, A["azul"], 24)
        o += [ring, core]
        for s in (-1, 1):
            o.append(cbox(f"Ventilacion_{s}", (0.12, 0.03, 0.08), (0.17 * s, -0.19, 1.71), A["marco"], 0.01))
            o.append(cbox(f"Luz_espinilla_{s}", (0.06, 0.012, 0.018), (0.17 * s, -0.128, 0.42), A["azul"], 0))
            a = o[-1].modifiers.new("Array", "ARRAY")
            a.relative_offset_displace = (0, 0, -2.2)
            a.count = 3
        o.append(cbox("Mochila", (0.42, 0.2, 0.42), (0, 0.27, 1.56), A["gris"], 0.05))
        for s in (-1, 1):
            parts = piece_heatsink(M, {})
            place(parts, (0.1 * s, 0.37, 1.68), 0, "Disipador")
            for p in parts:
                p.rotation_euler = (math.radians(-90), 0, 0)  # aletas hacia atrás
            o += parts
            t = x_cylinder(f"Propulsor_{s}", -0.1, 0.1, 0.06, 0, A["marco"])
            t.rotation_euler = (0, math.radians(90), 0)
            t.location = (0.12 * s, 0.33, 1.33)
            o.append(t)
            b = bmesh.new()
            bmesh.ops.create_cone(b, cap_ends=True, segments=16, radius1=0.045, radius2=0.045, depth=0.02)
            bmesh.ops.translate(b, verts=b.verts, vec=(0.12 * s, 0.33, 1.225))
            o.append(obj_from_bm(f"Tobera_luz_{s}", b, A["azul"]))
    bpy.context.view_layer.update()
    return o


def lesson9():
    def scene():
        reset()
        M = MATS()
        A = android_mats()
        workbench()
        return M, A
    for nivel, nm in ((1, "blockout"), (2, "formas"), (3, "detalle")):
        M, A = scene()
        camera((1.55, -4.1, 1.55), (0, 0, 1.07), 38)
        objs = build_android(M, A, nivel)
        render(f"l9_{nivel:02d}_{nm}", 1000, 1000)
        export_glb(f"androide_{nivel:02d}", mesh_copies(objs))
        if nivel == 3:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "androide.blend"))
    # hoja de giro (turnaround): frente, perfil y espalda en ortográfica
    for nm, loc in (("frente", (0, -6, 1.1)), ("perfil", (6, 0, 1.1)), ("espalda", (0, 6, 1.1))):
        M, A = scene()
        build_android(M, A, 3)
        camera(loc, (0, 0, 1.1), 50)
        bpy.context.scene.camera.data.type = "ORTHO"
        bpy.context.scene.camera.data.ortho_scale = 2.5
        render(f"l9_{nm}", 700, 1000)


def lesson9_eevee():
    reset()
    M = MATS()
    A = android_mats()
    studio(M)
    eevee()
    build_android(M, A, 3)
    camera((1.5, -5.4, 1.5), (0, 0, 1.1), 50)
    render("l9_eevee", 1600, 1000)


if MODE == "m9w":
    lesson9()
if MODE == "m9":
    lesson9()
    lesson9_eevee()
if MODE == "m8":
    lesson8()
if MODE == "m7":
    lesson7()
    lesson7_eevee()
if MODE == "m6":
    lesson6()
    lesson6_eevee()
if MODE == "m5w":
    lesson5()
if MODE == "m5":
    lesson5()
    lesson5_eevee()
if MODE == "m4":
    lesson4()
    lesson4_eevee()
if MODE == "m3e":
    lesson3_eevee()
if MODE == "m3":
    lesson3()
    lesson3_eevee()
if MODE in ("workbench", "all"):
    lesson1_workbench()
    lesson2_workbench()
if MODE in ("eevee", "all"):
    hero_renders()
print("FORJA OK")
