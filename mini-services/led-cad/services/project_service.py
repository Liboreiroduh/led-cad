"""Persistência simples de projetos em JSON (MVP sem banco — seção 27).

Os arquivos ficam em data/*.json. Cada arquivo guarda o ProjectModel
completo + preset_id, podendo ser recarregado depois. Ao salvar, um
THUMBNAIL SVG (vista frontal) é gerado pelo motor de desenho Python e
guardado em data/thumbs/{pid}.svg para a galeria do frontend.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.element import ProjectModel

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
THUMBS_DIR = DATA_DIR / "thumbs"
MAX_VERSIONS = 10  # histórico por projeto (versões mais antigas são descartadas)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return s or "projeto"


def list_projects() -> List[Dict[str, Any]]:
    DATA_DIR.mkdir(exist_ok=True)
    out: List[Dict[str, Any]] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name.endswith(".versions.json"):
            continue  # arquivo de histórico — contado no projeto correspondente
        if path.name.startswith("_"):
            continue  # arquivos internos (ex.: _session.json) não são projetos
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            model = data.get("model", {})
            if not model.get("elements"):
                continue  # arquivos auxiliares (ex.: pricing.json) não são projetos
            vers = read_versions(path.stem)
            out.append({
                "id": path.stem,
                "name": data.get("display_name") or model.get("project", {}).get("name", path.stem),
                "preset_id": data.get("preset_id", ""),
                "elements": len(model.get("elements", [])),
                "saved_at": data.get("saved_at", ""),
                "panel": model.get("panel", {}),
                "thumb": (THUMBS_DIR / f"{path.stem}.svg").exists(),
                "comparable": isinstance(data.get("bom_snapshot"), dict),
                "versions": len(vers),
            })
        except Exception:
            continue
    return out


# ---------------------------------------------------- histórico de versões


def _versions_path(pid: str) -> Path:
    return DATA_DIR / f"{_slug(pid)}.versions.json"


def read_versions(pid: str) -> List[Dict[str, Any]]:
    """Metadados leves das versões arquivadas do projeto (sem os modelos)."""
    p = _versions_path(pid)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        out = []
        for v in raw:
            snap = v.get("bom_snapshot") or {}
            out.append({k: v.get(k) for k in
                        ("v", "saved_at", "name")} | {
                "elements": v.get("elements", snap.get("elements", 0)),
                "mass_kg": v.get("mass_kg", snap.get("total_mass_kg", 0)),
                "cost_brl": v.get("cost_brl", snap.get("total_cost_brl", 0)),
            })
        return out
    except Exception:
        return []


def _append_version(pid: str, preset_id: str, payload: Dict[str, Any],
                    snap: Optional[Dict[str, Any]]) -> int:
    """Arquiva UMA versão (modelo completo + snapshot do BOM) no histórico.

    Guarda no máx. MAX_VERSIONS versões; gravação best-effort — nunca
    falha o salvamento principal. Retorna o nº da versão criada (0 = skip).
    """
    try:
        p = _versions_path(pid)
        archive = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        if not isinstance(archive, list):
            archive = []
        snap_key = json.dumps(snap, sort_keys=True, ensure_ascii=False) if snap else ""
        if archive and snap_key and \
                json.dumps(archive[-1].get("bom_snapshot"), sort_keys=True, ensure_ascii=False) == snap_key:
            return archive[-1].get("v", 0)  # nada mudou desde a última versão
        v_next = (archive[-1].get("v", 0) + 1) if archive else 1
        snap = snap if isinstance(snap, dict) else {}
        archive.append({
            "v": v_next,
            "saved_at": payload.get("saved_at", ""),
            "name": payload.get("display_name", pid),
            "preset_id": preset_id,
            "elements": len(payload.get("model", {}).get("elements", [])) or snap.get("elements", 0),
            "mass_kg": snap.get("total_mass_kg", 0),
            "cost_brl": snap.get("total_cost_brl", 0),
            "model": payload.get("model", {}),
            "bom_snapshot": snap or None,
        })
        archive = archive[-MAX_VERSIONS:]
        p.write_text(json.dumps(archive, ensure_ascii=False), encoding="utf-8")
        return v_next
    except Exception:
        return 0


def load_version(pid: str, v: int) -> Optional[Dict[str, Any]]:
    """Entrada completa (model + bom_snapshot) de uma versão arquivada."""
    p = _versions_path(pid)
    if not p.exists():
        return None
    try:
        archive = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    for entry in archive:
        if int(entry.get("v", -1)) == int(v):
            return entry
    return None


def delete_version(pid: str, v: int) -> bool:
    p = _versions_path(pid)
    if not p.exists():
        return False
    try:
        archive = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    keep = [e for e in archive if int(e.get("v", -1)) != int(v)]
    if len(keep) == len(archive):
        return False
    p.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
    return True


def save_project(model: ProjectModel, preset_id: str, name: Optional[str] = None,
                 thumb_svg: Optional[str] = None,
                 bom_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    display = name or model.project.name or "projeto"
    pid = _slug(display)
    path = DATA_DIR / f"{pid}.json"
    payload = {
        "saved_at": ts,
        "preset_id": preset_id,
        "display_name": display,
        "model": model.model_dump(),
    }
    if bom_snapshot is not None:
        payload["bom_snapshot"] = bom_snapshot
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    if thumb_svg:
        try:
            THUMBS_DIR.mkdir(exist_ok=True)
            (THUMBS_DIR / f"{pid}.svg").write_text(thumb_svg, encoding="utf-8")
        except Exception:
            pass  # thumbnail é opcional — nunca falha o save
    version = _append_version(pid, preset_id, payload, bom_snapshot)
    return {"id": pid, "name": display, "saved_at": ts, "file": path.name,
            "version": version}


def bom_snapshot_from(bom: Dict[str, Any], element_count: int = 0) -> Dict[str, Any]:
    """Resume o BOM no formato compacto guardado junto do projeto salvo
    (base do comparador de versões — diff feito 100% em Python)."""
    return {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elements": element_count,
        "total_mass_kg": round(float(bom.get("total_mass_kg", 0.0)), 2),
        "total_cost_brl": round(float(bom.get("total_cost_brl", 0.0)), 2),
        "items": [
            {"descr": it.get("descr", ""), "kind": it.get("kind", "perfil"),
             "unid": it.get("unid", ""), "quant": it.get("quant", 0),
             "peso_total": round(float(it.get("peso_total", 0.0)), 2),
             "custo_total": round(float(it.get("custo_total", 0.0)), 2)}
            for it in bom.get("items", [])
        ],
    }


def diff_snapshots(old_snap: Dict[str, Any], new_bom: Dict[str, Any],
                   *, meta_old: Dict[str, Any], meta_new: Dict[str, Any]) -> Dict[str, Any]:
    """Motor de diff entre DOIS snapshots de BOM (100% Python).

    `meta_old`/`meta_new` descrevem cada lado: {id, name, saved_at,
    elements, mass_kg, cost_brl}. Usado por: salvo↔atual, versão↔atual
    e salvo↔salvo (comparador A ↔ B)."""
    old = {i["descr"]: i for i in old_snap.get("items", [])}
    cur = {i["descr"]: i for i in new_bom.get("items", [])}

    def row(it: Dict[str, Any]) -> Dict[str, Any]:
        return {"descr": it["descr"], "kind": it.get("kind"), "unid": it.get("unid", ""),
                "quant": it.get("quant", 0), "peso_total": it.get("peso_total", 0.0),
                "custo_total": it.get("custo_total", 0.0)}

    added = [row(cur[d]) for d in cur if d not in old]
    removed = [row(old[d]) for d in old if d not in cur]
    changed = []
    for d in cur:
        if d not in old:
            continue
        o, n = old[d], cur[d]
        dq = float(n.get("quant", 0)) - float(o.get("quant", 0))
        dp = float(n.get("peso_total", 0)) - float(o.get("peso_total", 0))
        dc = float(n.get("custo_total", 0)) - float(o.get("custo_total", 0))
        if abs(dq) > 1e-9 or abs(dp) > 0.05 or abs(dc) > 0.5:
            changed.append({"descr": d, "kind": n.get("kind"), "unid": n.get("unid", ""),
                            "old": {"quant": o.get("quant", 0), "peso_total": o.get("peso_total", 0),
                                    "custo_total": o.get("custo_total", 0)},
                            "new": {"quant": n.get("quant", 0), "peso_total": n.get("peso_total", 0),
                                    "custo_total": n.get("custo_total", 0)},
                            "delta_quant": dq, "delta_peso": dp, "delta_custo": dc})
    changed.sort(key=lambda c: -abs(c["delta_custo"]))
    return {
        "ok": True,
        "id": meta_old.get("id", ""),
        "other_id": meta_new.get("id", ""),
        "name": meta_old.get("name", ""),
        "other_name": meta_new.get("name", ""),
        "saved_at": meta_old.get("saved_at", ""),
        "other_saved_at": meta_new.get("saved_at", ""),
        "saved_elements": meta_old.get("elements", 0),
        "current_elements": meta_new.get("elements", 0),
        "totals": {
            "saved": {"mass_kg": meta_old.get("mass_kg", 0), "cost_brl": meta_old.get("cost_brl", 0)},
            "current": {"mass_kg": meta_new.get("mass_kg", 0), "cost_brl": meta_new.get("cost_brl", 0)},
            "delta_mass_kg": round(float(meta_new.get("mass_kg", 0)) - float(meta_old.get("mass_kg", 0)), 2),
            "delta_cost_brl": round(float(meta_new.get("cost_brl", 0)) - float(meta_old.get("cost_brl", 0)), 2),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def _meta_from_data(pid: str, data: Dict[str, Any], snap: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": pid,
        "name": data.get("display_name", pid),
        "saved_at": snap.get("saved_at") or data.get("saved_at", ""),
        "elements": snap.get("elements", 0),
        "mass_kg": snap.get("total_mass_kg", 0),
        "cost_brl": snap.get("total_cost_brl", 0),
    }


def _no_snapshot_result(pid: str, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {"ok": False, "saved_at": (data or {}).get("saved_at", ""),
            "name": (data or {}).get("display_name", pid),
            "reason": "Este arquivo foi salvo por uma versão anterior sem "
                      "snapshot de materiais. Salve novamente para habilitar a comparação."}


def _meta_current(current_bom: Dict[str, Any], current_elements: int) -> Dict[str, Any]:
    return {"id": "__atual__", "name": "projeto atual",
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elements": current_elements,
            "mass_kg": round(float(current_bom.get("total_mass_kg", 0)), 2),
            "cost_brl": round(float(current_bom.get("total_cost_brl", 0)), 2)}


def diff_saved_vs_current(pid: str, current_bom: Dict[str, Any],
                          current_elements: int = 0) -> Optional[Dict[str, Any]]:
    """Compara o BOM de um projeto SALVO com o BOM ATUAL da sessão.

    Retorna itens ADICIONADOS, REMOVIDOS e ALTERADOS (quantidade/peso/custo)
    + totais lado a lado. None se o projeto não existir.
    """
    data = load_project(pid)
    if data is None:
        return None
    snap = data.get("bom_snapshot")
    if not snap or not isinstance(snap.get("items"), list):
        return _no_snapshot_result(pid, data)
    return diff_snapshots(snap, current_bom,
                          meta_old=_meta_from_data(pid, data, snap),
                          meta_new=_meta_current(current_bom, current_elements))


def diff_two_saved(pid_a: str, pid_b: str) -> Optional[Dict[str, Any]]:
    """Diff entre DOIS projetos SALVOS (A = lado antigo, B = lado novo)."""
    da, db = load_project(pid_a), load_project(pid_b)
    if da is None or db is None:
        return None
    sa, sb = da.get("bom_snapshot"), db.get("bom_snapshot")
    if not sa or not isinstance(sa.get("items"), list):
        return _no_snapshot_result(pid_a, da)
    if not sb or not isinstance(sb.get("items"), list):
        return _no_snapshot_result(pid_b, db)
    return diff_snapshots(sa, sb,
                          meta_old=_meta_from_data(pid_a, da, sa),
                          meta_new=_meta_from_data(pid_b, db, sb))


def diff_version_vs_current(pid: str, v: int, current_bom: Dict[str, Any],
                            current_elements: int = 0) -> Optional[Dict[str, Any]]:
    """Diff entre uma versão ARQUIVADA (v) e o BOM ATUAL da sessão."""
    entry = load_version(pid, v)
    if entry is None:
        return None
    snap = entry.get("bom_snapshot")
    if not snap or not isinstance(snap.get("items"), list):
        return _no_snapshot_result(pid, {"saved_at": entry.get("saved_at", ""),
                                         "display_name": entry.get("name", pid)})
    meta_old = _meta_from_data(pid, {"display_name": entry.get("name", pid),
                                     "saved_at": entry.get("saved_at", "")}, snap)
    meta_old["name"] = f"{meta_old['name']} (v{v})"
    return diff_snapshots(snap, current_bom,
                          meta_old=meta_old,
                          meta_new=_meta_current(current_bom, current_elements))


def thumb_path(pid: str) -> Optional[Path]:
    p = THUMBS_DIR / f"{_slug(pid)}.svg"
    return p if p.exists() else None


def build_versions_zip(pid: str) -> Optional[bytes]:
    """Exporta o histórico completo de versões como .zip (bytes).

    Conteúdo: LEIAME.txt (metadados do export), evolucao.svg (gráfico
    peso/custo gerado em Python) e versoes/vN.json (entrada completa de
    cada versão — modelo + snapshot do BOM, recarregável via import).
    Retorna None se o projeto não existir (nem salvo, nem com histórico).
    """
    import io
    import zipfile

    from drawing.sparkline import versions_spark_svg

    project = load_project(pid)
    p = _versions_path(pid)
    if project is None and not p.exists():
        return None
    try:
        archive = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except Exception:
        archive = []
    if not isinstance(archive, list):
        archive = []

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        name = (project or {}).get("name", archive[-1].get("name", pid) if archive else pid)
        lines = [
            "LED STRUCTURE CAD — histórico de versões",
            "=" * 42,
            f"Projeto: {name}",
            f"ID: {_slug(pid)}",
            f"Exportado em: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Versões arquivadas: {len(archive)}"
            + (f" (limite {MAX_VERSIONS})" if archive else ""),
            "",
            "Conteúdo do .zip:",
            "  versoes/vN.json — entrada completa da versão (modelo + snapshot do BOM).",
            "    Cada JSON pode ser reimportado pela UI (botão ⤒) ou via POST /api/project/import.",
            "  evolucao.svg — gráfico de evolução de peso/custo pelas versões (Python puro).",
            "",
            "Observações:",
            f"  - O histórico guarda no máximo {MAX_VERSIONS} versões (mais antigas descartadas).",
            "  - Versões com BOM idêntico à anterior não são duplicadas (dedupe no salvamento).",
        ]
        z.writestr("LEIAME.txt", "\n".join(lines), compress_type=zipfile.ZIP_DEFLATED)
        for entry in archive:
            v = entry.get("v", 0)
            z.writestr(f"versoes/v{v}.json",
                       json.dumps(entry, ensure_ascii=False, indent=1),
                       compress_type=zipfile.ZIP_DEFLATED)
        if len(archive) >= 2:
            z.writestr("evolucao.svg", versions_spark_svg(archive),
                       compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def load_project(pid: str) -> Optional[Dict[str, Any]]:
    path = DATA_DIR / f"{_slug(pid)}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def delete_project(pid: str) -> bool:
    path = DATA_DIR / f"{_slug(pid)}.json"
    existed = False
    if path.exists():
        path.unlink()
        existed = True
    versions = _versions_path(pid)
    if versions.exists():
        versions.unlink()
    thumb = THUMBS_DIR / f"{_slug(pid)}.svg"
    if thumb.exists():
        thumb.unlink()
    return existed
