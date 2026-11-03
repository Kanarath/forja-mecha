"""Simetría y repeticiones: espejo con recorte, Array lineal y Array radial."""
import math
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

from mathutils import Matrix

from . import util

EJES = [("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")]


class FORJA_OT_espejo(bpy.types.Operator):
    """Mirror en un clic. Con un objeto: lo hace simétrico respecto a su origen (corta la mitad sobrante).
Con varios: refleja los seleccionados respecto al activo"""
    bl_idname = "forja.espejo"
    bl_label = "Espejo"
    bl_options = {"REGISTER", "UNDO"}

    eje: EnumProperty(name="Eje", items=EJES, default="X")
    bisectar: BoolProperty(name="Cortar la mitad sobrante", default=True,
                           description="Bisect: elimina lo que cruza el plano del espejo")
    invertir: BoolProperty(name="Conservar el otro lado", default=False)

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and context.active_object and context.active_object.type == "MESH"

    def execute(self, context):
        i = "XYZ".index(self.eje)
        activo = context.active_object
        otros = [o for o in util.mallas_seleccionadas(context, True) if o != activo]
        destino = otros if otros else [activo]
        for o in destino:
            m = o.modifiers.new(f"Forja Espejo {self.eje}", "MIRROR")
            m.use_axis = [k == i for k in range(3)]
            m.use_bisect_axis[i] = self.bisectar
            m.use_bisect_flip_axis[i] = self.invertir
            m.use_clip = True
            m.use_mirror_merge = True
            if otros:
                m.mirror_object = activo
            util.ordenar_modificadores(o)
        return {"FINISHED"}


class FORJA_OT_repetir(bpy.types.Operator):
    """Array lineal: repite la pieza en fila (rejillas, luces, pernos)"""
    bl_idname = "forja.repetir"
    bl_label = "Repetir en fila"
    bl_options = {"REGISTER", "UNDO"}

    eje: EnumProperty(name="Eje", items=EJES, default="X")
    cantidad: IntProperty(name="Cantidad", default=5, min=2, max=200)
    separacion: FloatProperty(name="Separación (× tamaño)", default=1.5, min=0.0, soft_max=5.0,
                              description="1 = pegadas; 2 = hueco igual al tamaño")

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and context.active_object and context.active_object.type == "MESH"

    def execute(self, context):
        i = "XYZ".index(self.eje)
        for o in util.mallas_seleccionadas(context, True):
            m = o.modifiers.new("Forja Fila", "ARRAY")
            m.count = self.cantidad
            m.use_relative_offset = True
            d = [0.0, 0.0, 0.0]
            # copias de un cortador que se tocan confunden al booleano: siempre un hueco mínimo
            d[i] = max(self.separacion, 1.05) if util.es_cortador(o) else self.separacion
            m.relative_offset_displace = d
            util.ordenar_modificadores(o)
        return {"FINISHED"}


class FORJA_OT_radial(bpy.types.Operator):
    """Array radial: copias en círculo alrededor del cursor 3D (dientes, tornillos de una brida, aletas)"""
    bl_idname = "forja.radial"
    bl_label = "Repetir en círculo"
    bl_options = {"REGISTER", "UNDO"}

    eje: EnumProperty(name="Eje", items=EJES, default="Z")
    cantidad: IntProperty(name="Cantidad", default=8, min=2, max=128)

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and context.active_object and context.active_object.type == "MESH"

    def execute(self, context):
        o = context.active_object
        centro = bpy.data.objects.new("Forja_centro_radial", None)
        context.collection.objects.link(centro)
        centro.empty_display_type = "SPHERE"
        centro.empty_display_size = util.tamano(o) * 0.3
        centro.location = context.scene.cursor.location
        rot = [0.0, 0.0, 0.0]
        rot["XYZ".index(self.eje)] = 2 * math.pi / self.cantidad
        centro.rotation_euler = rot
        # el origen del objeto debe estar en el centro del círculo para que gire a su alrededor
        mw = o.matrix_world.copy()
        delta = mw.inverted() @ centro.location
        o.data.transform(Matrix.Translation(-delta))
        o.matrix_world = mw @ Matrix.Translation(delta)
        util.emparentar(centro, o)
        m = o.modifiers.new("Forja Radial", "ARRAY")
        m.count = self.cantidad
        m.use_relative_offset = False
        m.use_object_offset = True
        m.offset_object = centro
        util.ordenar_modificadores(o)
        self.report({"INFO"}, "Gira el Empty «Forja_centro_radial» para cambiar el reparto")
        return {"FINISHED"}


CLASES = (FORJA_OT_espejo, FORJA_OT_repetir, FORJA_OT_radial)
