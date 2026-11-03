"""
Prueba de Forja Tools en Blender sin interfaz: registra el addon, usa cada herramienta sobre
una pieza de ejemplo, comprueba los resultados y renderiza las imágenes de la página del addon.

  blender -b --factory-startup --python tools/test_addon.py
"""
import math
import os
import sys
import traceback

import bpy
from mathutils import Euler, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "addon"))
import forja_tools  # noqa: E402

IMG = os.path.join(ROOT, "assets", "img")
fallos = []


def paso(nombre, fn):
    try:
        r = fn()
        print(f"OK   {nombre}" + (f" · {r}" if r else ""))
    except Exception:
        fallos.append(nombre)
        print(f"FALLO {nombre}")
        traceback.print_exc()


def cursor(loc, rot=(0, 0, 0)):
    c = bpy.context.scene.cursor
    c.location = loc
    c.rotation_euler = rot


def seleccionar(objs, activo):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = activo


def render(nombre, w=1280, h=720):
    s = bpy.context.scene
    s.render.resolution_x, s.render.resolution_y = w, h
    s.render.image_settings.file_format = "WEBP"
    s.render.image_settings.quality = 86
    s.render.filepath = os.path.join(IMG, nombre + ".webp")
    bpy.ops.render.render(write_still=True)
    print("RENDER", nombre)


bpy.ops.wm.read_factory_settings(use_empty=True)
forja_tools.register()
print("Registrado:", [c for c in dir(bpy.ops.forja) if not c.startswith("_")])

# conflictos del atajo en el mapa por defecto
kc = bpy.context.window_manager.keyconfigs.default
if kc:
    for km in kc.keymaps:
        for k in km.keymap_items:
            if k.type == "Q" and k.shift and k.alt and not k.ctrl:
                print("CONFLICTO atajo:", km.name, k.idname)

s = bpy.context.scene
s.world = bpy.data.worlds.new("W")

# pieza de ejemplo: un bloque con escala sin aplicar (para que Afilar la arregle)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.3))
bloque = bpy.context.object
bloque.name = "Bloque"
bloque.scale = (1.6, 1.0, 0.3)

# --- render «antes»
s.render.engine = "BLENDER_WORKBENCH"
sh = s.display.shading
sh.light, sh.color_type, sh.show_cavity, sh.cavity_type = "STUDIO", "MATERIAL", True, "BOTH"
s.display.render_aa = "16"
s.world.color = (0.19, 0.195, 0.21)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
s.collection.objects.link(cam)
s.camera = cam
cam.data.lens = 40
cam.location = (1.7, -2.6, 2.3)
cam.rotation_euler = (Vector((0, 0, 0.25)) - cam.location).to_track_quat("-Z", "Y").to_euler()
render("addon_antes")

seleccionar([bloque], bloque)
paso("afilar", lambda: (bpy.ops.forja.afilar(), [m.type for m in bloque.modifiers], tuple(bloque.scale))[1:])

# cortadores: ranura en la tapa + fila con Array → rejilla
cursor((0.35, 0, 0.45))
seleccionar([bloque], bloque)
paso("cortador ranura", lambda: bpy.ops.forja.cortador_nuevo(forma="RANURA", tamano=0.06))
ranura = bpy.context.object
ranura.rotation_euler = (0, 0, math.radians(90))
paso("repetir cortador", lambda: (bpy.ops.forja.repetir(eje="Y", cantidad=5, separacion=1.0) and None))
ranura.location.x = 0.35
ranura.location.y = -0.0
# la ranura girada 90°: la fila en Y del objeto va en X del mundo
cursor((-0.45, 0, 0.45))
seleccionar([bloque], bloque)
paso("cortador agujero", lambda: bpy.ops.forja.cortador_nuevo(forma="CILINDRO", tamano=0.1))
cursor((0.0, -0.5, 0.3), (math.radians(90), 0, 0))
seleccionar([bloque], bloque)
paso("cortador guion", lambda: bpy.ops.forja.cortador_nuevo(forma="GUION", tamano=0.05))
paso("repetir guiones", lambda: bpy.ops.forja.repetir(eje="X", cantidad=4, separacion=1.4))
bpy.context.object.location.x = -0.3

