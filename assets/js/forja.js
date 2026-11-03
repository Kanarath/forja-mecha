// Forja Mecha — lógica común: ruta de módulos, progreso, comparadores y lightbox.

export const MODULOS = [
  { n: 0, slug: "m0-preparacion", titulo: "Preparar el hangar", desc: "Blender, addons gratuitos, navegación y tu estudio de render.", proyecto: "Estudio gris de render", listo: true },
  { n: 1, slug: "m1-celda-energia", titulo: "Celda de energía", desc: "Extrude, Inset, Loop Cut y Bevel: las 4 herramientas que más usarás.", proyecto: "Batería del mango del arma", listo: true },
  { n: 2, slug: "m2-sombreado", titulo: "Sombreado limpio", desc: "Normales, n-gons, Smooth by Angle, Harden Normals y Weighted Normal.", proyecto: "Módulo técnico sin artefactos", listo: true },
  { n: 3, slug: "m3-placa-blindaje", titulo: "Placa de blindaje", desc: "Booleanos no destructivos, paneles, rejillas y luces incrustadas.", proyecto: "Placa con paneles y luces", listo: true },
  { n: 4, slug: "m4-cabeza-robot", titulo: "Cabeza de robot", desc: "Subdivision Surface y support loops para curvas limpias.", proyecto: "Casco de androide", listo: true },
  { n: 5, slug: "m5-placa-base", titulo: "Placa base sci-fi", desc: "Kitbash, greebles, cables con curvas y tu biblioteca en el Asset Browser.", proyecto: "Núcleo con módulos y cableado", listo: true },
  { n: 6, slug: "m6-espada-arma", titulo: "Espada-arma", desc: "Blockout, silueta, lenguaje de formas y reparto de detalle.", proyecto: "Gunblade estilo mecha", listo: false },
  { n: 7, slug: "m7-brazo-robotico", titulo: "Brazo robótico", desc: "Pistones, bisagras, rótulas y rigging básico con huesos.", proyecto: "Brazo articulado", listo: false },
  { n: 8, slug: "m8-materiales-render", titulo: "Materiales y render", desc: "Metal procedural, desgaste en bordes, emisivos e iluminación de estudio.", proyecto: "Render de portfolio", listo: false },
  { n: 9, slug: "m9-androide", titulo: "Androide", desc: "Proyecto final: el cuerpo completo, pieza a pieza.", proyecto: "Tu androide", listo: false },
];

// --- almacenamiento seguro (modo privado o almacenamiento bloqueado => sin progreso, pero la web funciona)
const KEY = "forja-mecha:checks";
function loadChecks() {
  try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; }
}
function saveChecks(c) {
  try { localStorage.setItem(KEY, JSON.stringify(c)); } catch { /* sin almacenamiento */ }
}

export function progresoModulo(slug) {
  const checks = loadChecks();
  const total = Number(checks[`${slug}:total`] || 0);
  if (!total) return { hechos: 0, total: 0 };
  let hechos = 0;
  for (const k in checks) if (k.startsWith(slug + ":") && k !== `${slug}:total` && checks[k]) hechos++;
  return { hechos: Math.min(hechos, total), total };
}

// --- checklists de los retos
function initChecklists() {
  const slug = document.body.dataset.modulo;
  const boxes = document.querySelectorAll(".checklist input[type=checkbox]");
  if (!slug || !boxes.length) return;
  const checks = loadChecks();
  checks[`${slug}:total`] = boxes.length;
  saveChecks(checks);
  const out = document.querySelector("[data-progreso]");
  const pinta = () => {
    const done = [...boxes].filter(b => b.checked).length;
    if (out) out.innerHTML = done === boxes.length
      ? `<b>¡Módulo completado!</b> ${done}/${boxes.length} — tu pieza está forjada.`
      : `Progreso del reto: <b>${done}</b>/${boxes.length}`;
  };
  boxes.forEach((b, i) => {
    const id = `${slug}:${b.dataset.id || i}`;
    b.checked = !!checks[id];
    b.addEventListener("change", () => {
      const c = loadChecks();
      c[id] = b.checked;
      saveChecks(c);
      pinta();
    });
  });
  pinta();
}

