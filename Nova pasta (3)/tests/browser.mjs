import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { chromium, expect } from '@playwright/test';
import { createServer } from 'vite';

const artifactDirectory = path.resolve('artifacts/screenshots');
const mobileOnly = process.argv.includes('--mobile-only');
await mkdir(artifactDirectory, { recursive: true });
const errors = [];
const checks = [];
let server;
let browser;

function watchErrors(page) {
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('requestfailed', request => errors.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`));
}

function checked(message) {
  checks.push(message);
  console.log(`✓ ${message}`);
}

async function settle(page) {
  // The accessible busy state follows the actual animation, including slow GPUs.
  await expect(page.locator('#viewport')).toHaveAttribute('aria-busy', 'false', { timeout: 30_000 });
  await page.waitForTimeout(150);
}

async function openViewer(page) {
  watchErrors(page);
  await page.goto('http://127.0.0.1:5180', { waitUntil: 'networkidle' });
  await expect(page.locator('#viewport')).toHaveAttribute('data-ready', 'true', { timeout: 30_000 });
  await expect(page.locator('.viewer-error')).toHaveCount(0);
  await expect(page.locator('#model-loading')).toBeHidden();
  await expect(page.getByRole('heading', { name: /Esboço LED/ })).toBeVisible();
  await settle(page);
}

async function captureCanvas(page) {
  return page.locator('#viewport canvas').screenshot({ timeout: 30_000 });
}

async function pixelDifference(page, first, second, threshold = 24) {
  return page.evaluate(async ({ firstImage, secondImage, threshold }) => {
    async function pixels(source) {
      const picture = new Image();
      picture.src = source;
      await picture.decode();
      const canvas = document.createElement('canvas');
      canvas.width = picture.naturalWidth;
      canvas.height = picture.naturalHeight;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      context.drawImage(picture, 0, 0);
      return { data: context.getImageData(0, 0, canvas.width, canvas.height).data, width: canvas.width, height: canvas.height };
    }
    const [left, right] = await Promise.all([pixels(firstImage), pixels(secondImage)]);
    if (left.width !== right.width || left.height !== right.height) return 1;
    let different = 0;
    for (let offset = 0; offset < left.data.length; offset += 4) {
      const change = Math.abs(left.data[offset] - right.data[offset]) + Math.abs(left.data[offset + 1] - right.data[offset + 1]) + Math.abs(left.data[offset + 2] - right.data[offset + 2]);
      if (change > threshold) different++;
    }
    return different / (left.width * left.height);
  }, {
    firstImage: `data:image/png;base64,${first.toString('base64')}`,
    secondImage: `data:image/png;base64,${second.toString('base64')}`,
    threshold,
  });
}

async function assertChanged(page, before, description, minimum = 0.002) {
  await settle(page);
  const after = await captureCanvas(page);
  const difference = await pixelDifference(page, before, after);
  assert(difference > minimum, `${description}: o canvas mudou apenas ${(difference * 100).toFixed(3)}% dos pixels`);
  checked(`${description} (${(difference * 100).toFixed(2)}% dos pixels alterados)`);
  return after;
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(artifactDirectory, `${name}.png`), fullPage: true });
}

async function assertResponsive(page, width, height) {
  await page.setViewportSize({ width, height });
  await settle(page);
  const geometry = await page.evaluate(() => {
    const canvas = document.querySelector('#viewport canvas').getBoundingClientRect();
    return { viewport: window.innerWidth, page: document.documentElement.scrollWidth, canvasLeft: canvas.left, canvasRight: canvas.right, canvasWidth: canvas.width, canvasHeight: canvas.height };
  });
  assert(geometry.page <= geometry.viewport + 1, `Overflow horizontal em ${width}×${height}: ${geometry.page}px`);
  assert(geometry.canvasLeft >= 0 && geometry.canvasRight <= geometry.viewport + 1, `Canvas fora da tela em ${width}×${height}`);
  assert(geometry.canvasWidth > 200 && geometry.canvasHeight > 250, `Canvas pequeno demais em ${width}×${height}`);
  checked(`Layout ${width}×${height}: canvas contido e sem overflow horizontal`);
}

try {
  server = await createServer({ server: { host: '127.0.0.1', port: 5180, strictPort: true } });
  await server.listen();
  browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  await openViewer(page);
  assert(await page.locator('#viewport canvas').evaluate(canvas => Boolean(canvas.getContext('webgl2'))), 'WebGL 2 indisponível');
  checked('Página inicial carregada com WebGL 2 e controles acessíveis');
  if (!mobileOnly) {
  const initial = await captureCanvas(page);
  await screenshot(page, 'desktop');

  let previous = initial;
  for (const [view, label] of [['front', 'FRONTAL'], ['side', 'LATERAL'], ['top', 'SUPERIOR'], ['perspective', 'PERSPECTIVA']]) {
    await page.locator(`[data-view="${view}"]`).click();
    await expect(page.locator('#view-label')).toHaveText(label);
    await expect(page.locator(`[data-view="${view}"]`)).toHaveAttribute('aria-pressed', 'true');
    previous = await assertChanged(page, previous, `Câmera ${label.toLowerCase()}`);
    if (view === 'top') await screenshot(page, 'top');
  }

  await page.getByRole('combobox', { name: 'Modo de visualização' }).selectOption('structure');
  previous = await assertChanged(page, previous, 'Modo somente estrutura');
  await expect(page.locator('#mode-label')).toHaveText('SOMENTE ESTRUTURA');
  await screenshot(page, 'structure');
  await page.getByRole('combobox', { name: 'Modo de visualização' }).selectOption('wireframe');
  previous = await assertChanged(page, previous, 'Modo wireframe');
  await expect(page.locator('#mode-label')).toHaveText('WIREFRAME');
  await screenshot(page, 'wireframe');
  await page.getByRole('combobox', { name: 'Modo de visualização' }).selectOption('complete');
  previous = await assertChanged(page, previous, 'Restauração do painel completo');

  const dimensions = page.getByRole('switch', { name: 'Mostrar medidas' });
  const explode = page.getByRole('switch', { name: 'Explodir modelo' });
  const dimensionLabels = page.locator('#dimension-overlay .dimension-label:visible');
  await dimensions.click();
  await expect(dimensions).toHaveAttribute('aria-checked', 'true');
  await expect.poll(() => dimensionLabels.count()).toBeGreaterThan(0);
  const requiredDimensions = ['2880 mm', '3840 mm', '2500 mm', '2000 mm · traseira', 'Poste Ø150 mm', 'Base Ø600 mm'];
  assert.deepEqual(await page.locator('#dimension-overlay .dimension-label').allTextContents(), requiredDimensions, 'As seis cotas principais devem estar disponíveis');
  checked('Medidas ativadas com rótulos visíveis');
  await screenshot(page, 'dimensions');
  previous = await captureCanvas(page);
  await explode.click();
  await expect(explode).toHaveAttribute('aria-checked', 'true');
  previous = await assertChanged(page, previous, 'Vista explodida');
  await expect(dimensionLabels).toHaveCount(0);
  await expect(page.locator('#exploded-note')).toBeVisible();
  await screenshot(page, 'exploded');
  checked('Vista explodida oculta cotas nominais e exibe indicação de separação');
  await explode.click();
  previous = await assertChanged(page, previous, 'Reunião do modelo');
  await expect.poll(() => dimensionLabels.count()).toBeGreaterThan(0);
  checked('Medidas restauradas após reunir o modelo');

  await page.locator('[data-view="side"]').click();
  await page.locator('#display-mode').selectOption('wireframe');
  await explode.click();
  await settle(page);
  await page.getByRole('button', { name: 'Reset — restaurar visualização' }).click();
  await settle(page);
  await expect(dimensions).toHaveAttribute('aria-checked', 'false');
  await expect(explode).toHaveAttribute('aria-checked', 'false');
  await expect(page.locator('#display-mode')).toHaveValue('complete');
  await expect(page.locator('#view-label')).toHaveText('PERSPECTIVA');
  await expect(dimensionLabels).toHaveCount(0);
  const reset = await captureCanvas(page);
  const resetDifference = await pixelDifference(page, initial, reset);
  assert(resetDifference < 0.015, `Reset não restaurou o enquadramento inicial: ${(resetDifference * 100).toFixed(2)}%`);
  checked('Reset restaura câmera, modo, medidas e montagem');

  let canvasBox = await page.locator('#viewport canvas').boundingBox();
  await page.mouse.move(canvasBox.x + canvasBox.width * 0.46, canvasBox.y + canvasBox.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(canvasBox.x + canvasBox.width * 0.65, canvasBox.y + canvasBox.height * 0.43, { steps: 12 });
  await page.mouse.up();
  previous = await assertChanged(page, reset, 'Rotação por arrasto do mouse');
  await expect(page.locator('#view-label')).toHaveText('ÓRBITA LIVRE');
  await page.mouse.wheel(0, -380);
  previous = await assertChanged(page, previous, 'Zoom pela roda do mouse');
  await page.getByRole('button', { name: 'Afastar', exact: true }).click();
  previous = await assertChanged(page, previous, 'Botão afastar');
  await page.getByRole('button', { name: 'Aproximar', exact: true }).click();
  await assertChanged(page, previous, 'Botão aproximar');

  const fullscreen = page.locator('#fullscreen');
  await fullscreen.click();
  await expect(fullscreen).toHaveAttribute('aria-pressed', 'true');
  await settle(page);
  assert(await page.evaluate(() => Boolean(document.fullscreenElement || document.querySelector('.viewer-column.is-fullscreen'))), 'Tela cheia não foi ativada');
  await fullscreen.click();
  await expect(fullscreen).toHaveAttribute('aria-pressed', 'false');
  checked('Tela cheia abre e retorna ao layout');
  }

  for (const [width, height] of [[1440, 1000], [1024, 768], [768, 1024], [390, 844], [320, 720]]) {
    await assertResponsive(page, width, height);
  }

  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const mobile = await mobileContext.newPage();
  await openViewer(mobile);
  await expect(mobile.locator('.technical-details')).not.toHaveAttribute('open', '');
  await screenshot(mobile, 'mobile');
  const mobileCanvas = mobile.locator('#viewport canvas');
  const cdp = await mobileContext.newCDPSession(mobile);
  const mobileCanvasBox = await mobileCanvas.boundingBox();
  const center = { x: mobileCanvasBox.x + mobileCanvasBox.width * 0.46, y: mobileCanvasBox.y + mobileCanvasBox.height * 0.5 };
  let mobilePrevious = await captureCanvas(mobile);
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ ...center, id: 0 }] });
  for (let step = 1; step <= 10; step++) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: center.x + step * 6, y: center.y - step * 2, id: 0 }] });
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  mobilePrevious = await assertChanged(mobile, mobilePrevious, 'Rotação por toque');
  await expect(mobile.locator('#view-label')).toHaveText('ÓRBITA LIVRE');
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: center.x - 30, y: center.y, id: 0 }, { x: center.x + 30, y: center.y, id: 1 }] });
  for (let step = 1; step <= 8; step++) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: center.x - 30 - step * 4, y: center.y, id: 0 }, { x: center.x + 30 + step * 4, y: center.y, id: 1 }] });
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await assertChanged(mobile, mobilePrevious, 'Zoom por pinça com dois dedos');
  await mobile.locator('.technical-details summary').tap();
  await expect(mobile.locator('.technical-details')).toHaveAttribute('open', '');
  await expect(mobile.getByRole('heading', { name: 'Painel LED em V', exact: true })).toBeVisible();
  checked('Ficha técnica recolhida no celular e expansível por toque');
  await mobileContext.close();

  assert.deepEqual(errors, [], `Erros no navegador:\n${errors.join('\n')}`);
  checked('Nenhum erro JavaScript, console ou requisição de recurso');
  console.log(`\n${checks.length} verificações passaram. Capturas em ${artifactDirectory}`);
} catch (error) {
  if (errors.length) console.error(`Erros capturados no navegador:\n${errors.join('\n')}`);
  throw error;
} finally {
  await browser?.close();
  await server?.close();
}
