"""Kit de piezas procedurales (como Kit Ops, pero gratis): tornillos, rejillas, LEDs, engranajes,
disipadores, conectores, pistones animables y cables con caída."""
import math
import bmesh
import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty
from mathutils import Matrix, Vector

from . import util


def mats():
    return {
        "metal": util.material("Forja Metal oscuro", (0.06, 0.065, 0.075), 0.7, 0.32),
        "claro": util.material("Forja Metal claro", (0.55, 0.56, 0.6), 0.8, 0.28),
        "luz": util.material("Forja Luz azul", (0.2, 0.6, 1.0), 0, 0.2, (0.1, 0.5, 1.0), 10),
        "rojo": util.material("Forja Luz roja", (0.8, 0.05, 0.05), 0, 0.3, (1.0, 0.05, 0.04), 8),
    }


def tornillo(bm, r):
    util.cilindro(bm, (0, 0, r * 0.2), r, r * 0.4, 16)
    bm.normal_update()
    top = max((f for f in bm.faces if f.normal.z > 0.99), key=lambda f: f.calc_center_median().z)
    bmesh.ops.inset_individual(bm, faces=[top], thickness=r * 0.3, depth=0)
    # hueco hexagonal (Allen): el centro baja
    bmesh.ops.translate(bm, verts=top.verts, vec=(0, 0, -r * 0.25))


def tuerca(bm, r):
    util.cilindro(bm, (0, 0, r * 0.3), r, r * 0.6, 6)
    util.cilindro(bm, (0, 0, r * 0.45), r * 0.45, r * 0.9, 16, mat=1)


def rejilla(bm, r):
    w, h, t = r * 2, r * 1.3, r * 0.12
    for x, y, sx, sy in ((0, h / 2, w, t), (0, -h / 2, w, t), (w / 2, 0, t, h + t), (-w / 2, 0, t, h + t)):
        util.caja(bm, (x, y, t / 2), (sx, sy, t))
    n = 7
    for i in range(n):
        y = -h / 2 + h * (i + 0.5) / n
        util.caja(bm, (0, y, t * 0.5), (w - t, h / n * 0.9, t * 0.18),
                  rot=Matrix.Rotation(math.radians(35), 4, "X"), mat=1)
    util.caja(bm, (0, 0, -t * 0.2), (w, h, t * 0.1), mat=1)


def led(bm, r):
    util.prisma(bm, util.chaflan_rect(-r * 1.4, r * 1.4, -r * 0.6, r * 0.6, r * 0.3), 0, r * 0.25, mat=0)
    util.prisma(bm, util.chaflan_rect(-r * 1.1, r * 1.1, -r * 0.35, r * 0.35, r * 0.2), r * 0.2, r * 0.3, mat=1)


def engranaje(bm, r, dientes=14):
    pts = []
    for i in range(dientes):
        a, s = 2 * math.pi * i / dientes, 2 * math.pi / dientes
        for frac, rr in ((0.0, r * 0.82), (0.18, r), (0.5, r), (0.68, r * 0.82)):
            pts.append((rr * math.cos(a + s * frac), rr * math.sin(a + s * frac)))
    util.prisma(bm, pts, 0, r * 0.25)
    util.cilindro(bm, (0, 0, r * 0.18), r * 0.3, r * 0.36, 16, mat=1)


def disipador(bm, r):
    util.caja(bm, (0, 0, r * 0.05), (r * 2, r * 2, r * 0.1), mat=1)
    n = 9
    for i in range(n):
        x = -r * 0.9 + r * 1.8 * i / (n - 1)
        util.caja(bm, (x, 0, r * 0.4), (r * 0.08, r * 1.9, r * 0.6))


def conector(bm, r):
    util.prisma(bm, util.chaflan_rect(-r, r, -r * 0.6, r * 0.6, r * 0.2), 0, r * 0.6)
    for i in range(4):
        util.caja(bm, (-r * 0.6 + r * 0.4 * i, 0, r * 0.62), (r * 0.22, r * 0.7, r * 0.1), mat=1)


