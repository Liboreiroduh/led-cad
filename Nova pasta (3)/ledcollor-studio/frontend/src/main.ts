import "./style.css";

/* ------------------------------------------------------------------ */
/* LedCollor Studio — Task 01: shell do editor e viewport com grade mm */
/* ------------------------------------------------------------------ */

type ViewId = "frontal" | "lateral" | "superior" | "vista3d";
type ToolId = "select" | "pan" | "dim";

interface ViewConfig {
  label: string;
  hAxis: string;
  vAxis: string;
}

const VIEWS: Record<ViewId, ViewConfig> = {
  frontal: { label: "Vista frontal", hAxis: "X", vAxis: "Y" },
  lateral: { label: "Vista lateral", hAxis: "Z", vAxis: "Y" },
  superior: { label: "Vista superior", hAxis: "X", vAxis: "Z" },
  vista3d: { label: "Vista 3D", hAxis: "X", vAxis: "Y" },
};

const TOOL_LABELS: Record<ToolId, string> = {
  select: "Selecionar",
  pan: "Pan",
  dim: "Cota",
};

const REF_ZOOM = 0.2; // px por mm no zoom 100%
const MIN_ZOOM = 0.005;
const MAX_ZOOM = 5;

const canvas = document.getElementById("canvas") as HTMLCanvasElement;
const viewport = document.getElementById("viewport") as HTMLDivElement;
const view3d = document.getElementById("view-3d-placeholder") as HTMLDivElement;
const viewLabel = document.getElementById("view-label") as HTMLDivElement;
const tabsEl = document.getElementById("view-tabs") as HTMLElement;
const toolbarEl = document.getElementById("toolbar") as HTMLElement;
const statusCursor = document.getElementById("status-cursor") as HTMLSpanElement;
const statusZoom = document.getElementById("status-zoom") as HTMLSpanElement;
const statusGrid = document.getElementById("status-grid") as HTMLSpanElement;
const statusTool = document.getElementById("status-tool") as HTMLSpanElement;

const state = {
  view: "frontal" as ViewId,
  tool: "select" as ToolId,
  showGrid: true,
  pxPerMm: REF_ZOOM,
  panX: 0, // posição da origem (0,0) em px de tela
  panY: 0,
};

let dpr = 1;
let cursorMm = { x: 0, y: 0 };

/* ---------- Utilidades ---------- */

function centerOrigin(): void {
  state.panX = canvas.clientWidth / 2;
  state.panY = canvas.clientHeight / 2;
}

function screenToMm(px: number, py: number): { x: number; y: number } {
  return {
    x: (px - state.panX) / state.pxPerMm,
    y: (state.panY - py) / state.pxPerMm,
  };
}

function formatMm(v: number): string {
  return `${Math.round(v).toLocaleString("pt-BR")} mm`;
}

function pickStep(minPx: number): number {
  const candidates = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000];
  for (const c of candidates) {
    if (c * state.pxPerMm >= minPx) return c;
  }
  return candidates[candidates.length - 1];
}

/* ---------- Renderização ---------- */

function resize(): void {
  dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w === 0 || h === 0) return;
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  draw();
}

function draw(): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  if (state.showGrid) {
    const minor = pickStep(10);
    const major = minor * 5;

    ctx.strokeStyle = "#e3e8ee";
    ctx.lineWidth = 1;
    ctx.beginPath();
    drawGridLines(ctx, minor, w, h);
    ctx.stroke();

    ctx.strokeStyle = "#ccd5de";
    ctx.beginPath();
    drawGridLines(ctx, major, w, h);
    ctx.stroke();

    drawAxes(ctx, w, h);
    statusGrid.textContent = `Grade: ${minor.toLocaleString("pt-BR")} mm`;
  } else {
    statusGrid.textContent = "Grade: oculta";
  }

  drawOrigin(ctx);
}

function drawGridLines(
  ctx: CanvasRenderingContext2D,
  stepMm: number,
  w: number,
  h: number,
): void {
  const stepPx = stepMm * state.pxPerMm;
  for (let x = state.panX % stepPx; x <= w; x += stepPx) {
    ctx.moveTo(Math.round(x) + 0.5, 0);
    ctx.lineTo(Math.round(x) + 0.5, h);
  }
  for (let y = state.panY % stepPx; y <= h; y += stepPx) {
    ctx.moveTo(0, Math.round(y) + 0.5);
    ctx.lineTo(w, Math.round(y) + 0.5);
  }
}

function drawAxes(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = "#d64c4c";
  ctx.beginPath();
  ctx.moveTo(0, state.panY);
  ctx.lineTo(w, state.panY);
  ctx.stroke();

  ctx.strokeStyle = "#3a6fd8";
  ctx.beginPath();
  ctx.moveTo(state.panX, 0);
  ctx.lineTo(state.panX, h);
  ctx.stroke();
}

