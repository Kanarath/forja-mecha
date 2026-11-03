"""Materiales hard surface en un clic: pinturas con desgaste en bordes y suciedad (Cycles), metales y luces."""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatVectorProperty

from . import util

TIPOS = [
    ("PINTURA", "Pintura", "Pintura con rugosidad variable; con desgaste, el metal asoma en los bordes"),
    ("METAL", "Metal desnudo", "Acero/aluminio"),
    ("METAL_OSCURO", "Metal oscuro", "Estructura y mecanismos"),
    ("GOMA", "Goma", "Empuñaduras, juntas, cables"),
    ("LUZ", "Luz (emisivo)", "LEDs, visores, núcleos"),
    ("CRISTAL", "Cristal", "Visores y tapas transparentes"),
]


def pintura(nombre, color, desgaste=True, suciedad=True):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bsdf = N["Principled BSDF"]
    ruido = N.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 4
    rug = N.new("ShaderNodeMapRange")
    rug.inputs["To Min"].default_value = 0.32
    rug.inputs["To Max"].default_value = 0.52
    L.new(ruido.outputs["Fac"], rug.inputs["Value"])
    col = N.new("ShaderNodeRGB")
    col.outputs[0].default_value = (*color, 1)
    color_out, rug_out = col.outputs[0], rug.outputs["Result"]
    if desgaste:
        bev = N.new("ShaderNodeBevel")
        bev.inputs["Radius"].default_value = 0.03
        geo = N.new("ShaderNodeNewGeometry")
        dot = N.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        L.new(bev.outputs["Normal"], dot.inputs[0])
        L.new(geo.outputs["Normal"], dot.inputs[1])
        borde = N.new("ShaderNodeMath")
        borde.operation = "SUBTRACT"
        borde.inputs[0].default_value = 1.0
        L.new(dot.outputs["Value"], borde.inputs[1])
        r2 = N.new("ShaderNodeTexNoise")
        r2.inputs["Scale"].default_value = 12
        r2.inputs["Detail"].default_value = 8
        mul = N.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        L.new(borde.outputs["Value"], mul.inputs[0])
        L.new(r2.outputs["Fac"], mul.inputs[1])
        mascara = N.new("ShaderNodeMapRange")
        mascara.label = "Máscara de desgaste"
        mascara.inputs["From Min"].default_value = 0.01
        mascara.inputs["From Max"].default_value = 0.05
        L.new(mul.outputs["Value"], mascara.inputs["Value"])
        mix = N.new("ShaderNodeMixRGB")
        mix.inputs["Color2"].default_value = (0.32, 0.33, 0.35, 1)
        L.new(mascara.outputs["Result"], mix.inputs["Fac"])
        L.new(color_out, mix.inputs["Color1"])
        color_out = mix.outputs["Color"]
        rmix = N.new("ShaderNodeMixRGB")
        rmix.inputs["Color2"].default_value = (0.22, 0.22, 0.22, 1)
        L.new(mascara.outputs["Result"], rmix.inputs["Fac"])
        L.new(rug_out, rmix.inputs["Color1"])
        rug_out = rmix.outputs["Color"]
        L.new(mascara.outputs["Result"], bsdf.inputs["Metallic"])
    if suciedad:
        ao = N.new("ShaderNodeAmbientOcclusion")
        ao.inputs["Distance"].default_value = 0.08
        am = N.new("ShaderNodeMapRange")
        am.inputs["To Min"].default_value = 0.45
        L.new(ao.outputs["AO"], am.inputs["Value"])
        mul = N.new("ShaderNodeMixRGB")
        mul.blend_type = "MULTIPLY"
        mul.inputs["Fac"].default_value = 1
        L.new(color_out, mul.inputs["Color1"])
        L.new(am.outputs["Result"], mul.inputs["Color2"])
        color_out = mul.outputs["Color"]
    L.new(color_out, bsdf.inputs["Base Color"])
    L.new(rug_out, bsdf.inputs["Roughness"])
    m.diffuse_color = (*color, 1)
    # ordenar un poco los nodos para que se lean en el Shader Editor
    for i, n in enumerate([x for x in N if x != bsdf and x.type != "OUTPUT_MATERIAL"]):
        n.location = (-900 + (i % 4) * 200, 300 - (i // 4) * 220)
    return m


class FORJA_OT_material(bpy.types.Operator):
    """Crea y asigna un material hard surface. En modo edición se asigna solo a las caras seleccionadas"""
    bl_idname = "forja.material"
    bl_label = "Material Forja"
    bl_options = {"REGISTER", "UNDO"}

    tipo: EnumProperty(name="Tipo", items=TIPOS, default="PINTURA")
    color: FloatVectorProperty(name="Color", subtype="COLOR", size=3, min=0, max=1, default=(0.74, 0.75, 0.79))
    desgaste: BoolProperty(name="Desgaste en bordes (Cycles)", default=True)
    suciedad: BoolProperty(name="Suciedad en rincones", default=True)

    def execute(self, context):
        c = tuple(self.color)
        if self.tipo == "PINTURA":
            m = pintura("Forja Pintura", c, self.desgaste, self.suciedad)
        elif self.tipo == "METAL":
            m = bpy.data.materials.new("Forja Metal")
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*c, 1)
            b.inputs["Metallic"].default_value = 1.0
            b.inputs["Roughness"].default_value = 0.25
            m.diffuse_color = (*c, 1)
        elif self.tipo == "METAL_OSCURO":
            m = util.material("Forja Metal oscuro", (0.06, 0.065, 0.075), 0.7, 0.32)
        elif self.tipo == "GOMA":
            m = util.material("Forja Goma", (0.03, 0.03, 0.032), 0, 0.75)
        elif self.tipo == "LUZ":
            m = bpy.data.materials.new("Forja Luz")
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*c, 1)
            b.inputs["Emission Color"].default_value = (*c, 1)
            b.inputs["Emission Strength"].default_value = 9
            m.diffuse_color = (*c, 1)
        else:
            m = bpy.data.materials.new("Forja Cristal")
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (*c, 1)
            b.inputs["Roughness"].default_value = 0.05
            b.inputs["Transmission Weight"].default_value = 1.0
        if context.mode == "EDIT_MESH":
            o = context.edit_object
            if m.name not in o.data.materials:
                o.data.materials.append(m)
            o.active_material_index = list(o.data.materials).index(m)
            bpy.ops.object.material_slot_assign()
        else:
            for o in [x for x in context.selected_objects if x.type in {"MESH", "CURVE"}]:
                if o.data.materials:
                    o.data.materials[0] = m
                else:
                    o.data.materials.append(m)
        return {"FINISHED"}


CLASES = (FORJA_OT_material,)
