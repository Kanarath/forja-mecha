"""Revisor de Forja (detecta errores típicos) y Arreglo automático, como un MESHmachine para principiantes."""
import bmesh
import bpy
from bpy.props import BoolProperty

from . import util

MODS_NORMALES = {"WEIGHTED_NORMAL", "NORMAL_EDIT"}


def revisar(o):
    """Devuelve una lista de (nivel, texto). Nivel: 'ERROR', 'AVISO' o 'INFO'."""
    out = []
    if min(o.scale) < 0:
        out.append(("ERROR", "Escala negativa: normales invertidas. Usa «Arreglar» o un modificador Mirror."))
    elif any(abs(v - 1.0) > 1e-4 for v in o.scale):
        out.append(("AVISO", f"Escala sin aplicar ({o.scale.x:.2f}, {o.scale.y:.2f}, {o.scale.z:.2f}): biseles deformados."))
    tipos = [m.type for m in o.modifiers]
    if "BEVEL" in tipos:
        b = next(m for m in o.modifiers if m.type == "BEVEL")
        if b.limit_method == "NONE":
            out.append(("AVISO", "El Bevel no tiene Limit Method: también bisela las curvas. Usa Angle."))
        if not b.harden_normals and "WEIGHTED_NORMAL" not in tipos:
            out.append(("AVISO", "Bevel sin Harden Normals ni Weighted Normal: posibles manchas."))
    for t in MODS_NORMALES:
        if t in tipos and "BEVEL" in tipos and tipos.index(t) < tipos.index("BEVEL"):
            out.append(("AVISO", "Weighted Normal va antes del Bevel: pulsa «Ordenar modificadores»."))
    for m in o.modifiers:
        if m.type == "BOOLEAN" and m.operand_type == "OBJECT" and m.object is None:
            out.append(("ERROR", f"El booleano «{m.name}» no tiene cortador."))
    bm = bmesh.new()
    bm.from_mesh(o.data)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    tris = sum(1 for f in bm.faces if len(f.verts) == 3)
    abiertas = sum(1 for e in bm.edges if not e.is_manifold and not e.is_wire)
    sueltos = sum(1 for v in bm.verts if not v.link_edges)
    dobles = len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=0.0001)["targetmap"]) if bm.verts else 0
    cero = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    bm.free()
    subsurf = "SUBSURF" in tipos
    suave = any(p.use_smooth for p in o.data.polygons)
    if ngons and subsurf:
        out.append(("ERROR", f"{ngons} n-gons con Subdivision: pellizcos. Divídelos en quads (J, K)."))
    elif ngons and suave and "WEIGHTED_NORMAL" not in tipos and not any(m.type == "BEVEL" and m.harden_normals for m in o.modifiers):
        out.append(("AVISO", f"{ngons} n-gons con sombreado suave: usa «Afilar»."))
    elif ngons:
        out.append(("INFO", f"{ngons} n-gons (bien en caras planas con Bevel + Weighted Normal)."))
    if tris and subsurf:
        out.append(("AVISO", f"{tris} triángulos con Subdivision: revisa las zonas curvas."))
    if abiertas:
        out.append(("AVISO", f"{abiertas} aristas abiertas / no manifold (agujeros). Pueden romper booleanos."))
    if sueltos:
        out.append(("AVISO", f"{sueltos} vértices sueltos."))
    if dobles:
        out.append(("AVISO", f"{dobles} vértices duplicados."))
    if cero:
        out.append(("AVISO", f"{cero} caras de área cero (puntos negros en el render)."))
    if not out:
        out.append(("OK", "Todo correcto."))
    return out


class FORJA_OT_revisar(bpy.types.Operator):
    """Revisa los objetos seleccionados y te dice qué arreglar (no cambia nada)"""
    bl_idname = "forja.revisar"
    bl_label = "Revisar malla"

    def execute(self, context):
        objs = util.mallas_seleccionadas(context)
        if not objs:
            self.report({"WARNING"}, "Selecciona objetos de malla")
            return {"CANCELLED"}
        lineas = []
        problemas = 0
        for o in objs:
            res = revisar(o)
            problemas += sum(1 for n, _ in res if n in ("ERROR", "AVISO"))
            lineas.append(("TITULO", o.name))
            lineas += res
        context.window_manager["forja_informe"] = [f"{n}|{t}" for n, t in lineas]
        print("\n=== REVISOR DE FORJA ===")
        for n, t in lineas:
            print(f"[{n}] {t}")
        if not bpy.app.background:
            def dibujar(menu, ctx):
                iconos = {"TITULO": "OBJECT_DATA", "ERROR": "CANCEL", "AVISO": "ERROR", "INFO": "INFO", "OK": "CHECKMARK"}
                for n, t in lineas:
                    menu.layout.label(text=t, icon=iconos[n])
            context.window_manager.popup_menu(dibujar, title="Revisor de Forja", icon="TOOL_SETTINGS")
        self.report({"INFO"} if not problemas else {"WARNING"},
                    "Todo correcto" if not problemas else f"{problemas} cosa(s) que revisar")
        return {"FINISHED"}


class FORJA_OT_arreglar(bpy.types.Operator):
    """Arreglos automáticos seguros: aplica escala, corrige normales, une vértices duplicados y borra sueltos"""
    bl_idname = "forja.arreglar"
    bl_label = "Arreglar malla"
    bl_options = {"REGISTER", "UNDO"}

    escala: BoolProperty(name="Aplicar escala", default=True)
    normales: BoolProperty(name="Normales hacia fuera", default=True)
    dobles: BoolProperty(name="Unir duplicados", default=True)
    sueltos: BoolProperty(name="Borrar geometría suelta", default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        for o in util.mallas_seleccionadas(context):
            if self.escala:
                util.aplicar_escala(o)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            if self.dobles:
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
            if self.sueltos:
                sueltos = [v for v in bm.verts if not v.link_edges]
                bmesh.ops.delete(bm, geom=sueltos, context="VERTS")
                aristas = [e for e in bm.edges if not e.link_faces]
                bmesh.ops.delete(bm, geom=aristas, context="EDGES")
            if self.normales:
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
        return {"FINISHED"}


CLASES = (FORJA_OT_revisar, FORJA_OT_arreglar)
