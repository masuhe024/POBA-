"""Clasificación de productos Dropi con validación de pauta MANUAL (sin Dropkiller ni métricas de pago).

Flujo
  1. El catálogo se lee con el conector MCP de Dropi (list_products) y se guarda como texto o JSON.
  2. Este script calcula el CPA máximo COD de cada producto (scripts/modelo_financiero.py) y lo deja
     en ⚪ SIN DATOS de pauta.
  3. El usuario revisa a mano Meta Ad Library / Dropi y registra lo que ve en data/pauta_manual.json:
        {"1234": {"anuncios_activos": 6, "nota": "visto 2026-11-20, >7 días"}}
  4. El script reclasifica:
        🟢 VALIDADO EN PAUTA   anuncios_activos >= UMBRAL_VERDE (5)
        🟡 TESTEAR             1 .. UMBRAL_VERDE-1
        🔴 DESCARTAR           0 confirmado, o CPA máx <= 0 con el precio sugerido
        ⚪ SIN DATOS           aún no revisado

Uso
  python3 -I scripts/clasificar_dropi.py CATALOGO [--pauta data/pauta_manual.json] [--r 0.20] [--md salida.md]
  CATALOGO: salida de texto del MCP de Dropi (formato "items[N]: - id: ...") o lista JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo_financiero import Supuestos, cpa_max  # noqa: E402

UMBRAL_VERDE = 5
# Palabras que obligan a revisión manual por reglas del proyecto (Invima no verificado, tallas, perecederos)
ALERTAS = {
    "Invima": r"crema|s[eé]rum|perfum|colonia|shampoo|champ[uú]|t[oó]nico|gainer|prote[ií]na|suplement|vitamina|capsul|c[aá]psul|col[aá]geno|aceite|gel|jab[oó]n|maquilla|labial|keratina|tinte|minoxidil|biotina|loci[oó]n|pre.?entreno|shilajit|jarabe|cauteriz|verruga|nebuliz|respirator|terap|m[eé]dic",
    "Tallas": r"talla|faja|leggin|camis|pantal|jeans|vestido|zapat|tenis|brasier|bra |ropa|conjunto|pijama|boxer|bermuda|chaqueta|sandalia|licrad|blus[oó]n|sudadera|sueco|palazzo|brasier",
    "Política Meta (adultos)": r"vibrador|consolador|er[oó]tic|sex",
    "Perecedero": r"aliment|comida|snack|caf[eé]|t[eé] |chocolate",
}


def parse_mcp_texto(txt: str) -> list[dict]:
    """Parser mínimo del formato de texto del MCP de Dropi: toma las claves de primer nivel de cada item."""
    items, cur = [], None
    for line in txt.splitlines():
        m = re.match(r"^  - id: (\d+)\s*$", line)
        if m:
            cur = {"id": int(m.group(1)), "n_variaciones": 0}
            items.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^    ([a-z_]+)(?:\[(\d+)\])?(?:\{[^}]*\})?:\s?(.*)$", line)
        if not m:
            continue
        k, n, v = m.group(1), m.group(2), m.group(3).strip()
        if k == "variations":
            cur["n_variaciones"] = int(n or 0)
        elif k == "categories":
            cur["categories"] = v
        elif k in ("name", "sku"):
            cur[k] = v.strip('"')
        elif k in ("sale_price", "suggested_price", "stock", "supplier_id"):
            cur[k] = None if v == "null" else float(v)
    return items


def cargar_catalogo(ruta: str) -> list[dict]:
    txt = Path(ruta).read_text(encoding="utf-8")
    if txt.lstrip().startswith("["):
        data = json.loads(txt)
        for p in data:
            p.setdefault("n_variaciones", len(p.get("variations") or []))
        return data
    return parse_mcp_texto(txt)


def alertas(nombre: str, cats: str) -> list[str]:
    t = f"{nombre} {cats}".lower()
    out = [k for k, rx in ALERTAS.items() if re.search(rx, t)]
    if re.search(MARCAS, t):
        out.append("Marca/posible réplica")
    return out


def evaluar(p: dict, pauta: dict, r: Fraction, s: Supuestos) -> dict:
    C, P = p.get("sale_price") or 0, p.get("suggested_price") or 0
    cmax = float(cpa_max(P, C, r, s)) if P else float("nan")
    reg = pauta.get(str(p["id"]))
    if not P:
        estado = "⚪ SIN DATOS (sin precio sugerido)"
        cmax = 0.0
    elif cmax <= 0:
        estado = "🔴 DESCARTAR (CPA máx ≤ 0 con precio sugerido)"
    elif reg is None:
        estado = "⚪ SIN DATOS"
    else:
        a = int(reg.get("anuncios_activos", 0))
        estado = "🟢 VALIDADO EN PAUTA" if a >= UMBRAL_VERDE else ("🟡 TESTEAR" if a >= 1 else "🔴 DESCARTAR (0 anuncios)")
    return {
        "id": p["id"], "nombre": p.get("name", "?"), "proveedor": int(p.get("supplier_id") or 0),
        "costo": C, "sugerido": P, "x": (P / C) if C else 0, "stock": p.get("stock"),
        "tipo": "Variable" if p.get("n_variaciones") else "Simple",
        "cpa_max": cmax, "estado": estado, "alertas": alertas(p.get("name", ""), p.get("categories", "")),
        "anuncios": (reg or {}).get("anuncios_activos"), "nota": (reg or {}).get("nota", ""),
    }


ORDEN = {"🟢": 0, "🟡": 1, "⚪": 2, "🔴": 3}
# Marca registrada en el nombre (posible réplica): bloquear hasta verificar autenticidad
MARCAS = r"gaultier|dior|chanel|versace|carolina herrera|paco rabanne|lattafa|apple|iphone|airpods|samsung|xiaomi|nike|adidas|stanley|jbl|sony|levis|levi's|tommy|puma|good girl|scandal|acqua di gio|acgua di gio"


def tabla(filas: list[dict], r: Fraction) -> str:
    out = [f"| ID | Producto | Proveedor | Costo (COP) | Sugerido (COP) | x | Tipo | CPA máx r={float(r):.0%} c/IVA | Alertas | Anuncios | Estado |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in filas:
        out.append(f"| {f['id']} | {f['nombre']} | {f['proveedor']} | {f['costo']:,.0f} | {f['sugerido']:,.0f} | {f['x']:.1f} | {f['tipo']} | "
                   f"{f['cpa_max']:,.0f} | {', '.join(f['alertas']) or '—'} | {'' if f['anuncios'] is None else f['anuncios']} | {f['estado']} |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("catalogo")
    ap.add_argument("--pauta", default=str(Path(__file__).resolve().parent.parent / "data" / "pauta_manual.json"))
    ap.add_argument("--r", type=Fraction, default=Fraction(1, 5), help="tasa de devolución (default 0.20)")
    ap.add_argument("--md", help="guardar la tabla en este archivo")
    a = ap.parse_args(argv)
    pauta = json.loads(Path(a.pauta).read_text(encoding="utf-8")) if Path(a.pauta).exists() else {}
    s = Supuestos(iva_pauta=Fraction(19, 100))
    filas = [evaluar(p, pauta, a.r, s) for p in cargar_catalogo(a.catalogo)]
    filas.sort(key=lambda f: (ORDEN[f["estado"][0]], -(f["anuncios"] or 0), -f["cpa_max"]))
    md = tabla(filas, a.r)
    if a.md:
        Path(a.md).write_text(md + "\n", encoding="utf-8")
    print(md)
    cnt = {}
    for f in filas:
        cnt[f["estado"].split(" (")[0]] = cnt.get(f["estado"].split(" (")[0], 0) + 1
    print("\nResumen:", ", ".join(f"{k}: {v}" for k, v in cnt.items()))


if __name__ == "__main__":
    main()
