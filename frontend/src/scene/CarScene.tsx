import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  AdditiveBlending,
  BoxGeometry,
  Color,
  CylinderGeometry,
  DoubleSide,
  EdgesGeometry,
  PolarGridHelper,
  type Group,
  type LineBasicMaterial,
  type MeshBasicMaterial,
  type OrthographicCamera,
} from "three";
import { COMPONENTS, type ComponentId } from "../components/componentConfig";
import { createCoupeBodyGeometry } from "./coupeGeometry";
import {
  COUPE_CAMERA_POSITION,
  COUPE_MAX_ZOOM_RATIO,
  COUPE_MIN_ZOOM_RATIO,
  COUPE_ORBIT_INNER_RADIUS,
  COUPE_ORBIT_OUTER_RADIUS,
  COUPE_ROTATION_BASE_Y,
  COUPE_SAFE_FRAME_HEIGHT,
  COUPE_SAFE_FRAME_WIDTH,
} from "./sceneConfig";

interface CarSceneProps {
  selected: ComponentId;
  onSelect: (id: ComponentId) => void;
}

type Vec3 = readonly [number, number, number];

type PartGeometrySpec =
  | { kind: "box"; args: [number, number, number] }
  | { kind: "cylinder"; args: [number, number, number, number]; rotateX?: number };

interface PartGlowVolume {
  id: ComponentId;
  spec: PartGeometrySpec;
  position: Vec3;
}

const ACCENT = "#00d2be";
const ORBIT_TARGET = [0, 0.45, 0] as const;
const WHEEL_POSITIONS = [
  [1.48, 0.37, 0.82],
  [1.48, 0.37, -0.82],
  [-1.45, 0.37, 0.82],
  [-1.45, 0.37, -0.82],
] as const;

const MIRROR_POSITIONS = [
  [0.5, 0.92, 0.92],
  [0.5, 0.92, -0.92],
] as const;

const HEADLIGHT_POSITIONS = [
  [2.44, 0.5, 0.5],
  [2.44, 0.5, -0.5],
] as const;

const PART_GLOW_VOLUMES: readonly PartGlowVolume[] = [
  { id: "engine", spec: { kind: "box", args: [1, 0.42, 1] }, position: [1.55, 0.5, 0] },
  { id: "engine", spec: { kind: "box", args: [1.4, 0.22, 0.34] }, position: [0.5, 0.38, 0] },
  { id: "battery", spec: { kind: "box", args: [0.5, 0.26, 0.45] }, position: [-1.85, 0.52, 0.35] },
  { id: "battery", spec: { kind: "box", args: [0.34, 0.2, 0.3] }, position: [1.1, 0.54, -0.5] },
  ...WHEEL_POSITIONS.map<PartGlowVolume>((position) => ({
    id: "brakes",
    spec: { kind: "cylinder", args: [0.23, 0.23, 0.06, 20], rotateX: Math.PI / 2 },
    position,
  })),
  { id: "fuel", spec: { kind: "box", args: [0.9, 0.28, 1.1] }, position: [-1.15, 0.38, 0] },
  { id: "mileage", spec: { kind: "box", args: [0.3, 0.16, 0.5] }, position: [0.62, 0.88, -0.32] },
  { id: "diagnostics", spec: { kind: "box", args: [0.22, 0.14, 0.24] }, position: [0.95, 0.5, -0.55] },
];

function canUseWebGL() {
  if (typeof document === "undefined") return false;
  if (typeof navigator !== "undefined" && navigator.userAgent.includes("jsdom")) return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
  } catch {
    return false;
  }
}

function createPartGeometry(spec: PartGeometrySpec) {
  const geometry =
    spec.kind === "box"
      ? new BoxGeometry(...spec.args)
      : new CylinderGeometry(spec.args[0], spec.args[1], spec.args[2], spec.args[3]);

  if (spec.kind === "cylinder" && spec.rotateX) {
    geometry.rotateX(spec.rotateX);
  }
  return geometry;
}

function getFitZoom(width: number, height: number) {
  return Math.max(1, Math.min(width / COUPE_SAFE_FRAME_WIDTH, height / COUPE_SAFE_FRAME_HEIGHT));
}

