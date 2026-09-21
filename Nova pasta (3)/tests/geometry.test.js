import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { PROJECT, GEOMETRY, mm } from '../src/scene/project.js';
import { createLedStructure } from '../src/scene/createLedStructure.js';

const near = (actual, expected, epsilon = 1e-6) => assert.ok(Math.abs(actual - expected) <= epsilon,
  `${actual} must be within ${epsilon} of ${expected}`);
const collect = (root, kind) => {
  const result = [];
  root.traverse((object) => { if (object.userData.kind === kind) result.push(object); });
  return result;
};

test('V comes from the 2880 mm sides and 2000 mm rear opening', () => {
  near(Math.hypot(PROJECT.rearOpening / 2, GEOMETRY.depth), PROJECT.faceWidth);
  near(2 * PROJECT.faceWidth * Math.sin(GEOMETRY.halfAngle), PROJECT.rearOpening);
  near(GEOMETRY.angle, 2 * GEOMETRY.halfAngle);
  near(GEOMETRY.depth, 2701, 1);
  assert.equal(GEOMETRY.totalHeight, 6340);
  assert.equal(PROJECT.columns * PROJECT.cabinetWidth, PROJECT.faceWidth);
  assert.equal(PROJECT.rows * PROJECT.cabinetHeight, PROJECT.faceHeight);
});

test('assembly contains two exact-size 3 by 4 arrays, 24 cabinets and four symmetric anchors', () => {
  const model = createLedStructure();
  try {
    const faces = collect(model.group, 'face');
    const cabinets = collect(model.group, 'cabinet');
    const anchors = collect(model.group, 'anchor');
    assert.equal(faces.length, 2);
    assert.equal(cabinets.length, 24);
    assert.equal(anchors.length, 4);
    for (const face of faces) {
      assert.equal(collect(face, 'cabinet').length, 12);
      const start = new THREE.Vector3(0, 0, 0).applyMatrix4(face.matrixWorld);
      const end = new THREE.Vector3(mm(PROJECT.faceWidth), 0, 0).applyMatrix4(face.matrixWorld);
      near(start.distanceTo(end), mm(PROJECT.faceWidth));
      near(start.y, 2.5);
      const vertex = start.z < end.z ? start : end;
      const rear = start.z < end.z ? end : start;
      near(vertex.x, 0); near(vertex.z, 0);
      near(Math.abs(rear.x), 1); near(rear.z, mm(GEOMETRY.depth));
      const top = new THREE.Vector3(0, mm(PROJECT.faceHeight), 0).applyMatrix4(face.matrixWorld);
      near(top.y, 6.34);
    }
    for (const cabinet of cabinets) {
      near(cabinet.userData.nominalWidth, 0.96);
      near(cabinet.userData.nominalHeight, 0.96);
      const shell = cabinet.getObjectByName('cabinet-shell');
      const led = cabinet.getObjectByName('led-surface');
      const shellFront = shell.position.z + shell.geometry.parameters.depth / 2;
      const shellBack = shell.position.z - shell.geometry.parameters.depth / 2;
      const ledFront = led.position.z + led.geometry.parameters.depth / 2;
      const ledBack = led.position.z - led.geometry.parameters.depth / 2;
      assert.ok(shell.geometry.parameters.depth > 0);
      assert.ok(ledFront > shellFront, 'LED and shell visible surfaces must not be coplanar');
      near(ledBack, shellFront);
      near(ledFront, 0);
      near(ledFront - shellBack, mm(PROJECT.visual.cabinetDepth));
    }
    const base = model.group.getObjectByName('circular-base-plate');
    near(base.geometry.parameters.radiusTop * 2, 0.6);
    near(base.geometry.parameters.height, 0.025);
    const post = model.group.getObjectByName('central-tube');
    near(post.geometry.parameters.radiusTop * 2, 0.15);
    near(post.position.y + post.geometry.parameters.height / 2, 2.5);
    for (const anchor of anchors) {
      near(Math.abs(anchor.position.x), 0.15);
      near(Math.abs(anchor.position.z - mm(PROJECT.visual.postZ)), 0.15);
    }
  } finally { model.dispose(); }
});

test('mitred housings, LED layers and profiles stay in their own half of the V', () => {
  const model = createLedStructure();
  const vertex = new THREE.Vector3();
  try {
    for (const side of ['left', 'right']) {
      const sign = side === 'left' ? -1 : 1;
      for (const assembly of ['face', 'frame']) {
        model.group.getObjectByName(`${assembly}-${side}`).traverse((object) => {
          if (!object.isMesh) return;
          const positions = object.geometry.getAttribute('position');
          for (let index = 0; index < positions.count; index++) {
            vertex.fromBufferAttribute(positions, index).applyMatrix4(object.matrixWorld);
            assert.ok(sign * vertex.x >= -1e-7,
              `${assembly}-${side}/${object.name} crosses the V centre plane at x=${vertex.x}`);
          }
        });
      }
    }
  } finally { model.dispose(); }
});

test('structure, wireframe and explosion are reversible without changing cabinet topology', () => {
  const model = createLedStructure();
  try {
    const face = model.group.getObjectByName('face-left');
    const origin = face.position.clone();
    model.setMode('structure');
    assert.equal(face.visible, false);
    assert.equal(model.group.getObjectByName('frame-left').visible, true);
    model.setMode('wireframe');
    assert.equal(face.visible, true);
    assert.equal(model.group.getObjectByName('central-tube').visible, false);
    assert.equal(model.group.getObjectByName('wire-central-tube').visible, true);
    model.setMode('complete');
    assert.equal(model.group.getObjectByName('central-tube').visible, true);
    assert.equal(model.group.getObjectByName('wire-central-tube').visible, false);
    model.setExploded(true);
    assert.equal(model.update(1 / 60), true);
    for (let i = 0; i < 300; i++) model.update(1 / 60);
    assert.equal(model.update(1 / 60), false);
    assert.ok(face.position.distanceTo(origin) > 0.4);
    model.setExploded(false);
    for (let i = 0; i < 300; i++) model.update(1 / 60);
    near(face.position.distanceTo(origin), 0);
    assert.equal(collect(model.group, 'cabinet').length, 24);
    assert.equal(model.update(1 / 60), false);
  } finally { model.dispose(); }
});
