// <forja-visor>: visor 3D de los modelos exportados desde Blender (.glb).
// Uso:
//   <forja-visor data-modelos="celda_01,celda_02" data-etiquetas="Cilindro|Tapas"
//                data-notas="texto paso 1|texto paso 2" data-malla="on"></forja-visor>
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const BASE = new URL("../models/", import.meta.url);
const loader = new GLTFLoader();
const cache = new Map();

function cargar(nombre) {
  if (!cache.has(nombre)) {
    cache.set(nombre, loader.loadAsync(new URL(nombre + ".glb", BASE).href).then(g => {
      g.scene.traverse(o => {
        if (o.isLineSegments || o.isLine) {
          o.material = new THREE.LineBasicMaterial({ color: 0x0a0c10, transparent: true, opacity: 0.85 });
          o.userData.malla = true;
        } else if (o.isMesh) {
          o.material.polygonOffset = true;
          o.material.polygonOffsetFactor = 1;
          o.material.polygonOffsetUnits = 1;
          o.material.side = THREE.DoubleSide;
          // el emisivo de Blender (fuerza 9) satura en tiempo real: lo suavizamos
          if (o.material.emissiveIntensity > 3) o.material.emissiveIntensity = 3;
        }
      });
      return g.scene;
    }));
  }
  return cache.get(nombre);
}

class ForjaVisor extends HTMLElement {
  connectedCallback() {
    if (this._listo) return;
    this._listo = true;
    this.modelos = (this.dataset.modelos || "").split(",").map(s => s.trim()).filter(Boolean);
    this.etiquetas = (this.dataset.etiquetas || "").split("|");
    this.notas = (this.dataset.notas || "").split("|");
    this.malla = this.dataset.malla !== "off";
    this.innerHTML = `
      <div class="visor">
        <span class="badge3d">3D · ARRASTRA PARA GIRAR · RUEDA PARA ZOOM</span>
        <div class="loading">Cargando modelo…</div>
        <div class="hud">
          ${this.modelos.length > 1 ? this.modelos.map((m, i) =>
            `<button data-i="${i}">${this.etiquetas[i] || i + 1}</button>`).join("") : ""}
          <span class="sep"></span>
          <button data-act="malla">Malla</button>
          <button data-act="giro">Girar</button>
        </div>
      </div>
      <div class="visor-caption"></div>`;
    this.box = this.querySelector(".visor");
    this.caption = this.querySelector(".visor-caption");
    // solo se crea el contexto WebGL cuando el visor entra en pantalla
    this.obs = new IntersectionObserver(es => {
      this.visible = es[0].isIntersecting;
      if (this.visible && !this.renderer) this.init();
    }, { rootMargin: "200px" });
    this.obs.observe(this);
  }

  init() {
    const r = this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    r.setPixelRatio(Math.min(devicePixelRatio, 2));
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.toneMappingExposure = 0.8;
    this.box.prepend(r.domElement);

    this.scene = new THREE.Scene();
    const pm = new THREE.PMREMGenerator(r);
    this.scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = 0.55;
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(-3, 5, 4);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0x9cc8ff, 1.2);
    rim.position.set(3, 2, -4);
    this.scene.add(rim);

    this.cam = new THREE.PerspectiveCamera(35, 1, 0.01, 100);
    this.ctrl = new OrbitControls(this.cam, r.domElement);
    this.ctrl.enableDamping = true;
    this.ctrl.autoRotateSpeed = 1.6;

    this.querySelectorAll(".hud button[data-i]").forEach(b =>
      b.addEventListener("click", () => this.mostrar(Number(b.dataset.i))));
    const bMalla = this.querySelector('[data-act="malla"]');
    bMalla.classList.toggle("on", this.malla);
    bMalla.addEventListener("click", () => {
      this.malla = !this.malla;
      bMalla.classList.toggle("on", this.malla);
      this.aplicarMalla();
    });
    const bGiro = this.querySelector('[data-act="giro"]');
    bGiro.addEventListener("click", () => {
      this.ctrl.autoRotate = !this.ctrl.autoRotate;
      bGiro.classList.toggle("on", this.ctrl.autoRotate);
    });

    new ResizeObserver(() => this.ajustar()).observe(this.box);
    this.ajustar();
    this.mostrar(0, true);
    const loop = () => {
      requestAnimationFrame(loop);
      if (!this.visible) return;
      this.ctrl.update();
      r.render(this.scene, this.cam);
    };
    loop();
  }

  ajustar() {
    const w = this.box.clientWidth, h = this.box.clientHeight;
    this.renderer.setSize(w, h, false);
    this.cam.aspect = w / h;
    this.cam.updateProjectionMatrix();
  }

  aplicarMalla() {
    this.actual?.traverse(o => { if (o.userData.malla) o.visible = this.malla; });
  }

  async mostrar(i, encuadrar = false) {
    this.querySelectorAll(".hud button[data-i]").forEach(b => b.classList.toggle("on", Number(b.dataset.i) === i));
    this.caption.innerHTML = this.notas[i] || "";
    const loading = this.querySelector(".loading");
    loading.style.display = "grid";
    try {
      const modelo = await cargar(this.modelos[i]);
      if (this.actual) this.scene.remove(this.actual);
      this.actual = modelo;
      this.scene.add(modelo);
      this.aplicarMalla();
      if (encuadrar) this.encuadrar(modelo);
      loading.style.display = "none";
      // precarga el resto en segundo plano
      this.modelos.forEach(cargar);
    } catch (e) {
      loading.textContent = "No se pudo cargar el modelo 3D.";
      console.error(e);
    }
  }

  encuadrar(obj) {
    const box = new THREE.Box3().setFromObject(obj);
    const c = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3()).length();
    this.ctrl.target.copy(c);
    this.cam.position.copy(c).add(new THREE.Vector3(0.75, 0.55, 1).normalize().multiplyScalar(size * 1.75));
    this.cam.near = size / 100;
    this.cam.far = size * 20;
    this.cam.updateProjectionMatrix();
    this.ctrl.update();
  }
}

customElements.define("forja-visor", ForjaVisor);
