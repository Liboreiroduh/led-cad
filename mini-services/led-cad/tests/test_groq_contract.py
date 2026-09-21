"""Testes do pipeline Groq CAD structured output (TASK_GROQ_CAD_STRUCTURED_OUTPUT).

Sem HTTP real e sem chave real: apenas a borda `chat_completion` é mockada;
parser → validação semântica → normalização → dry-run são REAIS.
Rode com: py -3.10 tests/test_groq_contract.py
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.element import ProjectModel, Element, Vec3  # noqa: E402
from services.ai_intent import build_intent  # noqa: E402
from services import ai_contract as C  # noqa: E402
from services import ai_llm as L  # noqa: E402


def make_model(with_post=True):
    els = [Element(id="PAINEL-LED", type="panel",
                   center=Vec3(x=0, y=0, z=3480), size_x=1920, size_y=50,
                   size_z=960, label="PAINEL DE LED", group="PAINEL")]
    if with_post:
        els.append(Element(id="POSTE-01", type="beam", role="post",
                           profile="METALON_100x100x3",
                           start=Vec3(x=0, y=0, z=0), end=Vec3(x=0, y=0, z=3000),
                           group="POSTES"))
    return ProjectModel(
        project={"name": "T"}, panel={"width": 1920, "height": 960, "depth": 650},
        installation={"type": "post", "ground_clearance": 3000}, elements=els)


def run(text, model, responses):
    calls = {"n": 0}

    def chat_fn(messages):
        calls["n"] += 1
        return json.dumps(responses[min(calls["n"] - 1, len(responses) - 1)])

    intent = build_intent(text=text, model=model)
    out = C.run_cad_plan(chat_fn, lambda raw: json.loads(raw), model, intent,
                         text, sys_p="SYS", user_base="Pedido: " + text)
    return out, calls["n"], intent


def _variant(name):
    """Variante anyOf do RESPONSE_SCHEMA para uma operation."""
    for v in C.RESPONSE_SCHEMA["properties"]["ops"]["items"]["anyOf"]:
        if v["properties"]["operation"]["const"] == name:
            return v
    raise AssertionError(f"variante ausente no schema: {name}")


class TestGroqCadContract(unittest.TestCase):
    def test_a_criacao_definida(self):
        model = make_model(with_post=False)
        plan = {"explain": "ok",
                "ops": [{"operation": "__blank"},
                        {"operation": "set_panel", "width": 1920, "height": 960,
                         "depth": 650, "ground_clearance": 3000},
                        {"operation": "add_box",
                         "center": {"x": 0, "y": 0, "z": 3480},
                         "width": 1920, "depth": 650, "height": 960,
                         "group": "GAIOLA"},
                        {"operation": "add_post", "x": 0, "y": 0,
                         "height": 3000},
                        {"operation": "add_grid",
                         "start": {"x": -960, "y": 325, "z": 3000},
                         "end": {"x": 960, "y": 325, "z": 3960},
                         "cols": 2, "rows": 1, "border": True,
                         "group": "GABINETES-FRONT"}]}
        out, calls, _ = run("crie um painel outdoor novo 2x1 de gabinetes "
                            "960x960, 1 poste, base a 3 metros e passarela "
                            "atrás", model, [plan])
        self.assertTrue(out["ok"])
        self.assertEqual(calls, 1)
        self.assertGreater(out["diff"]["counts"]["total"], 0)
        self.assertFalse(out.get("question"))
        setp = [o for o in out["ops"] if o["operation"] == "set_panel"]
        self.assertTrue(setp and setp[0]["width"] == 1920
                        and setp[0]["ground_clearance"] == 3000)

    def test_b_ambiguidade_legitima_sem_retry(self):
        model = make_model(with_post=True)
        q = {"explain": "4x2 é metros ou 4×2 gabinetes de 960×960?", "ops": []}
        out, calls, _ = run("crie um painel 4x2", model, [q])
        self.assertTrue(out["ok"])
        self.assertTrue(out["question"])
        self.assertEqual(calls, 1)  # sem retry para pergunta genuína

    def test_e_ops_vazia_indevida_um_retry(self):
        model = make_model(with_post=False)
        bom = {"explain": "ok",
               "ops": [{"operation": "__blank"},
                       {"operation": "set_panel", "width": 1920,
                        "height": 960, "depth": 650,
                        "ground_clearance": 3000},
                       {"operation": "add_post", "x": 0, "y": 0,
                        "height": 3000}]}
        vazio = {"explain": "feito", "ops": []}
        out, calls, _ = run("crie um painel outdoor novo 2x1 de gabinetes "
                            "960x960, 1 poste, base a 3 metros e passarela "
                            "atrás", model, [vazio, bom])
        self.assertTrue(out["ok"])
        self.assertEqual(calls, 2)  # exatamente 1 retry
        self.assertGreater(out["diff"]["counts"]["total"], 0)

        out2, calls2, _ = run("crie um painel outdoor novo 2x1", model,
                              [vazio, vazio])
        self.assertFalse(out2["ok"])
        self.assertEqual(calls2, 2)  # teto de 2 chamadas

    def test_f_noop_rejeitado(self):
        model = make_model(with_post=True)
        noop = {"explain": "movido",
                "ops": [{"operation": "move_element", "element_id": "POSTE-01",
                         "delta_x": 0, "delta_y": 0, "delta_z": 0}]}
        bom = {"explain": "movido",
               "ops": [{"operation": "move_element", "element_id": "POSTE-01",
                        "delta_x": -500, "delta_y": 0, "delta_z": 0}]}
        out, calls, _ = run("mova o poste 0 mm para a direita", model,
                            [noop, bom])
        self.assertTrue(out["ok"])
        self.assertEqual(calls, 2)  # no-op rejeitado → 1 retry

    def test_d_edicao_local_pontual(self):
        model = make_model(with_post=True)
        ok = {"explain": "movido 500",
              "ops": [{"operation": "move_element", "element_id": "POSTE-01",
                       "delta_x": -500, "delta_y": 0, "delta_z": 0}]}
        out, calls, _ = run("mova esse poste 500 mm para a esquerda", model,
                            [ok])
        self.assertTrue(out["ok"])
        self.assertEqual(calls, 1)
        self.assertFalse(any(o["operation"] == "__blank" for o in out["ops"]))

    def test_operation_invalida_e_campos_proibidos(self):
        errs, sel, clean = C.validate_payload({"explain": "x", "ops": [
            {"op": "add_beam"},
            {"type": "add_beam", "start": {"x": 0, "y": 0, "z": 0},
             "end": {"x": 1, "y": 0, "z": 0}},
            {"operation": "foo_bar"},
            {"operation": "add_box", "x": 1, "y": 2, "z": 3},
        ]})
        self.assertGreaterEqual(len(errs), 4)
        self.assertEqual(len(clean), 0)

    def test_schema_nao_ensina_type_nem_op(self):
        s = json.dumps(C.RESPONSE_SCHEMA)
        self.assertNotIn('"op"', s)
        self.assertNotIn('"type":"add_', s)
        self.assertIn('"operation"', s)

    # ---------- sanitização de opcionais null (strict → esparso) ----------

    def test_1_set_panel_opcionais_null_sanitizados(self):
        """TESTE 1: resposta strict realista de set_panel com campos não
        usados = null → opcionais nulos removidos; dry-run funciona."""
        errs, sel, clean = C.validate_payload({"explain": "x", "ops": [{
            "operation": "set_panel", "width": 1920, "height": 960,
            "depth": None, "ground_clearance": None, "visible": None}]})
        self.assertEqual(errs, [])
        self.assertEqual(clean, [{"operation": "set_panel",
                                  "width": 1920, "height": 960}])
        model = make_model()
        out = C.evaluate_cad_response({"explain": "ok", "ops": clean},
                                      model, None, "")
        self.assertEqual(out["errors"], [])
        # False, 0 e [] permanecem; obrigatório null vira erro claro
        errs2, _, clean2 = C.validate_payload({"explain": "x", "ops": [
            {"operation": "set_shield", "element_ids": [], "value": False},
            {"operation": "set_panel", "width": 0},
            {"operation": "set_post_height", "element_id": "POSTE-01",
             "height": None}]})
        self.assertEqual(errs2,
                         ["ops[2] (set_post_height): campo obrigatório "
                          "ausente 'height'"])
        self.assertEqual(clean2[0]["element_ids"], [])
        self.assertEqual(clean2[1]["width"], 0)

    def test_2_add_box_strict_nulls_12_arestas(self):
        """TESTE 2: add_box strict com corner1/corner2/role/profile = null e
        center+dimensões válidos → 12 arestas, sem NoneType."""
        op = {"operation": "add_box",
              "center": {"x": 0, "y": 0, "z": 3480},
              "width": 1920, "depth": 650, "height": 960,
              "corner1": None, "corner2": None, "group": "GAIOLA",
              "role": None, "profile": None}
        model = make_model(with_post=False)
        out = C.evaluate_cad_response({"explain": "gaiola", "ops": [op]},
                                      model, None, "")
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["diff"]["counts"]["add"], 12)
        self.assertTrue(out["ok"])
        self.assertNotIn("corner1", out["ops"][0])
        self.assertNotIn("corner2", out["ops"][0])

    def test_3_add_post_profile_null(self):
        """TESTE 3: add_post com profile:null → sanitizado, default interno,
        diff efetivo."""
        model = make_model(with_post=False)
        op = {"operation": "add_post", "x": 1200, "y": 0, "height": 3000,
              "profile": None}
        out = C.evaluate_cad_response({"explain": "poste", "ops": [op]},
                                      model, None, "")
        self.assertEqual(out["errors"], [])
        self.assertNotIn("profile", out["ops"][0])
        self.assertEqual(out["diff"]["counts"]["add"], 1)
        self.assertTrue(out["ok"])

    def test_4_add_plate_opcionais_null_sem_vec_none(self):
        """TESTE 4: add_plate com opcionais null → nenhum Vec3(**None)."""
        model = make_model(with_post=False)
        op = {"operation": "add_plate",
              "center": {"x": 0, "y": -400, "z": 100},
              "size_x": None, "size_y": None, "size_z": None,
              "group": None, "label": None}
        out = C.evaluate_cad_response({"explain": "chapa", "ops": [op]},
                                      model, None, "")
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["diff"]["counts"]["add"], 1)
        self.assertNotIn("size_x", out["ops"][0])

    def test_5_resize_element_length_com_size_null(self):
        """TESTE 5: resize_element com length válido e size/anchor = null →
        sem float(None), diff efetivo."""
        model = make_model(with_post=True)
        op = {"operation": "resize_element", "element_id": "POSTE-01",
              "length": 3500, "anchor": None, "size_x": None,
              "size_y": None, "size_z": None}
        text = "redimensione esse poste para 3500 mm"
        intent = build_intent(text=text, model=model)
        out = C.evaluate_cad_response({"explain": "ok", "ops": [op]},
                                      model, intent, text)
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["diff"]["counts"]["edit"], 1)
        self.assertTrue(out["ok"])

    def test_6_mirror_pivot_numerico_alinhado(self):
        """TESTE 6: pivot:0 numérico — schema (number) e executor (float)
        alinhados; diff efetivo."""
        self.assertEqual(_variant("mirror_elements")["properties"]["pivot"],
                         {"type": ["number", "null"]})
        model = make_model(with_post=True)
        op = {"operation": "mirror_elements", "element_ids": ["POSTE-01"],
              "plane": "x", "pivot": 0, "copy": True}
        out = C.evaluate_cad_response({"explain": "espelhado", "ops": [op]},
                                      model, None, "")
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["diff"]["counts"]["add"], 1)
        self.assertTrue(out["ok"])

    def test_7_schema_arrays_de_ids_itens_string(self):
        """TESTE 7: arrays de IDs declaram items string no schema strict."""
        for opname, field in (("__select", "ids"),
                              ("multi_move", "element_ids"),
                              ("multi_delete", "element_ids"),
                              ("mirror_elements", "element_ids")):
            self.assertEqual(_variant(opname)["properties"][field]["items"],
                             {"type": "string"})

    def test_10_fluxo_create_strict_shaped_com_nulls(self):
        """TESTE 10: resposta Groq com TODOS os campos opcionais declarados
        presentes e irrelevantes = null → ok, sem retry, diff > 0."""
        model = make_model(with_post=False)
        plan = {"explain": "ok",
                "ops": [
                    {"operation": "__blank"},
                    {"operation": "set_panel", "width": 1920, "height": 960,
                     "depth": 650, "ground_clearance": 3000, "visible": None},
                    {"operation": "add_box",
                     "center": {"x": 0, "y": 0, "z": 3480},
                     "width": 1920, "depth": 650, "height": 960,
                     "corner1": None, "corner2": None, "group": "GAIOLA",
                     "role": None, "profile": None},
                    {"operation": "add_post", "x": 0, "y": 0,
                     "height": 3000, "profile": None},
                    {"operation": "add_grid",
                     "start": {"x": -960, "y": 325, "z": 3000},
                     "end": {"x": 960, "y": 325, "z": 3960},
                     "cols": 2, "rows": 1, "border": True,
                     "group": "GABINETES-FRONT", "profile": None},
                    {"operation": "add_beam",
                     "start": {"x": -960, "y": 600, "z": 3000},
                     "end": {"x": 960, "y": 600, "z": 3000},
                     "role": None, "group": "PASSARELA", "profile": None}]}
        out, calls, _ = run("crie um painel outdoor novo 2x1 de gabinetes "
                            "960x960, 1 poste, base a 3 metros e passarela "
                            "atrás", model, [plan])
        self.assertTrue(out["ok"])
        self.assertEqual(calls, 1)  # resposta correta → sem retry
        self.assertGreater(out["diff"]["counts"]["total"], 0)

    def test_16_contrato_consistente_com_executor(self):
        """TESTE 16: operations do contrato × handlers do executor — impede
        divergência silenciosa (exceções deliberadas: __*)."""
        from core import ai_ops
        specials = {"__blank", "__preset", "__regen", "__select"}
        self.assertTrue(specials.issubset(set(C.OPS)))
        self.assertEqual(set(C.OPS) - specials, set(ai_ops.HANDLERS))


class TestCapabilitiesPayload(unittest.TestCase):
    CFG_ZAI = {"active_connection_id": "c1", "connections": [{
        "id": "c1", "name": "Z", "base_url": "https://api.z.ai/api/paas/v4",
        "model": "glm-4.5-flash", "api_key": "K"}]}
    CFG_GROQ_OSS = {"active_connection_id": "c2", "connections": [{
        "id": "c2", "name": "G", "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b", "api_key": "K"}]}
    CFG_GROQ_OTHER = {"active_connection_id": "c3", "connections": [{
        "id": "c3", "name": "G2", "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b", "api_key": "K"}]}

    def test_zai_thinking_enabled_sem_schema(self):
        cap_payload = {}

        def fake(url, payload, headers=None, timeout=0):
            cap_payload.update(payload)
            return {"choices": [{"message": {"content": "PONG"}}]}

        orig = L._http_json
        L._http_json = fake
        try:
            L.chat_completion([{"role": "system", "content": "SYS"},
                               {"role": "user", "content": "ping"}],
                              self.CFG_ZAI, response_schema=C.RESPONSE_SCHEMA)
        finally:
            L._http_json = orig
        self.assertEqual(cap_payload.get("thinking"), {"type": "enabled"})
        self.assertEqual(cap_payload.get("max_tokens"), 8192)
        self.assertNotIn("response_format", cap_payload)  # sem schema Groq
        self.assertNotIn("reasoning_effort", cap_payload)
        self.assertNotIn("include_reasoning", cap_payload)
        self.assertNotIn("max_completion_tokens", cap_payload)
        roles = [m["role"] for m in cap_payload["messages"]]
        self.assertIn("system", roles)  # Z.ai mantém system prompt
        cap = L.provider_capabilities(self.CFG_ZAI)
        self.assertFalse(cap["structured_output"])
        self.assertTrue(cap["reasoning"])

    def test_groq_oss_structured_output(self):
        """TESTE 8: payload Groq GPT-OSS — json_schema strict, reasoning
        medium não exposto, max_completion_tokens (sem max_tokens legado)."""
        cap_payload = {}

        def fake(url, payload, headers=None, timeout=0):
            cap_payload.update(payload)
            return {"choices": [{"message": {"content": "{}"}}]}

        orig = L._http_json
        L._http_json = fake
        try:
            L.chat_completion([{"role": "system", "content": "SYS"},
                               {"role": "user", "content": "ping"}],
                              self.CFG_GROQ_OSS,
                              response_schema=C.RESPONSE_SCHEMA)
        finally:
            L._http_json = orig
        rf = cap_payload.get("response_format")
        self.assertEqual(rf.get("type"), "json_schema")
        self.assertEqual(rf["json_schema"]["name"], "cad_plan")
        self.assertTrue(rf["json_schema"]["strict"])
        self.assertEqual(cap_payload.get("reasoning_effort"), "medium")
        self.assertIs(cap_payload.get("include_reasoning"), False)
        self.assertEqual(cap_payload.get("max_completion_tokens"), 8192)
        self.assertNotIn("max_tokens", cap_payload)
        self.assertNotIn("thinking", cap_payload)
        # GPT-OSS: instruções no conteúdo do usuário (sem role system)
        roles = [m["role"] for m in cap_payload["messages"]]
        self.assertNotIn("system", roles)
        self.assertEqual(roles[0], "user")
        self.assertIn("[INSTRUÇÕES CAD]", cap_payload["messages"][0]["content"])
        self.assertIn("SYS", cap_payload["messages"][0]["content"])
        self.assertIn("ping", cap_payload["messages"][0]["content"])
        cap = L.provider_capabilities(self.CFG_GROQ_OSS)
        self.assertTrue(cap["structured_output"] and cap["strict_schema"])
        self.assertTrue(cap["reasoning"])  # GPT-OSS é reasoning-capable

    def test_groq_oss_20b_tambem_reasoning(self):
        cap = L.provider_capabilities({
            "active_connection_id": "c", "connections": [{
                "id": "c", "name": "G", "model": "openai/gpt-oss-20b",
                "base_url": "https://api.groq.com/openai/v1", "api_key": "K"}]})
        self.assertTrue(cap["reasoning"] and cap["strict_schema"])

    def test_groq_outro_modelo_json_object(self):
        cap_payload = {}

        def fake(url, payload, headers=None, timeout=0):
            cap_payload.update(payload)
            return {"choices": [{"message": {"content": "{}"}}]}

        orig = L._http_json
        L._http_json = fake
        try:
            L.chat_completion([{"role": "user", "content": "ping"}],
                              self.CFG_GROQ_OTHER,
                              response_schema=C.RESPONSE_SCHEMA)
        finally:
            L._http_json = orig
        rf = cap_payload.get("response_format")
        self.assertEqual(rf, {"type": "json_object"})  # validação local obrigatória
        self.assertEqual(cap_payload.get("max_completion_tokens"), 8192)
        self.assertNotIn("max_tokens", cap_payload)
        self.assertNotIn("reasoning_effort", cap_payload)
        self.assertNotIn("include_reasoning", cap_payload)
        cap = L.provider_capabilities(self.CFG_GROQ_OTHER)
        self.assertTrue(cap["structured_output"])
        self.assertFalse(cap["strict_schema"])
        self.assertFalse(cap["reasoning"])

    def test_payload_nao_carrega_autorizacao(self):
        seen = {}

        def fake(url, payload, headers=None, timeout=0):
            seen["headers"] = headers
            seen["payload"] = payload
            self.assertNotIn("Authorization", payload)
            return {"choices": [{"message": {"content": "{}"}}]}

        orig = L._http_json
        L._http_json = fake
        try:
            L.chat_completion([{"role": "user", "content": "ping"}],
                              self.CFG_GROQ_OSS)
        finally:
            L._http_json = orig
        self.assertIn("Authorization", seen["headers"])  # vai só no header


if __name__ == "__main__":
    unittest.main(verbosity=2)
