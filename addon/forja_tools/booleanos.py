"""Booleanos no destructivos al estilo BoxCutter / Bool Tool, pero sin dibujar: cortadores listos para mover."""
import math
import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from mathutils import Matrix, Vector

from . import util

OPERACIONES = [
    ("DIFFERENCE", "Cortar", "Resta el cortador (agujeros, ranuras, paneles)", "SELECT_SUBTRACT", 0),
    ("UNION", "Unir", "Suma el volumen del cortador", "SELECT_EXTEND", 1),
    ("INTERSECT", "Intersecar", "Deja solo la parte común", "SELECT_INTERSECT", 2),
    ("SLICE", "Rebanar", "Corta y crea una pieza separada con lo cortado", "SELECT_DIFFERENCE", 3),
]


def anadir_booleano(objetivo, cortador, operacion, solver="EXACT"):
    m = objetivo.modifiers.new(f"Forja {cortador.name}", "BOOLEAN")
    m.operation = operacion
    m.object = cortador
    m.solver = solver
    if solver == "EXACT" and any(md.type in {"ARRAY", "MIRROR"} for md in cortador.modifiers):
        # cortadores con copias (Array, Mirror) que podrían solaparse: más robusto, algo más lento
        m.use_self = True

    return m


class FORJA_OT_booleano(bpy.types.Operator):
    """Usa los objetos seleccionados como cortadores sobre el activo (el último que seleccionaste).
No destructivo: puedes mover los cortadores después"""
    bl_idname = "forja.booleano"
    bl_label = "Booleano Forja"
    bl_options = {"REGISTER", "UNDO"}

    operacion: EnumProperty(name="Operación", items=OPERACIONES, default="DIFFERENCE")
    rapido: BoolProperty(name="Solver rápido (Fast)", default=False,
                         description="Más rápido mientras diseñas; Exact es más fiable")

    @classmethod
    def poll(cls, context):
        a = context.active_object
        return (context.mode == "OBJECT" and a is not None and a.type == "MESH"
                and len([o for o in context.selected_objects if o.type == "MESH"]) >= 2)

    def execute(self, context):
        objetivo = context.active_object
        cortadores = [o for o in context.selected_objects if o != objetivo and o.type == "MESH"]
        solver = "FAST" if self.rapido else "EXACT"
        for c in cortadores:
            util.aplicar_escala(c)
            if self.operacion == "SLICE":
                pieza = objetivo.copy()
                pieza.data = objetivo.data.copy()
                pieza.name = objetivo.name + "_rebanada"
                for col in objetivo.users_collection:
                    col.objects.link(pieza)
                anadir_booleano(pieza, c, "INTERSECT", solver)
                util.ordenar_modificadores(pieza)
                anadir_booleano(objetivo, c, "DIFFERENCE", solver)
            else:
                anadir_booleano(objetivo, c, self.operacion, solver)
            util.preparar_cortador(context, c, objetivo)
        util.ordenar_modificadores(objetivo)
        util.seleccionar_solo(context, [objetivo], objetivo)
        self.report({"INFO"}, f"{len(cortadores)} cortador(es) en {objetivo.name}")
        return {"FINISHED"}


def forma_cortador(bm, forma, r, prof):
    """Crea la forma del cortador centrada en el origen, atravesando ±prof en Z."""
    if forma == "CAJA":
        util.caja(bm, (0, 0, 0), (r * 2, r * 2, prof * 2))
    elif forma == "CILINDRO":
        util.cilindro(bm, (0, 0, 0), r, prof * 2, 32)
    elif forma == "HEXAGONO":
        util.cilindro(bm, (0, 0, 0), r, prof * 2, 6)
    elif forma == "RANURA":
        pts = []
        for i in range(13):
            a = math.radians(90 + 15 * i)
            pts.append((-r * 1.6 + r * 0.4 * math.cos(a), r * 0.4 * math.sin(a)))
        for i in range(13):
            a = math.radians(-90 + 15 * i)
            pts.append((r * 1.6 + r * 0.4 * math.cos(a), r * 0.4 * math.sin(a)))
        util.prisma(bm, pts, -prof, prof)
    elif forma == "GUION":
        util.prisma(bm, util.chaflan_rect(-r * 1.5, r * 1.5, -r * 0.35, r * 0.35, r * 0.3), -prof, prof)
    elif forma == "PANEL":
        util.prisma(bm, util.chaflan_rect(-r * 1.4, r * 1.4, -r, r, r * 0.35), -prof, prof)