// --- portada: tarjetas de la ruta
function initRoadmap() {
  const el = document.querySelector("[data-roadmap]");
  if (!el) return;
  el.innerHTML = MODULOS.map(m => {
    const p = progresoModulo(m.slug);
    const pct = p.total ? Math.round((p.hechos / p.total) * 100) : 0;
    const done = p.total && p.hechos === p.total;
    const tag = m.listo ? "a" : "div";
    const href = m.listo ? ` href="modulos/${m.slug}.html"` : "";
    const estado = !m.listo ? "En la forja" : done ? "Completado" : pct ? `${pct}%` : "Disponible";
    return `<${tag} class="mod${m.listo ? "" : " locked"}${done ? " done" : ""}"${href}>
      <div class="badge-num">${String(m.n).padStart(2, "0")}</div>
      <div>
        <h3>${m.titulo}</h3>
        <p>${m.desc}</p>
        <div class="proj">◆ ${m.proyecto}</div>
        ${m.listo ? `<div class="bar"><i style="width:${done ? 100 : pct}%"></i></div>` : ""}
      </div>
      <span class="state">${estado}</span>
    </${tag}>`;
  }).join("");
}

// --- pie de lección: anterior / siguiente
function initPager() {
  const el = document.querySelector("[data-pager]");
  const slug = document.body.dataset.modulo;
  if (!el || !slug) return;
  const i = MODULOS.findIndex(m => m.slug === slug);
  const prev = MODULOS[i - 1], next = MODULOS[i + 1];
  const link = (m, cls, label) => m && m.listo
    ? `<a class="${cls}" href="${m.slug}.html"><small>${label}</small>${String(m.n).padStart(2, "0")} · ${m.titulo}</a>`
    : m ? `<a class="${cls}" href="../index.html#ruta"><small>${label} · en la forja</small>${String(m.n).padStart(2, "0")} · ${m.titulo}</a>` : `<span></span>`;
  el.innerHTML = link(prev, "prev", "← Anterior") + link(next, "next", "Siguiente →");
}

// --- comparador antes/después
function initCompare() {
  document.querySelectorAll(".compare").forEach(c => {
    const after = c.querySelector(".after"), handle = c.querySelector(".handle"), input = c.querySelector("input");
    const set = v => {
      after.style.clipPath = `inset(0 0 0 ${v}%)`;
      handle.style.left = v + "%";
    };
    input.addEventListener("input", () => set(input.value));
    set(input.value);
  });
}

// --- pestañas que cambian una imagen
function initTabs() {
  document.querySelectorAll("[data-tabs]").forEach(box => {
    const img = box.querySelector("img"), cap = box.querySelector("figcaption");
    const btns = box.querySelectorAll(".tabs button");
    btns.forEach(b => b.addEventListener("click", () => {
      btns.forEach(x => x.classList.toggle("on", x === b));
      img.src = b.dataset.src;
      if (cap) cap.innerHTML = b.dataset.cap || "";
    }));
  });
}

// --- lightbox para ampliar renders
function initLightbox() {
  const lb = document.createElement("div");
  lb.className = "lightbox";
  lb.innerHTML = "<img alt=''>";
  document.body.appendChild(lb);
  lb.addEventListener("click", () => lb.classList.remove("on"));
  document.addEventListener("keydown", e => { if (e.key === "Escape") lb.classList.remove("on"); });
  document.addEventListener("click", e => {
    const img = e.target.closest("figure img, img.shot");
    if (!img || img.closest(".compare")) return;
    lb.querySelector("img").src = img.currentSrc || img.src;
    lb.classList.add("on");
  });
}

// --- índice lateral que resalta la sección visible
function initToc() {
  const links = [...document.querySelectorAll(".toc a")];
  if (!links.length) return;
  const obs = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      links.forEach(a => a.classList.toggle("active", a.getAttribute("href") === "#" + en.target.id));
    });
  }, { rootMargin: "-30% 0px -60% 0px" });
  links.forEach(a => {
    const s = document.querySelector(a.getAttribute("href"));
    if (s) obs.observe(s);
  });
}

initRoadmap();
initChecklists();
initPager();
initCompare();
initTabs();
initLightbox();
initToc();
