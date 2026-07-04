import { BufferGeometry, ExtrudeGeometry, Float32BufferAttribute, Shape } from "three";

export const COUPE_BODY_LENGTH = 5.82;
export const COUPE_BODY_HEIGHT = 0.94;
export const COUPE_HOOD_LENGTH = 2.28;
export const COUPE_CABIN_CENTER_X = -0.62;

interface Section {
  x: number;
  top: number;
  bottom: number;
  halfWidth: number;
}

function createSectionedGeometry(sections: readonly Section[], segments = 32) {
  const positions: number[] = [];
  const indices: number[] = [];

  sections.forEach((section) => {
    const centerY = (section.top + section.bottom) / 2;
    const radiusY = (section.top - section.bottom) / 2;

    for (let index = 0; index < segments; index += 1) {
      const angle = (index / segments) * Math.PI * 2;
      const z = Math.cos(angle) * section.halfWidth;
      const y = centerY + Math.sin(angle) * radiusY;
      positions.push(section.x, y, z);
    }
  });

  for (let sectionIndex = 0; sectionIndex < sections.length - 1; sectionIndex += 1) {
    const current = sectionIndex * segments;
    const next = (sectionIndex + 1) * segments;

    for (let index = 0; index < segments; index += 1) {
      const nextIndex = (index + 1) % segments;
      indices.push(current + index, next + index, current + nextIndex);
      indices.push(current + nextIndex, next + index, next + nextIndex);
    }
  }

  const firstCenter = positions.length / 3;
  positions.push(sections[0].x, (sections[0].top + sections[0].bottom) / 2, 0);
  for (let index = 0; index < segments; index += 1) {
    indices.push(firstCenter, (index + 1) % segments, index);
  }

  const lastCenter = positions.length / 3;
  const lastSection = sections[sections.length - 1];
  const lastOffset = (sections.length - 1) * segments;
  positions.push(lastSection.x, (lastSection.top + lastSection.bottom) / 2, 0);
  for (let index = 0; index < segments; index += 1) {
    indices.push(lastCenter, lastOffset + index, lastOffset + ((index + 1) % segments));
  }

  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.center();
  return geometry;
}

export function createCoupeBodyGeometry() {
  const profile = new Shape();
  profile.moveTo(2.38, 0.24);
  profile.lineTo(2.46, 0.42);
  profile.quadraticCurveTo(2.46, 0.58, 2.2, 0.64);
  profile.lineTo(1.25, 0.78);
  profile.quadraticCurveTo(0.7, 0.84, 0.42, 1.06);
  profile.quadraticCurveTo(0.1, 1.2, -0.3, 1.2);
  profile.quadraticCurveTo(-1.2, 1.14, -1.85, 0.84);
  profile.quadraticCurveTo(-2.35, 0.74, -2.42, 0.56);
  profile.lineTo(-2.36, 0.26);
  profile.lineTo(-1.9, 0.2);
  profile.lineTo(1.9, 0.2);
  profile.closePath();

  const geometry = new ExtrudeGeometry(profile, {
    depth: 1.5,
    bevelEnabled: true,
    bevelThickness: 0.14,
    bevelSize: 0.12,
    bevelSegments: 4,
    steps: 1,
    curveSegments: 12,
  });

  geometry.translate(0, 0, -0.75);
  const position = geometry.attributes.position;
  for (let index = 0; index < position.count; index += 1) {
    const y = position.getY(index);
    if (y > 0.8) {
      const taper = 1 - (y - 0.8) * 0.55;
      position.setZ(index, position.getZ(index) * taper);
    }
  }
  geometry.computeVertexNormals();
  return geometry;
}

export function createCoupeCabinGeometry() {
  return createSectionedGeometry(
    [
      { x: -1.48, top: -0.18, bottom: -0.26, halfWidth: 0.24 },
      { x: -1.2, top: 0.24, bottom: -0.2, halfWidth: 0.62 },
      { x: -0.78, top: 0.64, bottom: -0.16, halfWidth: 0.86 },
      { x: -0.2, top: 0.76, bottom: -0.13, halfWidth: 0.94 },
      { x: 0.44, top: 0.68, bottom: -0.14, halfWidth: 0.88 },
      { x: 0.98, top: 0.38, bottom: -0.18, halfWidth: 0.62 },
      { x: 1.34, top: -0.06, bottom: -0.24, halfWidth: 0.26 },
    ],
    48,
  );
}
