"""Modelo financiero COD (dropshipping nacional, Colombia).

Todo el cálculo se hace en código determinista (sin modelos de IA).
Unidad base: PEDIDO GENERADO (incluye los que luego se rechazan/devuelven).

Notación
    P    PVP cobrado al cliente (recaudo contraentrega)
    C    costo del producto (proveedor / bodega Effi)
    Fi   flete de ida (se paga en todos los pedidos despachados)
    Fr   flete de retorno (solo en pedidos rechazados)
    k    comisión COD sobre el recaudo (solo pedidos entregados)
    r    tasa de devolución / rechazo (0..1)
    A    CPA por pedido generado (pauta)
    iva  IVA sobre la pauta digital (0 en el informe 01; 0.19 en el escenario corregido)

Resultado esperado por pedido generado
    entregado (prob 1-r):  P - k*P - C - Fi
    rechazado (prob r):    -(Fi + Fr)        (la mercancía vuelve; supuesto: sin pérdida de producto)
    pauta:                 -A*(1+iva)

    U(A) = (1-r)*(P*(1-k) - C - Fi) - r*(Fi + Fr) - A*(1+iva)
    CPA_max = [(1-r)*(P*(1-k) - C - Fi) - r*(Fi + Fr)] / (1+iva)     (U = 0)
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as Fr_
from typing import Union

Num = Union[int, float, Fr_]


@dataclass(frozen=True)
class Supuestos:
    flete_ida: Num = 20000
    flete_retorno: Num = 20000
    comision_cod: Num = Fr_(3, 100)
    iva_pauta: Num = 0
    fraccion_cpa_objetivo: Num = Fr_(6, 10)


def contribucion_entregado(P: Num, C: Num, s: Supuestos) -> Num:
    """Utilidad de un pedido ENTREGADO antes de pauta."""
    return P * (1 - s.comision_cod) - C - s.flete_ida


def costo_rechazado(s: Supuestos) -> Num:
    """Pérdida de un pedido RECHAZADO (flete ida + retorno)."""
    return s.flete_ida + s.flete_retorno


def cpa_max(P: Num, C: Num, r: Num, s: Supuestos) -> Num:
    """CPA de equilibrio por pedido generado (incluye IVA de la pauta si aplica)."""
    bruto = (1 - r) * contribucion_entregado(P, C, s) - r * costo_rechazado(s)
    return bruto / (1 + s.iva_pauta)


def utilidad_por_pedido(P: Num, C: Num, r: Num, cpa: Num, s: Supuestos) -> Num:
    return (1 - r) * contribucion_entregado(P, C, s) - r * costo_rechazado(s) - cpa * (1 + s.iva_pauta)


def margen_con_cpa_objetivo(P: Num, C: Num, r: Num, s: Supuestos) -> Num:
    cmax = cpa_max(P, C, r, s)
    return utilidad_por_pedido(P, C, r, cmax * s.fraccion_cpa_objetivo, s)


def pvp_minimo_para_cpa(cpa_deseado: Num, r: Num, s: Supuestos, ratio_costo: Num = Fr_(1, 3)) -> Fr_:
    """PVP mínimo para que CPA_max >= cpa_deseado con C = ratio_costo * P (despeje lineal)."""
    a = (1 - r) * (1 - s.comision_cod - ratio_costo)
    b = (1 - r) * s.flete_ida + r * costo_rechazado(s) + cpa_deseado * (1 + s.iva_pauta)
    return Fr_(b) / Fr_(a)


PRODUCTOS_INFORME_01 = [
    ("Masajeador cervical eléctrico", 119900),
    ("Set bandas de resistencia", 79900),
    ("Rodillo quita pelo mascotas (x2)", 69900),
    ("Corrector de postura", 69900),
    ("Soporte magnético celular (x2)", 64900),
]


if __name__ == "__main__":
    for etiqueta, s in [("Informe 01 (sin IVA pauta)", Supuestos()),
                        ("Corregido (IVA 19 % pauta)", Supuestos(iva_pauta=Fr_(19, 100)))]:
        print(f"\n## {etiqueta}")
        for n, P in PRODUCTOS_INFORME_01:
            C = round(P / 3)
            fila = [f"{n}: PVP {P:,} C {C:,}"]
            for r in (Fr_(1, 10), Fr_(15, 100), Fr_(2, 10), Fr_(3, 10)):
                fila.append(f"r={float(r):.0%} CPAmax {float(cpa_max(P, C, r, s)):,.0f} margen {float(margen_con_cpa_objetivo(P, C, r, s)):,.0f}")
            print(" | ".join(fila))
