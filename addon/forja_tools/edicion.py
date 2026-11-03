"""Herramientas de modo edición: hundir/sacar, apoyos para subdivisión, pliegues, círculo perfecto y placas."""
import math
import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty
from mathutils import Matrix, Vector

from . import util


def caras_sel(bm):
    return [f for f in bm.faces if f.select]


def extruir_mover(bm, caras, vec):
    r = bmesh.ops.extrude_face_region(bm, geom=caras)
    nuevas = [g for g in r["geom"] if isinstance(g, bmesh.types.BMFace)]
    verts = [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=verts, vec=vec)
    bmesh.ops.delete(bm, geom=caras, context="FACES")
    return nuevas


class FORJA_OT_hundir(bpy.types.Operator):
    """Inset + Extrude en un paso: el patrón más usado del hard surface.
Profundidad negativa = hundir (huecos, paneles); positiva = sacar (botones, relieves)"""
    bl_idname = "forja.hundir"
    bl_label = "Inset + Extrude"
    bl_options = {"REGISTER", "UNDO"}

    grosor: FloatProperty(name="Margen (Inset)", default=0.03, min=0.0, soft_max=0.5, unit="LENGTH")
    profundidad: FloatProperty(name="Profundidad", default=-0.03, soft_min=-0.5, soft_max=0.5, unit="LENGTH")
    individual: BoolProperty(name="Cada cara por separado", default=False)

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        o = context.edit_object
        bm = bmesh.from_edit_mesh(o.data)
        sel = caras_sel(bm)
        if not sel:
            self.report({"WARNING"}, "Selecciona caras (tecla 3)")
            return {"CANCELLED"}
        grupos = [[f] for f in sel] if self.individual else [sel]
        finales = []
        for g in grupos:
            n = sum((f.normal for f in g), Vector()).normalized()
            if self.grosor > 0:
                if self.individual:
                    bmesh.ops.inset_individual(bm, faces=g, thickness=self.grosor, depth=0, use_even_offset=True)
                else:
                    bmesh.ops.inset_region(bm, faces=g, thickness=self.grosor, depth=0, use_even_offset=True)
            if abs(self.profundidad) > 1e-6:
                g = extruir_mover(bm, g, n * self.profundidad)
            finales += g
        for f in bm.faces:
            f.select = False
        for f in finales:
            f.select = True
        bm.select_flush_mode()
        util.remarcar_si_afilado(o, bm)
        bmesh.update_edit_mesh(o.data)
        return {"FINISHED"}


class FORJA_OT_apoyos(bpy.types.Operator):
    """Support loops en las aristas seleccionadas: dos cortes pegados al borde para que la
Subdivision Surface las deje nítidas (módulo 4)"""
    bl_idname = "forja.apoyos"
    bl_label = "Support loops"
    bl_options = {"REGISTER", "UNDO"}

    distancia: FloatProperty(name="Distancia al borde", default=0.02, min=0.0005, soft_max=0.2, unit="LENGTH")

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        o = context.edit_object
        bm = bmesh.from_edit_mesh(o.data)
        aristas = [e for e in bm.edges if e.select]
        if not aristas:
            self.report({"WARNING"}, "Selecciona aristas (tecla 2)")
            return {"CANCELLED"}
        verts = list({v for e in aristas for v in e.verts})
        # bisel de 2 segmentos con perfil cuadrado = un apoyo a cada lado y la esquina intacta
        bmesh.ops.bevel(bm, geom=aristas + verts, offset=self.distancia, segments=2, profile=1.0,
                        affect="EDGES", clamp_overlap=True)
        util.remarcar_si_afilado(o, bm)
        bmesh.update_edit_mesh(o.data)
        return {"FINISHED"}


class FORJA_OT_pliegue(bpy.types.Operator):
    """Edge crease en las aristas seleccionadas: endurece sin añadir geometría"""
    bl_idname = "forja.pliegue"
    bl_label = "Pliegue (crease)"
    bl_options = {"REGISTER", "UNDO"}

    valor: FloatProperty(name="Pliegue", default=0.9, min=0.0, max=1.0)

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        o = context.edit_object
        bm = bmesh.from_edit_mesh(o.data)
        capa = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
        n = 0
        for e in bm.edges:
            if e.select:
                e[capa] = self.valor
                n += 1
        util.remarcar_si_afilado(o, bm)
        bmesh.update_edit_mesh(o.data)
        self.report({"INFO"}, f"Pliegue {self.valor:.2f} en {n} arista(s)")
        return {"FINISHED"}


