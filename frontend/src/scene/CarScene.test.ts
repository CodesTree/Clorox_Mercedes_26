import { expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { Box3 } from "three";
import { COMPONENTS } from "../components/componentConfig";
import { createCoupeBodyGeometry, createCoupeCabinGeometry } from "./coupeGeometry";
import { HIGHLIGHT_REGIONS } from "./highlightRegions";
import {
  COUPE_CAMERA_MODE,
  COUPE_CAMERA_POSITION,
  COUPE_ORBIT_OUTER_RADIUS,
  COUPE_ROTATION_BASE_Y,
  COUPE_SAFE_FRAME_HEIGHT,
  COUPE_SAFE_FRAME_WIDTH,
} from "./sceneConfig";

const themeCss = readFileSync("src/styles/theme.css", "utf8");
const carSceneSource = readFileSync("src/scene/CarScene.tsx", "utf8");

test("dashboard styling does not draw a second CSS orbit ring", () => {
  expect(themeCss).toContain(".car-stage");
  expect(themeCss).not.toMatch(/\.dashboard-stage::after\s*{[^}]*border:/s);
});

test("procedural coupe body uses a smooth sectioned geometry", () => {
  const geometry = createCoupeBodyGeometry();

  expect(geometry.type).toBe("BufferGeometry");
  expect(geometry.attributes.position.count).toBeGreaterThan(300);

  geometry.dispose();
});

test("procedural coupe has a long AMG GT-style side profile", () => {
  const geometry = createCoupeBodyGeometry();
  geometry.computeBoundingBox();

  const box = geometry.boundingBox as Box3;
  const length = box.max.x - box.min.x;
  const height = box.max.y - box.min.y;

  expect(length).toBeGreaterThan(5.55);
  expect(length).toBeLessThan(6.05);
  expect(height).toBeLessThan(1.12);

  geometry.dispose();
});

test("procedural coupe body is wide enough to avoid a stretched limousine look", () => {
  const geometry = createCoupeBodyGeometry();
  geometry.computeBoundingBox();

  const box = geometry.boundingBox as Box3;
  const length = box.max.x - box.min.x;
  const depth = box.max.z - box.min.z;
  expect(depth).toBeGreaterThan(1.78);
  expect(length / depth).toBeLessThan(3.35);

  geometry.dispose();
});

test("procedural coupe cabin forms a smooth concept-car dome", () => {
  const geometry = createCoupeCabinGeometry();
  geometry.computeBoundingBox();

  const box = geometry.boundingBox as Box3;
  expect(box.max.x - box.min.x).toBeGreaterThan(2.25);
  expect(box.max.y - box.min.y).toBeLessThan(1.15);

  geometry.dispose();
});

test("procedural coupe opens in a side-profile presentation", () => {
  expect(Math.abs(COUPE_ROTATION_BASE_Y)).toBeLessThan(0.15);
  expect(COUPE_CAMERA_POSITION[0]).toBe(0);
  expect(COUPE_CAMERA_POSITION[2]).toBeGreaterThan(5);
});

test("camera uses an orthographic safe frame so the car and orbit ring cannot crop", () => {
  expect(COUPE_CAMERA_MODE).toBe("orthographic");
  expect(COUPE_SAFE_FRAME_WIDTH).toBeLessThan(COUPE_ORBIT_OUTER_RADIUS * 2 + 0.6);
  expect(COUPE_SAFE_FRAME_HEIGHT).toBeLessThan(4.35);
  expect(carSceneSource).not.toContain("COUPE_TOP_VIEW_SAFE_FRAME_HEIGHT");
});

test("orbit controls use a fixed close start with smooth damped motion", () => {
  expect(carSceneSource).toContain("dampingFactor={0.075}");
  expect(carSceneSource).toContain("rotateSpeed={0.42}");
  expect(carSceneSource).toContain("zoomSpeed={0.52}");
  expect(carSceneSource).not.toContain("const safeZoom = getSafeZoom");
});

test("dashboard reserves a larger canvas for the car scene", () => {
  expect(themeCss).toMatch(/\.car-scene,\s*\.car-fallback\s*{[^}]*width:\s*min\(100%,\s*1040px\);/s);
  expect(themeCss).toMatch(/\.car-scene,\s*\.car-fallback\s*{[^}]*height:\s*min\(62vh,\s*580px\);/s);
});

test("component selectors map to local highlight regions instead of tinting the full body", () => {
  expect(Object.keys(HIGHLIGHT_REGIONS).sort()).toEqual(COMPONENTS.map((component) => component.id).sort());
  expect(HIGHLIGHT_REGIONS.engine.size[0]).toBeLessThan(2);
  expect(HIGHLIGHT_REGIONS.fuel.size[0]).toBeLessThan(1);
  expect(carSceneSource).not.toContain('emissive={selected === "engine" ?');
  expect(carSceneSource).toContain("depthTest={false}");
});
