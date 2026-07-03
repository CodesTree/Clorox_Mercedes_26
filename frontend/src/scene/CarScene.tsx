import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Group, OrthographicCamera } from "three";
import { COMPONENTS, type ComponentId } from "../components/componentConfig";
import { createCoupeBodyGeometry, createCoupeCabinGeometry } from "./coupeGeometry";
import { HIGHLIGHT_REGIONS } from "./highlightRegions";
import {
  COUPE_CAMERA_POSITION,
  COUPE_MAX_ZOOM_RATIO,
  COUPE_MIN_ZOOM_RATIO,
  COUPE_ORBIT_INNER_RADIUS,
  COUPE_ORBIT_OUTER_RADIUS,
  COUPE_ROTATION_BASE_Y,
  COUPE_ROTATION_SWAY_Y,
  COUPE_SAFE_FRAME_HEIGHT,
  COUPE_SAFE_FRAME_WIDTH,
} from "./sceneConfig";

interface CarSceneProps {
  selected: ComponentId;
  onSelect: (id: ComponentId) => void;
}

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

const ORBIT_TARGET = [0, 0.28, 0] as const;

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
      minPolarAngle={0.44}
      maxPolarAngle={1.55}
    />
  );
}

function ProceduralCoupe({ selected, onSelect }: CarSceneProps) {
  const group = useRef<Group>(null);
  const [pausedUntil, setPausedUntil] = useState(0);
  const bodyGeometry = useMemo(() => createCoupeBodyGeometry(), []);
  const cabinGeometry = useMemo(() => createCoupeCabinGeometry(), []);

  useFrame(({ clock }) => {
    if (!group.current) return;
    if (performance.now() > pausedUntil) {
      group.current.rotation.y = COUPE_ROTATION_BASE_Y + Math.sin(clock.elapsedTime * 0.22) * COUPE_ROTATION_SWAY_Y;
    }
  });

  const pause = () => setPausedUntil(performance.now() + 3000);
  const choose = (id: ComponentId) => {
    pause();
    onSelect(id);
  };
  const choosePart = (event: ThreeEvent<MouseEvent>, id: ComponentId) => {
    event.stopPropagation();
    choose(id);
  };
  const cabinPosition = HIGHLIGHT_REGIONS.service.position;
  const wheelPositions = [
    [-1.46, -0.06, 1.06],
    [-1.46, -0.06, -1.06],
    [1.48, -0.06, 1.06],
    [1.48, -0.06, -1.06],
  ] as const;
  const visibleWheelRims = [
    [-1.46, -0.06, 1.18],
    [1.48, -0.06, 1.18],
  ] as const;

  const renderHighlight = (id: ComponentId) => {
    const region = HIGHLIGHT_REGIONS[id];
    const active = selected === id;

    if (region.kind === "cabin") {
      return (
        <group key={id}>
          <mesh
            geometry={cabinGeometry}
            position={[region.position[0], region.position[1], region.position[2]]}
            renderOrder={3}
            onClick={(event) => choosePart(event, id)}
          >
            <meshBasicMaterial
              color="#00d2be"
              transparent
              opacity={active ? 0.18 : 0.035}
              depthWrite={false}
              depthTest={false}
            />
          </mesh>
          {active && (
            <mesh
              geometry={cabinGeometry}
              position={[region.position[0], region.position[1], region.position[2] + 0.02]}
              renderOrder={4}
              scale={[1.08, 1.08, 1.06]}
            >
              <meshBasicMaterial color="#7ffff5" transparent opacity={0.54} wireframe depthTest={false} />
            </mesh>
          )}
        </group>
      );
    }

    if (region.kind === "wheelPair") return null;

    return (
      <group key={id}>
        <mesh
          position={[region.position[0], region.position[1], region.position[2]]}
          renderOrder={3}
          onClick={(event) => choosePart(event, id)}
        >
          <boxGeometry args={[region.size[0], region.size[1], region.size[2]]} />
          <meshStandardMaterial
            color="#00d2be"
            emissive="#00d2be"
            emissiveIntensity={active ? 0.46 : 0.08}
            transparent
            opacity={active ? 0.27 : 0.055}
            depthWrite={false}
            depthTest={false}
            metalness={0.16}
            roughness={0.24}
          />
        </mesh>
        {active && (
          <mesh position={[region.position[0], region.position[1], region.position[2] + 0.01]} renderOrder={4}>
            <boxGeometry args={[region.size[0] + 0.1, region.size[1] + 0.08, region.size[2] + 0.1]} />
            <meshBasicMaterial color="#7ffff5" transparent opacity={0.58} wireframe depthTest={false} />
          </mesh>
        )}
      </group>
    );
  };

  return (
    <group ref={group} rotation={[0.02, COUPE_ROTATION_BASE_Y, 0]} onPointerDown={pause}>
      <mesh geometry={bodyGeometry} position={[0, 0.28, 0]}>
        <meshPhysicalMaterial
          color="#102021"
          emissive="#001312"
          emissiveIntensity={0.03}
          metalness={0.82}
          roughness={0.25}
          clearcoat={0.75}
          clearcoatRoughness={0.2}
        />
      </mesh>

      <mesh
        geometry={cabinGeometry}
        position={[cabinPosition[0], cabinPosition[1], 0]}
        onClick={(event) => choosePart(event, "service")}
      >
        <meshPhysicalMaterial color="#030606" metalness={0.95} roughness={0.18} clearcoat={0.85} />
      </mesh>

      <mesh position={[-0.44, 0.9, 0.78]} rotation={[0, 0, -0.07]}>
        <boxGeometry args={[1.78, 0.055, 0.035]} />
        <meshBasicMaterial color="#e6fffb" transparent opacity={0.62} />
      </mesh>

      <mesh position={[-0.08, 0.42, 1.02]}>
        <boxGeometry args={[4.54, 0.04, 0.035]} />
        <meshBasicMaterial color="#6df4e8" transparent opacity={0.22} />
      </mesh>

      {COMPONENTS.map((component) => renderHighlight(component.id))}

      {wheelPositions.map(([x, y, z]) => (
        <mesh key={`${x}-${z}`} position={[x, y, z]} rotation={[Math.PI / 2, 0, 0]} onClick={(event) => choosePart(event, "brakes")}>
          <cylinderGeometry args={[0.43, 0.43, 0.22, 56]} />
          <meshStandardMaterial
            color="#020404"
            emissive={selected === "brakes" ? "#00d2be" : "#000000"}
            emissiveIntensity={selected === "brakes" ? 0.34 : 0}
            metalness={0.6}
            roughness={0.32}
          />
        </mesh>
      ))}
      {visibleWheelRims.map(([x, y, z]) => (
        <mesh key={`rim-${x}`} position={[x, y, z]}>
          <torusGeometry args={[0.32, 0.035, 12, 48]} />
          <meshBasicMaterial color="#00d2be" transparent opacity={selected === "brakes" ? 0.82 : 0.18} />
        </mesh>
      ))}
      {[
        [-2.3, 0.2, 1.03],
        [2.46, 0.16, 1.03],
      ].map(([x, y, z]) => (
        <mesh key={`lamp-${x}`} position={[x, y, z]}>
          <boxGeometry args={[0.16, 0.06, 0.035]} />
          <meshBasicMaterial color={x > 0 ? "#bffff7" : "#b91414"} transparent opacity={0.75} />
        </mesh>
      ))}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.25, 0]}>
        <ringGeometry args={[COUPE_ORBIT_INNER_RADIUS, COUPE_ORBIT_OUTER_RADIUS, 140]} />
        <meshBasicMaterial color="#00d2be" transparent opacity={0.13} />
      </mesh>
      {selected === "brakes" &&
        visibleWheelRims.map(([x, y, z]) => (
          <mesh key={`brake-glow-${x}`} position={[x, y, z]}>
            <torusGeometry args={[0.43, 0.055, 12, 64]} />
            <meshBasicMaterial color="#00d2be" transparent opacity={0.5} />
          </mesh>
        ))}
    </group>
  );
}

function CarFallback({ selected, onSelect }: CarSceneProps) {
  return (
    <div className="car-fallback" data-testid="car-scene">
      <div className="car-fallback__halo" />
      <div className="car-fallback__silhouette">
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
        <ambientLight intensity={0.58} />
        <directionalLight position={[4, 7, 4]} intensity={2.1} />
        <pointLight color="#00d2be" position={[-4, 2, -3]} intensity={36} />
        <ProceduralCoupe selected={selected} onSelect={onSelect} />
        <CameraRig />
      </Canvas>
    </div>
  );
}