function drawOrigin(ctx: CanvasRenderingContext2D): void {
  const view = VIEWS[state.view];
  ctx.fillStyle = "#1b2530";
  ctx.beginPath();
  ctx.arc(state.panX, state.panY, 4, 0, Math.PI * 2);
  ctx.fill();

  ctx.font = "12px 'Segoe UI', system-ui, sans-serif";
  ctx.fillStyle = "#5b6b7b";
  ctx.fillText(
    `(0, 0)  ${view.hAxis}→  ↑${view.vAxis}`,
    state.panX + 9,
    state.panY - 9,
  );
}

function updateStatus(): void {
  const view = VIEWS[state.view];
  statusCursor.textContent =
    `${view.hAxis}: ${formatMm(cursorMm.x)} · ${view.vAxis}: ${formatMm(cursorMm.y)}`;
  statusZoom.textContent =
    `Zoom: ${Math.round((state.pxPerMm / REF_ZOOM) * 100)}%`;
  statusTool.textContent = `Ferramenta: ${TOOL_LABELS[state.tool]}`;
}

/* ---------- Interação no canvas ---------- */

let panning = false;
let lastPointer = { x: 0, y: 0 };

function startPan(e: PointerEvent): boolean {
  const middleButton = e.button === 1;
  const leftButtonPan = e.button === 0 && state.tool === "pan";
  if (!middleButton && !leftButtonPan) return false;
  panning = true;
  lastPointer = { x: e.clientX, y: e.clientY };
  canvas.classList.add("is-panning");
  canvas.setPointerCapture(e.pointerId);
  return true;
}

canvas.addEventListener("pointerdown", (e) => {
  startPan(e);
});

canvas.addEventListener("pointermove", (e) => {
  const rect = canvas.getBoundingClientRect();
  const px = e.clientX - rect.left;
  const py = e.clientY - rect.top;
  cursorMm = screenToMm(px, py);
  updateStatus();

  if (!panning) return;
  state.panX += e.clientX - lastPointer.x;
  state.panY += e.clientY - lastPointer.y;
  lastPointer = { x: e.clientX, y: e.clientY };
  draw();
});

canvas.addEventListener("pointerup", (e) => {
  panning = false;
  canvas.classList.remove("is-panning");
  if (canvas.hasPointerCapture(e.pointerId)) {
    canvas.releasePointerCapture(e.pointerId);
  }
});

canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  const before = screenToMm(mx, my);
  const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
  state.pxPerMm = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, state.pxPerMm * factor));
  // mantém o ponto sob o cursor fixo durante o zoom
  state.panX = mx - before.x * state.pxPerMm;
  state.panY = my + before.y * state.pxPerMm;
  draw();
  updateStatus();
}, { passive: false });

canvas.addEventListener("contextmenu", (e) => e.preventDefault());

/* ---------- Abas de vista ---------- */

tabsEl.addEventListener("click", (e) => {
  const btn = (e.target as HTMLElement).closest<HTMLElement>(".tab");
  if (!btn) return;
  const view = btn.dataset.view as ViewId;
  if (!view || view === state.view) return;

  state.view = view;
  for (const t of tabsEl.querySelectorAll(".tab")) {
    const active = t === btn;
    t.classList.toggle("is-active", active);
    t.setAttribute("aria-selected", String(active));
  }
  viewLabel.textContent = VIEWS[view].label;
  const is3d = view === "vista3d";
  view3d.hidden = !is3d;
  canvas.style.visibility = is3d ? "hidden" : "visible";
  if (!is3d) {
    centerOrigin();
    draw();
  }
  updateStatus();
});

/* ---------- Ferramentas ---------- */

function toggleGrid(): void {
  state.showGrid = !state.showGrid;
  const btn = toolbarEl.querySelector<HTMLElement>('.tool[data-tool="grid"]');
  btn?.setAttribute("aria-pressed", String(state.showGrid));
  draw();
}

function setTool(tool: ToolId): void {
  state.tool = tool;
  for (const t of toolbarEl.querySelectorAll<HTMLElement>(".tool:not(.is-toggle)")) {
    t.classList.toggle("is-active", t.dataset.tool === tool);
  }
  canvas.classList.toggle("tool-pan", tool === "pan");
  updateStatus();
}

toolbarEl.addEventListener("click", (e) => {
  const btn = (e.target as HTMLElement).closest<HTMLElement>(".tool");
  if (!btn) return;
  const tool = btn.dataset.tool;
  if (tool === "grid") toggleGrid();
  else if (tool === "select" || tool === "pan" || tool === "dim") setTool(tool);
});

window.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
  const key = e.key.toLowerCase();
  if (key === "v") setTool("select");
  else if (key === "h") setTool("pan");
  else if (key === "c") setTool("dim");
  else if (key === "g") toggleGrid();
});

/* ---------- Inicialização ---------- */

window.addEventListener("resize", resize);
new ResizeObserver(resize).observe(viewport);

centerOrigin();
resize();
updateStatus();

