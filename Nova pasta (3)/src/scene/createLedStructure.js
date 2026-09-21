import * as THREE from "three";
import { PROJECT, GEOMETRY, mm } from "./project.js";

const STYLE = {
  panel: 0x222b31,
  led: 0x152127,
  steel: 0x9aa7ac,
  darkSteel: 0x63727c,
  edges: 0x607780,
  wire: 0x27575b,
  animationSpeed: 7,
  animationEpsilon: 0.0001,
  cylinderSegments: 48,
  wireCylinderGenerators: 8,
};

/** Procedural assembly. Thicknesses/steel members are illustrative, not engineered. */
export function createLedStructure() {
  const group = new THREE.Group();
  group.name = "led-collor-v-assembly";
  group.userData.dimensions = PROJECT;
  const dimensions = PROJECT.visual;
  const width = mm(PROJECT.faceWidth);
  const height = mm(PROJECT.faceHeight);
  const depth = mm(GEOMETRY.depth);
  const freeHeight = mm(PROJECT.freeHeight);
  const profile = mm(dimensions.profileSize);
  const cabinetDepth = mm(dimensions.cabinetDepth);
  const ledDepth = mm(dimensions.ledDepth);
  const frameDepth = mm(dimensions.frameDepth);
  const postZ = mm(dimensions.postZ);
  const miterSlope = 1 / Math.tan(GEOMETRY.halfAngle);
  const apexProfileInset = (cabinetDepth + frameDepth) * miterSlope;
  const apexBraceInset =
    (cabinetDepth + frameDepth + mm(dimensions.braceSize)) * miterSlope +
    profile;
  const parts = [];
  const solids = [];
  const edgeLines = [];
  const wires = [];
  const panelGroups = [];
  const geometries = new Set();
  const materials = new Set();
  const textures = new Set();
  let explodedTarget = 0;
  let explodedAmount = 0;
  let disposed = false;

  const keepGeometry = (geometry) => {
    geometries.add(geometry);
    return geometry;
  };
  const keepMaterial = (material) => {
    materials.add(material);
    return material;
  };
  const steelMaterial = keepMaterial(
    new THREE.MeshStandardMaterial({
      color: STYLE.steel,
      metalness: 0.76,
      roughness: 0.35,
    }),
  );
  const darkSteelMaterial = keepMaterial(
    new THREE.MeshStandardMaterial({
      color: STYLE.darkSteel,
      metalness: 0.7,
      roughness: 0.4,
    }),
  );
  const panelMaterial = keepMaterial(
    new THREE.MeshStandardMaterial({
      color: STYLE.panel,
      metalness: 0.28,
      roughness: 0.72,
    }),
  );
  const texture = createLedTexture();
  if (texture) textures.add(texture);
  const ledMaterial = keepMaterial(
    new THREE.MeshStandardMaterial({
      color: STYLE.led,
      map: texture,
      emissive: 0x14343c,
      emissiveIntensity: 0.13,
      emissiveMap: texture,
      roughness: 0.91,
      metalness: 0.05,
    }),
  );
  const edgeMaterial = keepMaterial(
    new THREE.LineBasicMaterial({
      color: STYLE.edges,
      transparent: true,
      opacity: 0.48,
    }),
  );
  const wireMaterial = keepMaterial(
    new THREE.LineBasicMaterial({
      color: STYLE.wire,
      transparent: true,
      opacity: 0.85,
    }),
  );
  const edgesCache = new Map();

  function mesh(
    geometry,
    material,
    parent,
    name,
    showEdges = false,
    wire = true,
  ) {
    const object = new THREE.Mesh(geometry, material);
    object.name = name;
    object.castShadow = true;
    object.receiveShadow = true;
    parent.add(object);
    solids.push(object);
    if (showEdges || wire) {
      let edges = edgesCache.get(geometry);
      if (!edges) {
        edges = keepGeometry(
          geometry.type === "CylinderGeometry" &&
            geometry.parameters.radialSegments > 6
            ? cylinderOutline(geometry.parameters)
            : new THREE.EdgesGeometry(geometry, 24),
        );
        edgesCache.set(geometry, edges);
      }
      if (showEdges) {
        const outline = new THREE.LineSegments(edges, edgeMaterial);
        object.add(outline);
        edgeLines.push(outline);
      }
      if (wire) {
        const outline = new THREE.LineSegments(edges, wireMaterial);
        outline.visible = false;
        // Sibling lines remain visible when the filled mesh is hidden.
        parent.add(outline);
        wires.push({ outline, source: object });
      }
    }
    return object;
  }

  function box(w, h, d, parent, name, material = steelMaterial, edges = false) {
    return mesh(
      keepGeometry(new THREE.BoxGeometry(w, h, d)),
      material,
      parent,
      name,
      edges,
    );
  }

  function movable(name, offset) {
    const part = new THREE.Group();
    part.name = name;
    group.add(part);
    parts.push({ part, origin: part.position.clone(), offset });
    return part;
  }

  // Bevel the apex-facing end against the V's centre plane. Keeping each
  // housing/profile in its own half-space prevents it emerging through the
  // opposite LED face, while the exact external face plane stays unchanged.
  function miterAtApex(geometry, centerX, centerZ, apexAtStart) {
    const positions = geometry.getAttribute("position");
    for (let index = 0; index < positions.count; index++) {
      const x = positions.getX(index) + centerX;
      const inwardDepth = Math.max(0, -(positions.getZ(index) + centerZ));
      const minimumDistance = inwardDepth * miterSlope;
      const clippedX = apexAtStart
        ? Math.max(x, minimumDistance)
        : Math.min(x, width - minimumDistance);
      positions.setX(index, clippedX - centerX);
    }
    positions.needsUpdate = true;
    geometry.computeVertexNormals();
    return geometry;
  }

  function beamBetween(
    start,
    end,
    size,
    parent,
    name,
    material = darkSteelMaterial,
  ) {
    const distance = start.distanceTo(end);
    const beam = box(size, distance, size, parent, name, material);
    beam.position.copy(start).add(end).multiplyScalar(0.5);
    beam.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      end.clone().sub(start).normalize(),
    );
    return beam;
  }

  const shellGeometry = keepGeometry(
    new THREE.BoxGeometry(
      mm(PROJECT.cabinetWidth - dimensions.cabinetGap),
      mm(PROJECT.cabinetHeight - dimensions.cabinetGap),
      cabinetDepth - ledDepth,
    ),
  );
  const ledGeometry = keepGeometry(
    new THREE.BoxGeometry(
      mm(PROJECT.cabinetWidth - dimensions.ledInset * 2),
      mm(PROJECT.cabinetHeight - dimensions.ledInset * 2),
      ledDepth,
    ),
  );

  for (const sign of [-1, 1]) {
    const side = sign < 0 ? "left" : "right";
    const outside = new THREE.Vector3(
      sign * Math.cos(GEOMETRY.halfAngle),
      0,
      -Math.sin(GEOMETRY.halfAngle),
    );
    const face = movable(
      `face-${side}`,
      outside
        .clone()
        .multiplyScalar(mm(dimensions.explodedFaceOffset))
        .add(new THREE.Vector3(0, mm(dimensions.explodedFaceLift), 0)),
    );
    face.userData.kind = "face";
    face.userData.side = side;
    face.userData.nominalWidth = width;
    face.userData.nominalHeight = height;
    face.userData.start = [0, freeHeight, 0];
    face.userData.end = [sign * mm(PROJECT.rearOpening / 2), freeHeight, depth];
    const frame = movable(
      `frame-${side}`,
      outside
        .clone()
        .multiplyScalar(mm(dimensions.explodedFrameOffset))
        .add(new THREE.Vector3(0, mm(dimensions.explodedFrameLift), 0)),
    );
    frame.userData.kind = "frame";
    // Local +Z points outside on both faces; LED planes meet at the exact apex.
    for (const part of [face, frame]) {
      part.position.set(
        sign > 0 ? mm(PROJECT.rearOpening / 2) : 0,
        freeHeight,
        sign > 0 ? depth : 0,
      );
      part.rotation.y =
        sign > 0
          ? Math.PI / 2 + GEOMETRY.halfAngle
          : -Math.PI / 2 - GEOMETRY.halfAngle;
      parts.find((entry) => entry.part === part).origin.copy(part.position);
    }
    panelGroups.push(face);
    const apexColumn = sign < 0 ? 0 : PROJECT.columns - 1;
    const shellCenterZ = -(cabinetDepth + ledDepth) / 2;
    const apexShellGeometry = keepGeometry(
      miterAtApex(
        shellGeometry.clone(),
        mm((apexColumn + 0.5) * PROJECT.cabinetWidth),
        shellCenterZ,
        sign < 0,
      ),
    );

    for (let row = 0; row < PROJECT.rows; row++) {
      for (let column = 0; column < PROJECT.columns; column++) {
        const cabinet = new THREE.Group();
        cabinet.name = `cabinet-${side}-${row + 1}-${column + 1}`;
        cabinet.userData = {
          kind: "cabinet",
          side,
          row,
          column,
          nominalWidth: mm(PROJECT.cabinetWidth),
          nominalHeight: mm(PROJECT.cabinetHeight),
          depth: cabinetDepth,
        };
        cabinet.position.set(
          mm((column + 0.5) * PROJECT.cabinetWidth),
          mm((row + 0.5) * PROJECT.cabinetHeight),
          0,
        );
        face.add(cabinet);
        const shell = mesh(
          column === apexColumn ? apexShellGeometry : shellGeometry,
          panelMaterial,
          cabinet,
          "cabinet-shell",
          true,
        );
        // The housing ends at the LED layer's back, avoiding coplanar visible
        // surfaces while retaining the precise 100 mm total cabinet depth.
        shell.position.z = shellCenterZ;
        const screen = mesh(
          ledGeometry,
          ledMaterial,
          cabinet,
          "led-surface",
          false,
          false,
        );
        screen.position.z = -ledDepth / 2;
      }
    }

    // Apex uprights sit far enough along the face to fit behind both panels.
    // Other profiles retain their nominal positions in the cabinet grid.
    for (let column = 0; column <= PROJECT.columns; column++) {
      const upright = box(
        profile,
        height,
        frameDepth,
        frame,
        `vertical-profile-${column}`,
      );
      upright.position.set(
        column === 0
          ? (sign < 0 ? apexProfileInset : 0) + profile / 2
          : column === PROJECT.columns
            ? width - (sign > 0 ? apexProfileInset : 0) - profile / 2
            : mm(column * PROJECT.cabinetWidth),
        height / 2,
        -cabinetDepth - frameDepth / 2,
      );
    }
    for (let row = 0; row <= PROJECT.rows; row++) {
      const rail = mesh(
        keepGeometry(
          miterAtApex(
            new THREE.BoxGeometry(width, profile, frameDepth),
            width / 2,
            -cabinetDepth - frameDepth / 2,
            sign < 0,
          ),
        ),
        steelMaterial,
        frame,
        `horizontal-profile-${row}`,
      );
      rail.position.set(
        width / 2,
        row === 0
          ? profile / 2
          : row === PROJECT.rows
            ? height - profile / 2
            : mm(row * PROJECT.cabinetHeight),
        -cabinetDepth - frameDepth / 2,
      );
    }
    // Slim diagonal straps make the rear support legible in the structure view.
    const braceZ = -cabinetDepth - frameDepth - mm(dimensions.braceSize) / 2;
    for (let row = 0; row < PROJECT.rows; row += 2) {
      const lowY = mm(row * PROJECT.cabinetHeight) + profile;
      const highY = mm((row + 2) * PROJECT.cabinetHeight) - profile;
      beamBetween(
        new THREE.Vector3(sign < 0 ? apexBraceInset : profile, lowY, braceZ),
        new THREE.Vector3(
          width - (sign > 0 ? apexBraceInset : profile),
          highY,
          braceZ,
        ),
        mm(dimensions.braceSize),
        frame,
        `diagonal-brace-${row}`,
      );
    }
  }

  const support = movable(
    "internal-support",
    new THREE.Vector3(
      0,
      mm(dimensions.explodedFrameLift),
      mm(dimensions.explodedFrameOffset),
    ),
  );
  support.userData.kind = "support";
  const rearHalf = mm(PROJECT.rearOpening / 2) - cabinetDepth;
  const innerRearZ = depth - frameDepth;
  const spine = box(
    mm(dimensions.spineSize),
    height,
    mm(dimensions.spineSize),
    support,
    "central-support-spine",
    darkSteelMaterial,
  );
  spine.position.set(0, freeHeight + height / 2, postZ);
  for (const level of [
    freeHeight + profile / 2,
    freeHeight + height - profile / 2,
  ]) {
    const start = new THREE.Vector3(0, level, postZ);
    const rearLeft = new THREE.Vector3(-rearHalf, level, innerRearZ);
    const rearRight = new THREE.Vector3(rearHalf, level, innerRearZ);
    beamBetween(start, rearLeft, profile, support, "support-arm-left");
    beamBetween(start, rearRight, profile, support, "support-arm-right");
    beamBetween(rearLeft, rearRight, profile, support, "rear-cross-member");
  }

  const post = movable(
    "post",
    new THREE.Vector3(
      0,
      mm(dimensions.explodedPostLift),
      -mm(dimensions.explodedBaseOffset),
    ),
  );
  post.userData.kind = "post";
  post.userData.diameter = mm(PROJECT.postDiameter);
  post.userData.topHeight = freeHeight;
  const postRadius = mm(PROJECT.postDiameter) / 2;
  const plateThickness = mm(PROJECT.baseThickness);
  const postMesh = mesh(
    keepGeometry(
      new THREE.CylinderGeometry(
        postRadius,
        postRadius,
        freeHeight - plateThickness,
        STYLE.cylinderSegments,
      ),
    ),
    steelMaterial,
    post,
    "central-tube",
  );
  postMesh.position.set(0, (freeHeight + plateThickness) / 2, postZ);

  const base = movable(
    "base",
    new THREE.Vector3(0, 0, mm(dimensions.explodedBaseOffset)),
  );
  base.userData.kind = "base";
  base.userData.diameter = mm(PROJECT.baseDiameter);
  base.userData.thickness = plateThickness;
  const baseRadius = mm(PROJECT.baseDiameter) / 2;
  const baseMesh = mesh(
    keepGeometry(
      new THREE.CylinderGeometry(
        baseRadius,
        baseRadius,
        plateThickness,
        STYLE.cylinderSegments,
      ),
    ),
    steelMaterial,
    base,
    "circular-base-plate",
  );
  baseMesh.position.set(0, plateThickness / 2, postZ);
  const anchorGeometry = keepGeometry(
    new THREE.CylinderGeometry(
      mm(dimensions.anchorDiameter) / 2,
      mm(dimensions.anchorDiameter) / 2,
      mm(dimensions.anchorHeight),
      16,
    ),
  );
  const washerGeometry = keepGeometry(
    new THREE.CylinderGeometry(
      mm(dimensions.washerDiameter) / 2,
      mm(dimensions.washerDiameter) / 2,
      mm(dimensions.washerThickness),
      24,
    ),
  );
  const nutGeometry = keepGeometry(
    new THREE.CylinderGeometry(
      mm(dimensions.nutDiameter) / 2,
      mm(dimensions.nutDiameter) / 2,
      mm(dimensions.nutHeight),
      6,
    ),
  );
  let boltIndex = 0;
  for (const xSign of [-1, 1]) {
    for (const zSign of [-1, 1]) {
      const anchor = new THREE.Group();
      anchor.name = `anchor-${++boltIndex}`;
      anchor.userData.kind = "anchor";
      anchor.position.set(
        xSign * mm(PROJECT.anchorOffset),
        plateThickness,
        postZ + zSign * mm(PROJECT.anchorOffset),
      );
      base.add(anchor);
      const shaft = mesh(
        anchorGeometry,
        darkSteelMaterial,
        anchor,
        "anchor-shaft",
      );
      shaft.position.y = mm(dimensions.anchorHeight) / 2;
      const washer = mesh(
        washerGeometry,
        steelMaterial,
        anchor,
        "anchor-washer",
      );
      washer.position.y = mm(dimensions.washerThickness) / 2;
      const nut = mesh(nutGeometry, steelMaterial, anchor, "anchor-hex-nut");
      nut.position.y =
        mm(dimensions.washerThickness) + mm(dimensions.nutHeight) / 2;
    }
  }

  // Wire outlines copy mesh transforms after construction. EdgesGeometry avoids
  // the diagonal triangles produced by Material.wireframe on box surfaces.
  for (const { source, outline } of wires) {
    outline.name = `wire-${source.name}`;
    outline.position.copy(source.position);
    outline.quaternion.copy(source.quaternion);
    outline.scale.copy(source.scale);
  }

  function setMode(mode) {
    if (!["complete", "structure", "wireframe"].includes(mode)) return;
    group.userData.mode = mode;
    panelGroups.forEach((face) => {
      face.visible = mode !== "structure";
    });
    solids.forEach((solid) => {
      solid.visible = mode !== "wireframe";
    });
    edgeLines.forEach((outline) => {
      outline.visible = mode === "complete";
    });
    wires.forEach(({ outline }) => {
      outline.visible = mode === "wireframe";
    });
  }

  function update(deltaSeconds) {
    if (disposed) return false;
    const delta = Math.max(
      0,
      Math.min(Number.isFinite(deltaSeconds) ? deltaSeconds : 0, 0.1),
    );
    explodedAmount = THREE.MathUtils.damp(
      explodedAmount,
      explodedTarget,
      STYLE.animationSpeed,
      delta,
    );
    const moving =
      Math.abs(explodedTarget - explodedAmount) > STYLE.animationEpsilon;
    if (!moving) explodedAmount = explodedTarget;
    for (const { part, origin, offset } of parts) {
      part.position.copy(origin).addScaledVector(offset, explodedAmount);
    }
    return moving;
  }

  setMode("complete");
  group.updateMatrixWorld(true);
  return {
    group,
    setMode,
    setExploded(value) {
      explodedTarget = value ? 1 : 0;
      group.userData.exploded = Boolean(value);
    },
    update,
    dispose() {
      if (disposed) return;
      disposed = true;
      geometries.forEach((geometry) => geometry.dispose());
      materials.forEach((material) => material.dispose());
      textures.forEach((item) => item.dispose());
    },
  };
}

