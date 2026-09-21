import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { createLedStructure } from "./createLedStructure.js";
import { createCameraViews } from "./cameraViews.js";
import { createDimensions } from "./createDimensions.js";
import { GEOMETRY, mm } from "./project.js";

const STUDIO = {
  gridSize: 16,
  gridDivisions: 32,
  floorSize: 200,
  shadowSize: 1024,
  pixelRatioLimit: 1.8,
  cameraFov: 37,
  near: 0.05,
  far: 150,
};

export function createScene(container, { onOrbit, onError } = {}) {
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0xf4f6ef, 0.023);
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: "low-power",
  });
  renderer.setClearColor(0xf4f6ef, 0);
  renderer.setPixelRatio(
    Math.min(window.devicePixelRatio || 1, STUDIO.pixelRatioLimit),
  );
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.25;
  const canvas = renderer.domElement;
  canvas.tabIndex = 0;
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    "Painel LED em V tridimensional. Arraste para girar, use a roda do mouse ou dois dedos para zoom. As setas movem a vista; os botões acima escolhem o ângulo.",
  );
  container.prepend(canvas);

  const camera = new THREE.PerspectiveCamera(
    STUDIO.cameraFov,
    1,
    STUDIO.near,
    STUDIO.far,
  );
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.085;
  controls.rotateSpeed = 0.65;
  controls.zoomSpeed = 0.8;
  controls.panSpeed = 0.45;
  controls.screenSpacePanning = true;
  controls.minPolarAngle = 0.005;
  controls.maxPolarAngle = Math.PI / 2 + 0.12;
  controls.listenToKeyEvents(canvas);
  const views = createCameraViews(camera, controls);

  const generator = new THREE.PMREMGenerator(renderer);
  const environmentScene = new RoomEnvironment();
  const environment = generator.fromScene(environmentScene, 0.04);
  scene.environment = environment.texture;
  scene.environmentIntensity = 0.65;
  environmentScene.dispose();
  generator.dispose();
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd4deca, 2));
  const sun = new THREE.DirectionalLight(0xfff9ed, 3.8);
  sun.position.set(-5, 11, -6);
  sun.castShadow = true;
  sun.shadow.mapSize.set(STUDIO.shadowSize, STUDIO.shadowSize);
  Object.assign(sun.shadow.camera, {
    left: -7,
    right: 7,
    top: 9,
    bottom: -7,
    near: 0.5,
    far: 35,
  });
  sun.shadow.normalBias = 0.02;
  sun.shadow.bias = -0.0003;
  sun.shadow.radius = 3;
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0xe6edf5, 2);
  rim.position.set(5, 6, 4);
  scene.add(rim);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(STUDIO.floorSize, STUDIO.floorSize),
    new THREE.ShadowMaterial({ color: 0x768466, opacity: 0.17 }),
  );
  ground.name = "reference-floor";
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.006;
  ground.receiveShadow = true;
  scene.add(ground);
  const grid = new THREE.GridHelper(
    STUDIO.gridSize,
    STUDIO.gridDivisions,
    0xc3cdb8,
    0xd5dccd,
  );
  grid.position.set(0, -0.004, mm(GEOMETRY.depth) / 2);
  grid.material.transparent = true;
  grid.material.opacity = 0.43;
  grid.material.depthWrite = false;
  scene.add(grid);

  const model = createLedStructure();
  scene.add(model.group);
  const dimensions = createDimensions(
    scene,
    container.querySelector("#dimension-overlay"),
  );
  dimensions.setVisible(false);
  const orientationContainer = container.querySelector("#direction-overlay");
  const markers = [
    {
      label: "FRENTE",
      point: new THREE.Vector3(0, 0.025, -0.6),
      className: "front",
    },
    {
      label: "TRASEIRA",
      point: new THREE.Vector3(0, 0.025, mm(GEOMETRY.depth) + 1),
      className: "rear",
    },
  ].map((marker) => {
    const element = document.createElement("span");
    element.className = `direction-label ${marker.className}`;
    element.textContent = marker.label;
    orientationContainer.append(element);
    return { ...marker, element };
  });

  let width = 1;
  let height = 1;
  let request = 0;
  let lastTime = 0;
  let disposed = false;
  let measureEnabled = false;
  let exploded = false;
  let assemblyMoving = false;
  const projected = new THREE.Vector3();

  function invalidate() {
    if (!request && !disposed && !document.hidden) {
      container.setAttribute("aria-busy", "true");
      request = requestAnimationFrame(render);
    }
  }

  function render(time) {
    request = 0;
    if (disposed) return;
    const delta = Math.min((time - lastTime) / 1000 || 1 / 60, 0.05);
    lastTime = time;
    const cameraMoving = views.update(delta);
    const orbitMoving = controls.update();
    assemblyMoving = model.update(delta);
    dimensions.setVisible(measureEnabled && !exploded && !assemblyMoving);
    renderer.render(scene, camera);
    dimensions.update(camera, width, height);
    for (const { point, element } of markers) {
      projected.copy(point).project(camera);
      const x = ((projected.x + 1) * width) / 2;
      const y = ((1 - projected.y) * height) / 2;
      element.hidden =
        projected.z < -1 ||
        projected.z > 1 ||
        x < 35 ||
        x > width - 35 ||
        y < 48 ||
        y > height - 43;
      element.style.left = `${x}px`;
      element.style.top = `${y}px`;
    }
    const moving = Boolean(cameraMoving || orbitMoving || assemblyMoving);
    container.setAttribute("aria-busy", String(moving));
    if (moving) invalidate();
  }

  function resize() {
    width = Math.max(container.clientWidth, 1);
    height = Math.max(container.clientHeight, 1);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    views.resize();
    invalidate();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  const startOrbit = () => {
    views.cancel();
    onOrbit?.();
    invalidate();
  };
  controls.addEventListener("start", startOrbit);
  controls.addEventListener("change", invalidate);
  const onVisible = () => {
    if (!document.hidden) {
      lastTime = 0;
      invalidate();
    }
  };
  document.addEventListener("visibilitychange", onVisible);
  const contextLost = (event) => {
    event.preventDefault();
    onError?.(
      "O navegador interrompeu a visualização 3D. Recarregue para continuar.",
    );
  };
  canvas.addEventListener("webglcontextlost", contextLost);
  resize();
  views.goTo("perspective", true);
  invalidate();

  return {
    scene,
    camera,
    controls,
    model,
    renderer,
    view(name) {
      views.goTo(name);
      invalidate();
    },
    setMode(mode) {
      model.setMode(mode);
      invalidate();
    },
    setDimensions(value) {
      measureEnabled = value;
      invalidate();
    },
    setExploded(value) {
      exploded = value;
      model.setExploded(value);
      invalidate();
    },
    zoom(factor) {
      views.cancel();
      const offset = camera.position.clone().sub(controls.target);
      offset.setLength(
        THREE.MathUtils.clamp(
          offset.length() * factor,
          controls.minDistance,
          controls.maxDistance,
        ),
      );
      camera.position.copy(controls.target).add(offset);
      onOrbit?.();
      invalidate();
    },
    reset() {
      exploded = false;
      measureEnabled = false;
      model.setExploded(false);
      model.setMode("complete");
      views.reset();
      invalidate();
    },
    dispose() {
      disposed = true;
      cancelAnimationFrame(request);
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisible);
      canvas.removeEventListener("webglcontextlost", contextLost);
      controls.removeEventListener("start", startOrbit);
      controls.removeEventListener("change", invalidate);
      views.dispose?.();
      controls.dispose();
      dimensions.dispose();
      model.dispose();
      ground.geometry.dispose();
      ground.material.dispose();
      grid.geometry.dispose();
      grid.material.dispose();
      sun.shadow.dispose();
      environment.dispose();
      renderer.dispose();
      canvas.remove();
      markers.forEach((marker) => marker.element.remove());
    },
  };
}
