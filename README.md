# Forja Mecha

Web para aprender **modelado hard surface en Blender** (robots, androides y armas de estilo mecha) solo con herramientas gratuitas.

Cada módulo termina con una pieza hecha en Blender. Las imágenes y los modelos 3D de la web se generan con el propio Blender a partir de [`tools/forja_build.py`](tools/forja_build.py).

## Ruta

| # | Módulo | Estado |
|---|---|---|
| 00 | Preparar el hangar | ✅ |
| 01 | Celda de energía | ✅ |
| 02 | Sombreado limpio | ✅ |
| 03 | Placa de blindaje (booleanos) | ✅ |
| 04 | Cabeza de robot (subdivisión) | ✅ |
| 05 | Placa base sci-fi (kitbash) | 🔨 |
| 06 | Espada-arma (diseño de formas) | 🔨 |
| 07 | Brazo robótico (mecánica y rigging) | 🔨 |
| 08 | Materiales y render | 🔨 |
| 09 | Androide (proyecto final) | 🔨 |

## Estructura

```
index.html, atajos.html   portada y entrenador de atajos
modulos/                  una página por lección
assets/css, assets/js     estilos, progreso y visor 3D (three.js)
assets/img                renders generados con Blender
assets/models             cada paso exportado a .glb
assets/blend              archivos .blend de referencia
assets/scripts            scripts de Blender para el alumno (revisor de malla)
tools/forja_build.py      genera todos los renders y modelos
```

## Regenerar renders y modelos

```bash
blender -b --factory-startup --python tools/forja_build.py -- all
```

`workbench` genera solo las capturas de paso a paso (rápido) y `eevee` solo los renders bonitos.

## Ver en local

Cualquier servidor estático vale, por ejemplo:

```bash
npx http-server -p 5173
```