function cylinderOutline({ radiusTop, radiusBottom, height, radialSegments }) {
  const positions = [];
  for (let i = 0; i < radialSegments; i++) {
    const angle = (i / radialSegments) * Math.PI * 2;
    const nextAngle = ((i + 1) / radialSegments) * Math.PI * 2;
    for (const [radius, y] of [
      [radiusTop, height / 2],
      [radiusBottom, -height / 2],
    ]) {
      positions.push(
        Math.cos(angle) * radius,
        y,
        Math.sin(angle) * radius,
        Math.cos(nextAngle) * radius,
        y,
        Math.sin(nextAngle) * radius,
      );
    }
  }
  for (let i = 0; i < STYLE.wireCylinderGenerators; i++) {
    const angle = (i / STYLE.wireCylinderGenerators) * Math.PI * 2;
    positions.push(
      Math.cos(angle) * radiusTop,
      height / 2,
      Math.sin(angle) * radiusTop,
      Math.cos(angle) * radiusBottom,
      -height / 2,
      Math.sin(angle) * radiusBottom,
    );
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  return geometry;
}

function createLedTexture() {
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.fillStyle = "#53636a";
  context.fillRect(0, 0, canvas.width, canvas.height);
  for (let y = 4; y < 64; y += 8) {
    for (let x = 4; x < 64; x += 8) {
      context.fillStyle = "#90a2a8";
      context.beginPath();
      context.arc(x, y, 1.1, 0, Math.PI * 2);
      context.fill();
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(12, 12);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}