class FORJA_OT_cortador_nuevo(bpy.types.Operator):
    """Crea un cortador en el cursor 3D y corta el objeto activo al instante.
Truco: Shift + clic derecho sobre la superficie para colocar antes el cursor"""
    bl_idname = "forja.cortador_nuevo"
    bl_label = "Nuevo cortador"
    bl_options = {"REGISTER", "UNDO"}

    forma: EnumProperty(name="Forma", items=[
        ("CAJA", "Caja", "", "MESH_CUBE", 0),
        ("CILINDRO", "Cilindro", "Agujeros y tomas", "MESH_CYLINDER", 1),
        ("HEXAGONO", "Hexágono", "Tornillos Allen, encajes", "SEQ_CHROMA_SCOPE", 2),
        ("RANURA", "Ranura", "Ranura redondeada (rejillas)", "MESH_CAPSULE", 3),
        ("GUION", "Guion hexagonal", "El motivo de las luces de la ruta", "REMOVE", 4),
        ("PANEL", "Panel achaflanado", "Escotillas y tapas", "MESH_PLANE", 5),
    ], default="RANURA")
    tamano: FloatProperty(name="Tamaño", default=0.0, min=0.0, soft_max=2.0, unit="LENGTH",
                          description="0 = automático según el objeto")
    operacion: EnumProperty(name="Operación", items=OPERACIONES[:3], default="DIFFERENCE")

    def execute(self, context):
        objetivo = context.active_object if (context.active_object and context.active_object.type == "MESH"
                                             and context.active_object.select_get()) else None
        if objetivo is not None and util.es_cortador(objetivo):
            objetivo = objetivo.parent
        r = self.tamano or (util.tamano(objetivo) * 0.12 if objetivo else 0.2)
        bm = bmesh.new()
        forma_cortador(bm, self.forma, r, max(r, 0.05))
        c = util.objeto_desde_bm(context, f"Cortador_{self.forma.lower()}", bm, suave=False,
                                 matriz=util.matriz_cursor(context))
        if objetivo is not None:
            anadir_booleano(objetivo, c, self.operacion)
            util.ordenar_modificadores(objetivo)
        util.preparar_cortador(context, c, objetivo)
        if objetivo is not None and self.forma in ("RANURA", "GUION"):
            util.limitar_bisel(objetivo, r * 0.7)
        util.seleccionar_solo(context, [c], c)
        self.report({"INFO"}, "Cortador creado: muévelo (G), gíralo (R) o escálalo (S)")
        return {"FINISHED"}


