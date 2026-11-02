"""
REVISOR DE FORJA · Forja Mecha
Revisa los objetos seleccionados y te avisa de los errores típicos del hard surface.

Cómo usarlo:
  1. Selecciona uno o varios objetos (modo objeto).
  2. Workspace "Scripting" -> Text -> Open -> elige este archivo.
  3. Pulsa el botón ▶ (Run Script) o Alt+P con el ratón encima del texto.
  4. Lee el informe en la ventana emergente (y en Window -> Toggle System Console).

No modifica nada: solo lee y te cuenta qué arreglar.
"""
import bpy
import bmesh

MODIFICADORES_DE_NORMALES = {"WEIGHTED_NORMAL", "NORMAL_EDIT"}


def revisar(obj):
    avisos = []
    sx, sy, sz = obj.scale
    if min(sx, sy, sz) < 0:
        avisos.append("ERROR: escala negativa (espejo hecho con S -1). Normales invertidas. Arreglo: Ctrl+A > Scale y Shift+N en modo edición.")
    elif any(abs(v - 1.0) > 1e-4 for v in obj.scale):
        avisos.append(f"Escala sin aplicar ({sx:.2f}, {sy:.2f}, {sz:.2f}). El Bevel y otros modificadores saldrán deformados. Arreglo: Ctrl+A > Scale.")

    mods = [m.type for m in obj.modifiers]
    if "BEVEL" in mods:
        b = next(m for m in obj.modifiers if m.type == "BEVEL")
        if b.limit_method == "NONE":
            avisos.append("El Bevel no tiene Limit Method: biselará también las caras curvas. Prueba Angle (30°).")
        if not b.harden_normals and "WEIGHTED_NORMAL" not in mods:
            avisos.append("Bevel sin Harden Normals ni Weighted Normal: puede haber sombreado raro en caras grandes.")
    for tipo in MODIFICADORES_DE_NORMALES:
        if tipo in mods and "BEVEL" in mods and mods.index(tipo) < mods.index("BEVEL"):
            avisos.append("Weighted Normal está ANTES del Bevel. Muévelo debajo para que actúe sobre la malla final.")

    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    tris = sum(1 for f in bm.faces if len(f.verts) == 3)
    abiertos = sum(1 for e in bm.edges if not e.is_manifold and not e.is_wire)
    sueltos = sum(1 for v in bm.verts if not v.link_edges)
    duplicados = 0
    if bm.verts:
        r = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=0.0001)
        duplicados = len(r["targetmap"])
    area_cero = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    bm.free()

    suave = any(p.use_smooth for p in me.polygons)
    subsurf = "SUBSURF" in mods
    if ngons:
        if subsurf:
            avisos.append(f"{ngons} n-gons con Subdivision Surface: causarán pellizcos. Divídelos en quads (J para conectar vértices, K para cuchillo).")
        elif suave and "WEIGHTED_NORMAL" not in mods and not any(m.type == "BEVEL" and m.harden_normals for m in obj.modifiers):
            avisos.append(f"{ngons} n-gons con sombreado suave y sin Weighted Normal: probables manchas. Añade Bevel (Harden Normals) + Weighted Normal.")
        else:
            avisos.append(f"Info: {ngons} n-gons. En caras planas con Bevel + Weighted Normal suelen estar bien.")
    if tris and subsurf:
        avisos.append(f"{tris} triángulos con Subdivision Surface: revisa que no estén en zonas curvas visibles.")
    if abiertos:
        avisos.append(f"{abiertos} aristas abiertas o no manifold (agujeros o caras internas). Select > Select All by Trait > Non Manifold para verlas.")
    if sueltos:
        avisos.append(f"{sueltos} vértices sueltos. Select > Select All by Trait > Loose Geometry y bórralos.")
    if duplicados:
        avisos.append(f"{duplicados} vértices duplicados. En modo edición: A, después M > By Distance.")
    if area_cero:
        avisos.append(f"{area_cero} caras de área cero (aplastadas). Suelen dar puntos negros en el render.")
    if not suave:
        avisos.append("Info: sombreado plano (Shade Flat). Correcto para trabajar; para el acabado usa Shade Smooth + Bevel/Weighted Normal.")
    return avisos


def informe():
    objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not objs:
        return ["Selecciona al menos un objeto de malla y vuelve a ejecutar el script."]
    lineas = []
    for o in objs:
        avisos = revisar(o)
        problemas = [a for a in avisos if not a.startswith("Info")]
        lineas.append(f"■ {o.name}: " + ("todo correcto ✔" if not problemas else f"{len(problemas)} cosa(s) que revisar"))
        lineas += ["   · " + a for a in avisos]
    return lineas


lineas = informe()
print("\n=== REVISOR DE FORJA ===")
for l in lineas:
    print(l)

if bpy.context.window_manager.windows and not bpy.app.background:
    def dibujar(self, context):
        for l in lineas:
            self.layout.label(text=l)
    bpy.context.window_manager.popup_menu(dibujar, title="Revisor de Forja", icon="TOOL_SETTINGS")
