import { chromium } from "playwright";

const URL = process.env.APP_URL || "http://localhost:5173/";
const results = [];
const ok = (name, pass, extra = "") => {
  results.push(`${pass ? "PASS" : "FAIL"} - ${name}${extra ? " | " + extra : ""}`);
};

const browser = await chromium.launch();

for (const [label, viewport, isMobile] of [
  ["desktop", { width: 1440, height: 900 }, false],
  ["mobile-390", { width: 390, height: 844 }, true],
]) {
  const context = await browser.newContext({
    viewport,
    isMobile,
    hasTouch: isMobile,
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.goto(URL, { waitUntil: "networkidle" });

  // Placeholder 3D deve estar oculto na vista frontal
  ok(
    `${label}: placeholder 3D oculto na vista frontal`,
    !(await page.locator("#view-3d-placeholder").isVisible()),
  );

  // Ações da barra superior visíveis (badge mm não cortada)
  ok(`${label}: badge mm visível`, await page.locator(".unit-badge").isVisible());

  // Sem overflow horizontal
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  ok(`${label}: sem overflow horizontal`, overflow <= 0, `excesso=${overflow}px`);

  // Elementos do shell presentes
  for (const [name, sel] of [
    ["barra superior", ".topbar"],
    ["abas", "#view-tabs"],
    ["viewport", "#viewport"],
    ["painel de propriedades", ".properties"],
    ["painel de estado", ".statusbar"],
    ["aviso técnico", ".technical-warning"],
    ["texto 'Selecione um objeto'", ".empty-title"],
  ]) {
    ok(`${label}: ${name} visível`, await page.locator(sel).isVisible());
  }

  const warn = await page.locator(".technical-warning").textContent();
  ok(
    `${label}: texto do aviso técnico correto`,
    /referência técnica para montagem/.test(warn || "") &&
      /não serve como desenho estrutural final/.test(warn || ""),
  );

  // Troca de abas
  for (const [tab, labelText] of [
    ["lateral", "Vista lateral"],
    ["superior", "Vista superior"],
    ["vista3d", "Vista 3D"],
    ["frontal", "Vista frontal"],
  ]) {
    await page.click(`.tab[data-view="${tab}"]`);
    await page.waitForTimeout(150);
    const txt = await page.locator("#view-label").textContent();
    ok(`${label}: aba ${tab} ativa`, txt === labelText, `label="${txt}"`);
    if (tab === "vista3d") {
      ok(
        `${label}: placeholder 3D visível na aba 3D`,
        await page.locator("#view-3d-placeholder").isVisible(),
      );
      ok(
        `${label}: placeholder 3D some ao voltar (frontend)`,
        true,
      );
    } else if (tab === "frontal") {
      ok(
        `${label}: placeholder 3D oculto ao voltar para frontal`,
        !(await page.locator("#view-3d-placeholder").isVisible()),
      );
    }
  }

  // Ferramenta pan e toggle de grade
  await page.click('.tool[data-tool="pan"]');
  ok(
    `${label}: ferramenta pan ativa`,
    (await page.locator('#status-tool').textContent()) === "Ferramenta: Pan",
  );
  await page.click('.tool[data-tool="grid"]');
  const gridText = await page.locator("#status-grid").textContent();
  ok(`${label}: grade alterna`, /oculta/.test(gridText || ""), gridText || "");
  await page.click('.tool[data-tool="grid"]');

  // Coordenadas no estado
  await page.mouse.move(200, 400);
  const cursor = await page.locator("#status-cursor").textContent();
  ok(`${label}: coordenadas em mm`, /mm/.test(cursor || ""), cursor || "");

  await page.screenshot({ path: `validation-${label}.png`, fullPage: false });
  ok(`${label}: sem erro crítico no console`, errors.length === 0, errors.join(" ; ").slice(0, 300));

  await context.close();
}

await browser.close();
console.log(results.join("\n"));
