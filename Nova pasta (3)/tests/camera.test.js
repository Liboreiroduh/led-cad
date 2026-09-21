import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { createCameraViews } from "../src/scene/cameraViews.js";
import { PROJECT, GEOMETRY, mm } from "../src/scene/project.js";

globalThis.window = { matchMedia: () => ({ matches: false }) };

function setup(aspect = 1.5) {
  const camera = new THREE.PerspectiveCamera(37, aspect, 0.05, 150);
  const controls = {
    target: new THREE.Vector3(),
    addEventListener() {},
    removeEventListener() {},
    update() { camera.lookAt(this.target); camera.updateMatrixWorld(); },
  };
  return { camera, controls, views: createCameraViews(camera, controls) };
}

test("all standard views keep the assembly visible on portrait and landscape screens", () => {
  const top = mm(PROJECT.freeHeight + PROJECT.faceHeight);
  const rear = mm(PROJECT.rearOpening) / 2;
  const depth = mm(GEOMETRY.depth);
  const base = mm(PROJECT.baseDiameter) / 2;
  const points = [];
  for (const x of [-rear, rear]) {
    for (const y of [mm(PROJECT.freeHeight), top]) {
      points.push(new THREE.Vector3(x, y, depth));
      points.push(new THREE.Vector3(0, y, 0));
    }
  }
  for (const x of [-base, base])
    for (const z of [-base, base]) points.push(new THREE.Vector3(x, 0, z));

  for (const aspect of [0.55, 1, 1.7, 2.5]) {
    const { camera, views } = setup(aspect);
    for (const name of ["perspective", "front", "side", "top"]) {
      views.goTo(name, true);
      for (const point of points) {
        const projected = point.clone().project(camera);
        assert.ok(Math.abs(projected.x) < 1 && Math.abs(projected.y) < 1,
          `${name}, aspect ${aspect}: vertex fell outside viewport`);
        assert.ok(projected.z > -1 && projected.z < 1, "vertex lies inside clipping range");
      }
    }
    views.dispose();
  }
});

test("camera transitions finish and cancellation preserves user control", () => {
  const { camera, controls, views } = setup();
  views.goTo("perspective", true);
  const initial = camera.position.clone();
  views.goTo("side");
  assert.equal(views.update(0.2), true);
  assert.ok(camera.position.distanceTo(initial) > 0.01);
  views.cancel();
  const cancelled = camera.position.clone();
  assert.equal(views.update(0.9), false);
  assert.ok(camera.position.equals(cancelled));
  views.goTo("top");
  assert.equal(views.update(0.9), false);
  controls.update();
  assert.ok(camera.position.y > controls.target.y + 1);
  assert.equal(views.currentView, "top");
});

test("resizing a manual view retains its angle and recovers safe framing", () => {
  const { camera, controls, views } = setup(2);
  views.goTo("perspective", true);
  views.cancel();
  const direction = camera.position.clone().sub(controls.target).normalize();
  camera.aspect = 0.55;
  camera.updateProjectionMatrix();
  views.resize();
  assert.ok(camera.position.clone().sub(controls.target).normalize().distanceTo(direction) < 1e-8);
  controls.target.set(100, -100, 100);
  views.update(0.01);
  assert.ok(Math.abs(controls.target.x) < 3 && controls.target.y > 0 && controls.target.z < 5);
});
