import { ExtrudeGeometry, Shape } from "three";

export const COUPE_BODY_LENGTH = 5.82;
export const COUPE_BODY_HEIGHT = 0.94;
export const COUPE_HOOD_LENGTH = 2.28;
export const COUPE_CABIN_CENTER_X = -0.62;

export function createCoupeBodyGeometry() {
  const body = new Shape();
  body.moveTo(-2.8, -0.26);
  body.bezierCurveTo(-2.68, 0.0, -2.4, 0.22, -1.9, 0.33);
  body.bezierCurveTo(-1.15, 0.48, -0.24, 0.5, 0.72, 0.46);
  body.bezierCurveTo(1.58, 0.43, 2.44, 0.31, 2.72, 0.15);
  body.bezierCurveTo(2.94, 0.0, 2.88, -0.19, 2.58, -0.29);
  body.lineTo(1.22, -0.39);
  body.bezierCurveTo(0.28, -0.47, -1.42, -0.47, -2.32, -0.37);
  body.bezierCurveTo(-2.58, -0.34, -2.74, -0.3, -2.8, -0.26);

  const geometry = new ExtrudeGeometry(body, {
    depth: 1.68,
    bevelEnabled: true,
    bevelSegments: 16,
    bevelSize: 0.065,
    bevelThickness: 0.08,
    curveSegments: 36,
    steps: 2,
  });
  geometry.center();
  return geometry;
}

export function createCoupeCabinGeometry() {
  const cabin = new Shape();
  cabin.moveTo(-1.24, -0.15);
  cabin.bezierCurveTo(-0.98, 0.17, -0.58, 0.5, -0.04, 0.62);
  cabin.bezierCurveTo(0.44, 0.67, 0.88, 0.34, 1.06, -0.15);
  cabin.bezierCurveTo(0.24, -0.08, -0.5, -0.08, -1.24, -0.15);

  const geometry = new ExtrudeGeometry(cabin, {
    depth: 1.48,
    bevelEnabled: true,
    bevelSegments: 14,
    bevelSize: 0.04,
    bevelThickness: 0.065,
    curveSegments: 34,
    steps: 2,
  });
  geometry.center();
  return geometry;
}
