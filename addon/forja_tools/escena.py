"""Estudio de render en un clic (el del módulo 0): ciclorama, luces de tres puntos, cámara y ajustes."""
import math
import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty
from mathutils import Vector

from . import util


class FORJA_OT_estudio(bpy.types.Operator):
    """Crea el estudio gris de la ruta alrededor de la selección: fondo curvo, 3 luces de área,
cámara de 50 mm y ajustes de render (AgX + Glare)"""
    bl_idname = "forja.estudio"
    bl_label = "Estudio de render"
    bl_options = {"REGISTER", "UNDO"}

    motor: EnumProperty(name="Motor", items=[("BLENDER_EEVEE_NEXT", "EEVEE (rápido)", ""),
                                             ("CYCLES", "Cycles (realista)", "")], default="BLENDER_EEVEE_NEXT")
    glare: BoolProperty(name="Brillo en las luces (Glare)", default=True)

    def execute(self, context):
        sel = [o for o in context.selected_objects if o.type in {"MESH", "CURVE"}]
        if sel:
            pts = [o.matrix_world @ Vector(c) for o in sel for c in o.bound_box]
            mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
            mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        else:
            mn, mx = Vector((-1, -1, 0)), Vector((1, 1, 2))
        centro = (mn + mx) / 2
        t = max((mx - mn).length, 0.5)
        col = bpy.data.collections.get("Forja Estudio") or bpy.data.collections.new("Forja Estudio")
        if col.name not in context.scene.collection.children:
            context.scene.collection.children.link(col)
        # ciclorama: suelo que se curva hacia arriba al fondo
        bm = bmesh.new()
        perfil = [(-6 * t, 0)]
        for i in range(13):
            a = math.radians(-90 + i * 7.5)
            perfil.append((2 * t + 2 * t * math.cos(a), 2 * t + 2 * t * math.sin(a)))
        perfil.append((4 * t, 6 * t))
        filas = [[bm.verts.new((x, y, z)) for (y, z) in perfil] for x in (-8 * t, 8 * t)]
        for i in range(len(perfil) - 1):
            bm.faces.new((filas[0][i], filas[1][i], filas[1][i + 1], filas[0][i + 1]))
        suelo = util.objeto_desde_bm(context, "Ciclorama", bm,
                                     [util.material("Forja Estudio", (0.17, 0.175, 0.185), 0, 0.5)])
        suelo.location = (centro.x, centro.y, mn.z)
        util.mover_a_coleccion(suelo, col)

        def luz(nombre, rel, energia, tam, color=(1, 1, 1)):
            l = bpy.data.lights.new(nombre, "AREA")
            l.energy, l.size, l.color = energia * t * t, tam * t, color
            ob = bpy.data.objects.new(nombre, l)
            col.objects.link(ob)
            ob.location = centro + Vector(rel) * t
            ob.rotation_euler = (centro - ob.location).to_track_quat("-Z", "Y").to_euler()
        luz("Luz principal", (-2, -2, 2.5), 95, 1.5)
        luz("Luz de relleno", (2.5, -1.5, 0.8), 18, 3, (0.85, 0.9, 1))
        luz("Contraluz", (1, 2.5, 2.2), 160, 1, (0.6, 0.75, 1))
        cam = bpy.data.objects.new("Camara Forja", bpy.data.cameras.new("Camara Forja"))
        col.objects.link(cam)
        cam.data.lens = 50
        cam.location = centro + Vector((0.75, -1.8, 0.55)) * t
        cam.rotation_euler = (centro - cam.location).to_track_quat("-Z", "Y").to_euler()
        s = context.scene
        s.camera = cam
        s.render.engine = self.motor
        if self.motor == "CYCLES":
            s.cycles.samples = 128
            s.cycles.use_denoising = True
        s.world = s.world or bpy.data.worlds.new("World")
        s.world.color = (0.02, 0.02, 0.025)
        s.view_settings.view_transform = "AgX"
        if self.glare:
            s.use_nodes = True
            nt = s.node_tree
            rl = next((n for n in nt.nodes if n.type == "R_LAYERS"), None) or nt.nodes.new("CompositorNodeRLayers")
            comp = next((n for n in nt.nodes if n.type == "COMPOSITE"), None) or nt.nodes.new("CompositorNodeComposite")
            g = next((n for n in nt.nodes if n.type == "GLARE"), None) or nt.nodes.new("CompositorNodeGlare")
            g.glare_type = "FOG_GLOW"
            g.threshold = 1.2
            g.size = 7
            nt.links.new(rl.outputs["Image"], g.inputs["Image"])
            nt.links.new(g.outputs["Image"], comp.inputs["Image"])
        self.report({"INFO"}, "Estudio listo: pulsa Num 0 para ver la cámara y F12 para renderizar")
        return {"FINISHED"}


CLASES = (FORJA_OT_estudio,)