def toma_aire(bm, r):
    util.cilindro(bm, (0, 0, r * 0.15), r, r * 0.3, 32)
    bm.normal_update()
    top = max((f for f in bm.faces if f.normal.z > 0.99), key=lambda f: f.calc_center_median().z)
    bmesh.ops.inset_individual(bm, faces=[top], thickness=r * 0.15, depth=0)
    bmesh.ops.translate(bm, verts=top.verts, vec=(0, 0, -r * 0.25))
    for i in range(8):  # aspas
        util.caja(bm, (0, 0, r * 0.05), (r * 1.6, r * 0.12, r * 0.04),
                  rot=Matrix.Rotation(math.radians(22.5 * i), 4, "Z") @ Matrix.Rotation(math.radians(25), 4, "X"), mat=1)


PIEZAS = {
    "TORNILLO": ("Tornillo", tornillo, ("metal", "claro")),
    "TUERCA": ("Tuerca", tuerca, ("metal", "claro")),
    "REJILLA": ("Rejilla", rejilla, ("claro", "metal")),
    "LED": ("LED", led, ("metal", "luz")),
    "ENGRANAJE": ("Engranaje", engranaje, ("claro", "metal")),
    "DISIPADOR": ("Disipador", disipador, ("claro", "metal")),
    "CONECTOR": ("Conector", conector, ("claro", "metal")),
    "TOMA": ("Toma de aire", toma_aire, ("metal", "claro")),
}


class FORJA_OT_pieza(bpy.types.Operator):
    """Añade una pieza de kitbash en el cursor 3D, orientada a la superficie.
Coloca antes el cursor con Shift + clic derecho (con Orientation: Geometry en el cursor)"""
    bl_idname = "forja.pieza"
    bl_label = "Añadir pieza"
    bl_options = {"REGISTER", "UNDO"}

    tipo: EnumProperty(name="Pieza", items=[(k, v[0], "") for k, v in PIEZAS.items()], default="TORNILLO")
    tamano: FloatProperty(name="Tamaño", default=0.05, min=0.001, soft_max=1.0, unit="LENGTH")

    def execute(self, context):
        nombre, fn, mm = PIEZAS[self.tipo]
        M = mats()
        bm = bmesh.new()
        fn(bm, self.tamano)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        o = util.objeto_desde_bm(context, nombre, bm, [M[k] for k in mm], matriz=util.matriz_cursor(context))
        util.bisel(o, self.tamano * 0.04, 2)
        util.normales_ponderadas(o)
        a = context.active_object
        if a is not None and a.type == "MESH" and a.select_get() and not util.es_cortador(a):
            util.emparentar(o, a)
        util.seleccionar_solo(context, [o], o)
        return {"FINISHED"}


class FORJA_OT_piston(bpy.types.Operator):
    """Pistón que se estira solo (módulo 7): camisa + vástago con Damped Track entre dos anclajes.
Mueve los Empties de los extremos o empareéntalos con las piezas"""
    bl_idname = "forja.piston"
    bl_label = "Pistón animable"
    bl_options = {"REGISTER", "UNDO"}

    largo: FloatProperty(name="Largo", default=0.6, min=0.05, soft_max=5, unit="LENGTH")
    radio: FloatProperty(name="Radio", default=0.04, min=0.002, soft_max=0.5, unit="LENGTH")

    def execute(self, context):
        M = mats()
        base = util.matriz_cursor(context)
        a = bpy.data.objects.new("Piston_anclaje_A", None)
        b = bpy.data.objects.new("Piston_anclaje_B", None)
        for e in (a, b):
            context.collection.objects.link(e)
            e.empty_display_type = "SPHERE"
            e.empty_display_size = self.radio * 1.5
        a.matrix_world = base
        b.matrix_world = base @ Matrix.Translation((0, 0, self.largo))
        partes = []
        for nombre, desde, hacia, largo, r, mt in (("Piston_camisa", a, b, self.largo * 0.6, self.radio, M["metal"]),
                                                    ("Piston_vastago", b, a, self.largo * 0.55, self.radio * 0.55, M["claro"])):
            bm = bmesh.new()
            util.cilindro(bm, (0, 0, largo / 2), r, largo, 16)
            util.cilindro(bm, (0, 0, 0), r * 1.3, r * 0.8, 16, mat=0)
            o = util.objeto_desde_bm(context, nombre, bm, [mt])
            o.parent = desde
            c = o.constraints.new("DAMPED_TRACK")
            c.target = hacia
            c.track_axis = "TRACK_Z"
            util.bisel(o, r * 0.15, 2)
            partes.append(o)
        util.seleccionar_solo(context, [b], b)
        self.report({"INFO"}, "Mueve el anclaje B (seleccionado) y verás el pistón trabajar")
        return {"FINISHED"}


