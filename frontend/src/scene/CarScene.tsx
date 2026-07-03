import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useLoader, useThree, type ThreeEvent } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Box3, Mesh, MeshPhysicalMaterial, Vector3 } from "three";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
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
const IMPORTED_CAR_MODEL_PATH = "/models/car-v2/11497_Car_v2.obj";
const AERO_STRIPS: ReadonlyArray<{
  position: readonly [number, number, number];
  rotation: number;
  size: [number, number, number];
}> = [
  { position: [0.7, 0.68, 0.92], rotation: -0.04, size: [1.72, 0.024, 0.026] },
  { position: [1.22, 0.64, 0.92], rotation: -0.08, size: [0.96, 0.022, 0.026] },
];
const IMPORTED_WHEEL_HIGHLIGHTS = [
  [-1.86, -0.05, 1.3],
  [1.72, -0.05, 1.3],
] as const;

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

function ImportedComponentHighlights({ selected, onSelect }: CarSceneProps) {
  const choosePart = (event: ThreeEvent<MouseEvent>, id: ComponentId) => {
    event.stopPropagation();
    onSelect(id);
  };

  return (
    <group>
      {COMPONENTS.map((component) => {
        const region = HIGHLIGHT_REGIONS[component.id];
        const active = selected === component.id;

        if (region.kind === "wheelPair") {
          return (
            <group key={component.id}>
              {IMPORTED_WHEEL_HIGHLIGHTS.map(([x, y, z]) => (
                <mesh key={`imported-wheel-${x}`} position={[x, y, z]} onClick={(event) => choosePart(event, component.id)}>
                  <torusGeometry args={[0.62, active ? 0.07 : 0.04, 16, 88]} />
                  <meshBasicMaterial color="#7ffff5" transparent opacity={active ? 0.72 : 0.2} depthTest={false} />
                </mesh>
              ))}
            </group>
          );
        }

        return (
          <group key={component.id}>
            <mesh
              position={[region.position[0], region.position[1], region.position[2]]}
              renderOrder={4}
              onClick={(event) => choosePart(event, component.id)}
            >
              <boxGeometry args={[region.size[0], region.size[1], region.size[2]]} />
              <meshStandardMaterial
                color="#00d2be"
                emissive="#00d2be"
                emissiveIntensity={active ? 0.58 : 0.1}
                transparent
                opacity={active ? 0.34 : 0.08}
                depthWrite={false}
                depthTest={false}
                metalness={0.16}
                roughness={0.24}
              />
            </mesh>
            {active && (
              <mesh position={[region.position[0], region.position[1], region.position[2] + 0.02]} renderOrder={5}>
                <boxGeometry args={[region.size[0] + 0.14, region.size[1] + 0.1, region.size[2] + 0.14]} />
                <meshBasicMaterial color="#7ffff5" transparent opacity={0.72} wireframe depthTest={false} />
              </mesh>
            )}
          </group>
        );
      })}
    </group>
  );
}

function ImportedCarModel({ selected, onSelect }: CarSceneProps) {
  const source = useLoader(OBJLoader, IMPORTED_CAR_MODEL_PATH);
  const bodyMaterial = useMemo(
    () =>
      new MeshPhysicalMaterial({
        color: "#263f42",
        emissive: "#0a2625",
        emissiveIntensity: 0.14,
        metalness: 0.5,
        roughness: 0.3,
        clearcoat: 0.62,
        clearcoatRoughness: 0.26,
        transparent: true,
        opacity: 0.84,
        depthWrite: false,
      }),
    [],
  );
  const model = useMemo(() => {
    const clone = source.clone(true);
    const bounds = new Box3().setFromObject(clone);
    const center = bounds.getCenter(new Vector3());
    clone.position.sub(center);

    clone.traverse((child) => {
      if (!(child instanceof Mesh)) return;
      child.castShadow = true;
      child.receiveShadow = true;
      child.material = bodyMaterial;
    });

    return clone;
  }, [bodyMaterial, source]);

  return (
    <>
      <group
        position={[0, 0.42, 0]}
        rotation={[-Math.PI / 2, 0, Math.PI / 2]}
        scale={[0.029, 0.029, 0.029]}
        onClick={(event) => {
          event.stopPropagation();
          onSelect("service");
        }}
      >
        <primitive object={model} />
      </group>
      <ImportedComponentHighlights selected={selected} onSelect={onSelect} />
    </>
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
    [-1.86, -0.05, 1.16],
    [-1.86, -0.05, -1.16],
    [1.72, -0.05, 1.16],
    [1.72, -0.05, -1.16],
  ] as const;
  const visibleWheelRims = [
    [-1.86, -0.05, 1.28],
    [1.72, -0.05, 1.28],
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

      {AERO_STRIPS.map((strip) => (
        <mesh key={`aero-strip-${strip.position[0]}`} position={strip.position} rotation={[0, 0, strip.rotation]}>
          <boxGeometry args={strip.size} />
          <meshBasicMaterial color="#e6fffb" transparent opacity={0.52} />
        </mesh>
      ))}

      <mesh position={[-0.2, 0.25, 1.04]}>
        <boxGeometry args={[4.6, 0.028, 0.026]} />
        <meshBasicMaterial color="#6df4e8" transparent opacity={0.18} />
      </mesh>

      {COMPONENTS.map((component) => renderHighlight(component.id))}

      {wheelPositions.map(([x, y, z]) => (
        <mesh key={`${x}-${z}`} position={[x, y, z]} rotation={[Math.PI / 2, 0, 0]} onClick={(event) => choosePart(event, "brakes")}>
          <cylinderGeometry args={[0.54, 0.54, 0.3, 80]} />
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
        <mesh key={`arch-shadow-${x}`} position={[x, y + 0.02, z + 0.005]}>
          <torusGeometry args={[0.62, 0.03, 12, 96]} />
          <meshBasicMaterial color="#141716" transparent opacity={0.55} />
        </mesh>
      ))}
      {visibleWheelRims.map(([x, y, z]) => (
        <mesh key={`arch-lip-${x}`} position={[x, y + 0.02, z + 0.02]}>
          <torusGeometry args={[0.6, 0.044, 18, 96]} />
          <meshStandardMaterial color="#102021" emissive="#001312" emissiveIntensity={0.02} metalness={0.72} roughness={0.25} />
        </mesh>
      ))}
      {visibleWheelRims.map(([x, y, z]) => (
        <mesh key={`rim-${x}`} position={[x, y, z]}>
          <torusGeometry args={[0.38, 0.06, 18, 80]} />
          <meshBasicMaterial color="#00d2be" transparent opacity={selected === "brakes" ? 0.82 : 0.18} />
        </mesh>
      ))}
      {[
        [-2.58, 0.2, 1.08],
        [2.62, 0.14, 1.08],
      ].map(([x, y, z]) => (
        <mesh key={`lamp-${x}`} position={[x, y, z]}>
          <boxGeometry args={[0.18, 0.042, 0.026]} />
          <meshBasicMaterial color={x > 0 ? "#bffff7" : "#b91414"} transparent opacity={0.7} />
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
        <Suspense fallback={<ProceduralCoupe selected={selected} onSelect={onSelect} />}>
          <ImportedCarModel selected={selected} onSelect={onSelect} />
        </Suspense>
        <CameraRig />
      </Canvas>
    </div>
  );
}
