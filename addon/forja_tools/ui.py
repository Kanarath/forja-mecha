"""Interfaz: panel «Forja» en la barra lateral (N), menú circular (Shift+Alt+Q) y piezas en Shift+A."""
import bpy

from . import util


def boton(col, op, texto, icono="NONE", **props):
    b = col.operator(op, text=texto, icon=icono)
    for k, v in props.items():
        setattr(b, k, v)
    return b


class FORJA_PT_principal(bpy.types.Panel):
    bl_label = "Forja Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forja"

    def draw(self, context):
        l = self.layout
        if context.mode == "EDIT_MESH":
            l.label(text="Modo edición", icon="EDITMODE_HLT")
        else:
            l.label(text="Modo objeto", icon="OBJECT_DATA")
        l.label(text="Menú rápido: Shift + Alt + Q", icon="EVENT_Q")


class FORJA_PT_acabado(bpy.types.Panel):
    bl_label = "Acabado"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forja"
    bl_parent_id = "FORJA_PT_principal"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def draw(self, context):
        c = self.layout.column(align=True)
        c.scale_y = 1.3
        boton(c, "forja.afilar", "Afilar (receta)", "MOD_BEVEL")
        r = c.row(align=True)
        boton(r, "forja.ancho_bisel", "Ancho bisel", "DRIVER_DISTANCE")
        boton(r, "forja.escalonar", "Step", "SORTBYEXT")
        r = c.row(align=True)
        boton(r, "forja.ordenar", "Ordenar pila", "SORTSIZE")
        boton(r, "forja.limpiar_acabado", "Quitar", "X")


class FORJA_PT_booleanos(bpy.types.Panel):
    bl_label = "Cortes (booleanos)"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forja"
    bl_parent_id = "FORJA_PT_principal"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def draw(self, context):
        l = self.layout
        l.label(text="Cortadores → luego la pieza:")
        g = l.grid_flow(columns=2, align=True)
        for op, txt, ic in (("DIFFERENCE", "Cortar", "SELECT_SUBTRACT"), ("UNION", "Unir", "SELECT_EXTEND"),
                            ("INTERSECT", "Intersecar", "SELECT_INTERSECT"), ("SLICE", "Rebanar", "SELECT_DIFFERENCE")):
            boton(g, "forja.booleano", txt, ic, operacion=op)
        l.label(text="Nuevo cortador en el cursor:")
        g = l.grid_flow(columns=3, align=True)
        for f, txt, ic in (("RANURA", "Ranura", "MESH_CAPSULE"), ("CILINDRO", "Agujero", "MESH_CYLINDER"),
                           ("CAJA", "Caja", "MESH_CUBE"), ("HEXAGONO", "Hexágono", "SEQ_CHROMA_SCOPE"),
                           ("GUION", "Guion", "REMOVE"), ("PANEL", "Panel", "MESH_PLANE")):
            boton(g, "forja.cortador_nuevo", txt, ic, forma=f)
        r = l.row(align=True)
        boton(r, "forja.ver_cortadores", "Ver/ocultar", "HIDE_OFF")
        boton(r, "forja.aplicar_booleanos", "Aplicar", "CHECKMARK")


class FORJA_PT_simetria(bpy.types.Panel):
    bl_label = "Simetría y repetición"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forja"
    bl_parent_id = "FORJA_PT_principal"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def draw(self, context):
        l = self.layout
        r = l.row(align=True)
        r.label(text="Espejo:")
        for e in "XYZ":
            boton(r, "forja.espejo", e, eje=e)
        r = l.row(align=True)
        boton(r, "forja.repetir", "En fila", "MOD_ARRAY")
        boton(r, "forja.radial", "En círculo", "PROP_CON")


class FORJA_PT_piezas(bpy.types.Panel):
    bl_label = "Piezas (kitbash)"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forja"
    bl_parent_id = "FORJA_PT_principal"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def draw(self, context):
        from .piezas import PIEZAS
        l = self.layout
        g = l.grid_flow(columns=2, align=True)
        for k, v in PIEZAS.items():
            boton(g, "forja.pieza", v[0], tipo=k)
        r = l.row(align=True)
        boton(r, "forja.piston", "Pistón", "CON_TRACKTO")
        boton(r, "forja.cable", "Cable", "CURVE_BEZCURVE")


class FORJA_PT_edicion(bpy.types.Panel):
    bl_label = "Modelado"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forja"
    bl_parent_id = "FORJA_PT_principal"

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def draw(self, context):
        c = self.layout.column(align=True)
        c.scale_y = 1.2
        r = c.row(align=True)
        boton(r, "forja.hundir", "Hundir", "TRIA_DOWN", profundidad=-0.03)
        boton(r, "forja.hundir", "Sacar", "TRIA_UP", profundidad=0.03)
        boton(c, "forja.linea_panel", "Línea de panel", "MOD_WIREFRAME")
        boton(c, "forja.placa", "Placa desde caras", "MOD_SOLIDIFY")
        r = c.row(align=True)
        boton(r, "forja.apoyos", "Support loops", "MOD_SUBSURF")
        boton(r, "forja.pliegue", "Pliegue", "MOD_SMOOTH")
        boton(c, "forja.circulo", "Círculo perfecto", "MESH_CIRCLE")