function CameraRig() {
  const { camera, size } = useThree();
  const orthographicCamera = camera as OrthographicCamera;
  const fitZoom = getFitZoom(size.width, size.height);

  useEffect(() => {
    orthographicCamera.position.set(COUPE_CAMERA_POSITION[0], COUPE_CAMERA_POSITION[1], COUPE_CAMERA_POSITION[2]);
    orthographicCamera.zoom = fitZoom;
    orthographicCamera.lookAt(ORBIT_TARGET[0], ORBIT_TARGET[1], ORBIT_TARGET[2]);
    orthographicCamera.updateProjectionMatrix();
  }, [fitZoom, orthographicCamera]);

  return (
    <OrbitControls
      enableDamping
      dampingFactor={0.075}
      enablePan={false}
      target={[...ORBIT_TARGET]}
      minZoom={fitZoom * COUPE_MIN_ZOOM_RATIO}
      maxZoom={fitZoom * COUPE_MAX_ZOOM_RATIO}
      rotateSpeed={0.42}
      zoomSpeed={0.52}
      minPolarAngle={0.08}
      maxPolarAngle={1.52}
    />
  );
}

function PartGlow({ volume, selected, onSelect }: { volume: PartGlowVolume } & CarSceneProps) {
  const fillMaterial = useRef<MeshBasicMaterial>(null);
  const lineMaterial = useRef<LineBasicMaterial>(null);
  const geometry = useMemo(() => createPartGeometry(volume.spec), [volume.spec]);
  const edgeGeometry = useMemo(() => new EdgesGeometry(geometry), [geometry]);

  useEffect(() => {
    return () => {
      geometry.dispose();
      edgeGeometry.dispose();
    };
  }, [edgeGeometry, geometry]);

  useFrame(({ clock }, delta) => {
    const active = selected === volume.id;
    const pulse = 0.55 + 0.4 * Math.sin(clock.elapsedTime * 3.2);
    const ease = Math.min(1, delta * 10);
    if (fillMaterial.current) {
      const target = active ? pulse * 0.4 : 0;
      fillMaterial.current.opacity += (target - fillMaterial.current.opacity) * ease;
    }
    if (lineMaterial.current) {
      const target = active ? pulse : 0;
      lineMaterial.current.opacity += (target - lineMaterial.current.opacity) * ease;
    }
  });

  const choosePart = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onSelect(volume.id);
  };

  return (
    <group position={[...volume.position]} onClick={choosePart}>
      <mesh geometry={geometry} renderOrder={8}>
        <meshBasicMaterial
          ref={fillMaterial}
          color={ACCENT}
          transparent
          opacity={0}
          depthTest={false}
          blending={AdditiveBlending}
        />
      </mesh>
      <lineSegments geometry={edgeGeometry} renderOrder={9}>
        <lineBasicMaterial ref={lineMaterial} color={ACCENT} transparent opacity={0} depthTest={false} />
      </lineSegments>
    </group>
  );
}

