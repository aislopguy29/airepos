// node render.js plan.json frames_dir start end [step]   -> writes JPEG frames start..end-1 (stride = step, offset = start)
// node render.js plan.json pv out_prefix t1,t2,...         -> PNG stills
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
(async () => {
  const [planPath, a2, a3, a4, a5] = process.argv.slice(2);
  const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', e => console.error('PAGEERR:', e.message));
  await page.goto('file://' + path.join(__dirname, 'scene.html'));
  await page.evaluate(() => window.ready()); await page.evaluate(p => window.setup(p), plan);
  const t0 = Date.now();
  if (a2 === 'pv') {
    for (const t of a4.split(',').map(Number)) { const url = await page.evaluate(i => window.frame(i, 'png'), Math.round(t * plan.fps)); fs.writeFileSync(`${a3}_${t.toFixed(2)}.png`, Buffer.from(url.split(',')[1], 'base64')); }
  } else {
    fs.mkdirSync(a2, { recursive: true }); const start = +a3, end = +a4, step = +(a5 || 1); let n = 0;
    for (let i = start; i < end; i += step) {
      const url = await page.evaluate(k => window.frame(k, 'jpeg'), i);
      fs.writeFileSync(path.join(a2, String(i).padStart(5, '0') + '.jpg'), Buffer.from(url.split(',')[1], 'base64'));
      if (++n % 60 === 0) console.error(`  worker ${start}: ${n} frames  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