class FORJA_OT_linea_panel(bpy.types.Operator):
    """Línea de panel no destructiva siguiendo el contorno de las caras seleccionadas.
Selecciona caras en modo edición y pulsa: aparece un surco fino alrededor"""
    bl_idname = "forja.linea_panel"
    bl_label = "Línea de panel desde caras"
    bl_options = {"REGISTER", "UNDO"}

    ancho: FloatProperty(name="Ancho", default=0.012, min=0.0005, soft_max=0.1, unit="LENGTH")
    profundidad: FloatProperty(name="Profundidad", default=0.02, min=0.001, soft_max=0.2, unit="LENGTH")

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        o = context.edit_object
        bm = bmesh.from_edit_mesh(o.data)
        sel = [f for f in bm.faces if f.select]
        if not sel:
            self.report({"WARNING"}, "Selecciona primero las caras del panel")
            return {"CANCELLED"}
        borde = [e for e in bm.edges if sum(f.select for f in e.link_faces) == 1]
        if not borde:
            self.report({"WARNING"}, "La selección no tiene contorno (¿has seleccionado todo?)")
            return {"CANCELLED"}
        mw = o.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        nuevo = bmesh.new()
        arriba, abajo = {}, {}
        for e in borde:
            for v in e.verts:
                if v in arriba:
                    continue
                n = Vector()
                for f in v.link_faces:
                    if f.select:
                        n += f.normal
                n = (nmat @ (n if n.length else v.normal)).normalized()
                p = mw @ v.co
                arriba[v] = nuevo.verts.new(p + n * self.profundidad)
                abajo[v] = nuevo.verts.new(p - n * self.profundidad)
        for e in borde:
            a, b = e.verts
            nuevo.faces.new((arriba[a], arriba[b], abajo[b], abajo[a]))
        bmesh.ops.recalc_face_normals(nuevo, faces=nuevo.faces)
        c = util.objeto_desde_bm(context, "Cortador_linea_panel", nuevo, suave=False)
        s = c.modifiers.new("Grosor", "SOLIDIFY")
        s.thickness = self.ancho
        s.offset = 0
        s.use_even_offset = True
        anadir_booleano(o, c, "DIFFERENCE")
        util.ordenar_modificadores(o)
        util.preparar_cortador(context, c, o)
        if util.limitar_bisel(o, self.ancho):
            self.report({"WARNING"}, "Bisel reducido para que quepa en el surco (si no, salen manchas)")
        else:
            self.report({"INFO"}, "Línea de panel creada (el cortador está en la colección Cortadores)")
        return {"FINISHED"}


class FORJA_OT_ver_cortadores(bpy.types.Operator):
    """Muestra u oculta todos los cortadores de la escena"""
    bl_idname = "forja.ver_cortadores"
    bl_label = "Mostrar/ocultar cortadores"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lc = context.view_layer.layer_collection.children.get(util.CORTADORES)
        if lc is None:
            self.report({"INFO"}, "No hay cortadores todavía")
            return {"CANCELLED"}
        lc.hide_viewport = not lc.hide_viewport
        return {"FINISHED"}


class FORJA_OT_aplicar_booleanos(bpy.types.Operator):
    """Aplica los booleanos del objeto activo (destructivo) y borra los cortadores que ya no usa nadie.
Guarda una copia del archivo antes si no estás seguro"""
    bl_idname = "forja.aplicar_booleanos"
    bl_label = "Aplicar booleanos"
    bl_options = {"REGISTER", "UNDO"}

    borrar_cortadores: BoolProperty(name="Borrar cortadores sin uso", default=True)

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return context.mode == "OBJECT" and o and o.type == "MESH" and any(m.type == "BOOLEAN" for m in o.modifiers)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        o = context.active_object
        usados = []
        with context.temp_override(object=o, active_object=o):
            for m in [m for m in o.modifiers if m.type == "BOOLEAN"]:
                if m.object:
                    usados.append(m.object)
                bpy.ops.object.modifier_apply(modifier=m.name)
        borrados = 0
        if self.borrar_cortadores:
            for c in usados:
                en_uso = any(m.type == "BOOLEAN" and m.object == c for ob in bpy.data.objects for m in ob.modifiers)
                if not en_uso:
                    bpy.data.objects.remove(c)
                    borrados += 1
        self.report({"INFO"}, f"Booleanos aplicados · {borrados} cortador(es) borrados")
        return {"FINISHED"}


CLASES = (FORJA_OT_booleano, FORJA_OT_cortador_nuevo, FORJA_OT_linea_panel,
          FORJA_OT_ver_cortadores, FORJA_OT_aplicar_booleanos)
