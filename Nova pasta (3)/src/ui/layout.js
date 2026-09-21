import { icon } from "./icons.js";
import { PROJECT, GEOMETRY } from "../scene/project.js";

function planDiagram() {
  const scale = 82 / GEOMETRY.depth;
  const half = (PROJECT.rearOpening / 2) * scale;
  const left = 130 - half;
  const right = 130 + half;
  const slope = 90 - (GEOMETRY.halfAngle * 180) / Math.PI;
  return `<svg class="plan-diagram" viewBox="0 0 260 125" role="img" aria-label="Vértice frontal, duas faces de ${PROJECT.faceWidth} milímetros, abertura traseira de ${PROJECT.rearOpening} milímetros">
    <path d="M${left} 27 130 109 ${right} 27" fill="#e9eedf" stroke="#6a7856" stroke-width="3" stroke-linejoin="round"/>
    <path d="M${left} 15H${right}M${left} 10v13M${right} 10v13M130 29v65" stroke="#9ba78d" stroke-width="1" stroke-dasharray="2 2"/>
    <circle cx="130" cy="109" r="3.5" fill="#596845"/>
    <text x="130" y="10" text-anchor="middle">${PROJECT.rearOpening.toLocaleString("pt-BR")}</text>
    <text x="${left + 3}" y="77" transform="rotate(${-slope} ${left + 3} 77)">${PROJECT.faceWidth.toLocaleString("pt-BR")}</text>
    <text x="${right + 4}" y="57" transform="rotate(${slope} ${right + 4} 57)">${PROJECT.faceWidth.toLocaleString("pt-BR")}</text>
    <text x="130" y="64" text-anchor="middle">${((GEOMETRY.angle * 180) / Math.PI).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}°</text>
    <text x="130" y="124" text-anchor="middle">FRENTE</text>
  </svg>`;
}

