"""Pruebas del modelo financiero COD. Ejecutar: python3 -m pytest -q scripts/  (o python3 scripts/test_modelo_financiero.py)

Tres verificaciones independientes:
  1. Álgebra exacta (Fraction) contra la fórmula cerrada.
  2. Derivación alternativa por enumeración de resultados (valor esperado sobre {entregado, rechazado}).
  3. Simulación Monte Carlo (ley de grandes números) con semilla fija.
  4. Regresión: los números publicados en el informe 01 coinciden con el modelo (tolerancia ±1 COP por redondeo).
"""
import random
import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo_financiero import (PRODUCTOS_INFORME_01, Supuestos, contribucion_entregado, cpa_max,
                               margen_con_cpa_objetivo, pvp_minimo_para_cpa, utilidad_por_pedido)

S0 = Supuestos()


def _ev_enumerado(P, C, r, cpa, s):
    """Valor esperado sumando explícitamente cada rama del árbol de resultados."""
    ramas = [
        (1 - r, P - s.comision_cod * P - C - s.flete_ida),   # entregado: recaudo - comisión - producto - flete ida
        (r, -s.flete_ida - s.flete_retorno),                  # rechazado: flete ida + flete retorno, sin comisión ni producto
    ]
    assert sum(p for p, _ in ramas) == 1
    return sum(p * v for p, v in ramas) - cpa * (1 + s.iva_pauta)


def test_cpa_max_es_punto_de_equilibrio_exacto():
    for _, P in PRODUCTOS_INFORME_01:
        C = F(P, 3)
        for r in (F(1, 10), F(15, 100), F(2, 10), F(3, 10)):
            for s in (S0, Supuestos(iva_pauta=F(19, 100))):
                cm = cpa_max(P, C, r, s)
                assert utilidad_por_pedido(P, C, r, cm, s) == 0
                assert _ev_enumerado(P, C, r, cm, s) == 0
                # monotonía: más devolución => menor CPA máximo
                assert cpa_max(P, C, r + F(1, 100), s) < cm


def test_formula_cerrada_igual_a_enumeracion():
    for _, P in PRODUCTOS_INFORME_01:
        for r in (F(0), F(1, 10), F(1, 4), F(1, 2)):
            for cpa in (0, 10000, 25000):
                assert utilidad_por_pedido(P, F(P, 3), r, cpa, S0) == _ev_enumerado(P, F(P, 3), r, cpa, S0)


def test_monte_carlo_converge():
    rnd = random.Random(20261119)
    P, C, r, cpa = 119900, 39967, 0.15, 25000
    n = 400_000
    tot = 0.0
    for _ in range(n):
        if rnd.random() < r:
            tot += -(S0.flete_ida + S0.flete_retorno)
        else:
            tot += P * (1 - float(S0.comision_cod)) - C - S0.flete_ida
        tot -= cpa
    sim = tot / n
    exacto = float(utilidad_por_pedido(P, C, F(15, 100), cpa, S0))
    # error estándar ~ sqrt(r(1-r))*(contrib+40000)/sqrt(n) ≈ 54 COP; tolerancia 5 sigma
    assert abs(sim - exacto) < 300, (sim, exacto)


# Valores publicados en informes/2026-11-19_informe-01_candidatos.md (CPA máx y margen, r = 10/15/20 %)
PUBLICADO = {
    119900: ([46702, 41886, 37069], [18681, 16754, 14828]),
    79900: ([23783, 20240, 16696], [9513, 8096, 6678]),
    69900: ([18053, 14828, 11602], [7221, 5931, 4641]),
    64900: ([15188, 12122, 9056], [6075, 4849, 3622]),
}


def test_regresion_informe_01():
    for P, (cpas, margenes) in PUBLICADO.items():
        C = round(P / 3)
        for r, cp, mg in zip((F(1, 10), F(15, 100), F(2, 10)), cpas, margenes):
            assert abs(float(cpa_max(P, C, r, S0)) - cp) <= 1
            assert abs(float(margen_con_cpa_objetivo(P, C, r, S0)) - mg) <= 1


def test_umbral_pvp_80k():
    # Afirmación del informe: PVP < ~80k => CPA máx < 20k (r=15 %, C=P/3, sin IVA)
    umbral = pvp_minimo_para_cpa(20000, F(15, 100), S0)
    assert 79000 < umbral < 80000, float(umbral)
    assert cpa_max(umbral, umbral / 3, F(15, 100), S0) == 20000


def test_contribucion_entregado_desglose():
    # 119.900 - 3.597 (3 %) - 39.967 - 20.000 = 56.336
    assert contribucion_entregado(119900, 39967, S0) == F(56336)


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            try:
                fn(); print("OK  ", nombre)
            except AssertionError as e:
                fallos += 1; print("FAIL", nombre, e)
    sys.exit(1 if fallos else 0)