COLORES = [("NARANJA", "Naranja", ""), ("AZUL", "Azul", ""), ("NEGRO", "Negro", ""), ("ROJO", "Rojo", ""),
           ("MIXTO", "Mazo de colores", "")]
RGB = {"NARANJA": (0.85, 0.3, 0.05), "AZUL": (0.05, 0.28, 0.85), "NEGRO": (0.03, 0.03, 0.035), "ROJO": (0.7, 0.04, 0.04)}


class FORJA_OT_cable(bpy.types.Operator):
    """Cable (o mazo de cables) entre los dos objetos seleccionados, con caída por gravedad.
Es una curva: edítala con Tab si quieres cambiar su recorrido"""
    bl_idname = "forja.cable"
    bl_label = "Cable entre objetos"
    bl_options = {"REGISTER", "UNDO"}

    radio: FloatProperty(name="Grosor", default=0.015, min=0.001, soft_max=0.2, unit="LENGTH")
    caida: FloatProperty(name="Caída", default=0.15, min=0.0, soft_max=2.0, unit="LENGTH")
    cantidad: IntProperty(name="Cables", default=3, min=1, max=8)
    color: EnumProperty(name="Color", items=COLORES, default="MIXTO")

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and len(context.selected_objects) == 2

    def execute(self, context):
        a, b = context.selected_objects
        if b == context.active_object:
            a, b = b, a
        pa, pb = a.matrix_world.translation, b.matrix_world.translation
        d = (pb - pa)
        lado = d.cross(Vector((0, 0, 1)))
        lado = lado.normalized() if lado.length > 1e-6 else Vector((1, 0, 0))
        creados = []
        for k in range(self.cantidad):
            off = lado * (k - (self.cantidad - 1) / 2) * self.radio * 2.2
            cu = bpy.data.curves.new("Cable", "CURVE")
            cu.dimensions = "3D"
            cu.bevel_depth = self.radio
            cu.bevel_resolution = 3
            cu.use_fill_caps = True
            sp = cu.splines.new("BEZIER")
            pts = [pa + off, pa + d * 0.33 + off + Vector((0, 0, -self.caida)),
                   pa + d * 0.66 + off + Vector((0, 0, -self.caida)), pb + off]
            sp.bezier_points.add(len(pts) - 1)
            for bp, p in zip(sp.bezier_points, pts):
                bp.co = p
                bp.handle_left_type = bp.handle_right_type = "AUTO"
            nombre = self.color if self.color != "MIXTO" else ["NARANJA", "AZUL", "NEGRO", "ROJO"][k % 4]
            cu.materials.append(util.material(f"Forja Cable {nombre.lower()}", RGB[nombre], 0, 0.45))
            o = bpy.data.objects.new("Cable", cu)
            context.collection.objects.link(o)
            creados.append(o)
        util.seleccionar_solo(context, creados, creados[0])
        return {"FINISHED"}


CLASES = (FORJA_OT_pieza, FORJA_OT_piston, FORJA_OT_cable)