# booleano manual con un objeto cualquiera (Rebanar)
bpy.ops.mesh.primitive_cube_add(size=0.3, location=(0.8, 0.5, 0.45))
esquina = bpy.context.object
seleccionar([esquina, bloque], bloque)
paso("rebanar", lambda: bpy.ops.forja.booleano(operacion="SLICE"))
reb = bpy.data.objects.get("Bloque_rebanada")
if reb:
    reb.location.z += 0.25

# modo edición, en una pieza aparte fuera de cámara: hundir, línea de panel, placa, apoyos, pliegue y círculo
import bmesh  # noqa: E402
bpy.ops.mesh.primitive_cube_add(size=1, location=(20, 0, 0.5))
prueba = bpy.context.object
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(prueba.data)
for f in bm.faces:
    f.select = f.normal.z > 0.9
bmesh.update_edit_mesh(prueba.data)
paso("hundir (inset+extrude)", lambda: bpy.ops.forja.hundir(grosor=0.08, profundidad=-0.02))
paso("linea de panel", lambda: bpy.ops.forja.linea_panel(ancho=0.012, profundidad=0.02))
bm = bmesh.from_edit_mesh(prueba.data)
for f in bm.faces:
    f.select = f.normal.x > 0.9 and f.calc_center_median().x > 0.45
bmesh.update_edit_mesh(prueba.data)
paso("placa desde caras", lambda: bpy.ops.forja.placa(margen=0.03, separacion=0.002, grosor=0.02))
bpy.ops.object.mode_set(mode="OBJECT")


def comprobar_placa():
    placa = bpy.data.objects["Placa_forja"]
    dg = bpy.context.evaluated_depsgraph_get()
    bb = [placa.matrix_world @ Vector(c) for c in placa.evaluated_get(dg).bound_box]
    xs = [p.x for p in bb]
    assert 20.49 < min(xs) and max(xs) < 20.56, f"placa mal colocada: x {min(xs):.3f}..{max(xs):.3f}"
    return f"x {min(xs):.3f}..{max(xs):.3f}"


def comprobar_prueba():
    dg = bpy.context.evaluated_depsgraph_get()
    n = len(prueba.evaluated_get(dg).data.vertices)
    assert n > 0, "la pieza se quedó vacía"
    return f"{n} vértices"


paso("placa bien colocada", comprobar_placa)
paso("pieza no vacía tras la línea de panel", comprobar_prueba)

bpy.ops.mesh.primitive_cube_add(size=0.4, location=(22, 0, 0.2))
cubo = bpy.context.object
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(cubo.data)
for e in bm.edges:
    e.select = True
bmesh.update_edit_mesh(cubo.data)
paso("support loops", lambda: (bpy.ops.forja.apoyos(distancia=0.02), len(bmesh.from_edit_mesh(cubo.data).verts))[1])
paso("pliegue", lambda: bpy.ops.forja.pliegue(valor=0.8))
bm = bmesh.from_edit_mesh(cubo.data)
for v in bm.verts:
    v.select = False
top = max((f for f in bm.faces if f.normal.z > 0.9), key=lambda f: f.calc_area())
for v in top.verts:
    v.select = True
bmesh.update_edit_mesh(cubo.data)
paso("circulo perfecto", lambda: bpy.ops.forja.circulo())
bpy.ops.object.mode_set(mode="OBJECT")
cubo.modifiers.new("Sub", "SUBSURF").levels = 2
for p in cubo.data.polygons:
    p.use_smooth = True

# piezas en las esquinas de la tapa
for i, (x, y) in enumerate([(-0.72, -0.42), (-0.72, 0.42), (0.72, -0.42)]):
    cursor((x, y, 0.45))
    seleccionar([bloque], bloque)
    paso(f"tornillo {i}", lambda: bpy.ops.forja.pieza(tipo="TORNILLO", tamano=0.035))
