import "./styles/main.css";
import { createLayout } from "./ui/layout.js";
import { bindControls } from "./ui/controls.js";
import { createScene } from "./scene/createScene.js";

createLayout(document.getElementById("app"));
let viewer;
let ui;
const viewport = document.getElementById("viewport");
function showError(message) {
  document.getElementById("model-loading").hidden = true;
  if (viewport.querySelector(".viewer-error")) return;
  const error = document.createElement("div");
  error.className = "viewer-error";
  error.setAttribute("role", "alert");
  const heading = document.createElement("h2");
  heading.textContent = "Não foi possível abrir o modelo";
  const text = document.createElement("p");
  text.textContent = message;
  const retry = document.createElement("button");
  retry.textContent = "Tentar novamente";
  retry.addEventListener("click", () => window.location.reload());
  error.append(heading, text, retry);
  viewport.append(error);
  document
    .querySelectorAll(
      ".view-toolbar button, .viewport-tools button, .display-options button, .display-options select",
    )
    .forEach((control) => {
      control.disabled = true;
    });
}

try {
  viewer = createScene(viewport, {
    onOrbit: () => ui?.onOrbit(),
    onError: showError,
  });
  ui = bindControls(viewer);
  document.getElementById("model-loading").hidden = true;
  viewport.dataset.ready = "true";
} catch (error) {
  console.error("Não foi possível iniciar a cena 3D:", error);
  showError(
    "Este visualizador precisa de WebGL 2. Tente atualizar o navegador ou ativar a aceleração gráfica. A ficha técnica continua disponível abaixo.",
  );
}

if (import.meta.hot)
  import.meta.hot.dispose(() => {
    ui?.dispose();
    viewer?.dispose();
  });