export function createLayout(root) {
  const number = (value) =>
    new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
  const dimension = (label, value) =>
    `<div class="spec-row"><dt>${label}</dt><dd>${value}</dd></div>`;
  root.innerHTML = `
    <header class="site-header">
      <a class="brand" href="./" aria-label="LED COLLOR, início"><span class="brand-symbol">${icon("cube")}</span><span>LED<span class="brand-light">COLLOR</span><small>SOLUÇÕES EM LED</small></span></a>
      <span class="header-divider"></span><span class="header-label">ESTÚDIO DE PROJETOS</span>
      <div class="header-right"><span class="status-dot"></span> Apresentação técnica <span class="version">REV. 01</span></div>
    </header>
    <main>
      <section class="project-heading" aria-labelledby="project-title">
        <div><div class="eyebrow"><span>VISUALIZAÇÃO INTERATIVA</span><span class="eyebrow-line"></span><span>01 / PAINÉIS</span></div><h1 id="project-title">Esboço LED <span>3×4 m</span><span class="title-tag">PAINEL EM V</span></h1><p>Duas faces. Uma nova perspectiva.</p></div>
        <div class="heading-meta"><span>DIMENSÃO POR FACE</span><strong>${number(PROJECT.faceWidth)} <i>×</i> ${number(PROJECT.faceHeight)} <small>mm</small></strong></div>
      </section>
      <section class="workspace" aria-label="Apresentação interativa do painel LED">
        <div class="viewer-column">
          <nav class="view-toolbar" aria-label="Vistas do modelo"><div class="view-buttons">
            ${[
              ["perspective", "cube", "Perspectiva"],
              ["front", "front", "Frontal"],
              ["side", "side", "Lateral"],
              ["top", "top", "Superior"],
            ]
              .map(
                ([name, glyph, label]) =>
                  `<button class="view-button ${name === "perspective" ? "is-active" : ""}" data-view="${name}" aria-pressed="${name === "perspective"}">${icon(glyph)}<span>${label}</span></button>`,
              )
              .join("")}
          </div><button class="reset-button" id="reset" title="Restaurar vista e configurações" aria-label="Reset — restaurar visualização">${icon("reset")}<span>Reset</span></button></nav>
          <div class="viewport" id="viewport" aria-label="Modelo 3D interativo">
            <div class="viewport-caption"><span class="status-dot"></span><span id="view-label">PERSPECTIVA</span><span class="caption-slash">/</span><span>MODELO 3D</span></div>
            <div class="model-loading" id="model-loading" role="status"><span class="loader"></span>Preparando o modelo 3D…</div>
            <div class="dimension-overlay" id="dimension-overlay" aria-hidden="true"></div>
            <div class="direction-overlay" id="direction-overlay" aria-hidden="true"></div>
            <div class="viewport-tools" aria-label="Zoom e tela cheia"><button id="zoom-in" title="Aproximar" aria-label="Aproximar">${icon("plus")}</button><button id="zoom-out" title="Afastar" aria-label="Afastar">${icon("minus")}</button><span></span><button id="fullscreen" title="Tela cheia" aria-label="Tela cheia" aria-pressed="false">${icon("expand")}</button></div>
            <div class="model-badge"><span class="badge-square"></span><span id="mode-label">PAINEL COMPLETO</span></div>
            <div class="exploded-note" id="exploded-note" hidden>Vista explodida · distâncias ilustrativas</div>
            <span class="viewport-scale">UNIDADES EM MILÍMETROS</span>
          </div>
          <div class="viewer-bottom"><div class="interaction-hint">${icon("pointer")}<span><strong>Arraste</strong> para girar <b>·</b> <strong>Scroll ou pinça</strong> para zoom</span></div><span class="orbit-badge">ÓRBITA 360° ${icon("reset")}</span></div>
        </div>
        <aside class="sidebar" aria-label="Configurações e ficha técnica">
          <section class="display-options"><div class="section-label">EXPLORAR O MODELO <span>01</span></div><label class="field-label" for="display-mode">Modo de visualização</label><div class="select-wrap"><select id="display-mode"><option value="complete">Painel completo</option><option value="structure">Somente estrutura</option><option value="wireframe">Wireframe</option></select>${icon("chevron")}</div>
            <button class="toggle-row" id="toggle-dimensions" role="switch" aria-checked="false"><span>${icon("ruler")}Mostrar medidas</span><span class="switch" aria-hidden="true"></span></button>
            <button class="toggle-row" id="toggle-explode" role="switch" aria-checked="false"><span>${icon("explode")}Explodir modelo</span><span class="switch" aria-hidden="true"></span></button>
            <p class="controls-note" id="controls-note">Explore a montagem em todos os ângulos.</p>
          </section>
          <details class="technical-details" open><summary><span class="section-label">FICHA TÉCNICA <span>02</span></span>${icon("chevron")}</summary><div class="technical-body"><h2>Painel LED em V</h2><p class="spec-subtitle">Composição modular · dupla face</p><dl>
            ${dimension("Faces", "2")}${dimension("Dimensão por face", `${number(PROJECT.faceWidth)} × ${number(PROJECT.faceHeight)} mm`)}${dimension("Gabinetes por face", `${PROJECT.columns * PROJECT.rows} <span class="muted">/ ${PROJECT.columns} × ${PROJECT.rows}</span>`)}${dimension("Gabinete", `${PROJECT.cabinetWidth} × ${PROJECT.cabinetHeight} mm`)}${dimension("Altura livre", `${number(PROJECT.freeHeight)} mm`)}${dimension("Altura total", `${number(GEOMETRY.totalHeight)} mm`)}${dimension("Abertura traseira", `até ${number(PROJECT.rearOpening)} mm`)}${dimension("Poste", `Ø${PROJECT.postDiameter} mm`)}${dimension("Base", `Ø${PROJECT.baseDiameter} × ${PROJECT.baseThickness} mm`)}
            </dl><div class="plan-card"><div class="plan-title"><span>GEOMETRIA EM PLANTA</span><span>VISTA SUPERIOR</span></div>${planDiagram()}<div class="plan-depth">Profundidade calculada <strong>${GEOMETRY.depth.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mm</strong></div></div></div></details>
          <div class="sidebar-foot">${icon("info")}<span>Geometria de montagem.<br> Espessuras de perfis representativas.</span></div>
        </aside>
      </section>
      <div class="project-foot"><div class="project-warning">${icon("warning")}<p>Essa é apenas uma referência técnica para montagem, não serve como desenho estrutural final.</p></div><span>LED COLLOR <b>/</b> PROJETOS</span></div>
      <p class="sr-only" id="announcement" aria-live="polite"></p>
    </main>`;
  if (window.matchMedia("(max-width: 760px)").matches)
    root.querySelector(".technical-details").open = false;
}
