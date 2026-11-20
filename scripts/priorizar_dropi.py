"""Priorización ampliada del catálogo Dropi (sin métricas de ventas; demanda = pauta manual del usuario).

  python3 -I scripts/priorizar_dropi.py data/dropi_raw [--cpa 30000] [--r 0.20] [--md informes/x.md] [--csv data/x.csv]

Reglas
  * NO se descarta por CPA bajo a precio sugerido: se calcula el PVP mínimo (1 ud y combo 2x) para un CPA objetivo.
  * EXCLUSIÓN DURA solo por alto riesgo: Invima medicinal estricto (medicamentos, suplementos, dispositivos médicos),
    productos para adultos y réplicas / marcas registradas de terceros.
  * ADVERTENCIAS (no excluyen): cosmético (verificar NSO Invima), tallas, voluminoso/frágil, política Meta, dato dudoso.
  * Score de potencial (0–100) = HEURÍSTICA técnica, NO ventas: margen estructural, ticket combinable, stock (capacidad),
    logística COD y simplicidad operativa. La demanda real la aporta data/pauta_manual.json.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo_financiero import Supuestos, cpa_max  # noqa: E402

EXCLUIR = {
    "Invima medicinal": r"suplement|gainer|pre.?entreno|prote[ií]na|vitamin|multivit|dolor|analg|antiinflam|shilajit|jarabe|c[aá]psul|capsul|col[aá]geno|"
                        r"minoxidil|biotina|medic|cauteriz|verruga|nebuliz|respirator|ipl|l[aá]ser|ems\b|ems-|electrodo|"
                        r"gimnasia pasiva|electroestim|tens\b|ox[ií]metro|tensi[oó]metro|gluc[oó]metro|term[oó]metro cl[ií]n",
    "Adultos": r"vibrador|consolador|er[oó]tic|sex|lilo|lubricante [ií]ntim|estimulaci[oó]n",
    "Réplica/marca": r"gaultier|dior|chanel|versace|carolina herrera|paco rabanne|lattafa|tous|apple|iphone|airpods|airopds|"
                     r"samsung|xiaomi|redmi|nike|adidas|puma|levis|tommy|stanley|jbl|charge ?5|flip ?7|go ?4|sony|babyliss|"
                     r"dewalt|taladro dw|\bdw\b|shure|sm58|mickey|disney|labubu|hello kitty|kitty|good girl|scandal|acqua|acgua|"
                     r"maison alhambra|orientica|tuya|honor magic",
}
ADVERTIR = {
    "Cosmético: verificar NSO Invima": r"perfum|crema|s[eé]rum|shampoo|keratina|maquilla|labial|loci[oó]n|splash|tinte|cera\b|gel\b",
    "Tallas": r"talla|jean|mom |pantal|camis|blus|vestido|zapat(?!ero)|sandalia|brasier|sudadera|leggin|conjunto deport|licrad",
    "Voluminoso/frágil": r"[aá]rbol|armario|zapatero|perchero|platero|mesita|sancochera|olla|vidrio|calefactor|pantalla tel|"
                         r"duvet|s[aá]banas|guadaña|palomitas|bbq|exprimidora|escurridor",
    "Marca de tercero: verificar autenticidad": r"simoniz|truly|bioaqua|hermex|baofeng|happy pets",
    "Política Meta (vigilancia)": r"esp[ií]a|rastreador|localizador",
    "Alcohol (restricción pauta)": r"shots|vino",
}


def parse_mcp_texto(txt: str) -> list[dict]:
    items, cur, var = [], None, None
    for line in txt.splitlines():
        m = re.match(r"^  - id: (\d+)\s*$", line)
        if m:
            cur = {"id": int(m.group(1)), "n_var": 0, "var_stock": 0, "var_sug": [], "var_cost": []}
            items.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^    ([a-z_]+)(?:\[(\d+)\])?(?:\{[^}]*\})?:\s?(.*)$", line)
        if m:
            k, n, v = m.group(1), m.group(2), m.group(3).strip()
            if k == "variations":
                cur["n_var"] = int(n or 0)
            elif k == "categories":
                cur["cats"] = v
            elif k == "name":
                cur["name"] = v.strip('"')
            elif k in ("sale_price", "suggested_price", "stock"):
                cur[k] = None if v == "null" else float(v)
            continue
        m = re.match(r"^        (stock|sale_price|suggested_price): (\S+)$", line)
        if m and m.group(2) != "null":
            val = float(m.group(2))
            {"stock": lambda: cur.__setitem__("var_stock", cur["var_stock"] + val),
             "sale_price": lambda: cur["var_cost"].append(val),
             "suggested_price": lambda: cur["var_sug"].append(val)}[m.group(1)]()
    out = []
    for c in items:
        sug = c.get("suggested_price") or (min(c["var_sug"]) if c["var_sug"] else 0)
        cost = c.get("sale_price") or (min(c["var_cost"]) if c["var_cost"] else 0)
        stock = c.get("stock") or c["var_stock"]
        out.append({"id": c["id"], "nombre": c.get("name", "?"), "costo": cost, "sugerido": sug,
                    "stock": stock, "cats": c.get("cats", ""), "n_var": c["n_var"]})
    return out


def cargar(directorio: str) -> list[dict]:
    vistos = {}
    for p in sorted(Path(directorio).iterdir()):
        if p.suffix == ".txt":
            filas = parse_mcp_texto(p.read_text(encoding="utf-8"))
        elif p.suffix == ".json":
            filas = [{"id": r[0], "nombre": r[1], "costo": r[2], "sugerido": r[3] or 0, "stock": r[4], "cats": r[5], "n_var": r[6]}
                     for r in json.loads(p.read_text(encoding="utf-8")) if isinstance(r[0], int)]
        else:
            continue
        for f in filas:
            vistos.setdefault(f["id"], f)
    return list(vistos.values())


def etiquetas(nombre, cats, reglas):
    t = f" {nombre} | {cats} ".lower()
    return [k for k, rx in reglas.items() if re.search(rx, t)]


def pvp_minimo(costo_total, cpa, r, s):
    """PVP con CPA_max == cpa (despeje lineal de modelo_financiero.cpa_max)."""
    return ((1 - r) * (costo_total + s.flete_ida) + r * (s.flete_ida + s.flete_retorno) + cpa * (1 + s.iva_pauta)) / ((1 - r) * (1 - s.comision_cod))


def redondear_pvp(x):
    return int(math.ceil(float(x) / 1000.0) * 1000 - 100)  # ej. 87.900


def evaluar(p, cpa_obj, r, s):
    C, P = p["costo"], p["sugerido"]
    excl = etiquetas(p["nombre"], p["cats"].split(",")[0] if False else p["nombre"], EXCLUIR)  # solo nombre: categorías de Dropi son ruidosas
    adv = etiquetas(p["nombre"], "", ADVERTIR)
    dudoso = C < 3000 or (P and P < C) or p["stock"] > 100000
    if dudoso:
        adv.append("Dato dudoso (costo/precio/stock)")
    p1 = pvp_minimo(C, cpa_obj, r, s)
    p2 = pvp_minimo(2 * C, cpa_obj, r, s)
    cpa_sug = float(cpa_max(P, C, r, s)) if P else None
    if P and P >= p1:
        estrategia = "1 ud a precio sugerido"
    elif P and p1 <= 1.25 * P:
        estrategia = "1 ud subiendo PVP"
    elif p2 <= 1.6 * max(P, 1) * 1.0 or not P:
        estrategia = "Combo 2x"
    else:
        estrategia = "Combo 2x o kit 3x"
    # --- score heurístico 0-100 (NO es demanda) ---
    markup = (P / C) if C and P else 0
    s_margen = min(markup, 4) / 4 * 30
    s_ticket = 20 if 15000 <= C <= 70000 else (12 if C <= 120000 else 4)
    s_stock = min(math.log10(max(p["stock"], 1)) / 3, 1) * 20      # 1000+ uds = 20
    s_log = 15 - (8 if "Voluminoso/frágil" in adv else 0) - (5 if "Tallas" in adv else 0)
    s_simple = 10 if p["n_var"] == 0 else 6
    s_cat = 5 if re.search(r"hogar|cocina|mascota|tecnolog|belleza", p["cats"], re.I) else 0
    score = round(s_margen + s_ticket + s_stock + max(s_log, 0) + s_simple + s_cat - (25 if dudoso else 0))
    return {**p, "excluir": excl, "advertencias": adv, "pvp_min_1": redondear_pvp(p1), "pvp_min_combo2": redondear_pvp(p2),
            "pvp_3x": int(3 * C), "cpa_max_sugerido": cpa_sug, "estrategia": estrategia, "score": max(score, 0),
            "categoria": next((c for c in ("Mascotas", "Cocina", "Hogar", "Tecnologia", "Belleza") if c.lower() in p["cats"].lower()),
                              p["cats"].split(",")[0] if p["cats"] else "?")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("directorio")
    ap.add_argument("--cpa", type=int, default=30000, help="CPA objetivo por pedido generado, antes de IVA")
    ap.add_argument("--r", type=F, default=F(1, 5))
    ap.add_argument("--min-stock", type=int, default=20)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--md")
    ap.add_argument("--csv")
    a = ap.parse_args(argv)
    s = Supuestos(iva_pauta=F(19, 100))
    pauta_path = Path(__file__).resolve().parent.parent / "data" / "pauta_manual.json"
    pauta = json.loads(pauta_path.read_text(encoding="utf-8")) if pauta_path.exists() else {}
    todos = [evaluar(p, a.cpa, a.r, s) for p in cargar(a.directorio)]
    excl = [t for t in todos if t["excluir"]]
    sin_stock = [t for t in todos if not t["excluir"] and t["stock"] < a.min_stock]
    ok = [t for t in todos if not t["excluir"] and t["stock"] >= a.min_stock]
    for t in ok:
        reg = pauta.get(str(t["id"]))
        t["anuncios"] = None if reg is None else int(reg.get("anuncios_activos", 0))
    ok.sort(key=lambda t: (-(t["anuncios"] or -1), -t["score"]))
    lineas = [f"| # | ID | Producto | Categoría | Costo | PVP sugerido | PVP mín 1 ud | PVP mín combo 2x | Estrategia | Stock | Score | Advertencias |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, t in enumerate(ok[: a.top], 1):
        lineas.append(f"| {i} | {t['id']} | {t['nombre']} | {t['categoria']} | {t['costo']:,.0f} | {t['sugerido']:,.0f} | {t['pvp_min_1']:,} | "
                      f"{t['pvp_min_combo2']:,} | {t['estrategia']} | {t['stock']:,.0f} | {t['score']} | {', '.join(t['advertencias']) or '—'} |")
    resumen = (f"Productos únicos leídos: {len(todos)} | excluidos por alto riesgo: {len(excl)} | stock < {a.min_stock}: {len(sin_stock)} | "
               f"priorizables: {len(ok)} | CPA objetivo {a.cpa:,} + IVA 19 %, devolución {float(a.r):.0%}")
    md = resumen + "\n\n" + "\n".join(lineas)
    if a.md:
        Path(a.md).write_text(md + "\n\n### Excluidos (alto riesgo)\n" + "\n".join(
            f"- {t['id']} {t['nombre']} → {', '.join(t['excluir'])}" for t in excl) + "\n", encoding="utf-8")
    if a.csv:
        import csv
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["rank", "id", "nombre", "categoria", "costo", "pvp_sugerido", "pvp_min_1", "pvp_min_combo2", "estrategia", "stock",
                        "score", "advertencias", "anuncios_activos_meta", "fecha_revision", "nota"])
            for i, t in enumerate(ok, 1):
                w.writerow([i, t["id"], t["nombre"], t["categoria"], int(t["costo"]), int(t["sugerido"]), t["pvp_min_1"], t["pvp_min_combo2"],
                            t["estrategia"], int(t["stock"]), t["score"], "; ".join(t["advertencias"]), "", "", ""])
    print(md)


if __name__ == "__main__":
    main()
