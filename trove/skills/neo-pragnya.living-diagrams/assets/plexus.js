/*!
 * plexus.js — a living constellation canvas (no dependencies). Part of the "living-diagrams" skill · MIT · Neo Pragnya
 *
 *   <canvas data-plexus="orbits"></canvas>   agents ride tilted orbits around a glowing core; they drift off their
 *                                           path and a soft spring (not a wall) guides them back; neighbours link
 *   <canvas data-plexus="web"></canvas>      free-floating nodes that link when close: a classic plexus
 *
 * Options (data attributes):
 *   data-colors="#f0cf7a,#bcd0ff"   node/link colours (first is the "gold" accent)
 *   data-core="#ffecb4"             core colour (orbits only)
 *   data-count="30"                 number of nodes
 *   data-rings="4"                  number of orbits (orbits only)
 *   data-place="right|center"       where the system sits (orbits; "right" leaves room for copy on the left)
 *   data-stars="90"                 background star count (0 to disable)
 *
 * The cursor gently attracts nearby nodes and lights their links; a click sends a pulse ring from the core that
 * nudges every node it crosses. Pauses off-screen. Honours prefers-reduced-motion and ?motion=static (one still frame).
 * Place the canvas inside a position:relative container; it fills it (CSS: position:absolute; inset:0).
 */
