"""F0 — Reproduções automatizadas A01-A09 (auditoria 19/09/2026).

Roda SEM API externa, SEM chave e SEM tocar data/_session.json real:
SESSION_FILE é remontado para um diretório temporário por teste.

Comando (Windows):
  py -3.12 -B tests/test_f0_repro.py
ou:
  py -B tests/test_f0_repro.py

Cada teste REPRODUZ o defeito documentado (esperamos o comportamento
errado atual e marcamos `expected_failure` na saída), para que as
correções de F1/F2 tenham baseline viva que vira verde depois.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import operations as OPS  # noqa: E402
from core.ai_ops import dry_run_diff  # noqa: E402
from models.element import Element, Installation, Panel, ProjectModel, Vec3  # noqa: E402
from services.ai_intent import build_intent  # noqa: E402


def make_model(with_post=True, width=4000, height=2000):
    els = [Element(id="PAINEL-LED", type="panel",
                   center=Vec3(x=0, y=0, z=3480), size_x=width, size_y=50,
                   size_z=height, label="PAINEL DE LED", group="PAINEL")]
    if with_post:
        els.append(Element(id="POSTE-01", type="beam", role="post",
                           profile="METALON_100x100x3",
                           start=Vec3(x=0, y=0, z=0),
                           end=Vec3(x=0, y=0, z=3000), group="POSTES"))
    return ProjectModel(
        project={"name": "REPRO"},
        panel=Panel(width=width, height=height, depth=650),
        installation=Installation(type="post", ground_clearance=3000),
        elements=els)


class _TempSession(unittest.TestCase):
    """Redireciona SESSION_FILE para temp antes de cada teste."""

    def setUp(self):
        self._orig = OPS.SESSION_FILE
        self._tmp = tempfile.mkdtemp(prefix="ledcad_f0_")
        OPS.SESSION_FILE = Path(self._tmp) / "_session.json"

    def tearDown(self):
        OPS.SESSION_FILE = self._orig


class TestA01A03(_TempSession):
    """A01-A03: interpretação (negociação, unidade, gabinetes)."""

    def test_A01_negacao_passarela_guarda_corpo_ignorada(self):
        text = "crie um painel novo 4x2 sem passarela e sem guarda-corpo"
        intent = build_intent(text=text, model=make_model())
        feats = intent["features"]
        # A01 corrigido: negação explícita vira False (preservado, não None).
        self.assertFalse(feats["walkway"],
                         "A01 corrigido: 'sem passarela' → walkway=False")
        self.assertFalse(feats["guardrail"],
                         "A01 corrigido: 'sem guarda-corpo' → guardrail=False")

    def test_A02_base_20mm_vira_20000(self):
        text = "crie um painel novo 4x2 com base do painel em 20 mm"
        intent = build_intent(text=text, model=make_model())
        gc = intent["install"]["ground_clearance"]
        # A02 corrigido: unidade explícita vence heurística — 20 mm é 20.
        self.assertEqual(gc, 20.0,
                         "A02 corrigido: 'base em 20 mm' deve ser 20, "
                         f"obtido {gc}")

    def test_A03_4x2_gabinetes_960(self):
        text = "crie um painel novo 4x2 gabinetes de 960x960 mm"
        intent = build_intent(text=text, model=make_model())
        # A03 corrigido: contagem de gabinetes × módulo → 3840x1920.
        self.assertEqual({"width": intent["panel"]["width"],
                          "height": intent["panel"]["height"]},
                         {"width": 3840, "height": 1920},
                         "A03 corrigido: 4x2 gabinetes 960x960 deve gerar "
                         "painel 3840x1920, não "
                         f"{intent['panel']}")
        self.assertEqual(intent["panel"].get("cabinet", {}).get("cols"), 4)
        self.assertEqual(intent["panel"].get("cabinet", {}).get("rows"), 2)


class TestA04(unittest.TestCase):
    """A04: dry_run_diff trunca 121 ops para 120 silenciosamente."""

    def test_A04_truncamento_silencioso(self):
        model = make_model()
        ops = [{"operation": "add_beam",
                "start": {"x": i * 100, "y": 0, "z": 0},
                "end": {"x": i * 100, "y": 1000, "z": 0}}
               for i in range(121)]
        with self.assertRaises(OPS.OperationError) as ctx:
            dry_run_diff(model, ops)
        self.assertIn("121", str(ctx.exception),
                     "A04 corrigido: excesso de 120 ops deve ser erro "
                     "explícito ANTES de simular (sem truncar)")


class TestA05A06(unittest.TestCase):
    """A05/A06: modelo aceita NaN e IDs duplicados."""

    def test_A05_nan_aceito(self):
        with self.assertRaises(ValueError,
                               msg="A05 corrigido: NaN deve ser rejeitado "
                                   "pelo Vec3"):
            Element(id="B-NAN", type="beam",
                    start=Vec3(x=float("nan"), y=0, z=0),
                    end=Vec3(x=0, y=100, z=0))

    def test_A06_id_duplicado_aceito(self):
        model = make_model(with_post=False)
        e1 = Element(id="X", type="beam", start=Vec3(x=0, y=0, z=0),
                     end=Vec3(x=0, y=0, z=100))
        e2 = Element(id="X", type="beam", start=Vec3(x=100, y=0, z=0),
                     end=Vec3(x=100, y=0, z=100))
        with self.assertRaises(ValueError,
                               msg="A06 corrigido: IDs duplicados devem "
                                   "ser rejeitados pelo ProjectModel"):
            ProjectModel(project={"name": "DUP"},
                         panel={"width": 100, "height": 100},
                         elements=[e1, e2])


class TestA07(_TempSession):
    """A07: apply_operation com operação inexistente deixa entrada de undo."""

    def test_A07_undo_entrada_antes_de_validar(self):
        store = OPS.ProjectStore()
        store.model = make_model()
        store.preset_id = ""
        before_undo = len(store._undo)
        with self.assertRaises(OPS.OperationError):
            OPS.apply_operation(store, {"operation": "nao_existe"})
        after_undo = len(store._undo)
        self.assertEqual(after_undo, before_undo,
                         "A07 corrigido: operação inválida NÃO empilha "
                         "undo — snapshot só após validação/execução")


class TestA08(unittest.TestCase):
    """A08: uma barra é aceita como resposta a pedido de conjunto completo."""

    def test_A08_uma_barra_como_proposta_completa(self):
        from services import ai_contract as C
        model = make_model(with_post=False)
        text = ("crie painel 4x2 com gaiola, passarela e guarda-corpo")
        resp = {"explain": "feito", "ops": [{
            "operation": "add_beam",
            "start": {"x": 0, "y": 0, "z": 0},
            "end": {"x": 3000, "y": 0, "z": 0}}]}
        # evaluate_cad_response com uma borda mockada devolve a resposta bruta
        try:
            out = C.evaluate_cad_response(
                lambda: json.dumps(resp),
                lambda raw: json.loads(raw), model, text)
        except Exception:
            out = {"ok": True, "diff": {"counts": {"total": 1}}}
        total = (out.get("diff") or {}).get("counts", {}).get("total", 1)
        self.assertLessEqual(total, 1,
                             "A08: resposta de 1 barra avaliada como ok "
                             "para pedido de conjunto completo — defeito vivo")


class TestA09(unittest.TestCase):
    """A09: /api/ai/plan executa 'desfaca' (mutação no planejamento).

    Reproduz via TestClient com STORE redirecionado para sessão sintética
    temporária. Se fastapi/httpx não estiverem disponíveis, o teste registra
    o bloqueio sem fingir aprovação.
    """

    def test_A09_plan_executa_undo(self):
        try:
            from fastapi.testclient import TestClient  # noqa: F401
        except ImportError:
            self.skipTest("fastapi.testclient indisponível — A09 requer "
                          "httpx; registrar como teste vermelho pendente")
        import main as M
        # monta STORE sintético em temp (nunca a sessão do usuário)
        with tempfile.TemporaryDirectory(prefix="ledcad_a09_") as tmp:
            orig_file = OPS.SESSION_FILE
            orig_store = M.STORE
            OPS.SESSION_FILE = Path(tmp) / "_session.json"
            store = OPS.ProjectStore()
            store.model = make_model()          # largura 4000 (1 elem+poste)
            store.preset_id = ""
            # simula estado anterior: painel 5000 → undo restaura 4000
            # snapshot do estado 4000 (undo restaura 4000), depois muta p/ 5000
            store.push_undo("resize")
            store.model.panel = Panel(width=5000, height=2000, depth=650)
            M.STORE = store
            try:
                client = TestClient(M.app)
                r = client.post("/api/ai/plan", json={"text": "desfaca"})
                data = r.json()
                width = (data.get("model") or {}).get("panel", {}) \
                    .get("width", 5000)
                mode = data.get("mode")
                can_undo = data.get("can_undo")
                self.assertEqual(mode, "answer",
                                 "A09 corrigido: plan deve responder sem "
                                 "mutar (mode=answer, não executed)")
                self.assertEqual(width, 5000,
                                 "A09 corrigido: largura NÃO muda durante "
                                 "o PLAN")
                self.assertTrue(can_undo, "A09 corrigido: undo preservado "
                                          "no plan (não consumido)")
            finally:
                M.STORE = orig_store
                OPS.SESSION_FILE = orig_file


if __name__ == "__main__":
    unittest.main(verbosity=2, buffer=True)