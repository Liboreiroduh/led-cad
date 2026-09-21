/** All design dimensions are millimetres; the Three.js world uses metres. */
export const PROJECT = Object.freeze({
  faceWidth: 2880,
  faceHeight: 3840,
  cabinetWidth: 960,
  cabinetHeight: 960,
  columns: 3,
  rows: 4,
  rearOpening: 2000,
  freeHeight: 2500,
  postDiameter: 150,
  baseDiameter: 600,
  baseThickness: 25,
  anchorOffset: 150,
  // Representative fabrication details, not structural specifications.
  visual: Object.freeze({
    postZ: 350,
    cabinetDepth: 100,
    cabinetGap: 4,
    ledInset: 7,
    ledDepth: 2,
    profileSize: 50,
    frameDepth: 55,
    rearBracketSize: 36,
    braceSize: 30,
    spineSize: 70,
    anchorDiameter: 24,
    anchorHeight: 70,
    washerDiameter: 48,
    washerThickness: 5,
    nutDiameter: 38,
    nutHeight: 20,
    explodedFaceOffset: 450,
    explodedFaceLift: 120,
    explodedFrameLift: 200,
    explodedFrameOffset: 100,
    explodedPostLift: 300,
    explodedBaseOffset: 300,
  }),
});

export const mm = (value) => value / 1000;

const halfOpening = PROJECT.rearOpening / 2;
export const GEOMETRY = Object.freeze({
  depth: Math.sqrt(PROJECT.faceWidth ** 2 - halfOpening ** 2),
  halfAngle: Math.asin(halfOpening / PROJECT.faceWidth),
  angle: 2 * Math.asin(halfOpening / PROJECT.faceWidth),
  totalHeight: PROJECT.freeHeight + PROJECT.faceHeight,
});
