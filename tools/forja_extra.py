"""
Forja Mecha - módulos extra (10-13): Geometry Nodes, Decals, ciclo de caminar y dron.
Reutiliza las piezas y utilidades de forja_build.py.

  blender -b --factory-startup --python tools/forja_extra.py -- m10|m11|m12|m13
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(__file__))
import forja_build as fb  # noqa: E402  (no ejecuta nada: su MODE no coincide)

MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else ""
IMG, GLB, BLEND = fb.IMG, fb.GLB, fb.BLEND
DESC = os.path.join(fb.ROOT, "assets", "descargas")
os.makedirs(DESC, exist_ok=True)


def activos(node):
    return [s for s in node.inputs if s.enabled]


def salidas(node):
    return [s for s in node.outputs if s.enabled]


# ------------------------------------------------ Lección 10: Geometry Nodes

def gn_greebles(kit):
    """Árbol «Forja Greebles»: reparte piezas del kit sobre las caras que miran hacia arriba."""
    ng = bpy.data.node_groups.new("Forja Greebles", "GeometryNodeTree")
    it = ng.interface
    it.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    s_den = it.new_socket("Densidad", in_out="INPUT", socket_type="NodeSocketFloat")
    s_den.default_value = 30.0
    s_dist = it.new_socket("Distancia mínima", in_out="INPUT", socket_type="NodeSocketFloat")
    s_dist.default_value = 0.15
    s_seed = it.new_socket("Semilla", in_out="INPUT", socket_type="NodeSocketInt")
    s_seed.default_value = 0
    s_up = it.new_socket("Solo hacia arriba", in_out="INPUT", socket_type="NodeSocketFloat")
    s_up.default_value = 0.9
    it.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    normal = N.new("GeometryNodeInputNormal")
    sep = N.new("ShaderNodeSeparateXYZ")
    cmp = N.new("FunctionNodeCompare")
    cmp.data_type, cmp.operation = "FLOAT", "GREATER_THAN"
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    col = N.new("GeometryNodeCollectionInfo")
    col.inputs["Collection"].default_value = kit
    col.inputs["Separate Children"].default_value = True
    col.inputs["Reset Children"].default_value = True
    rnd_i = N.new("FunctionNodeRandomValue")
    rnd_i.data_type = "INT"
    rnd_s = N.new("FunctionNodeRandomValue")
    rnd_s.data_type = "FLOAT"
    inst = N.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True
    join = N.new("GeometryNodeJoinGeometry")
    L.new(normal.outputs["Normal"], sep.inputs[0])
    L.new(sep.outputs["Z"], activos(cmp)[0])
    L.new(gi.outputs["Solo hacia arriba"], activos(cmp)[1])
    L.new(gi.outputs[0], dist.inputs["Mesh"])
    L.new(cmp.outputs["Result"], dist.inputs["Selection"])
    L.new(gi.outputs["Distancia mínima"], dist.inputs["Distance Min"])
    L.new(gi.outputs["Densidad"], dist.inputs["Density Max"])
    L.new(gi.outputs["Semilla"], dist.inputs["Seed"])
    ri = activos(rnd_i)
    ri[0].default_value, ri[1].default_value = 0, len(kit.objects) - 1
    L.new(gi.outputs["Semilla"], ri[-1])
    rs = activos(rnd_s)
    rs[0].default_value, rs[1].default_value = 0.7, 1.3
    L.new(gi.outputs["Semilla"], rs[-1])
    L.new(dist.outputs["Points"], inst.inputs["Points"])
    L.new(col.outputs[0], inst.inputs["Instance"])
    L.new(salidas(rnd_i)[0], inst.inputs["Instance Index"])
    L.new(dist.outputs["Rotation"], inst.inputs["Rotation"])
    L.new(salidas(rnd_s)[0], inst.inputs["Scale"])
    L.new(gi.outputs[0], join.inputs[0])
    L.new(inst.outputs["Instances"], join.inputs[0])
    L.new(join.outputs[0], go.inputs[0])
    for i, n in enumerate((gi, normal, sep, cmp, dist, col, rnd_i, rnd_s, inst, join, go)):
        n.location = (i * 180 - 900, (i % 3) * -160)
    return ng


def gn_remaches(pieza, cantidad=40):
    """Árbol «Forja Remaches»: copia una pieza a lo largo de una curva, a intervalos iguales."""
    ng = bpy.data.node_groups.new("Forja Remaches", "GeometryNodeTree")
    it = ng.interface
    it.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    s = it.new_socket("Cantidad", in_out="INPUT", socket_type="NodeSocketInt")
    s.default_value = cantidad
    it.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    res = N.new("GeometryNodeResampleCurve")
    obj = N.new("GeometryNodeObjectInfo")
    obj.inputs["Object"].default_value = pieza
    inst = N.new("GeometryNodeInstanceOnPoints")
    real = N.new("GeometryNodeRealizeInstances")
    L.new(gi.outputs[0], res.inputs["Curve"])
    L.new(gi.outputs["Cantidad"], res.inputs["Count"])
    L.new(res.outputs[0], inst.inputs["Points"])
    L.new(obj.outputs["Geometry"], inst.inputs["Instance"])
    L.new(inst.outputs[0], real.inputs[0])
    L.new(real.outputs[0], go.inputs[0])
    return ng


def gn_tuberia(abrazadera, radio=0.03, cada=8):
    """Árbol «Forja Tubería»: convierte una curva en tubo y pone abrazaderas orientadas a lo largo."""
    ng = bpy.data.node_groups.new("Forja Tuberia", "GeometryNodeTree")
    it = ng.interface
    it.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    s = it.new_socket("Radio", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = radio
    s = it.new_socket("Abrazaderas", in_out="INPUT", socket_type="NodeSocketInt")
    s.default_value = cada
    it.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    circ = N.new("GeometryNodeCurvePrimitiveCircle")
    circ.inputs["Resolution"].default_value = 16
    c2m = N.new("GeometryNodeCurveToMesh")
    c2m.inputs["Fill Caps"].default_value = True
    smooth = N.new("GeometryNodeSetShadeSmooth")
    res = N.new("GeometryNodeResampleCurve")
    tan = N.new("GeometryNodeInputTangent")
    align = N.new("FunctionNodeAlignEulerToVector")
    align.axis = "X"
    obj = N.new("GeometryNodeObjectInfo")
    obj.inputs["Object"].default_value = abrazadera
    inst = N.new("GeometryNodeInstanceOnPoints")
    mat = N.new("GeometryNodeSetMaterial")
    mat.inputs["Material"].default_value = bpy.data.materials.get("Metal oscuro")
    join = N.new("GeometryNodeJoinGeometry")
    real = N.new("GeometryNodeRealizeInstances")
    L.new(gi.outputs["Radio"], circ.inputs["Radius"])
    L.new(gi.outputs[0], c2m.inputs["Curve"])
    L.new(circ.outputs["Curve"], c2m.inputs["Profile Curve"])
    L.new(c2m.outputs[0], smooth.inputs[0])
    L.new(smooth.outputs[0], mat.inputs[0])
    L.new(gi.outputs[0], res.inputs["Curve"])
    L.new(gi.outputs["Abrazaderas"], res.inputs["Count"])
    L.new(tan.outputs[0], align.inputs["Vector"])
    L.new(res.outputs[0], inst.inputs["Points"])
    L.new(obj.outputs["Geometry"], inst.inputs["Instance"])
    L.new(align.outputs[0], inst.inputs["Rotation"])
    L.new(mat.outputs[0], join.inputs[0])
    L.new(inst.outputs[0], join.inputs[0])
    L.new(join.outputs[0], real.inputs[0])
    L.new(real.outputs[0], go.inputs[0])
    return ng


def set_input(mod, nombre, valor):
    for item in mod.node_group.interface.items_tree:
        if getattr(item, "in_out", None) == "INPUT" and item.name == nombre:
            mod[item.identifier] = valor


def kit_collection(M, K):
    """Colección oculta con las piezas que repartirán los Geometry Nodes."""
    kit = bpy.data.collections.new("Kit Greebles")
    bpy.context.scene.collection.children.link(kit)
    piezas = [fb.piece_connector(M, K), fb.piece_heatsink(M, K)]
    objs = []
    for i, parts in enumerate(piezas):
        # cada pieza del kit se une en un solo objeto, en el origen
        for p in parts:
            p.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        with bpy.context.temp_override(selected_editable_objects=parts, active_object=parts[0], object=parts[0]):
            for p in parts:
                for m in list(p.modifiers):
                    with bpy.context.temp_override(object=p, active_object=p):
                        bpy.ops.object.modifier_apply(modifier=m.name)
            bpy.ops.object.join()
        o = parts[0]
        o.scale = (0.42, 0.42, 0.42) if i == 1 else (1, 1, 1)
        objs.append(o)
    b = bmesh.new()
    bmesh.ops.create_cube(b, size=1.0)
    bmesh.ops.scale(b, vec=(0.12, 0.08, 0.05), verts=b.verts)
    bmesh.ops.translate(b, verts=b.verts, vec=(0, 0, 0.025))
    objs.append(fb.bevel_mod(fb.obj_from_bm("Caja_greeble", b, M["dark"]), 0.004))
    objs.append(fb.bolt("Tornillo_greeble", 0, 0, M, z=0))
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        kit.objects.link(o)
        o.location = (0, 0, 0)
    bpy.context.view_layer.layer_collection.children[kit.name].exclude = True
    return kit


def placa_gn(M):
    p = fb.plate_base(M)
    p.data.materials[0] = M["armor"]
    fb.bevel_mod(p, 0.006)
    return p


def lesson10():
    def scene():
        fb.reset()
        M = fb.MATS()
        K = fb.kit_mats()
        fb.workbench()
        fb.camera((1.45, -2.35, 2.25), (0.02, -0.05, 0.08), 40)
        return M, K
    for nm, seed, dens in (("semilla_a", 0, 30), ("semilla_b", 7, 30), ("semilla_c", 42, 30), ("densidad", 3, 90)):
        M, K = scene()
        kit = kit_collection(M, K)
        p = placa_gn(M)
        mod = p.modifiers.new("Greebles", "NODES")
        mod.node_group = gn_greebles(kit)
        set_input(mod, "Semilla", seed)
        set_input(mod, "Densidad", float(dens))
        set_input(mod, "Distancia mínima", 0.15 if dens < 50 else 0.1)
        fb.render(f"l10_{nm}")
        if nm == "semilla_a":
            fb.export_glb("gn_greebles", fb.mesh_copies([p]))
    # remaches por una curva + tubería con abrazaderas
    M, K = scene()
    p = placa_gn(M)
    tor = fb.bolt("Remache", 0, 0, M, z=0)
    tor.scale = (0.7, 0.7, 0.7)
    tor.location = (0, 0, -5)
    cu = bpy.data.curves.new("Linea_remaches", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    pts = fb.offset_poly([(x, y) for x, y in fb.chamfer_rect(-1.0, 1.0, -0.65, 0.65, 0.3)], 0.05)
    sp.points.add(len(pts) - 1)
    for pt, (x, y) in zip(sp.points, pts):
        pt.co = (x, y, 0.16, 1)
    sp.use_cyclic_u = True
    rem = bpy.data.objects.new("Remaches", cu)
    bpy.context.scene.collection.objects.link(rem)
    mod = rem.modifiers.new("Remaches", "NODES")
    mod.node_group = gn_remaches(tor, 44)
    abr = fb.cbox("Abrazadera", (0.04, 0.09, 0.09), (0, 0, -5), M["dark"], 0.01)
    abr.location = (0, 0, 0)
    abr.hide_render = True
    abr.hide_set(True)
    cu2 = bpy.data.curves.new("Tuberia", "CURVE")
    cu2.dimensions = "3D"
    sp2 = cu2.splines.new("BEZIER")
    tub = [(-0.75, 0.32, 0.23), (-0.2, 0.32, 0.23), (0.15, 0.1, 0.23), (0.75, 0.1, 0.23)]
    sp2.bezier_points.add(len(tub) - 1)
    for bp, co in zip(sp2.bezier_points, tub):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    tubo = bpy.data.objects.new("Tuberia", cu2)
    bpy.context.scene.collection.objects.link(tubo)
    mod2 = tubo.modifiers.new("Tuberia", "NODES")
    mod2.node_group = gn_tuberia(abr, 0.03, 7)
    tubo.data.materials.append(K["cobre"])
    tor.hide_render = True
    tor.hide_set(True)
    fb.render("l10_remaches_tuberia")
    fb.export_glb("gn_remaches", fb.mesh_copies([p, rem, tubo]))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "geometry_nodes.blend"))


def lesson10_eevee():
    fb.reset()
    M = fb.MATS()
    K = fb.kit_mats()
    fb.studio(M)
    fb.eevee()
    kit = kit_collection(M, K)
    p = placa_gn(M)
    mod = p.modifiers.new("Greebles", "NODES")
    mod.node_group = gn_greebles(kit)
    set_input(mod, "Semilla", 7)
    set_input(mod, "Densidad", 45.0)
    piv = bpy.data.objects.new("Soporte", None)
    bpy.context.scene.collection.objects.link(piv)
    p.parent = piv
    piv.rotation_euler = (math.radians(55), 0, math.radians(-15))
    piv.location = (0, 0, 0.62)
    fb.camera((1.3, -5.0, 1.8), (0.1, 0, 0.62), 50)
    fb.render("l10_eevee", 1600, 900)


# ------------------------------------------------------ Lección 11: Decals

COLS, FILAS = 4, 3
GRAFITO = (0.07, 0.075, 0.085)
BLANCO, AMARILLO, NEGRO, ROJO, CIAN = (0.95, 0.95, 0.95), (1.0, 0.72, 0.04), (0.02, 0.02, 0.02), (0.85, 0.06, 0.05), (0.2, 0.7, 1.0)


def _flat(name, bm, color):
    o = fb.obj_from_bm(name, bm)
    o.color = (*color, 1)
    return o


def _texto(txt, cx, cy, color, ancho=0.85, alto=0.5):
    cu = bpy.data.curves.new("T", "FONT")
    cu.body = txt
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.extrude = 0
    o = bpy.data.objects.new("T", cu)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.update()
    d = o.dimensions
    s = min(ancho / max(d.x, 1e-4), alto / max(d.y, 1e-4))
    o.scale = (s, s, s)
    o.location = (cx, cy, 0)
    o.color = (*color, 1)
    return o


def _rect(cx, cy, w, h, color, rot=0.0):
    b = bmesh.new()
    bmesh.ops.create_grid(b, x_segments=1, y_segments=1, size=0.5)
    bmesh.ops.scale(b, vec=(w, h, 1), verts=b.verts)
    bmesh.ops.rotate(b, verts=b.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(rot, 3, "Z"))
    bmesh.ops.translate(b, verts=b.verts, vec=(cx, cy, 0))
    return _flat("R", b, color)


def _poly(pts, color, z=0.0):
    b = bmesh.new()
    b.faces.new([b.verts.new((x, y, z)) for x, y in pts])
    return _flat("P", b, color)


def _anillo(cx, cy, r1, r2, color, lados=64):
    b = bmesh.new()
    vo = [b.verts.new((cx + r2 * math.cos(2 * math.pi * i / lados), cy + r2 * math.sin(2 * math.pi * i / lados), 0)) for i in range(lados)]
    vi = [b.verts.new((cx + r1 * math.cos(2 * math.pi * i / lados), cy + r1 * math.sin(2 * math.pi * i / lados), 0)) for i in range(lados)]
    for i in range(lados):
        j = (i + 1) % lados
        b.faces.new((vo[i], vo[j], vi[j], vi[i]))
    return _flat("A", b, color)


def recortar(poly, x0, x1, y0, y1):
    """Recorta un polígono a un rectángulo (Sutherland-Hodgman)."""
    def corta(pts, dentro, cruce):
        out = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            if dentro(p):
                if not dentro(q):
                    out.append(cruce(q, p))
                out.append(p)
            elif dentro(q):
                out.append(cruce(q, p))
        return out

    def en_x(xc):
        return lambda a, b: (xc, a[1] + (b[1] - a[1]) * (xc - a[0]) / (b[0] - a[0]))

    def en_y(yc):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (yc - a[1]) / (b[1] - a[1]), yc)
    for dentro, cruce in ((lambda p: p[0] >= x0, en_x(x0)), (lambda p: p[0] <= x1, en_x(x1)),
                          (lambda p: p[1] >= y0, en_y(y0)), (lambda p: p[1] <= y1, en_y(y1))):
        poly = corta(poly, dentro, cruce)
        if not poly:
            break
    return poly


def celda(c, r):
    return c + 0.5, -(r + 0.5)


def decal_atlas():
    """Renderiza la hoja de decals (PNG con transparencia) en una cuadrícula de 4×3."""
    fb.reset()
    s = bpy.context.scene
    s.render.engine = "BLENDER_WORKBENCH"
    sh = s.display.shading
    sh.light, sh.color_type = "FLAT", "OBJECT"
    sh.show_cavity = sh.show_specular_highlight = False
    s.display.render_aa = "16"
    s.render.film_transparent = True
    s.view_settings.view_transform = "Standard"
    x, y = celda(0, 0)
    _texto("FM-09", x, y, GRAFITO, 0.86, 0.42)
    x, y = celda(1, 0)
    _texto("NO STEP", x, y + 0.06, GRAFITO, 0.84, 0.22)
    _rect(x, y - 0.18, 0.84, 0.05, GRAFITO)
    # franjas de peligro: amarillo con bandas negras, recortadas a un cuadrado
    x, y = celda(2, 0)
    _rect(x, y, 0.84, 0.84, AMARILLO)
    for k in range(-5, 5):
        d = k * 0.2
        banda = [(x + d - 0.42, y - 0.42), (x + d - 0.32, y - 0.42), (x + d + 0.52, y + 0.42), (x + d + 0.42, y + 0.42)]
        recorte = recortar(banda, x - 0.42, x + 0.42, y - 0.42, y + 0.42)
        if len(recorte) >= 3:
            _poly(recorte, NEGRO, 0.001)
    x, y = celda(3, 0)
    _poly([(x - 0.4, y + 0.08), (x + 0.1, y + 0.08), (x + 0.1, y + 0.25), (x + 0.42, y), (x + 0.1, y - 0.25),
           (x + 0.1, y - 0.08), (x - 0.4, y - 0.08)], GRAFITO)
    x, y = celda(0, 1)
    _texto("03", x, y, GRAFITO, 0.8, 0.7)
    x, y = celda(1, 1)
    _rect(x, y, 0.86, 0.34, ROJO)
    _texto("PELIGRO", x, y, BLANCO, 0.74, 0.2).location.z = 0.002
    x, y = celda(2, 1)
    _anillo(x, y, 0.33, 0.4, BLANCO)
    _anillo(x, y, 0.17, 0.22, BLANCO)
    _rect(x, y, 0.06, 0.06, BLANCO)
    for a in range(4):
        _rect(x + 0.3 * math.cos(a * math.pi / 2), y + 0.3 * math.sin(a * math.pi / 2), 0.2 if a % 2 == 0 else 0.03, 0.03 if a % 2 == 0 else 0.2, BLANCO)
    x, y = celda(3, 1)
    for k, dy in enumerate((0.22, 0.0, -0.22)):
        _poly([(x - 0.38, y + dy + 0.12), (x, y + dy - 0.04), (x + 0.38, y + dy + 0.12), (x + 0.38, y + dy + 0.02),
               (x, y + dy - 0.14), (x - 0.38, y + dy + 0.02)], AMARILLO if k == 1 else BLANCO)
    x, y = celda(0, 2)
    _texto("UNIT-01", x, y, CIAN, 0.86, 0.24)
    x, y = celda(1, 2)
    import random
    rnd = random.Random(3)
    px = x - 0.4
    while px < x + 0.38:
        w = rnd.choice((0.015, 0.03, 0.045))
        _rect(px + w / 2, y + 0.04, w, 0.42, GRAFITO)
        px += w + rnd.choice((0.015, 0.03))
    _texto("00319-A", x, y - 0.3, GRAFITO, 0.6, 0.1)
    x, y = celda(2, 2)
    tri = [(x, y + 0.38), (x + 0.42, y - 0.34), (x - 0.42, y - 0.34)]
    _poly(tri, AMARILLO)
    _poly([(x, y + 0.24), (x + 0.3, y - 0.27), (x - 0.3, y - 0.27)], NEGRO, 0.001)
    _texto("!", x, y - 0.08, AMARILLO, 0.2, 0.32).location.z = 0.002
    x, y = celda(3, 2)
    _texto("FORJA//MECHA", x, y, GRAFITO, 0.9, 0.14)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    s.collection.objects.link(cam)
    s.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = COLS
    cam.location = (COLS / 2, -FILAS / 2, 5)
    s.render.resolution_x, s.render.resolution_y = 512 * COLS, 512 * FILAS
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    ruta = os.path.join(DESC, "forja_decals.png")
    s.render.filepath = ruta
    bpy.ops.render.render(write_still=True)
    # copia ligera para mostrar en la web
    s.render.resolution_percentage = 50
    s.render.image_settings.file_format = "WEBP"
    s.render.filepath = os.path.join(IMG, "l11_atlas.webp")
    bpy.ops.render.render(write_still=True)
    return ruta


def decal_material(ruta):
    m = bpy.data.materials.new("Decal")
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bsdf = N["Principled BSDF"]
    tex = N.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(ruta, check_existing=True)
    tex.extension = "CLIP"
    L.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    L.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.45
    return m


def decal(nombre, celda_cr, ancho, centro, normal, objetivo, mat, giro=0.0):
    """Plano con UV en una celda de la hoja, orientado a la superficie y pegado con Shrinkwrap."""
    c, r = celda_cr
    alto = ancho
    b = bmesh.new()
    b.loops.layers.uv.new("UVMap")
    bmesh.ops.create_grid(b, x_segments=6, y_segments=6, size=0.5, calc_uvs=True)
    uv = b.loops.layers.uv.active
    for f in b.faces:
        for lp in f.loops:
            u, v = lp[uv].uv
            lp[uv].uv = ((c + u) / COLS, (FILAS - 1 - r + v) / FILAS)
    bmesh.ops.scale(b, vec=(ancho, alto, 1), verts=b.verts)
    o = fb.obj_from_bm(nombre, b, mat)
    rot = Vector((0, 0, 1)).rotation_difference(Vector(normal).normalized()).to_matrix().to_4x4()
    o.matrix_world = Matrix.Translation(centro) @ rot @ Matrix.Rotation(giro, 4, "Z")
    sw = o.modifiers.new("Pegar", "SHRINKWRAP")
    sw.target = objetivo
    sw.wrap_method = "NEAREST_SURFACEPOINT"
    sw.offset = 0.0015
    o.visible_shadow = False
    return o


def android_con_decals(M, A, ruta, con=True):
    objs = fb.build_android(M, A, 3)
    if not con:
        return objs, []
    byname = {o.name: o for o in objs}
    mat = decal_material(ruta)
    up = math.pi / 2
    ds = [
        decal("Decal_FM09", (0, 0), 0.13, (0.11, -0.2, 1.47), (0, -1, 0.07), byname["Pecho"], mat),
        decal("Decal_logo", (3, 2), 0.15, (-0.105, -0.2, 1.47), (0, -1, 0.07), byname["Pecho"], mat),
        decal("Decal_peligro", (2, 0), 0.09, (0.49, -0.16, 1.76), (0, -1, 0), byname["Hombrera_1"], mat),
        decal("Decal_03", (0, 1), 0.1, (-0.49, -0.16, 1.77), (0, -1, 0), byname["Hombrera_-1"], mat),
        decal("Decal_flecha_D", (3, 0), 0.1, (0.17, -0.105, 0.95), (0, -1, 0), byname["Muslo_1"], mat, -up),
        decal("Decal_flecha_I", (3, 0), 0.1, (-0.17, -0.105, 0.95), (0, -1, 0), byname["Muslo_-1"], mat, -up),
        decal("Decal_aviso", (2, 2), 0.08, (-0.17, -0.128, 0.27), (0, -1, 0.1), byname["Espinilla_-1"], mat),
        decal("Decal_barras", (1, 2), 0.09, (0.17, -0.128, 0.27), (0, -1, 0.1), byname["Espinilla_1"], mat),
        decal("Decal_unit", (0, 2), 0.12, (0.0, -0.152, 1.1), (0, -1, 0), byname["Placa_pelvis"], mat),
    ]
    return objs, ds


def lesson11():
    ruta = decal_atlas()
    for con, nm in ((False, "antes"), (True, "despues")):
        fb.reset()
        M = fb.MATS()
        A = fb.android_mats()
        fb.studio(M)
        fb.eevee()
        objs, ds = android_con_decals(M, A, ruta, con)
        fb.camera((0.75, -2.3, 1.75), (0.08, 0, 1.45), 50)
        fb.render(f"l11_{nm}", 1280, 800)
        if con:
            fb.camera((1.5, -5.4, 1.5), (0, 0, 1.1), 50)
            fb.render("l11_eevee", 1600, 1000)
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "decals.blend"))
    # planos de decal visibles (Workbench + malla en azul)
    fb.reset()
    M = fb.MATS()
    A = fb.android_mats()
    fb.workbench()
    objs, ds = android_con_decals(M, A, ruta, True)
    cmat = fb.mat("Cortador", (0.1, 0.6, 1.0))
    for d in ds:
        fb.wire_overlay(d, 0.0012, evaluated=True, material=cmat)
    fb.camera((0.75, -2.3, 1.75), (0.08, 0, 1.45), 50)
    fb.render("l11_planos", 1280, 800)


# ------------------------------------------------ Lección 12: ciclo de caminar

HUESOS = {  # nombre: (cabeza, cola, padre, deforma)
    "raiz": ((0, 0, 0), (0, 0.3, 0), None),
    "cadera": ((0, 0, 1.08), (0, 0, 1.2), "raiz"),
    "torso": ((0, 0, 1.2), (0, 0, 1.75), "cadera"),
}
for _l, _s in (("L", 1), ("R", -1)):
    x = 0.165 * _s
    HUESOS.update({
        f"muslo.{_l}": ((x, 0, 1.08), (x, -0.03, 0.64), "cadera"),
        f"espinilla.{_l}": ((x, -0.03, 0.64), (x, 0, 0.14), f"muslo.{_l}"),
        f"pie.{_l}": ((x, 0, 0.14), (x, -0.16, 0.06), f"espinilla.{_l}"),
        f"pie_ik.{_l}": ((x, 0, 0.14), (x, -0.16, 0.14), "raiz"),
        f"polo.{_l}": ((x, -0.9, 0.64), (x, -1.0, 0.64), "raiz"),
    })


def hueso_de(nombre):
    """Qué hueso mueve cada pieza del androide (por su nombre)."""
    lado = "L" if nombre.endswith("_1") else "R" if nombre.endswith("_-1") else None
    if nombre.startswith(("Pie_", "Tobillo_")):
        return f"pie.{lado}"
    if nombre.startswith(("Espinilla_", "Rodilla_", "Rodillera_", "Luz_espinilla_")):
        return f"espinilla.{lado}"
    if nombre.startswith("Muslo_"):
        return f"muslo.{lado}"
    if nombre.startswith(("Cadera_", "Falda_", "Pelvis", "Placa_pelvis")):
        return "cadera"
    return "torso"


def rig_androide(objs):
    arm_data = bpy.data.armatures.new("Rig")
    arm = bpy.data.objects.new("Rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    arm.show_in_front = True
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    for nombre, (h, t, padre) in HUESOS.items():
        b = eb.new(nombre)
        b.head, b.tail = h, t
        if padre:
            b.parent = eb[padre]
        b.use_deform = False
    for l in "LR":
        eb[f"espinilla.{l}"].use_connect = True
    bpy.ops.object.mode_set(mode="OBJECT")
    for l in "LR":
        pb = arm.pose.bones[f"espinilla.{l}"]
        ik = pb.constraints.new("IK")
        ik.target, ik.subtarget = arm, f"pie_ik.{l}"
        ik.pole_target, ik.pole_subtarget = arm, f"polo.{l}"
        ik.pole_angle = math.radians(-90)
        ik.chain_count = 2
        cr = arm.pose.bones[f"pie.{l}"].constraints.new("COPY_ROTATION")
        cr.target, cr.subtarget = arm, f"pie_ik.{l}"
    bpy.context.view_layer.update()
    # emparentar cada pieza suelta con su hueso, conservando su posición
    for o in objs:
        if o.parent is not None:
            continue
        mw = o.matrix_world.copy()
        o.parent = arm
        o.parent_type = "BONE"
        o.parent_bone = hueso_de(o.name)
        bpy.context.view_layer.update()
        o.matrix_world = mw
    for o in bpy.data.objects:  # pivotes (Empties) de brazos, cabeza y disipadores
        if o.type == "EMPTY" and o.parent is None:
            mw = o.matrix_world.copy()
            o.parent, o.parent_type, o.parent_bone = arm, "BONE", "torso"
            bpy.context.view_layer.update()
            o.matrix_world = mw
    return arm


def animar_caminar(arm):
    """Ciclo de 24 fotogramas: contacto, bajada, paso y subida, en cada pierna."""
    s = bpy.context.scene
    s.frame_start, s.frame_end = 1, 24
    zancada, alto = 0.26, 0.13
    # (fotograma, y del pie, z del pie) para la pierna izquierda; la derecha va 12 fotogramas desfasada
    claves = [(1, -zancada, 0), (4, -zancada * 0.5, 0), (7, 0, 0), (10, zancada * 0.5, 0), (13, zancada, 0),
              (16, zancada * 0.45, alto * 0.8), (19, 0, alto), (22, -zancada * 0.6, alto * 0.5), (25, -zancada, 0)]
    for l, desfase in (("L", 0), ("R", 12)):
        pb = arm.pose.bones[f"pie_ik.{l}"]
        for f, y, z in claves:
            fr = (f - 1 + desfase) % 24 + 1
            pb.location = (0, -y, z)  # el hueso apunta a -Y del mundo: su Y local es «adelante» y su Z, «arriba»
            pb.keyframe_insert("location", frame=fr)
            if fr == 1:
                pb.keyframe_insert("location", frame=25)
    cad = arm.pose.bones["cadera"]
    for f, dz in ((1, 0), (4, -0.035), (7, 0), (10, 0.02), (13, 0), (16, -0.035), (19, 0), (22, 0.02), (25, 0)):
        cad.location = (0, dz, 0)  # el hueso de la cadera apunta hacia arriba: su Y local es la Z del mundo
        cad.keyframe_insert("location", frame=f)
    tor = arm.pose.bones["torso"]
    tor.rotation_mode = "XYZ"
    for f, rz in ((1, 4), (13, -4), (25, 4)):
        tor.rotation_euler = (0, math.radians(rz), 0)
        tor.keyframe_insert("rotation_euler", frame=f)
    for s_, nombre in ((1, "Hombro_1"), (-1, "Hombro_-1")):
        e = bpy.data.objects[nombre]
        e.rotation_mode = "XYZ"
        base = e.rotation_euler.copy()
        for f, ang in ((1, 18), (13, -18), (25, 18)):
            e.rotation_euler = (base.x + math.radians(ang * s_), base.y, base.z)
            e.keyframe_insert("rotation_euler", frame=f)
    for ob in [arm] + [bpy.data.objects["Hombro_1"], bpy.data.objects["Hombro_-1"]]:
        for fc in ob.animation_data.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = "BEZIER"
            fc.modifiers.new("CYCLES")


def tira(nombres, salida, w, h):
    """Une varios renders en una sola imagen horizontal (la tira que anima la web)."""
    import numpy as np
    total = np.zeros((h, w * len(nombres), 4), dtype=np.float32)
    for i, ruta in enumerate(nombres):
        img = bpy.data.images.load(ruta)
        px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
        total[:, i * w:(i + 1) * w] = px
        bpy.data.images.remove(img)
    out = bpy.data.images.new("tira", w * len(nombres), h, alpha=True)
    out.pixels.foreach_set(total.ravel())
    out.filepath_raw = salida
    out.file_format = "WEBP"
    out.save()


def lesson12():
    fb.reset()
    M = fb.MATS()
    A = fb.android_mats()
    fb.workbench()
    objs = fb.build_android(M, A, 3)
    arm = rig_androide(objs)
    animar_caminar(arm)
    s = bpy.context.scene
    # vista lateral: la mejor para leer un ciclo de caminar
    fb.camera((5.0, -0.2, 1.05), (0, -0.2, 1.0), 50)
    s.camera.data.type = "ORTHO"
    s.camera.data.ortho_scale = 2.6
    w, h = 300, 420
    rutas = []
    tmp = os.environ.get("TEMP", "/tmp")
    for i, f in enumerate(range(1, 25, 3)):
        s.frame_set(f)
        s.render.resolution_x, s.render.resolution_y = w, h
        s.render.image_settings.file_format = "PNG"
        s.render.filepath = os.path.join(tmp, f"caminar_{i:02d}.png")
        bpy.ops.render.render(write_still=True)
        rutas.append(s.render.filepath)
    tira(rutas, os.path.join(IMG, "l12_tira.webp"), w, h)
    # las 4 poses clave de la pierna izquierda
    s.camera.data.ortho_scale = 2.4
    for f, nm in ((1, "contacto"), (4, "bajada"), (7, "paso"), (10, "subida")):
        s.frame_set(f)
        fb.render(f"l12_{nm}", 520, 640)
    # el rig a la vista: huesos encima de la malla
    s.frame_set(1)
    arm.data.display_type = "OCTAHEDRAL"
    fb.camera((2.2, -3.4, 1.4), (0, 0, 1.0), 40)
    s.camera.data.type = "PERSP"
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "androide_caminar.blend"))


def lesson12_rig_img():
    """Imagen del esqueleto: huesos como varillas de colores sobre el androide en rayos X."""
    fb.reset()
    M = fb.MATS()
    A = fb.android_mats()
    fb.workbench()
    objs = fb.build_android(M, A, 3)
    arm = rig_androide(objs)
    bpy.context.view_layer.update()
    cian = fb.mat("Hueso", (0.1, 0.7, 1.0))
    amarillo = fb.mat("Control", (1.0, 0.75, 0.1))
    for pb in arm.pose.bones:
        h = arm.matrix_world @ pb.head
        t = arm.matrix_world @ pb.tail
        d = t - h
        b = bmesh.new()
        bmesh.ops.create_cone(b, cap_ends=True, segments=8, radius1=0.025, radius2=0.008, depth=d.length)
        bmesh.ops.translate(b, verts=b.verts, vec=(0, 0, d.length / 2))
        control = pb.name.startswith(("pie_ik", "polo", "raiz"))
        o = fb.obj_from_bm("Hueso_" + pb.name, b, amarillo if control else cian)
        o.matrix_world = Matrix.Translation(h) @ Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        o.show_in_front = True
    for o in objs:
        if o.type == "MESH" and not o.name.startswith("Hueso_"):
            o.color = (0.6, 0.6, 0.6, 0.25)
    sh = bpy.context.scene.display.shading
    sh.show_xray = True
    sh.xray_alpha = 0.6
    fb.camera((2.2, -3.4, 1.4), (0, -0.3, 0.9), 38)
    fb.render("l12_rig", 900, 1000)


def lesson12_eevee():
    fb.reset()
    M = fb.MATS()
    A = fb.android_mats()
    fb.studio(M)
    fb.eevee()
    objs = fb.build_android(M, A, 3)
    arm = rig_androide(objs)
    animar_caminar(arm)
    bpy.context.scene.frame_set(4)
    fb.camera((2.6, -4.6, 1.4), (0, -0.1, 1.0), 50)
    fb.render("l12_eevee", 1600, 1000)


# ----------------------------------------------------- Lección 13: dron mecha

def torno(bm, perfil, segs=32, centro=(0, 0, 0), mat=0):
    """Gira un perfil (radio, z) alrededor de Z: anillos, conductos, bujes. Como el modificador Screw."""
    cx, cy, cz = centro
    anillos = [[bm.verts.new((cx + r * math.cos(2 * math.pi * i / segs), cy + r * math.sin(2 * math.pi * i / segs), cz + z))
                for i in range(segs)] for r, z in perfil]
    n = len(perfil)
    for k in range(n):
        a, b = anillos[k], anillos[(k + 1) % n]
        for i in range(segs):
            j = (i + 1) % segs
            f = bm.faces.new((a[i], a[j], b[j], b[i]))
            f.material_index = mat
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def caja(bm, centro, medidas, rot=None, mat=0):
    m = Matrix.Translation(centro) @ (rot or Matrix.Identity(4)) @ Matrix.Diagonal((*medidas, 1))
    antes = set(bm.faces)
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    for f in set(bm.faces) - antes:
        f.material_index = mat


def dron_mats():
    A = fb.android_mats()
    return {**A, "rojo": fb.mat("Ojo rojo", (0.8, 0.05, 0.05), 0, 0.2, (1.0, 0.05, 0.03), 14)}


ROTORES = [(sx * 0.78, sy * 0.58) for sx in (-1, 1) for sy in (-1, 1)]


def build_drone(M, D, paso):
    """1: blockout · 2: formas · 3: detalle · 4: acabado con bisel y decals."""
    objs = []
    bev = paso >= 4

    def obj(nombre, bm, mats, suave=False, ancho=0.006):
        o = fb.obj_from_bm(nombre, bm, mats[0])
        for m in mats[1:]:
            o.data.materials.append(m)
        if bev:
            fb.bevel_mod(o, ancho)
        elif suave:
            for p in o.data.polygons:
                p.use_smooth = True
        objs.append(o)
        return o

    g = M["armor"]
    if paso == 1:
        b = bmesh.new()
        caja(b, (0, 0, 0), (1.0, 0.7, 0.26))
        obj("Cuerpo", b, [g])
        for i, (x, y) in enumerate(ROTORES):
            b = bmesh.new()
            bmesh.ops.create_cone(b, cap_ends=True, segments=24, radius1=0.3, radius2=0.3, depth=0.1,
                                  matrix=Matrix.Translation((x, y, 0.05)))
            obj(f"Rotor_{i}", b, [g])
            b = bmesh.new()
            caja(b, ((x * 0.55), (y * 0.55), 0.02), (abs(x) * 0.9, 0.08, 0.06),
                 rot=Matrix.Rotation(math.atan2(y, x), 4, "Z"))
            obj(f"Brazo_{i}", b, [g])
        b = bmesh.new()
        bmesh.ops.create_uvsphere(b, u_segments=16, v_segments=8, radius=0.16, matrix=Matrix.Translation((0, -0.3, -0.17)))
        obj("Torreta", b, [g], suave=True)
        for s in (-1, 1):
            b = bmesh.new()
            caja(b, (0.3 * s, -0.15, -0.2), (0.1, 0.55, 0.1))
            obj(f"Arma_{s}", b, [g])
            b = bmesh.new()
            caja(b, (0.3 * s, 0.05, -0.38), (0.05, 0.6, 0.05))
            obj(f"Patin_{s}", b, [g])
        return objs

    blanco, marco, gris = D["blanco"], D["marco"], D["gris"]
    luz_azul = D["azul"] if paso >= 3 else marco
    ojo = D["rojo"] if paso >= 3 else marco
    # cuerpo: prisma achaflanado + meseta superior (Inset + Extrude) + vientre oscuro
    b = fb.prism_bm(fb.chamfer_rect(-0.5, 0.5, -0.35, 0.35, 0.16), -0.1, 0.12)
    t = fb.top_face(b)
    bmesh.ops.inset_individual(b, faces=[t], thickness=0.07, depth=0)
    fb.extrude_move(b, [t], (0, 0, 0.05))
    bmesh.ops.recalc_face_normals(b, faces=b.faces)
    cuerpo = obj("Cuerpo", b, [blanco])
    b = fb.prism_bm(fb.chamfer_rect(-0.42, 0.42, -0.28, 0.28, 0.12), -0.18, -0.1)
    obj("Vientre", b, [marco])
    for i, (x, y) in enumerate(ROTORES):
        ang = math.atan2(y, x)
        L = math.hypot(x, y)
        b = bmesh.new()
        # brazo: viga que se estrecha hacia el rotor
        perfil = [(0.3, -0.05), (L - 0.28, -0.035), (L - 0.28, 0.035), (0.3, 0.05)]
        bm2 = fb.prism_bm([(px, pz) for px, pz in perfil], -0.045, 0.045)
        bmesh.ops.rotate(bm2, verts=bm2.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        bmesh.ops.rotate(bm2, verts=bm2.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(ang, 3, "Z"))
        obj(f"Brazo_{i}", bm2, [gris])
        # conducto del rotor: anillo hueco hecho por torno
        b = bmesh.new()
        torno(b, [(0.3, -0.02), (0.3, 0.12), (0.27, 0.12), (0.25, 0.08), (0.25, -0.02)], 40, (x, y, 0))
        obj(f"Conducto_{i}", b, [blanco], suave=True)
        b = bmesh.new()
        torno(b, [(0.012, -0.0), (0.05, 0.0), (0.05, 0.05), (0.03, 0.07), (0.0, 0.07)], 24, (x, y, 0.0))
        bmesh.ops.remove_doubles(b, verts=b.verts, dist=0.001)
        obj(f"Buje_{i}", b, [marco], suave=True)
        # soportes del motor en cruz
        for k in range(3):
            b = bmesh.new()
            a = math.radians(30 + 120 * k)
            caja(b, (x + 0.15 * math.cos(a), y + 0.15 * math.sin(a), 0.01), (0.2, 0.025, 0.02),
                 rot=Matrix.Rotation(a, 4, "Z"))
            obj(f"Soporte_{i}_{k}", b, [marco])
        if paso >= 3:
            b = bmesh.new()
            for k in range(6):  # aspas: una pieza repetida en círculo (lo que hace «En círculo» del addon)
                a = 2 * math.pi * k / 6 + i
                caja(b, (x + 0.15 * math.cos(a), y + 0.15 * math.sin(a), 0.04), (0.2, 0.055, 0.008),
                     rot=Matrix.Rotation(a, 4, "Z") @ Matrix.Rotation(math.radians(22), 4, "X"))
            obj(f"Aspas_{i}", b, [gris])
            b = bmesh.new()
            bmesh.ops.create_uvsphere(b, u_segments=12, v_segments=6, radius=0.025,
                                      matrix=Matrix.Translation((x * 1.31, y * 1.28, 0.06)))
            obj(f"Luz_nav_{i}", b, [D["rojo"] if x < 0 else D["azul"]], suave=True)
    # torreta con mono-ojo
    b = bmesh.new()
    bmesh.ops.create_uvsphere(b, u_segments=24, v_segments=12, radius=0.16, matrix=Matrix.Translation((0, -0.3, -0.2)))
    obj("Torreta", b, [marco], suave=True)
    b = bmesh.new()
    torno(b, [(0.0, 0.0), (0.075, 0.0), (0.075, 0.03), (0.055, 0.03), (0.055, 0.012), (0.0, 0.012)], 32)
    bmesh.ops.remove_doubles(b, verts=b.verts, dist=0.001)
    bmesh.ops.rotate(b, verts=b.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(b, verts=b.verts, vec=(0, -0.44, -0.2))
    obj("Ojo_marco", b, [gris], suave=True)
    b = bmesh.new()
    bmesh.ops.create_cone(b, cap_ends=True, segments=32, radius1=0.056, radius2=0.056, depth=0.01,
                          matrix=Matrix.Translation((0, -0.464, -0.2)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    obj("Ojo", b, [ojo], suave=True)
    for s in (-1, 1):
        # cañones bajo el cuerpo: perfil de cilindros por torno, tumbados hacia delante
        b = bmesh.new()
        torno(b, [(0.0, -0.3), (0.06, -0.3), (0.06, 0.05), (0.035, 0.08), (0.035, 0.3), (0.045, 0.3),
                  (0.045, 0.36), (0.025, 0.36), (0.025, 0.2), (0.0, 0.2)], 20)
        bmesh.ops.remove_doubles(b, verts=b.verts, dist=0.001)
        bmesh.ops.rotate(b, verts=b.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        bmesh.ops.translate(b, verts=b.verts, vec=(0.3 * s, -0.1, -0.22))
        obj(f"Canon_{s}", b, [gris], suave=True)
        # patines de aterrizaje: dos patas y una barra
        for y in (-0.15, 0.25):
            b = bmesh.new()
            caja(b, (0.3 * s, y, -0.29), (0.035, 0.035, 0.22))
            obj(f"Pata_{s}_{y}", b, [marco])
        b = bmesh.new()
        caja(b, (0.3 * s, 0.05, -0.4), (0.05, 0.75, 0.04))
        obj(f"Patin_{s}", b, [marco])
    if paso >= 3:
        coll = bpy.data.collections.new("Cortadores")
        bpy.context.scene.collection.children.link(coll)

        def cortador(o):
            bpy.context.scene.collection.objects.unlink(o)
            coll.objects.link(o)
            o.display_type, o.hide_render = "WIRE", True
        cortador(fb.ring_wall("Cortador_panel", fb.chamfer_rect(-0.26, 0.26, -0.2, 0.1, 0.07), 0.14, 0.25, 0.014))
        v = fb.prism("Cortador_rejilla", fb.chamfer_rect(-0.22, -0.195, 0.14, 0.205, 0.012), 0.12, 0.25)
        a = v.modifiers.new("Array", "ARRAY")
        a.count, a.use_relative_offset, a.use_constant_offset = 9, False, True
        a.constant_offset_displace = (0.055, 0, 0)
        cortador(v)
        m = cuerpo.modifiers.new("Boolean", "BOOLEAN")
        m.operand_type, m.collection, m.solver = "COLLECTION", coll, "EXACT"
        cuerpo.modifiers.move(len(cuerpo.modifiers) - 1, 0)
        for s in (-1, 1):  # luces en los flancos
            b = bmesh.new()
            for k in range(4):
                caja(b, (0.505 * s, -0.12 + k * 0.08, 0.02), (0.012, 0.045, 0.018))
            obj(f"Luces_{s}", b, [luz_azul])
        b = bmesh.new()
        cil = bmesh.ops.create_cone(b, cap_ends=True, segments=8, radius1=0.008, radius2=0.004, depth=0.3,
                                    matrix=Matrix.Translation((0.32, 0.22, 0.3)))
        obj("Antena", b, [marco], suave=True)
        for k, (x, y) in enumerate(((-0.4, -0.25), (0.4, -0.25), (-0.4, 0.25), (0.4, 0.25))):
            objs.append(fb.bolt(f"Tornillo_{k}", x, y, M, z=0.12))
    if paso >= 4 and os.path.exists(os.path.join(DESC, "forja_decals.png")):
        mat = decal_material(os.path.join(DESC, "forja_decals.png"))
        objs.append(decal("Decal_unit", (0, 2), 0.16, (0.02, -0.26, 0.175), (0, 0, 1), cuerpo, mat))
        objs.append(decal("Decal_peligro", (2, 0), 0.07, (0.3, -0.24, 0.175), (0, 0, 1), cuerpo, mat))
    return objs


def lesson13():
    nombres = {1: "blockout", 2: "formas", 3: "detalle", 4: "final"}
    for paso, nm in nombres.items():
        fb.reset()
        M = fb.MATS()
        D = dron_mats()
        fb.workbench()
        fb.camera((1.9, -2.7, 1.7), (0, 0, -0.08), 35)
        objs = build_drone(M, D, paso)
        fb.render(f"l13_{paso:02d}_{nm}")
        export_objs = [o for o in objs if not o.hide_render and not o.name.startswith("Decal")]
        fb.export_glb(f"dron_{paso:02d}", fb.mesh_copies(export_objs))
        if paso == 4:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLEND, "dron_mecha.blend"))


def lesson13_eevee():
    fb.reset()
    M = fb.MATS()
    D = dron_mats()
    fb.studio(M)
    fb.eevee()
    objs = build_drone(M, D, 4)
    piv = bpy.data.objects.new("Vuelo", None)
    bpy.context.scene.collection.objects.link(piv)
    for o in objs + [o for o in bpy.data.objects if o.name.startswith("Cortador")]:
        if o.parent is None:
            o.parent = piv
    piv.location = (0, 0, 1.15)
    piv.rotation_euler = (math.radians(-8), 0, math.radians(-25))
    fb.camera((1.7, -3.9, 2.35), (0, 0, 1.02), 50)
    fb.render("l13_eevee", 1600, 900)


if MODE == "m13":
    lesson13()
    lesson13_eevee()
if MODE == "m12":
    lesson12()
    lesson12_rig_img()
    lesson12_eevee()
if MODE == "m11":
    lesson11()
if MODE == "m10":
    lesson10()
    lesson10_eevee()
print("FORJA EXTRA OK")