function BundleCoupe({ selected, onSelect }: CarSceneProps) {
  const car = useRef<Group>(null);
  const bodyEdgeMaterial = useRef<LineBasicMaterial>(null);
  const [pausedUntil, setPausedUntil] = useState(0);
  const bodyGeometry = useMemo(() => createCoupeBodyGeometry(), []);
  const bodyEdgeGeometry = useMemo(() => new EdgesGeometry(bodyGeometry, 22), [bodyGeometry]);
  const grid = useMemo(() => new PolarGridHelper(3.4, 8, 3, 48, 0x1a2224, 0x141a1c), []);
  const accentColor = useMemo(() => new Color(ACCENT), []);
  const edgeBaseColor = useMemo(() => new Color("#2e3a3c"), []);

  useEffect(() => {
    return () => {
      bodyGeometry.dispose();
      bodyEdgeGeometry.dispose();
    };
  }, [bodyEdgeGeometry, bodyGeometry, grid]);

  useFrame(({ clock }, delta) => {
    if (car.current && performance.now() > pausedUntil) {
      car.current.rotation.y += delta * 0.12;
    }

    if (bodyEdgeMaterial.current) {
      const pulse = 0.55 + 0.4 * Math.sin(clock.elapsedTime * 3.2);
      const active = selected === "service";
      const ease = Math.min(1, delta * 5);
      bodyEdgeMaterial.current.color.lerp(active ? accentColor : edgeBaseColor, ease);
      const targetOpacity = active ? 0.35 + pulse * 0.65 : 0.75;
      bodyEdgeMaterial.current.opacity += (targetOpacity - bodyEdgeMaterial.current.opacity) * ease;
    }
  });

  const pause = () => setPausedUntil(performance.now() + 3000);
  const choosePart = (event: ThreeEvent<MouseEvent>, id: ComponentId) => {
    event.stopPropagation();
    pause();
    onSelect(id);
  };

  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
        <circleGeometry args={[3.6, 48]} />
        <meshBasicMaterial color="#0c0f10" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <ringGeometry args={[COUPE_ORBIT_INNER_RADIUS, COUPE_ORBIT_OUTER_RADIUS, 64]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.12} side={DoubleSide} />
      </mesh>
      <primitive object={grid} />

      <group ref={car} rotation={[0, COUPE_ROTATION_BASE_Y, 0]} onPointerDown={pause}>
        <mesh geometry={bodyGeometry} onClick={(event) => choosePart(event, "service")}>
          <meshStandardMaterial color="#161a1c" metalness={0.85} roughness={0.38} />
        </mesh>
        <lineSegments geometry={bodyEdgeGeometry}>
          <lineBasicMaterial ref={bodyEdgeMaterial} color="#2e3a3c" transparent opacity={0.75} />
        </lineSegments>

        <mesh position={[-2.15, 0.88, 0]} onClick={(event) => choosePart(event, "service")}>
          <boxGeometry args={[0.28, 0.05, 1.15]} />
          <meshStandardMaterial color="#161a1c" metalness={0.85} roughness={0.38} />
        </mesh>

        {MIRROR_POSITIONS.map(([x, y, z]) => (
          <mesh key={`mirror-${z}`} position={[x, y, z]} onClick={(event) => choosePart(event, "service")}>
            <boxGeometry args={[0.16, 0.07, 0.14]} />
            <meshStandardMaterial color="#161a1c" metalness={0.85} roughness={0.38} />
          </mesh>
        ))}

        {WHEEL_POSITIONS.map(([x, y, z]) => (
          <group key={`wheel-${x}-${z}`} position={[x, y, z]} onClick={(event) => choosePart(event, "brakes")}>
            <mesh rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.37, 0.37, 0.26, 24]} />
              <meshStandardMaterial color="#0b0d0e" metalness={0.4} roughness={0.7} />
            </mesh>
            <mesh position={[0, 0, z > 0 ? 0.135 : -0.135]}>
              <torusGeometry args={[0.24, 0.025, 8, 24]} />
              <meshStandardMaterial color="#4a585c" metalness={0.9} roughness={0.3} />
            </mesh>
          </group>
        ))}

        {HEADLIGHT_POSITIONS.map(([x, y, z]) => (
          <mesh key={`headlight-${z}`} position={[x, y, z]}>
            <boxGeometry args={[0.06, 0.09, 0.34]} />
            <meshBasicMaterial color="#cfe8e4" />
          </mesh>
        ))}
        <mesh position={[-2.44, 0.62, 0]}>
          <boxGeometry args={[0.05, 0.07, 1.3]} />
          <meshBasicMaterial color="#d8443a" />
        </mesh>

        {PART_GLOW_VOLUMES.map((volume) => (
          <PartGlow key={`${volume.id}-${volume.position.join("-")}`} volume={volume} selected={selected} onSelect={onSelect} />
        ))}
      </group>
    </>
  );
}

function CarFallback({ selected, onSelect }: CarSceneProps) {
  return (
    <div className="car-fallback" data-testid="car-scene">
      <div className="car-fallback__halo" />
      <div className={`car-fallback__silhouette${selected === "service" ? " car-fallback__silhouette--service" : ""}`}>
        <div className="car-fallback__roof" />
        <div className="car-fallback__wheel car-fallback__wheel--rear" />
        <div className="car-fallback__wheel car-fallback__wheel--front" />
      </div>
      {COMPONENTS.map((component) => (
        <button
          key={component.id}
          aria-label={`Select ${component.label}`}
          className={`fallback-hotspot fallback-hotspot--${component.id} ${
            selected === component.id ? "fallback-hotspot--active" : ""
          }`}
          type="button"
          onClick={() => onSelect(component.id)}
        />
      ))}
    </div>
  );
}

export function CarScene({ selected, onSelect }: CarSceneProps) {
  if (!canUseWebGL()) {
    return <CarFallback selected={selected} onSelect={onSelect} />;
  }

  return (
    <div className="car-scene" data-testid="car-scene">
      <Canvas orthographic camera={{ position: [...COUPE_CAMERA_POSITION], zoom: 80 }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[4, 8, 3]} intensity={1.9} />
        <pointLight color={ACCENT} position={[-6, 2.5, -5]} intensity={40} distance={40} />
        <pointLight color="#6a8a92" position={[5, 1.5, -4]} intensity={14} distance={30} />
        <Suspense fallback={null}>
          <BundleCoupe selected={selected} onSelect={onSelect} />
        </Suspense>
        <CameraRig />
      </Canvas>
    </div>
  );
}
