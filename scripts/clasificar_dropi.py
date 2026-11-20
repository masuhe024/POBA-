"""Clasifica productos de Dropi según ventas de 7/30 días (exportación de Dropkiller u otra fuente).

Uso: python3 -I scripts/clasificar_dropi.py ventas.json
Entrada: lista JSON de objetos. Claves aceptadas (la primera que exista):
  nombre: name | producto
  proveedor: supplier | supplier_name | proveedor | supplier_id
  ventas 7 días: sales_7d | ventas_7d | sales_count_7d
  ventas 30 días: sales_30d | ventas_30d | sales_count_30d
  serie diaria (opcional, más antigua → más reciente): daily_sales | ventas_diarias
  tipo: type ("SIMPLE"/"VARIABLE") o variations (lista; no vacía = Variable)
  badge (opcional): badge | badges
  fecha de creación (opcional): created_at | fecha_creacion
Sin ventas no se clasifica: el producto queda como SIN DATOS (no como DESCARTAR).
"""
import json
import sys


def g(d, *ks, default=None):
    for k in ks:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def constante(serie):
    """Tendencia constante: al menos 4 de los últimos 7 días con ventas y sin concentración >60 % en un solo día."""
    s = [float(x or 0) for x in serie[-7:]]
    tot = sum(s)
    return tot > 0 and sum(1 for x in s if x > 0) >= 4 and max(s) / tot <= 0.6


def clasificar(p):
    v7 = g(p, "sales_7d", "ventas_7d", "sales_count_7d")
    if v7 is None:
        return "⚪ SIN DATOS", None
    v7 = float(v7)
    serie = g(p, "daily_sales", "ventas_diarias")
    if v7 > 10 and (serie is None or constante(serie)):
        return "🟢 WINNER ACTIVO", v7
    if v7 > 10:  # >10 pero concentrado en pocos días: no es constante
        return "🟡 EN CALENTAMIENTO (pico no constante)", v7
    if 3 <= v7 <= 9:
        return "🟡 EN CALENTAMIENTO", v7
    if v7 == 10:
        return "🟡 EN CALENTAMIENTO (límite)", v7
    return "🔴 DESCARTAR", v7


ACCION = {"🟢": "Testear ya: 3–5 creativos, validar CPA máx con scripts/modelo_financiero.py",
          "🟡": "Monitorear 7 días; testear con presupuesto mínimo si sube"}

if __name__ == "__main__":
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    filas, otros = [], {}
    for p in data:
        est, v7 = clasificar(p)
        tipo = g(p, "type")
        if tipo is None:
            tipo = "Variable" if g(p, "variations", default=[]) else "Sugerido/Simple"
        if est[0] in "🟢🟡":
            filas.append((v7, g(p, "name", "producto", default="?"), g(p, "supplier", "supplier_name", "proveedor", "supplier_id", default="?"), tipo, est, ACCION[est[0]]))
        else:
            otros[est] = otros.get(est, 0) + 1
    filas.sort(key=lambda f: -f[0])
    print("| Producto | Proveedor | Ventas (7 días) | Tipo (Sugerido/Variable) | Estado | Acción Recomendada |")
    print("|---|---|---|---|---|---|")
    for v7, n, pr, t, e, a in filas:
        print(f"| {n} | {pr} | {v7:g} | {t} | {e} | {a} |")
    for e, c in otros.items():
        print(f"\n{e}: {c} productos")