(() => {
  "use strict";
  const TAU = Math.PI * 2;
  const still =
    new URLSearchParams(location.search).get("motion") === "static" ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const hexToRgb = (hex) => {
    const h = hex.replace("#", "");
    const n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h, 16);
    return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
  };

  function init(canvas) {
    if (canvas.__plexus) return;
    canvas.__plexus = true;
    const ctx = canvas.getContext("2d");
    const mode = canvas.dataset.plexus || "orbits";
    const colors = (canvas.dataset.colors || "#f0cf7a,#bcd0ff").split(",").map((s) => s.trim());
    const core = canvas.dataset.core || "#ffecb4";
    const place = canvas.dataset.place || "right";
    let seed = 11;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

    const ringCount = parseInt(canvas.dataset.rings || "4", 10);
    const RINGS = Array.from({ length: ringCount }, (_, i) => ({
      r: 0.3 + (0.66 * i) / Math.max(1, ringCount - 1),
      tilt: 0.3 + rnd() * 0.14,
      rot: (rnd() - 0.5) * 0.9,
      speed: 0.22 / (1 + i * 0.9),
      color: hexToRgb(colors[i % colors.length]),
    }));
    const count = parseInt(canvas.dataset.count || "30", 10);
    const nodes = Array.from({ length: count }, (_, i) => ({
      ring: RINGS[i % RINGS.length],
      a: rnd() * TAU,
      speed: (0.7 + rnd() * 0.6) * (i % 3 === 0 ? -1 : 1),
      drift: 0,
      dv: 0,
      size: 1.6 + rnd() * 2.4,
      color: colors[i % colors.length],
      fx: rnd(),
      fy: rnd(),
      vx: (rnd() - 0.5) * 0.25,
      vy: (rnd() - 0.5) * 0.25,
      x: 0,
      y: 0,
    }));
    const stars = Array.from({ length: parseInt(canvas.dataset.stars ?? "90", 10) }, () => ({
      x: rnd(),
      y: rnd(),
      s: rnd() * 1.2 + 0.2,
      p: rnd() * TAU,
    }));
    const pointer = { x: -9999, y: -9999 };
    const pulses = [];
    let w = 0;
    let h = 0;
    let cx = 0;
    let cy = 0;
    let R = 0;
    let visible = true;

    function resize() {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.max(1, w * dpr);
      canvas.height = Math.max(1, h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const wide = w > 760;
      cx = place === "center" || !wide ? w * 0.5 : w * 0.8;
      cy = wide ? h * 0.5 : h * 0.9;
      R = place === "center" ? Math.min(w, h) * 0.42 : Math.min(wide ? w * 0.25 : w * 0.48, h * (wide ? 0.6 : 0.4));
    }
    const onRing = (ring, a, extra = 0) => {
      const rr = R * ring.r * (1 + extra);
      const ex = Math.cos(a) * rr;
      const ey = Math.sin(a) * rr * ring.tilt;
      return [cx + ex * Math.cos(ring.rot) - ey * Math.sin(ring.rot), cy + ex * Math.sin(ring.rot) + ey * Math.cos(ring.rot)];
    };

    function draw(time) {
      const t = time / 1000;
      ctx.clearRect(0, 0, w, h);
      for (const s of stars) {
        ctx.globalAlpha = 0.35 + 0.35 * Math.sin(t * 1.3 + s.p);
        ctx.fillStyle = "#dfe8ff";
        ctx.fillRect(s.x * w, s.y * h, s.s, s.s);
      }
      ctx.globalAlpha = 1;

      if (mode === "orbits") {
        for (const ring of RINGS) {
          ctx.beginPath();
          for (let i = 0; i <= 96; i++) {
            const [x, y] = onRing(ring, (i / 96) * TAU);
            if (i) ctx.lineTo(x, y);
            else ctx.moveTo(x, y);
          }
          ctx.strokeStyle = `rgba(${ring.color},0.32)`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
        const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.22);
        glow.addColorStop(0, `rgba(${hexToRgb(core)},0.95)`);
        glow.addColorStop(0.25, `rgba(${hexToRgb(colors[0])},0.55)`);
        glow.addColorStop(1, `rgba(${hexToRgb(colors[0])},0)`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(cx, cy, R * 0.22, 0, TAU);
        ctx.fill();
        ctx.fillStyle = core;
        ctx.beginPath();
        ctx.arc(cx, cy, 4.5, 0, TAU);
        ctx.fill();
      }

      for (let i = pulses.length - 1; i >= 0; i--) {
        const age = t - pulses[i];
        if (age > 2.4) {
          pulses.splice(i, 1);
          continue;
        }
        ctx.beginPath();
        ctx.arc(cx, cy, (age / 2.4) * Math.max(R * 1.05, w * 0.6), 0, TAU);
        ctx.strokeStyle = `rgba(${hexToRgb(colors[0])},${0.55 * (1 - age / 2.4)})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      for (const g of nodes) {
        let px;
        let py;
        if (mode === "orbits") {
          if (!still) g.a += g.ring.speed * g.speed * 0.016;
          [px, py] = onRing(g.ring, g.a, g.drift);
          const hit = pulses.some((p) => Math.abs(((t - p) / 2.4) * R * 1.05 - Math.hypot(px - cx, py - cy)) < 14);
          g.dv += (Math.sin(t * 0.7 + g.a * 3) * 0.04 - g.drift) * 0.02 + (hit ? 0.02 : 0); // spring back to the orbit
          g.dv *= 0.9;
          g.drift += g.dv;
        } else {
          if (!still) {
            g.fx += g.vx / Math.max(1, w);
            g.fy += g.vy / Math.max(1, h);
            if (g.fx < 0 || g.fx > 1) g.vx *= -1;
            if (g.fy < 0 || g.fy > 1) g.vy *= -1;
          }
          px = g.fx * w;
          py = g.fy * h;
        }
        const dx = pointer.x - px;
        const dy = pointer.y - py;
        const pull = Math.max(0, 1 - Math.hypot(dx, dy) / 170);
        g.x = px + dx * pull * 0.18;
        g.y = py + dy * pull * 0.18;
      }

      const reach = mode === "orbits" ? R * 0.32 : Math.min(w, h) * 0.22;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < reach) {
            const lit = Math.max(0, 1 - Math.hypot(pointer.x - (a.x + b.x) / 2, pointer.y - (a.y + b.y) / 2) / 170);
            ctx.globalAlpha = (1 - d / reach) * (0.45 + lit * 0.5);
            ctx.strokeStyle = a.color;
            ctx.lineWidth = 0.8 + lit;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }
      ctx.globalAlpha = 1;
      for (const g of nodes) {
        const near = Math.max(0, 1 - Math.hypot(pointer.x - g.x, pointer.y - g.y) / 170);
        ctx.fillStyle = g.color;
        ctx.shadowColor = g.color;
        ctx.shadowBlur = 8 + near * 14;
        ctx.beginPath();
        ctx.arc(g.x, g.y, g.size * (1 + near * 0.8), 0, TAU);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    }

    const loop = (time) => {
      if (visible) draw(time);
      requestAnimationFrame(loop);
    };
    resize();
    window.addEventListener("resize", () => {
      resize();
      if (still) draw(4000);
    });
    if (still) return void draw(4000);
    const host = canvas.parentElement || canvas;
    host.addEventListener("pointermove", (e) => {
      const rect = canvas.getBoundingClientRect();
      pointer.x = e.clientX - rect.left;
      pointer.y = e.clientY - rect.top;
    });
    host.addEventListener("pointerleave", () => (pointer.x = pointer.y = -9999));
    host.addEventListener("click", (e) => {
      if (!e.target.closest("a,button")) pulses.push(performance.now() / 1000);
    });
    new IntersectionObserver(([entry]) => (visible = entry.isIntersecting)).observe(canvas);
    setInterval(() => visible && pulses.push(performance.now() / 1000), 6000);
    requestAnimationFrame(loop);
  }

  const auto = (root = document) => root.querySelectorAll("canvas[data-plexus]").forEach(init);
  window.Plexus = { init, auto };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => auto());
  else auto();
})();