class FORJA_PT_material(bpy.types.Panel):
    bl_label = "Materiales y render"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forja"
    bl_parent_id = "FORJA_PT_principal"

    def draw(self, context):
        l = self.layout
        g = l.grid_flow(columns=2, align=True)
        boton(g, "forja.material", "Pintura blanca", tipo="PINTURA", color=(0.74, 0.75, 0.79))
        boton(g, "forja.material", "Pintura naranja", tipo="PINTURA", color=(0.85, 0.36, 0.08))
        boton(g, "forja.material", "Metal oscuro", tipo="METAL_OSCURO")
        boton(g, "forja.material", "Goma", tipo="GOMA")
        boton(g, "forja.material", "Luz azul", tipo="LUZ", color=(0.1, 0.5, 1.0))
        boton(g, "forja.material", "Luz roja", tipo="LUZ", color=(1.0, 0.05, 0.04))
        if context.mode == "OBJECT":
            boton(l, "forja.estudio", "Estudio de render", "LIGHT_AREA")


class FORJA_PT_revisar(bpy.types.Panel):
    bl_label = "Revisión"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forja"
    bl_parent_id = "FORJA_PT_principal"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def draw(self, context):
        l = self.layout
        r = l.row(align=True)
        boton(r, "forja.revisar", "Revisar", "VIEWZOOM")
        boton(r, "forja.arreglar", "Arreglar", "TOOL_SETTINGS")
        informe = context.window_manager.get("forja_informe")
        if informe:
            caja = l.box()
            iconos = {"TITULO": "OBJECT_DATA", "ERROR": "CANCEL", "AVISO": "ERROR", "INFO": "INFO", "OK": "CHECKMARK"}
            for linea in list(informe)[:14]:
                nivel, texto = linea.split("|", 1)
                caja.label(text=texto, icon=iconos.get(nivel, "DOT"))


class FORJA_MT_pie(bpy.types.Menu):
    bl_label = "Forja"
    bl_idname = "FORJA_MT_pie"

    def draw(self, context):
        p = self.layout.menu_pie()
        if context.mode == "EDIT_MESH":
            boton(p, "forja.hundir", "Hundir", "TRIA_DOWN", profundidad=-0.03)       # izquierda
            boton(p, "forja.hundir", "Sacar", "TRIA_UP", profundidad=0.03)           # derecha
            boton(p, "forja.apoyos", "Support loops", "MOD_SUBSURF")                 # abajo
            boton(p, "forja.linea_panel", "Línea de panel", "MOD_WIREFRAME")         # arriba
            boton(p, "forja.placa", "Placa desde caras", "MOD_SOLIDIFY")
            boton(p, "forja.circulo", "Círculo perfecto", "MESH_CIRCLE")
            boton(p, "forja.pliegue", "Pliegue", "MOD_SMOOTH")
            p.separator()
            return
        boton(p, "forja.booleano", "Cortar", "SELECT_SUBTRACT", operacion="DIFFERENCE")   # izquierda
        boton(p, "forja.afilar", "Afilar", "MOD_BEVEL")                                    # derecha
        boton(p, "forja.revisar", "Revisar", "VIEWZOOM")                                   # abajo
        boton(p, "forja.cortador_nuevo", "Nuevo cortador", "MESH_CAPSULE", forma="RANURA")  # arriba
        boton(p, "forja.booleano", "Unir", "SELECT_EXTEND", operacion="UNION")
        boton(p, "forja.ancho_bisel", "Ancho bisel", "DRIVER_DISTANCE")
        boton(p, "forja.booleano", "Rebanar", "SELECT_DIFFERENCE", operacion="SLICE")
        boton(p, "forja.espejo", "Espejo X", "MOD_MIRROR", eje="X")


class FORJA_MT_anadir(bpy.types.Menu):
    bl_label = "Piezas Forja"
    bl_idname = "FORJA_MT_anadir"

    def draw(self, context):
        from .piezas import PIEZAS
        for k, v in PIEZAS.items():
            boton(self.layout, "forja.pieza", v[0], tipo=k)
        self.layout.separator()
        self.layout.operator("forja.piston", icon="CON_TRACKTO")


def menu_anadir(self, context):
    self.layout.menu(FORJA_MT_anadir.bl_idname, icon="MOD_BUILD")


CLASES = (FORJA_PT_principal, FORJA_PT_acabado, FORJA_PT_booleanos, FORJA_PT_simetria, FORJA_PT_piezas,
          FORJA_PT_edicion, FORJA_PT_material, FORJA_PT_revisar, FORJA_MT_pie, FORJA_MT_anadir)
