import * as THREE from "three";
import { PROJECT, GEOMETRY, mm } from "./project.js";

export function createDimensions(scene, labelContainer) {
  const group = new THREE.Group();
  group.name = "technical-dimensions";
  const material = new THREE.LineBasicMaterial({
    color: 0x6a8052,
    transparent: true,
    opacity: 0.8,
    depthTest: false,
    depthWrite: false,
  });
  const positions = [];
  const labels = [];
  const depth = mm(GEOMETRY.depth);
  const halfRear = mm(PROJECT.rearOpening) / 2;
  const bottom = mm(PROJECT.freeHeight);
  const top = bottom + mm(PROJECT.faceHeight);
  const postZ = mm(PROJECT.visual.postZ);
  const vector = (x, y, z) => new THREE.Vector3(x, y, z);

  function segment(a, b) {
    positions.push(...a.toArray(), ...b.toArray());
  }

  function dimension(text, start, end, options = {}) {
    segment(start, end);
    const tick = options.tick || vector(0, 0.075, 0);
    segment(start.clone().sub(tick), start.clone().add(tick));
    segment(end.clone().sub(tick), end.clone().add(tick));
    if (options.from) segment(options.from, start);
    if (options.to) segment(options.to, end);
    const label = document.createElement("span");
    label.className = `dimension-label${options.small ? " dimension-label--small" : ""}`;
    label.textContent = text;
    label.style.transform = "translate(-50%, -50%)";
    label.hidden = true;
    labelContainer.append(label);
    labels.push({
      element: label,
      point: options.label || start.clone().lerp(end, 0.5),
      offset: options.offset || [0, -12],
    });
  }

  dimension(
    `${PROJECT.faceWidth} mm`,
    vector(-0.25, top + 0.3, 0),
    vector(-halfRear - 0.25, top + 0.3, depth),
    {
      from: vector(0, top, 0),
      to: vector(-halfRear, top, depth),
      label: vector(-halfRear / 2 - 0.25, top + 0.3, depth / 2),
    },
  );
  dimension(
    `${PROJECT.faceHeight} mm`,
    vector(halfRear + 0.3, bottom, depth),
    vector(halfRear + 0.3, top, depth),
    {
      tick: vector(0.075, 0, 0),
      from: vector(halfRear, bottom, depth),
      to: vector(halfRear, top, depth),
      offset: [-2, 0],
    },
  );
  dimension(
    `${PROJECT.freeHeight} mm`,
    vector(-0.6, 0, -0.22),
    vector(-0.6, bottom, -0.22),
    {
      tick: vector(0.075, 0, 0),
      from: vector(0, 0, postZ),
      to: vector(0, bottom, 0),
      offset: [-18, 0],
    },
  );
  dimension(
    `${PROJECT.rearOpening} mm · traseira`,
    vector(-halfRear, top + 0.3, depth + 0.38),
    vector(halfRear, top + 0.3, depth + 0.38),
    {
      from: vector(-halfRear, top, depth),
      to: vector(halfRear, top, depth),
      small: true,
      offset: [0, -12],
    },
  );
  const postRadius = mm(PROJECT.postDiameter) / 2;
  const postStart = vector(-postRadius, bottom * 0.42, postZ);
  const postEnd = vector(postRadius, bottom * 0.42, postZ);
  const postLabel = vector(0.77, bottom * 0.43, -0.13);
  segment(postEnd, postLabel);
  dimension(`Poste Ø${PROJECT.postDiameter} mm`, postStart, postEnd, {
    small: true,
    label: postLabel,
    offset: [-3, -8],
  });
  const baseRadius = mm(PROJECT.baseDiameter) / 2;
  dimension(
    `Base Ø${PROJECT.baseDiameter} mm`,
    vector(-baseRadius, 0.055, postZ - baseRadius - 0.2),
    vector(baseRadius, 0.055, postZ - baseRadius - 0.2),
    {
      from: vector(-baseRadius, 0.025, postZ),
      to: vector(baseRadius, 0.025, postZ),
      small: true,
      offset: [0, 17],
    },
  );

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  const lines = new THREE.LineSegments(geometry, material);
  lines.renderOrder = 20;
  group.add(lines);
  scene.add(group);
  const projected = new THREE.Vector3();
  let visible = false;
  group.visible = false;

  function setVisible(value) {
    visible = Boolean(value);
    group.visible = visible;
    if (!visible)
      labels.forEach(({ element }) => {
        element.hidden = true;
      });
  }

  function update(camera, width, height) {
    if (!visible || width < 1 || height < 1) return;
    const occupied = [];
    for (const { element, point, offset } of labels) {
      projected.copy(point).project(camera);
      element.hidden =
        projected.z < -1 ||
        projected.z > 1 ||
        Math.abs(projected.x) > 1.12 ||
        Math.abs(projected.y) > 1.08;
      if (element.hidden) continue;
      const labelWidth = element.offsetWidth || 95;
      const labelHeight = element.offsetHeight || 26;
      let x = ((projected.x + 1) * width) / 2 + offset[0];
      let y = ((1 - projected.y) * height) / 2 + offset[1];
      const minY = labelHeight / 2 + 12;
      const maxY = height - labelHeight / 2 - 18;
      x = THREE.MathUtils.clamp(
        x,
        labelWidth / 2 + 8,
        width - labelWidth / 2 - 8,
      );
      y = THREE.MathUtils.clamp(y, minY, maxY);
      const intersects = (candidate) =>
        occupied.some(
          (box) =>
            Math.abs(x - box.x) < (labelWidth + box.width) / 2 + 6 &&
            Math.abs(candidate - box.y) < (labelHeight + box.height) / 2 + 5,
        );
      if (intersects(y)) {
        for (let step = 1; step < 8; step++) {
          const shift =
            Math.ceil(step / 2) * (labelHeight + 8) * (step % 2 ? 1 : -1);
          const candidate = THREE.MathUtils.clamp(y + shift, minY, maxY);
          if (!intersects(candidate)) {
            y = candidate;
            break;
          }
        }
      }
      element.style.left = `${x.toFixed(1)}px`;
      element.style.top = `${y.toFixed(1)}px`;
      occupied.push({ x, y, width: labelWidth, height: labelHeight });
    }
  }

  return {
    setVisible,
    update,
    dispose() {
      scene.remove(group);
      geometry.dispose();
      material.dispose();
      labels.forEach(({ element }) => element.remove());
    },
  };
}
