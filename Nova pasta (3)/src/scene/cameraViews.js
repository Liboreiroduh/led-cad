import * as THREE from "three";
import { PROJECT, GEOMETRY, mm } from "./project.js";

// Camera framing uses the actual assembly size and the current viewport ratio.
const FRAME_PADDING = 1.16;
const TRANSITION_SECONDS = 0.85;

export function createCameraViews(camera, controls) {
  const depth = mm(GEOMETRY.depth);
  const totalHeight = mm(PROJECT.freeHeight + PROJECT.faceHeight);
  const halfWidth = mm(PROJECT.rearOpening) / 2;
  const target = new THREE.Vector3(0, totalHeight / 2, depth / 2);
  const bounds = new THREE.Box3(
    new THREE.Vector3(-halfWidth - 0.3, -0.14, -0.62),
    new THREE.Vector3(halfWidth + 0.3, totalHeight + 0.35, depth + 0.42),
  );
  const corners = [];
  for (const x of [bounds.min.x, bounds.max.x])
    for (const y of [bounds.min.y, bounds.max.y])
      for (const z of [bounds.min.z, bounds.max.z])
        corners.push(new THREE.Vector3(x, y, z));

  const directions = {
    perspective: new THREE.Vector3(0.08, 0.5, -1).normalize(),
    front: new THREE.Vector3(0, 0, -1),
    side: new THREE.Vector3(1, 0, 0),
    // A tiny frontward offset keeps the front vertex toward the bottom of the plan.
    top: new THREE.Vector3(0, 1, -0.006).normalize(),
  };
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const right = new THREE.Vector3();
  const up = new THREE.Vector3();
  const relative = new THREE.Vector3();
  const offset = new THREE.Vector3();
  const previousTarget = new THREE.Vector3();
  let animation = null;
  let currentView = "perspective";
  let initialized = false;
  let previousAspect = camera.aspect;

  controls.minDistance = 3.3;
  controls.maxDistance = 45;
  controls.minPolarAngle = 0.005;
  controls.maxPolarAngle = Math.PI / 2 + 0.08;
  controls.enableDamping = true;
  controls.dampingFactor = 0.085;

  function fitDistance(direction) {
    const verticalTan = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
    const horizontalTan = verticalTan * Math.max(camera.aspect, 0.15);
    right.crossVectors(camera.up, direction).normalize();
    up.crossVectors(direction, right).normalize();
    let distance = controls.minDistance;
    for (const corner of corners) {
      relative.copy(corner).sub(target);
      const pointDepth = relative.dot(direction);
      distance = Math.max(
        distance,
        pointDepth +
          (Math.abs(relative.dot(right)) * FRAME_PADDING) / horizontalTan,
        pointDepth + (Math.abs(relative.dot(up)) * FRAME_PADDING) / verticalTan,
      );
    }
    return distance;
  }

  function clearDamping() {
    // OrbitControls keeps small deltas after dragging; consume them before a preset.
    const damping = controls.enableDamping;
    controls.enableDamping = false;
    controls.update();
    controls.enableDamping = damping;
  }

  function goTo(name, immediate = false) {
    if (!directions[name]) return;
    clearDamping();
    currentView = name;
    const direction = directions[name];
    const distance = fitDistance(direction);
    controls.maxDistance = Math.max(45, distance * 2.1);
    const destination = target.clone().addScaledVector(direction, distance);
    if (immediate || reducedMotion.matches || !initialized) {
      animation = null;
      controls.target.copy(target);
      camera.position.copy(destination);
      camera.lookAt(target);
      controls.update();
    } else {
      animation = {
        elapsed: 0,
        from: camera.position.clone(),
        to: destination,
        fromTarget: controls.target.clone(),
        toTarget: target.clone(),
      };
    }
    initialized = true;
  }

  function cancel() {
    animation = null;
    currentView = null;
  }

  function constrainTarget() {
    previousTarget.copy(controls.target);
    controls.target.x = THREE.MathUtils.clamp(controls.target.x, -1.8, 1.8);
    controls.target.y = THREE.MathUtils.clamp(
      controls.target.y,
      0.9,
      totalHeight - 0.5,
    );
    controls.target.z = THREE.MathUtils.clamp(
      controls.target.z,
      -0.8,
      depth + 0.8,
    );
    camera.position.add(relative.copy(controls.target).sub(previousTarget));
  }

  function update(deltaSeconds) {
    if (animation) {
      animation.elapsed += Math.max(0, deltaSeconds);
      const progress = Math.min(animation.elapsed / TRANSITION_SECONDS, 1);
      const eased = progress * progress * (3 - 2 * progress);
      camera.position.lerpVectors(animation.from, animation.to, eased);
      controls.target.lerpVectors(
        animation.fromTarget,
        animation.toTarget,
        eased,
      );
      camera.lookAt(controls.target);
      if (progress === 1) animation = null;
    }
    constrainTarget();
    return Boolean(animation);
  }

  function resize() {
    if (!initialized) return;
    if (currentView) {
      goTo(currentView, true);
    } else if (Math.abs(previousAspect - camera.aspect) > 0.01) {
      // Preserve a manually chosen angle, but bring the assembly back into view.
      offset.copy(camera.position).sub(controls.target).normalize();
      const distance = fitDistance(offset);
      controls.target.copy(target);
      camera.position.copy(target).addScaledVector(offset, distance);
      controls.maxDistance = Math.max(45, distance * 2.1);
      controls.update();
    }
    previousAspect = camera.aspect;
  }

  controls.addEventListener("start", cancel);
  return {
    goTo,
    update,
    resize,
    cancel,
    reset: () => goTo("perspective"),
    get currentView() {
      return currentView;
    },
    dispose() {
      controls.removeEventListener("start", cancel);
      animation = null;
    },
  };
}
