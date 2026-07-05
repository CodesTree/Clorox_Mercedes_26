import { expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { Box3 } from "three";
import { COMPONENTS } from "../components/componentConfig";
import { createCoupeBodyGeometry, createCoupeCabinGeometry } from "./coupeGeometry";
import { HIGHLIGHT_REGIONS } from "./highlightRegions";
import {
  COUPE_CAMERA_MODE,
  COUPE_CAMERA_POSITION,
  COUPE_MAX_ZOOM_RATIO,
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

test("bundle coupe body ports Claude's exported extruded silhouette", () => {
  const geometry = createCoupeBodyGeometry();

  expect(geometry.type).toBe("ExtrudeGeometry");
  expect(geometry.attributes.position.count).toBeGreaterThan(500);
  expect(carSceneSource).toContain("createCoupeBodyGeometry");
  expect(carSceneSource).not.toContain("OBJLoader");

  geometry.dispose();
});

test("bundle coupe has Claude's AMG-style side profile", () => {
  const geometry = createCoupeBodyGeometry();
  geometry.computeBoundingBox();

  const box = geometry.boundingBox as Box3;
  const length = box.max.x - box.min.x;
  const height = box.max.y - box.min.y;

  expect(length).toBeGreaterThan(5.1);
  expect(length).toBeLessThan(5.16);
  expect(height).toBeGreaterThan(1.2);
  expect(height).toBeLessThan(1.26);

  geometry.dispose();
});

test("bundle coupe body uses the prototype body depth", () => {
  const geometry = createCoupeBodyGeometry();
  geometry.computeBoundingBox();

  const box = geometry.boundingBox as Box3;
  const length = box.max.x - box.min.x;
  const depth = box.max.z - box.min.z;
  expect(depth).toBeGreaterThan(1.74);
  expect(depth).toBeLessThan(1.82);
  expect(length / depth).toBeLessThan(2.95);

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
  expect(COUPE_SAFE_FRAME_WIDTH).toBeGreaterThan(COUPE_ORBIT_OUTER_RADIUS * 2 + 1);
  expect(COUPE_SAFE_FRAME_HEIGHT).toBeGreaterThan(4.35);
  expect(COUPE_MAX_ZOOM_RATIO).toBeGreaterThanOrEqual(1.65);
  expect(carSceneSource).not.toContain("COUPE_TOP_VIEW_SAFE_FRAME_HEIGHT");
});

test("orbit controls use a fixed close start with smooth damped motion", () => {
  expect(carSceneSource).toContain("dampingFactor={0.075}");
  expect(carSceneSource).toContain("rotateSpeed={0.42}");
  expect(carSceneSource).toContain("zoomSpeed={0.52}");
  expect(carSceneSource).not.toContain("const safeZoom = getSafeZoom");
});

test("dashboard reserves a larger canvas for the car scene", () => {
  expect(themeCss).toMatch(/\.dashboard-stage\s*{[^}]*overflow:\s*visible;/s);
  expect(themeCss).toMatch(/\.car-stage\s*{[^}]*overflow:\s*visible;/s);
  expect(themeCss).toMatch(/\.car-scene,\s*\.car-fallback\s*{[^}]*width:\s*min\(132vw,\s*1680px\);/s);
  expect(themeCss).toMatch(/\.car-scene,\s*\.car-fallback\s*{[^}]*height:\s*min\(88vh,\s*820px\);/s);
});

test("booking date and time controls use the dark dashboard theme", () => {
  expect(themeCss).toMatch(/\.booking-modal input:is\(\[type="date"\],\s*\[type="time"\]\)\s*{[^}]*color-scheme:\s*dark;/s);
  expect(themeCss).toMatch(/\.booking-modal input:is\(\[type="date"\],\s*\[type="time"\]\)::\-webkit-calendar-picker-indicator\s*{[^}]*filter:/s);
});

test("dashboard typography is sized for presentation viewing", () => {
  expect(themeCss).toMatch(/\.value-header h1\s*{[^}]*font-size:\s*64px;/s);
  expect(themeCss).toMatch(/\.telemetry-stat strong\s*{[^}]*font-size:\s*32px;/s);
  expect(themeCss).toMatch(/\.component-callout p\s*{[^}]*font-size:\s*12px;/s);
  expect(themeCss).toMatch(/\.dock-button strong\s*{[^}]*font-size:\s*11px;/s);
});

test("dashboard visual system matches Claude cinematic stage v2", () => {
  expect(themeCss).toContain("--bg: #0a0d0e;");
  expect(themeCss).toMatch(/radial-gradient\(80% 55% at 50% 32%,\s*rgba\(0,\s*210,\s*190,\s*0\.07\)/s);
  expect(themeCss).toMatch(/\.stage-border\s*{[^}]*border-radius:\s*12px;/s);
  expect(themeCss).toMatch(/\.component-callout,\s*\.depreciation-panel,\s*\.booking-modal\s*{[^}]*border-radius:\s*16px;/s);
  expect(themeCss).toMatch(/\.dock-button\s*{[^}]*border-radius:\s*14px;/s);
  expect(themeCss).toMatch(/\.component-callout--top\s*{[^}]*left:\s*50%;/s);
  expect(themeCss).toMatch(/\.component-callout--left\s*{[^}]*left:\s*14%;/s);
  expect(themeCss).toMatch(/\.component-callout--lower-right\s*{[^}]*right:\s*8%;/s);
  expect(themeCss).toMatch(/\.depreciation-panel\s*{[^}]*right:\s*26px;[^}]*bottom:\s*26px;/s);
});

test("component callout cards anchor to 3 fixed points and fade in", () => {
  expect(themeCss).toMatch(/@keyframes callout-in\s*{[^}]*opacity:\s*0;/s);
  expect(themeCss).toMatch(/\.component-callout\s*{[^}]*animation:\s*callout-in\s+180ms\s+ease-out;/s);
  expect(themeCss).toMatch(/\.component-callout--top\s*{[^}]*top:\s*14%;[^}]*left:\s*50%;[^}]*transform:\s*translateX\(-50%\);/s);
  expect(themeCss).toMatch(/\.component-callout--left\s*{[^}]*top:\s*48%;[^}]*left:\s*14%;/s);
  expect(themeCss).toMatch(/\.component-callout--lower-right\s*{[^}]*top:\s*66%;[^}]*right:\s*8%;/s);
});

test("component selectors map to local highlight regions instead of tinting the full body", () => {
  expect(Object.keys(HIGHLIGHT_REGIONS).sort()).toEqual(COMPONENTS.map((component) => component.id).sort());
  expect(HIGHLIGHT_REGIONS.engine.size[0]).toBeLessThan(2);
  expect(HIGHLIGHT_REGIONS.fuel.size[0]).toBeLessThan(1);
  expect(HIGHLIGHT_REGIONS.engine.shape).toBe("engineBay");
  expect(HIGHLIGHT_REGIONS.fuel.shape).toBe("fuelTank");
  expect(HIGHLIGHT_REGIONS.battery.shape).toBe("batteryModule");
  expect(HIGHLIGHT_REGIONS.service.kind).toBe("fullFrame");
  expect(carSceneSource).toContain("PART_GLOW_VOLUMES");
  expect(carSceneSource).toContain("<BundleCoupe selected={selected} onSelect={onSelect} />");
  expect(carSceneSource).toContain("new EdgesGeometry(bodyGeometry, 22)");
  expect(carSceneSource).toContain("<cylinderGeometry");
  expect(carSceneSource).not.toContain('emissive={selected === "engine" ?');
  expect(carSceneSource).toContain("depthTest={false}");
});