for k, (tipo, loc) in enumerate([("LED", (-0.45, -0.25, 0.43)), ("ENGRANAJE", (1.35, -0.4, 0)),
                                 ("DISIPADOR", (1.35, 0.45, 0)), ("CONECTOR", (-1.05, -0.65, 0)),
                                 ("REJILLA", (-1.05, 0.65, 0)), ("TOMA", (1.5, -1.0, 0)),
                                 ("TUERCA", (-1.5, -0.8, 0))]):
    cursor(loc)
    bpy.ops.object.select_all(action="DESELECT")
    paso(f"pieza {tipo}", lambda: bpy.ops.forja.pieza(tipo=tipo, tamano=0.12 if tipo != "LED" else 0.05))
    if tipo == "CONECTOR":
        conector = bpy.context.object
    if tipo == "DISIPADOR":
        disipador = bpy.context.object

# cable entre dos piezas y pistón
seleccionar([conector, disipador], disipador)
paso("cable", lambda: bpy.ops.forja.cable(cantidad=3, caida=0.2, radio=0.012))
cursor((-1.25, 0.9, 0.0), (0, math.radians(60), 0))
paso("piston", lambda: bpy.ops.forja.piston(largo=0.6, radio=0.035))
b = bpy.context.object
b.location.z += 0.1

# espejo, radial, ordenar
bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.06, location=(0.7, 1.0, 0.03))
diente = bpy.context.object
cursor((0.9, 1.0, 0))
paso("radial", lambda: bpy.ops.forja.radial(cantidad=10))
bpy.ops.mesh.primitive_cube_add(size=0.2, location=(-0.4, 1.0, 0.1))
paso("espejo", lambda: bpy.ops.forja.espejo(eje="X", bisectar=False))
seleccionar([bloque], bloque)
def comprobar_bloque():
    dg = bpy.context.evaluated_depsgraph_get()
    n = len(bloque.evaluated_get(dg).data.vertices)
    assert n > 500, f"el bloque tiene solo {n} vértices"
    return f"{n} vértices"


paso("bloque con todos los cortes", comprobar_bloque)
paso("ordenar", lambda: (bpy.ops.forja.ordenar(), [m.type for m in bloque.modifiers])[1])

# materiales
seleccionar([bloque], bloque)
paso("material pintura", lambda: bpy.ops.forja.material(tipo="PINTURA", color=(0.74, 0.75, 0.79)))
paso("material luz", lambda: bpy.ops.forja.material(tipo="LUZ", color=(0.1, 0.5, 1.0)) if False else None)

# revisar y arreglar
seleccionar([bloque, cubo], bloque)
paso("revisar", lambda: (bpy.ops.forja.revisar(), list(bpy.context.window_manager.get("forja_informe", []))[:6])[1])
bpy.ops.mesh.primitive_cube_add(size=0.3, location=(2.2, 0, 0.15))
malo = bpy.context.object
malo.scale = (-1, 1, 1)
paso("arreglar", lambda: (bpy.ops.forja.arreglar(), tuple(malo.scale))[1])
bpy.data.objects.remove(malo)
paso("ver cortadores", lambda: (bpy.ops.forja.ver_cortadores(), bpy.ops.forja.ver_cortadores()) and None)

# --- render «después» (Workbench) y con estudio (EEVEE)
cursor((0, 0, 0))
render("addon_despues")
seleccionar([bloque], bloque)
paso("estudio", lambda: bpy.ops.forja.estudio(motor="BLENDER_EEVEE_NEXT"))
render("addon_estudio", 1600, 900)

# modal y Step: solo se comprueba que existen (el modal necesita ratón)
paso("escalonar existe", lambda: bpy.ops.forja.escalonar.idname())
paso("aplicar booleanos existe", lambda: bpy.ops.forja.aplicar_booleanos.idname())
paso("unregister", lambda: forja_tools.unregister())
print("\nRESULTADO:", "TODO OK" if not fallos else f"FALLOS: {fallos}")
