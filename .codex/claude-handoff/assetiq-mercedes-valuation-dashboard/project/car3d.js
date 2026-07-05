/* <car-3d> — stylized low-poly AMG-style coupe with glowing part highlights (Three.js).
   Attributes: part (engine|battery|brakes|fuel|odometer|obd|service), camera (hero|front|top),
   rotate ("1"|"0"), accent (hex). */
(function () {
  if (customElements.get('car-3d')) return;

  let threeP = null;
  const loadThree = () =>
    threeP ||
    (threeP = import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js').catch(() =>
      import('https://unpkg.com/three@0.160.0/build/three.module.js')
    ));

  class Car3D extends HTMLElement {
    static get observedAttributes() {
      return ['part', 'camera', 'rotate', 'accent', 'interactive'];
    }

    connectedCallback() {
      if (this._started) {
        this._running = true;
        if (this._tickFn) this._tickFn();
        return;
      }
      this._started = true;
      this.style.display = 'block';
      if (!this.style.position) this.style.position = 'relative';
      loadThree()
        .then((THREE) => {
          if (this.isConnected) this._setup(THREE);
        })
        .catch(() => {
          this.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#5c6a68;font:500 12px monospace">3D preview unavailable</div>';
        });
    }

    disconnectedCallback() {
      this._running = false;
    }

    attributeChangedCallback() {
      if (this._ready) this._apply();
    }

    _apply() {
      this._part = this.getAttribute('part') || '';
      this._rotate = this.getAttribute('rotate') !== '0';
      this._interactive = this.getAttribute('interactive') === '1';
      const name = this.getAttribute('camera') || 'hero';
      if (name !== this._camName) {
        this._camName = name;
        const cam = this._cams[name] || this._cams.hero;
        this._look.copy(cam[1]);
        const off = cam[0].clone().sub(cam[1]);
        this._sphT.setFromVector3(off);
        if (!this._sphInit) {
          this._sph.copy(this._sphT);
          this._sphInit = true;
        }
      }
      if (this._renderer) this._renderer.domElement.style.cursor = this._interactive ? 'grab' : '';
    }

    _setup(THREE) {
      const accent = new THREE.Color(this.getAttribute('accent') || '#00D2BE');
      this._accent = accent;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
      let renderer;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      } catch (e) {
        this.innerHTML =
          '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#5c6a68;font:500 12px monospace">WebGL unavailable</div>';
        return;
      }
      renderer.setClearColor(0x000000, 0);
      renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
      renderer.domElement.style.cssText = 'width:100%;height:100%;display:block';
      this.appendChild(renderer.domElement);

      // ---- lights
      scene.add(new THREE.AmbientLight(0xaebfbc, 0.55));
      const key = new THREE.DirectionalLight(0xffffff, 1.9);
      key.position.set(4, 8, 3);
      scene.add(key);
      const rim = new THREE.PointLight(accent, 40, 40);
      rim.position.set(-6, 2.5, -5);
      scene.add(rim);
      const fill = new THREE.PointLight(0x6a8a92, 14, 30);
      fill.position.set(5, 1.5, -4);
      scene.add(fill);

      // ---- car group
      const car = new THREE.Group();
      scene.add(car);
      this._car = car;

      // body: extruded side profile, tapered roof
      const s = new THREE.Shape();
      s.moveTo(2.38, 0.24);
      s.lineTo(2.46, 0.42);
      s.quadraticCurveTo(2.46, 0.58, 2.2, 0.64);
      s.lineTo(1.25, 0.78);
      s.quadraticCurveTo(0.7, 0.84, 0.42, 1.06);
      s.quadraticCurveTo(0.1, 1.2, -0.3, 1.2);
      s.quadraticCurveTo(-1.2, 1.14, -1.85, 0.84);
      s.quadraticCurveTo(-2.35, 0.74, -2.42, 0.56);
      s.lineTo(-2.36, 0.26);
      s.lineTo(-1.9, 0.2);
      s.lineTo(1.9, 0.2);
      s.closePath();

      const geo = new THREE.ExtrudeGeometry(s, {
        depth: 1.5,
        bevelEnabled: true,
        bevelThickness: 0.14,
        bevelSize: 0.12,
        bevelSegments: 4,
        steps: 1,
        curveSegments: 12,
      });
      geo.translate(0, 0, -0.75);
      const pos = geo.attributes.position;
      for (let i = 0; i < pos.count; i++) {
        const y = pos.getY(i);
        if (y > 0.8) {
          const f = 1 - (y - 0.8) * 0.55;
          pos.setZ(i, pos.getZ(i) * f);
        }
      }
      geo.computeVertexNormals();
      const bodyMat = new THREE.MeshStandardMaterial({ color: 0x161a1c, metalness: 0.85, roughness: 0.38 });
      car.add(new THREE.Mesh(geo, bodyMat));

      this._edgeBase = new THREE.Color(0x2e3a3c);
      this._edgeMat = new THREE.LineBasicMaterial({ color: this._edgeBase.clone(), transparent: true, opacity: 0.75 });
      car.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 22), this._edgeMat));

      // spoiler + mirrors
      const sp = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.05, 1.15), bodyMat);
      sp.position.set(-2.15, 0.88, 0);
      car.add(sp);
      const mirG = new THREE.BoxGeometry(0.16, 0.07, 0.14);
      [[0.5, 0.92, 0.92], [0.5, 0.92, -0.92]].forEach(([x, y, z]) => {
        const m = new THREE.Mesh(mirG, bodyMat);
        m.position.set(x, y, z);
        car.add(m);
      });

      // wheels + rims
      const wheelG = new THREE.CylinderGeometry(0.37, 0.37, 0.26, 24);
      wheelG.rotateX(Math.PI / 2);
      const wheelM = new THREE.MeshStandardMaterial({ color: 0x0b0d0e, metalness: 0.4, roughness: 0.7 });
      const rimG = new THREE.TorusGeometry(0.24, 0.025, 8, 24);
      const rimM = new THREE.MeshStandardMaterial({ color: 0x4a585c, metalness: 0.9, roughness: 0.3 });
      const wheelPos = [
        [1.48, 0.37, 0.82],
        [1.48, 0.37, -0.82],
        [-1.45, 0.37, 0.82],
        [-1.45, 0.37, -0.82],
      ];
      for (const [x, y, z] of wheelPos) {
        const w = new THREE.Mesh(wheelG, wheelM);
        w.position.set(x, y, z);
        car.add(w);
        const r = new THREE.Mesh(rimG, rimM);
        r.position.set(x, y, z > 0 ? z + 0.135 : z - 0.135);
        car.add(r);
      }

      // head/tail lights
      const hlG = new THREE.BoxGeometry(0.06, 0.09, 0.34);
      const hlM = new THREE.MeshBasicMaterial({ color: 0xcfe8e4 });
      [[2.44, 0.5, 0.5], [2.44, 0.5, -0.5]].forEach(([x, y, z]) => {
        const m = new THREE.Mesh(hlG, hlM);
        m.position.set(x, y, z);
        car.add(m);
      });
      const tl = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.07, 1.3), new THREE.MeshBasicMaterial({ color: 0xd8443a }));
      tl.position.set(-2.44, 0.62, 0);
      car.add(tl);

      // ---- ground
      const ground = new THREE.Mesh(new THREE.CircleGeometry(3.6, 48), new THREE.MeshBasicMaterial({ color: 0x0c0f10 }));
      ground.rotation.x = -Math.PI / 2;
      ground.position.y = -0.02;
      scene.add(ground);
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(3.45, 3.6, 64),
        new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.12, side: THREE.DoubleSide })
      );
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = -0.01;
      scene.add(ring);
      const grid = new THREE.PolarGridHelper(3.4, 8, 3, 48, 0x1a2224, 0x141a1c);
      grid.position.y = 0.0;
      scene.add(grid);

      // ---- glowing x-ray parts
      this._glowMats = {};
      const addPart = (id, g, x, y, z) => {
        const fillM = new THREE.MeshBasicMaterial({
          color: accent,
          transparent: true,
          opacity: 0,
          depthTest: false,
          blending: THREE.AdditiveBlending,
        });
        const lineM = new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0, depthTest: false });
        lineM.userData.line = true;
        const m = new THREE.Mesh(g, fillM);
        m.position.set(x, y, z);
        m.renderOrder = 8;
        car.add(m);
        const l = new THREE.LineSegments(new THREE.EdgesGeometry(g), lineM);
        l.position.set(x, y, z);
        l.renderOrder = 9;
        car.add(l);
        (this._glowMats[id] = this._glowMats[id] || []).push(fillM, lineM);
      };

      addPart('engine', new THREE.BoxGeometry(1.0, 0.42, 1.0), 1.55, 0.5, 0);
      addPart('engine', new THREE.BoxGeometry(1.4, 0.22, 0.34), 0.5, 0.38, 0);
      addPart('battery', new THREE.BoxGeometry(0.5, 0.26, 0.45), -1.85, 0.52, 0.35);
      addPart('battery', new THREE.BoxGeometry(0.34, 0.2, 0.3), 1.1, 0.54, -0.5);
      const discG = new THREE.CylinderGeometry(0.23, 0.23, 0.06, 20);
      discG.rotateX(Math.PI / 2);
      for (const [x, y, z] of wheelPos) addPart('brakes', discG, x, y, z);
      addPart('fuel', new THREE.BoxGeometry(0.9, 0.28, 1.1), -1.15, 0.38, 0);
      addPart('odometer', new THREE.BoxGeometry(0.3, 0.16, 0.5), 0.62, 0.88, -0.32);
      addPart('obd', new THREE.BoxGeometry(0.22, 0.14, 0.24), 0.95, 0.5, -0.55);
      // 'service' highlights the whole body via edge pulse (handled in tick)

      // ---- cameras
      this._cams = {
        hero: [new THREE.Vector3(5.4, 2.6, 5.4), new THREE.Vector3(0, 0.45, 0)],
        front: [new THREE.Vector3(-6.4, 2.2, 5.2), new THREE.Vector3(0, 0.45, 0)],
        top: [new THREE.Vector3(0, 12.5, 0.6), new THREE.Vector3(0, 0, 0)],
        side: [new THREE.Vector3(0, 1.4, 7.4), new THREE.Vector3(0, 0.45, 0)],
      };
      this._look = new THREE.Vector3(0, 0.45, 0);
      this._sph = new THREE.Spherical();
      this._sphT = new THREE.Spherical();
      this._pauseUntil = 0;

      this._scene = scene;
      this._camera = camera;
      this._renderer = renderer;
      this._ready = true;
      this._running = true;
      this._t = 0;
      this._apply();
      this._camera.position.setFromSpherical(this._sph).add(this._look);

      // ---- drag-to-orbit / scroll-to-zoom (only when interactive="1")
      const el = renderer.domElement;
      el.style.touchAction = 'none';
      let drag = null;
      el.addEventListener('pointerdown', (e) => {
        if (!this._interactive) return;
        drag = [e.clientX, e.clientY];
        el.setPointerCapture(e.pointerId);
        el.style.cursor = 'grabbing';
        this._pauseUntil = performance.now() + 2500;
      });
      el.addEventListener('pointermove', (e) => {
        if (!drag) return;
        const dx = e.clientX - drag[0];
        const dy = e.clientY - drag[1];
        drag = [e.clientX, e.clientY];
        this._sphT.theta -= dx * 0.006;
        this._sphT.phi = Math.min(1.52, Math.max(0.08, this._sphT.phi - dy * 0.005));
        this._pauseUntil = performance.now() + 2500;
      });
      const endDrag = () => {
        drag = null;
        el.style.cursor = this._interactive ? 'grab' : '';
      };
      el.addEventListener('pointerup', endDrag);
      el.addEventListener('pointercancel', endDrag);
      el.addEventListener('wheel', (e) => {
        if (!this._interactive) return;
        e.preventDefault();
        this._sphT.radius = Math.min(13, Math.max(4.5, this._sphT.radius + e.deltaY * 0.01));
        this._pauseUntil = performance.now() + 2500;
      }, { passive: false });

      const resize = () => {
        const w = this.clientWidth || 300;
        const h = this.clientHeight || 200;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      };
      this._ro = new ResizeObserver(resize);
      this._ro.observe(this);
      resize();

      const clock = new THREE.Clock();
      const tick = () => {
        if (!this._running || !this.isConnected) return;
        requestAnimationFrame(tick);
        const dt = Math.min(0.05, clock.getDelta());
        this._t += dt;
        if (this._rotate && performance.now() > this._pauseUntil) car.rotation.y += dt * 0.12;
        const pulse = 0.55 + 0.4 * Math.sin(this._t * 3.2);
        for (const k in this._glowMats) {
          const on = k === this._part;
          for (const m of this._glowMats[k]) {
            const target = on ? (m.userData.line ? pulse : pulse * 0.4) : 0;
            m.opacity += (target - m.opacity) * Math.min(1, dt * 10);
          }
        }
        const svc = this._part === 'service';
        this._edgeMat.color.lerp(svc ? accent : this._edgeBase, Math.min(1, dt * 5));
        this._edgeMat.opacity += ((svc ? 0.35 + pulse * 0.65 : 0.75) - this._edgeMat.opacity) * Math.min(1, dt * 5);
        const k = Math.min(1, dt * 4);
        this._sph.radius += (this._sphT.radius - this._sph.radius) * k;
        this._sph.theta += (this._sphT.theta - this._sph.theta) * k;
        this._sph.phi += (this._sphT.phi - this._sph.phi) * k;
        camera.position.setFromSpherical(this._sph).add(this._look);
        camera.lookAt(this._look);
        renderer.render(scene, camera);
      };
      this._tickFn = tick;
      tick();
    }
  }

  customElements.define('car-3d', Car3D);
})();
