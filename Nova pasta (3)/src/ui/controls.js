const VIEW_NAMES = {
  perspective: "Perspectiva",
  front: "Frontal",
  side: "Lateral",
  top: "Superior",
};
const MODE_NAMES = {
  complete: "Painel completo",
  structure: "Somente estrutura",
  wireframe: "Wireframe",
};

export function bindControls(viewer) {
  const controller = new AbortController();
  const options = { signal: controller.signal };
  const find = (id) => document.getElementById(id);
  const announce = (message) => {
    find("announcement").textContent = message;
  };
  let dimensions = false;
  let exploded = false;
  const setViewLabel = (name) => {
    document.querySelectorAll("[data-view]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.view === name);
      button.setAttribute("aria-pressed", String(button.dataset.view === name));
    });
    find("view-label").textContent = (
      VIEW_NAMES[name] || "Órbita livre"
    ).toUpperCase();
  };
  document.querySelectorAll("[data-view]").forEach((button) =>
    button.addEventListener(
      "click",
      () => {
        viewer.view(button.dataset.view);
        setViewLabel(button.dataset.view);
        announce(`Vista ${VIEW_NAMES[button.dataset.view]}.`);
      },
      options,
    ),
  );
  find("display-mode").addEventListener(
    "change",
    (event) => {
      viewer.setMode(event.target.value);
      find("mode-label").textContent =
        MODE_NAMES[event.target.value].toUpperCase();
      announce(`Modo ${MODE_NAMES[event.target.value]}.`);
    },
    options,
  );
  function updateToggles() {
    find("toggle-dimensions").setAttribute("aria-checked", String(dimensions));
    find("toggle-explode").setAttribute("aria-checked", String(exploded));
    find("exploded-note").hidden = !exploded;
    find("controls-note").textContent =
      exploded && dimensions
        ? "As cotas reaparecem ao reunir o modelo."
        : exploded
          ? "Componentes separados para entender a montagem."
          : "Explore a montagem em todos os ângulos.";
  }
  find("toggle-dimensions").addEventListener(
    "click",
    () => {
      dimensions = !dimensions;
      viewer.setDimensions(dimensions);
      updateToggles();
      announce(
        dimensions
          ? exploded
            ? "Medidas serão exibidas ao reunir o modelo."
            : "Medidas ativadas."
          : "Medidas ocultas.",
      );
    },
    options,
  );
  find("toggle-explode").addEventListener(
    "click",
    () => {
      exploded = !exploded;
      viewer.setExploded(exploded);
      updateToggles();
      announce(
        exploded
          ? "Vista explodida. Distâncias ilustrativas."
          : "Modelo reunido.",
      );
    },
    options,
  );
  find("reset").addEventListener(
    "click",
    () => {
      viewer.reset();
      dimensions = exploded = false;
      find("display-mode").value = "complete";
      find("mode-label").textContent = MODE_NAMES.complete.toUpperCase();
      updateToggles();
      setViewLabel("perspective");
      announce("Visualização restaurada.");
    },
    options,
  );
  find("zoom-in").addEventListener("click", () => viewer.zoom(0.84), options);
  find("zoom-out").addEventListener("click", () => viewer.zoom(1.19), options);

  const fullscreenTarget = document.querySelector(".viewer-column");
  const fullscreenButton = find("fullscreen");
  const updateFullscreen = () => {
    const active =
      !!document.fullscreenElement ||
      fullscreenTarget.classList.contains("is-fullscreen");
    fullscreenButton.setAttribute("aria-pressed", String(active));
    fullscreenButton.setAttribute(
      "aria-label",
      active ? "Sair da tela cheia" : "Tela cheia",
    );
    fullscreenButton.title = active ? "Sair da tela cheia" : "Tela cheia";
  };
  fullscreenButton.addEventListener(
    "click",
    async () => {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (fullscreenTarget.classList.contains("is-fullscreen")) {
        fullscreenTarget.classList.remove("is-fullscreen");
        document.body.style.overflow = "";
      } else if (fullscreenTarget.requestFullscreen) {
        try {
          await fullscreenTarget.requestFullscreen();
        } catch {
          fullscreenTarget.classList.add("is-fullscreen");
          document.body.style.overflow = "hidden";
        }
      } else {
        fullscreenTarget.classList.add("is-fullscreen");
        document.body.style.overflow = "hidden";
      }
      updateFullscreen();
    },
    options,
  );
  document.addEventListener("fullscreenchange", updateFullscreen, options);
  document.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Escape" &&
        fullscreenTarget.classList.contains("is-fullscreen")
      ) {
        fullscreenTarget.classList.remove("is-fullscreen");
        document.body.style.overflow = "";
        updateFullscreen();
      }
    },
    options,
  );
  return {
    onOrbit: () => setViewLabel(null),
    dispose: () => controller.abort(),
  };
}
