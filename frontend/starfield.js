// Static starfield painted once onto a fixed background canvas.
// No animation, so prefers-reduced-motion needs no special handling.
(function () {
  const canvas = document.getElementById('starfield');
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext('2d');

  const STARS_PER_MEGAPIXEL = 260;
  const RESIZE_DEBOUNCE_MS = 150;
  const SEED = 20260930;

  // Small seeded PRNG (mulberry32) so the sky doesn't reshuffle on every resize.
  function makeRandom(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function draw() {
    const dpr = window.devicePixelRatio || 1;
    const width = window.innerWidth;
    const height = window.innerHeight;

    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const random = makeRandom(SEED);
    const count = Math.round((width * height) / 1e6 * STARS_PER_MEGAPIXEL);

    for (let i = 0; i < count; i++) {
      const x = random() * width;
      const y = random() * height;
      // Most stars are tiny and dim; a few are slightly larger.
      const isBright = random() < 0.06;
      const radius = isBright ? 0.9 + random() * 0.5 : 0.35 + random() * 0.45;
      const alpha = isBright ? 0.45 + random() * 0.25 : 0.12 + random() * 0.28;

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(232, 236, 244, ${alpha.toFixed(3)})`;
      ctx.fill();
    }
  }

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(draw, RESIZE_DEBOUNCE_MS);
  });

  draw();
})();
