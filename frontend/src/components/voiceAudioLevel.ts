import { useEffect, useRef, useState } from "react";

export function levelFromFrequencyData(data: Uint8Array): number {
  if (data.length === 0) return 0;
  let sum = 0;
  for (let index = 0; index < data.length; index += 1) {
    sum += data[index];
  }
  return Math.min(1, sum / data.length / 128);
}

let sharedAudioContext: AudioContext | null = null;

export function getAudioContext(): AudioContext | null {
  if (sharedAudioContext) return sharedAudioContext;
  const Ctor =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  sharedAudioContext = new Ctor();
  return sharedAudioContext;
}

interface LevelResult {
  level: number;
  idle: boolean;
}

function pollAnalyser(analyser: AnalyserNode, onLevel: (level: number) => void): () => void {
  const data = new Uint8Array(analyser.frequencyBinCount);
  let frameId = 0;
  let cancelled = false;

  const tick = () => {
    if (cancelled) return;
    analyser.getByteFrequencyData(data);
    onLevel(levelFromFrequencyData(data));
    frameId = window.requestAnimationFrame(tick);
  };
  frameId = window.requestAnimationFrame(tick);

  return () => {
    cancelled = true;
    window.cancelAnimationFrame(frameId);
  };
}

export function useMicLevel(active: boolean): LevelResult {
  const [level, setLevel] = useState(0);
  const [idle, setIdle] = useState(true);

  useEffect(() => {
    if (!active) {
      setLevel(0);
      setIdle(true);
      return undefined;
    }

    let cancelled = false;
    let stopPolling: (() => void) | null = null;
    let stream: MediaStream | null = null;

    const context = getAudioContext();
    if (!context || !navigator.mediaDevices?.getUserMedia) {
      setIdle(true);
      return undefined;
    }

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((acquiredStream) => {
        if (cancelled) {
          acquiredStream.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = acquiredStream;
        const source = context.createMediaStreamSource(acquiredStream);
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        setIdle(false);
        stopPolling = pollAnalyser(analyser, setLevel);
      })
      .catch(() => {
        setIdle(true);
      });

    return () => {
      cancelled = true;
      stopPolling?.();
      stream?.getTracks().forEach((track) => track.stop());
      setIdle(true);
      setLevel(0);
    };
  }, [active]);

  return { level, idle };
}

export function usePlaybackLevel(audioElement: HTMLAudioElement | null): LevelResult {
  const [level, setLevel] = useState(0);
  const [idle, setIdle] = useState(true);
  const sourceCacheRef = useRef(new WeakMap<HTMLAudioElement, MediaElementAudioSourceNode>());

  useEffect(() => {
    if (!audioElement) {
      setLevel(0);
      setIdle(true);
      return undefined;
    }

    const context = getAudioContext();
    if (!context) {
      setIdle(true);
      return undefined;
    }

    let source = sourceCacheRef.current.get(audioElement);
    if (!source) {
      source = context.createMediaElementSource(audioElement);
      source.connect(context.destination);
      sourceCacheRef.current.set(audioElement, source);
    }

    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    setIdle(false);
    const stopPolling = pollAnalyser(analyser, setLevel);

    return () => {
      stopPolling();
      setIdle(true);
      setLevel(0);
    };
  }, [audioElement]);

  return { level, idle };
}
