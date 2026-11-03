"""Acabado: la «receta» hard surface en un clic, ancho de bisel interactivo, Step y orden de modificadores."""
import math
import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty

from . import util


class FORJA_OT_afilar(bpy.types.Operator):
    """Receta hard surface en un clic: aplica escala, Shade Smooth, marca aristas afiladas,
Bevel (Angle + Harden Normals) y Weighted Normal, y ordena los modificadores"""
    bl_idname = "forja.afilar"
    bl_label = "Afilar (receta hard surface)"
    bl_options = {"REGISTER", "UNDO"}

    angulo: FloatProperty(name="Ángulo", default=math.radians(30), min=math.radians(1),
                          max=math.radians(180), subtype="ANGLE",
                          description="Las aristas más dobladas que este ángulo se biselan y quedan duras")
    ancho: FloatProperty(name="Ancho del bisel", default=0.0, min=0.0, soft_max=0.2, unit="LENGTH",
                         description="0 = automático según el tamaño de la pieza")
    segmentos: IntProperty(name="Segmentos", default=3, min=1, max=12)
    aplicar_escala: BoolProperty(name="Aplicar escala", default=True,
                                 description="Evita biseles deformados (Ctrl+A → Scale)")
    normales: BoolProperty(name="Weighted Normal", default=True)
    marcar_afiladas: BoolProperty(name="Marcar afiladas", default=True,
                                  description="Marca como Sharp las aristas que superan el ángulo")

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and any(o.type == "MESH" for o in context.selected_objects)

    def execute(self, context):
        objs = util.mallas_seleccionadas(context)
        for o in objs:
            if self.aplicar_escala:
                util.aplicar_escala(o)
            me = o.data
            for p in me.polygons:
                p.use_smooth = True
            if self.marcar_afiladas:
                bm = bmesh.new()
                bm.from_mesh(me)
                util.marcar_afiladas(bm, self.angulo)
                bm.to_mesh(me)
                bm.free()
            ancho = self.ancho or max(0.002, util.tamano(o) * 0.004)
            util.bisel(o, ancho, self.segmentos, self.angulo)
            if self.normales:
                util.normales_ponderadas(o)
            util.ordenar_modificadores(o)
            me.update()
        self.report({"INFO"}, f"Afilado: {len(objs)} objeto(s)")
        return {"FINISHED"}


class FORJA_OT_ancho_bisel(bpy.types.Operator):
    """Ajusta el ancho del bisel moviendo el ratón. Rueda: segmentos. Clic: aceptar. Clic derecho: cancelar"""
    bl_idname = "forja.ancho_bisel"
    bl_label = "Ancho del bisel (interactivo)"
    bl_options = {"REGISTER", "UNDO", "GRAB_CURSOR", "BLOCKING"}

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return context.mode == "OBJECT" and o is not None and o.type == "MESH"

    def invoke(self, context, event):
        o = context.active_object
        self.mod = next((m for m in o.modifiers if m.type == "BEVEL"), None)
        if self.mod is None:
            bpy.ops.forja.afilar()
            self.mod = next((m for m in o.modifiers if m.type == "BEVEL"), None)
        self.inicio = (self.mod.width, self.mod.segments)
        self.x0 = event.mouse_x
        context.window_manager.modal_handler_add(self)
        self.texto(context)
        return {"RUNNING_MODAL"}

    def texto(self, context):
        context.area.header_text_set(
            f"Ancho: {self.mod.width:.4f} · Segmentos: {self.mod.segments}   "
            "[Ratón] ancho · [Rueda] segmentos · [Clic] aceptar · [Clic dcho/Esc] cancelar")

    def modal(self, context, event):
        if event.type == "MOUSEMOVE":
            factor = 1.0 + (event.mouse_x - self.x0) * 0.004
            self.mod.width = max(0.0001, self.inicio[0] * max(0.02, factor))
        elif event.type == "WHEELUPMOUSE":
            self.mod.segments = min(12, self.mod.segments + 1)
        elif event.type == "WHEELDOWNMOUSE":
            self.mod.segments = max(1, self.mod.segments - 1)
        elif event.type in {"LEFTMOUSE", "RET", "NUMPAD_ENTER"} and event.value == "PRESS":
            context.area.header_text_set(None)
            return {"FINISHED"}
        elif event.type in {"RIGHTMOUSE", "ESC"} and event.value == "PRESS":
            self.mod.width, self.mod.segments = self.inicio
            context.area.header_text_set(None)
            return {"CANCELLED"}
        self.texto(context)
        return {"RUNNING_MODAL"}


class FORJA_OT_escalonar(bpy.types.Operator):
    """Step: aplica el bisel actual a la malla y añade otro más fino encima.
Útil cuando quieres un bisel grande de forma y otro pequeño de brillo"""
    bl_idname = "forja.escalonar"
    bl_label = "Escalonar bisel (Step)"
    bl_options = {"REGISTER", "UNDO"}

    factor: FloatProperty(name="Nuevo ancho (×)", default=0.35, min=0.05, max=1.0)

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return context.mode == "OBJECT" and o and o.type == "MESH" and any(m.type == "BEVEL" for m in o.modifiers)

    def execute(self, context):
        o = context.active_object
        b = next(m for m in o.modifiers if m.type == "BEVEL")
        ancho, seg, ang = b.width, b.segments, b.angle_limit
        # aplicar todo lo que va antes del bisel (incluido) para conservar los cortes
        hasta = list(o.modifiers).index(b)
        with context.temp_override(object=o, active_object=o):
            for m in list(o.modifiers)[: hasta + 1]:
                bpy.ops.object.modifier_apply(modifier=m.name)
        nuevo = util.bisel(o, ancho * self.factor, max(2, seg - 1), ang)
        util.ordenar_modificadores(o)
        self.report({"INFO"}, f"Bisel aplicado; nuevo bisel de {nuevo.width:.4f}")
        return {"FINISHED"}


class FORJA_OT_ordenar(bpy.types.Operator):
    """Ordena la pila: Mirror → Array → Solidify → Boolean → Bevel → Subdivision → Weighted Normal"""
    bl_idname = "forja.ordenar"
    bl_label = "Ordenar modificadores"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = util.mallas_seleccionadas(context, incluir_cortadores=True)
        for o in objs:
            util.ordenar_modificadores(o)
        self.report({"INFO"}, f"Pila ordenada en {len(objs)} objeto(s)")
        return {"FINISHED"}


class FORJA_OT_limpiar_acabado(bpy.types.Operator):
    """Quita el bisel y las normales de Forja (para volver a modelar en limpio)"""
    bl_idname = "forja.limpiar_acabado"
    bl_label = "Quitar acabado"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        for o in util.mallas_seleccionadas(context):
            for m in list(o.modifiers):
                if m.name in ("Forja Bisel", "Forja Normales"):
                    o.modifiers.remove(m)
        return {"FINISHED"}


CLASES = (FORJA_OT_afilar, FORJA_OT_ancho_bisel, FORJA_OT_escalonar, FORJA_OT_ordenar, FORJA_OT_limpiar_acabado)
