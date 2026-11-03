"""Utilidades compartidas por todas las herramientas de Forja Tools."""
import bpy
import bmesh
from mathutils import Matrix, Vector

CORTADORES = "Cortadores"

# Orden «correcto» de la pila de modificadores en hard surface.
# Simetría y repeticiones primero, luego cortes, después el bisel y al final las normales.
ORDEN = {
    "MIRROR": 0, "ARRAY": 1, "SOLIDIFY": 2, "BOOLEAN": 3, "BEVEL": 5,
    "SUBSURF": 6, "TRIANGULATE": 7, "WEIGHTED_NORMAL": 8, "NODES": 9,
}


def mallas_seleccionadas(context, incluir_cortadores=False):
    objs = [o for o in context.selected_objects if o.type == "MESH"]
    if not incluir_cortadores:
        objs = [o for o in objs if not es_cortador(o)]
    return objs


def es_cortador(o):
    return any(c.name.startswith(CORTADORES) for c in o.users_collection) or o.get("forja_cortador", False)


def coleccion_cortadores(context):
    col = bpy.data.collections.get(CORTADORES)
    if col is None:
        col = bpy.data.collections.new(CORTADORES)
    if col.name not in context.scene.collection.children:
        context.scene.collection.children.link(col)
    return col


def mover_a_coleccion(o, col):
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)


def emparentar(hijo, padre):
    """Emparenta conservando la posición (como Ctrl+P → Keep Transform)."""
    mw = hijo.matrix_world.copy()
    hijo.parent = padre
    hijo.matrix_world = mw


def preparar_cortador(context, cortador, objetivo=None):
    cortador["forja_cortador"] = True
    cortador.display_type = "WIRE"
    cortador.hide_render = True
    cortador.visible_camera = False
    cortador.visible_shadow = False
    mover_a_coleccion(cortador, coleccion_cortadores(context))
    if objetivo is not None and cortador.parent is None:
        emparentar(cortador, objetivo)


def aplicar_escala(o):
    """Ctrl+A → Scale, sin depender del contexto (también vale para varios usuarios de la malla)."""
    if all(abs(s - 1.0) < 1e-6 for s in o.scale):
        return False
    if o.data.users > 1:
        o.data = o.data.copy()
    s = Matrix.Diagonal(o.scale.to_4d())
    o.data.transform(s)
    for c in o.children:  # los hijos no deben moverse
        c.matrix_parent_inverse = s @ c.matrix_parent_inverse
    o.scale = (1, 1, 1)
    o.data.update()
    return True


def ordenar_modificadores(o):
    mods = list(o.modifiers)
    orden = sorted(range(len(mods)), key=lambda i: (ORDEN.get(mods[i].type, 4), i))
    for destino, i in enumerate(orden):
        nombre = mods[i].name
        actual = list(o.modifiers).index(o.modifiers[nombre])
        if actual != destino:
            o.modifiers.move(actual, destino)


def tamano(o):
    d = o.dimensions
    return max(max(d.x, d.y, d.z), 1e-4)


def material(nombre, color, metal=0.0, rugosidad=0.4, emision=None, fuerza=0.0):
    m = bpy.data.materials.get(nombre)
    if m:
        return m
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rugosidad
    if emision:
        b.inputs["Emission Color"].default_value = (*emision, 1)
        b.inputs["Emission Strength"].default_value = fuerza
    m.diffuse_color = (*(emision or color), 1)
    return m


def objeto_desde_bm(context, nombre, bm, materiales=(), suave=True, matriz=None):
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    for mt in materiales:
        me.materials.append(mt)
    for p in me.polygons:
        p.use_smooth = suave
    o = bpy.data.objects.new(nombre, me)
    context.collection.objects.link(o)
    if matriz is not None:
        o.matrix_world = matriz
    return o


def bisel(o, ancho, segmentos=2, angulo=0.5236):
    b = o.modifiers.get("Forja Bisel") or o.modifiers.new("Forja Bisel", "BEVEL")
    b.width = ancho
    b.segments = segmentos
    b.limit_method = "ANGLE"
    b.angle_limit = angulo
    b.harden_normals = True
    # Clamp Overlap degenera la malla en surcos finos (normales nulas = manchas negras);
    # en su lugar limitamos el ancho con limitar_bisel()
    b.use_clamp_overlap = False
    b.miter_outer = "MITER_ARC"
    return b


def marcar_afiladas(bm, angulo):
    """Aristas más dobladas que el ángulo → duras; el resto, suaves."""
    for e in bm.edges:
        if e.is_manifold:
            e.smooth = e.calc_face_angle(0) < angulo


def remarcar_si_afilado(o, bm):
    """Tras editar una pieza ya «afilada», la geometría nueva hereda el mismo criterio de aristas duras."""
    b = o.modifiers.get("Forja Bisel")
    if b is not None:
        bm.normal_update()
        marcar_afiladas(bm, b.angle_limit)
        for f in bm.faces:
            f.smooth = True


def limitar_bisel(o, hueco):
    """El bisel no puede superar la mitad del surco más fino, o los dos lados se pisan."""
    b = next((m for m in o.modifiers if m.type == "BEVEL"), None)
    if b is not None and b.width > hueco * 0.4:
        b.width = hueco * 0.4
        return True
    return False


def normales_ponderadas(o):
    w = o.modifiers.get("Forja Normales") or o.modifiers.new("Forja Normales", "WEIGHTED_NORMAL")
    w.keep_sharp = True
    w.mode = "FACE_AREA"
    return w


def seleccionar_solo(context, objs, activo=None):
    for o in context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    if activo is not None:
        context.view_layer.objects.active = activo


def matriz_cursor(context, escala=1.0):
    c = context.scene.cursor
    return Matrix.Translation(c.location) @ c.rotation_euler.to_matrix().to_4x4() @ Matrix.Scale(escala, 4)


def caja(bm, centro, medidas, rot=None, mat=0):
    """Añade una caja al bmesh y le asigna un índice de material."""
    m = Matrix.Translation(centro) @ (rot or Matrix.Identity(4)) @ Matrix.Diagonal((*medidas, 1))
    antes = set(bm.faces)
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    for f in set(bm.faces) - antes:
        f.material_index = mat


def cilindro(bm, centro, radio, alto, lados=16, rot=None, mat=0, radio2=None):
    m = Matrix.Translation(centro) @ (rot or Matrix.Identity(4))
    antes = set(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=lados, radius1=radio,
                          radius2=radio if radio2 is None else radio2, depth=alto, matrix=m)
    nuevas = set(bm.faces) - antes
    for f in nuevas:
        f.material_index = mat
    return nuevas


def prisma(bm, puntos, z0, z1, mat=0):
    """Extruye un contorno 2D (XY) entre dos alturas."""
    vs = [bm.verts.new((x, y, z0)) for x, y in puntos]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, z1 - z0))
    for g in r["geom"]:
        if isinstance(g, bmesh.types.BMFace):
            g.material_index = mat
    f.material_index = mat
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def chaflan_rect(x0, x1, y0, y1, c):
    return [(x0, y0 + c), (x0 + c, y0), (x1 - c, y0), (x1, y0 + c),
            (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c)]