class FORJA_OT_circulo(bpy.types.Operator):
    """Convierte los vértices seleccionados en un círculo perfecto (como LoopTools → Circle).
Ideal para agujeros redondos hechos a mano"""
    bl_idname = "forja.circulo"
    bl_label = "Círculo perfecto"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        o = context.edit_object
        bm = bmesh.from_edit_mesh(o.data)
        vs = [v for v in bm.verts if v.select]
        if len(vs) < 3:
            self.report({"WARNING"}, "Selecciona al menos 3 vértices (un bucle)")
            return {"CANCELLED"}
        c = sum((v.co for v in vs), Vector()) / len(vs)
        n = Vector()
        for i, v in enumerate(vs):  # normal del plano medio
            n += (vs[i - 1].co - c).cross(v.co - c)
        if n.length < 1e-9:
            n = vs[0].normal.copy()
        n.normalize()
        if any(v.normal.dot(n) < 0 for v in vs[:1]):
            n = -n
        u = (vs[0].co - c)
        u = (u - n * u.dot(n)).normalized()
        w = n.cross(u)
        r = sum(((v.co - c) - n * (v.co - c).dot(n)).length for v in vs) / len(vs)
        orden = sorted(vs, key=lambda v: math.atan2((v.co - c).dot(w), (v.co - c).dot(u)))
        a0 = math.atan2((orden[0].co - c).dot(w), (orden[0].co - c).dot(u))
        for i, v in enumerate(orden):
            a = a0 + 2 * math.pi * i / len(orden)
            v.co = c + (u * math.cos(a) + w * math.sin(a)) * r
        util.remarcar_si_afilado(o, bm)
        bmesh.update_edit_mesh(o.data)
        return {"FINISHED"}


class FORJA_OT_placa(bpy.types.Operator):
    """Placa de blindaje desde caras: copia las caras seleccionadas como una pieza aparte,
con margen, separación y grosor. La capa extra de los mechas en un clic"""
    bl_idname = "forja.placa"
    bl_label = "Placa desde caras"
    bl_options = {"REGISTER", "UNDO"}

    margen: FloatProperty(name="Margen", default=0.02, min=0.0, soft_max=0.3, unit="LENGTH")
    separacion: FloatProperty(name="Separación", default=0.002, min=0.0, soft_max=0.1, unit="LENGTH")
    grosor: FloatProperty(name="Grosor", default=0.03, min=0.001, soft_max=0.3, unit="LENGTH")

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        o = context.edit_object
        bm = bmesh.from_edit_mesh(o.data)
        sel = caras_sel(bm)
        if not sel:
            self.report({"WARNING"}, "Selecciona las caras que cubrirá la placa")
            return {"CANCELLED"}
        nuevo = bmesh.new()
        mapa = {}
        for f in sel:
            vs = []
            for v in f.verts:
                if v not in mapa:
                    mapa[v] = nuevo.verts.new(v.co)
                vs.append(mapa[v])
            nuevo.faces.new(vs)
        nuevo.normal_update()
        if self.margen > 0:
            bmesh.ops.inset_region(nuevo, faces=list(nuevo.faces), thickness=self.margen, depth=0, use_even_offset=True)
            borde = [f for f in nuevo.faces if any(e.is_boundary for e in f.edges)]
            interiores = [f for f in nuevo.faces if f not in borde]
            if interiores:
                bmesh.ops.delete(nuevo, geom=borde, context="FACES")
        nuevo.normal_update()
        for v in nuevo.verts:
            v.co += v.normal * self.separacion
        p = util.objeto_desde_bm(context, "Placa_forja", nuevo, materiales=list(o.data.materials)[:1],
                                 matriz=o.matrix_world.copy())
        s = p.modifiers.new("Grosor", "SOLIDIFY")
        s.thickness = self.grosor
        s.offset = 1.0
        s.use_even_offset = True
        util.bisel(p, max(0.001, self.grosor * 0.15), 2)
        util.normales_ponderadas(p)
        util.emparentar(p, o)
        self.report({"INFO"}, "Placa creada como objeto aparte (emparentada a la pieza)")
        return {"FINISHED"}


CLASES = (FORJA_OT_hundir, FORJA_OT_apoyos, FORJA_OT_pliegue, FORJA_OT_circulo, FORJA_OT_placa)
