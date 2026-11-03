"""
Forja Tools · herramientas hard surface gratuitas de Forja Mecha
https://kanarath.github.io/forja-mecha/addon.html

Panel en la barra lateral (N) → pestaña «Forja» · menú circular: Shift + Alt + Q
"""

bl_info = {
    "name": "Forja Tools",
    "author": "Forja Mecha",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Vista 3D → Barra lateral (N) → Forja · Shift+Alt+Q",
    "description": "Herramientas hard surface gratuitas: afilar, cortes no destructivos, kitbash y revisión",
    "category": "Mesh",
}

import bpy

from . import acabado, booleanos, edicion, escena, materiales, piezas, revisar, simetria, ui

MODULOS = (acabado, booleanos, simetria, edicion, piezas, materiales, revisar, escena, ui)
_atajos = []


def register():
    for m in MODULOS:
        for c in m.CLASES:
            bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_add.append(ui.menu_anadir)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        for mapa in ("Object Mode", "Mesh"):
            km = kc.keymaps.new(name=mapa, space_type="EMPTY")
            kmi = km.keymap_items.new("wm.call_menu_pie", "Q", "PRESS", shift=True, alt=True)
            kmi.properties.name = ui.FORJA_MT_pie.bl_idname
            _atajos.append((km, kmi))


def unregister():
    for km, kmi in _atajos:
        km.keymap_items.remove(kmi)
    _atajos.clear()
    bpy.types.VIEW3D_MT_add.remove(ui.menu_anadir)
    for m in reversed(MODULOS):
        for c in reversed(m.CLASES):
            bpy.utils.unregister_class(c)
