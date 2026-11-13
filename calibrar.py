"""Calibragem: roda muitas ilhas para várias combinações de parâmetros e mostra uma linha por combinação.

uso: python calibrar.py [n_ilhas]   (as combinações estão em VARIANTES)
As metas estão em docs/RULES.md: mortos-vivos presentes até tarde, finais variados, vivos no meio da história.
"""
import json
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor

import config as C
import motor
import narrativa as N

VARIANTES = json.loads(sys.argv[2]) if len(sys.argv) > 2 else [{}]
PADRAO = {k: getattr(C, k) for k in dir(C) if k.isupper()}   # cada ilha começa dos valores do config.py


def uma(args):
    seed, ajustes = args
    for k, v in PADRAO.items():
        setattr(C, k, v)
    for k, v in ajustes.items():
        setattr(C, k, v)
    m = motor.Mundo.novo(seed)
    while not m.fim and m.h < C.DIAS_MAX * 24:
        m.passo()
    s = m.serie

    def em(d, k):
        i = d * 24
        return s[i][k] if i < len(s) else (s[-1][k] if k == "vivos" else 0)
    f = N.formato(m)
    return {"fim": m.fim, "pop0": s[0]["vivos"], **{f"v{d}": em(d, "vivos") for d in (7, 14, 30, 60, 120, 180)},
            **{f"z{d}": em(d, "zumbis") for d in (14, 30, 60, 120, 180)}, "ritmo": f["ritmo"], "fichas": f["fichas"]}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    with ProcessPoolExecutor() as ex:
        for aj in VARIANTES:
            res = list(ex.map(uma, [(s, aj) for s in range(1, n + 1)]))
            fins = {k: sum(1 for x in res if x["fim"] == k) for k in ("vitoria", "derrota", "horizonte")}
            q = lambda k: st.median(x[k] for x in res)
            vq = lambda d: st.median(x[f"v{d}"] / x["pop0"] for x in res)
            zviva = sum(1 for x in res if x["z60"] > 100) / n
            print(f"{json.dumps(aj, ensure_ascii=False):60s} vit {fins['vitoria']:2d} der {fins['derrota']:2d} hor {fins['horizonte']:2d} | "
                  f"vivos d14 {vq(14):.0%} d30 {vq(30):.0%} d60 {vq(60):.0%} d180 {vq(180):.0%} | "
                  f"zumbis d14 {q('z14'):.0f} d30 {q('z30'):.0f} d60 {q('z60'):.0f} d120 {q('z120'):.0f} | z60>100 em {zviva:.0%}",
                  flush=True)
            com = lambda fa: sum(1 for x in res if x["ritmo"].get(fa, 0) >= 2) / n
            fr = lambda fi: sum(1 for x in res if fi in x["fichas"]) / n
            perda = {b: sum(1 for x in res if f"perda:{b}" in x["fichas"]) for b in ("pouca", "metade", "grande", "quase_toda")}
            print(f"{'':60s} perda {perda} | vivos d7 {vq(7):.0%} | 2+ marcos nos dias 15-30 {com('15-30'):.0%} "
                  f"31-60 {com('31-60'):.0%} 61-120 {com('61-120'):.0%} | seita {fr('ev:seita'):.0%} cheiro {fr('ev:cheiro'):.0%} "
                  f"traição {fr('ev:traicao'):.0%} cura {fr('ideia:cura'):.0%}", flush=True)


if __name__ == "__main__":
    main()
