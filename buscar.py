"""Busca de ilhas: roda muitas sementes aleatórias até o fim e resume o enredo de cada uma.

uso: python buscar.py [n_ilhas] [arquivo_saida]
As sementes são sorteadas pelo sistema operacional (fora da faixa 1-100 da calibragem) e ficam gravadas na saída,
para que qualquer ilha possa ser refeita igual com `python sim.py init --seed N`.
"""
import collections
import json
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import config as C
import motor
import narrativa as N

HERE = Path(__file__).resolve().parent


def resumo(seed):
    m = motor.Mundo.novo(seed)
    while not m.fim and m.h < C.DIAS_MAX * 24:
        m.passo()
    navio = m.flags.get("navio", 0)
    f = N.formato(m)
    s = m.serie
    pop0 = s[0]["vivos"]
    zs = [x["zumbis"] for x in s]
    pico = max(zs) if zs else 0

    def vivos_dia(d):
        i = navio + d * 24
        return s[i]["vivos"] if i < len(s) else s[-1]["vivos"]
    quedas = [(e["h"], m.L[e["lugar"]].nome) for e in m.log if e["tipo"] == "queda" and e["lugar"] in m.L]
    ultima_queda = quedas[-1] if quedas else None
    c = collections.Counter(e["tipo"] for e in m.log)
    marcos = []
    for e in m.log:
        if e["tipo"] in ("traicao", "golpe", "guerra", "campanha", "seita", "rei_morre", "apodrece", "assassinato", "bruxa") \
                or (e["tipo"] == "ideia" and e.get("ideia") in ("cura", "cacada", "antidoto", "isca", "fogo")) \
                or (e["tipo"] == "queda" and e["lugar"] in ("cidadela", "penamor", "torrevelha", "valverde", "pedralva", "ribafria")):
            marcos.append(f"d{(e['h'] - navio) // 24} {e['tipo']}:{(e['lugar'] or '')}")
    return {
        "seed": seed, "fim": m.fim, "fim_tipo": m.flags.get("fim_tipo"), "dias": (m.h - navio) // 24,
        "pop0": pop0, "vivos_fim": s[-1]["vivos"], "pico_zumbis": pico, "zumbis_fim": s[-1]["zumbis"],
        "vivos": {d: vivos_dia(d) for d in (7, 14, 30, 60, 90, 180, 270)},
        "temperamento": N.temperamento(m), "protagonistas_vivos": sum(1 for x in m.holofote if m.P[x["id"]].morte is None),
        "ultima_queda": [(ultima_queda[0] - navio) // 24, ultima_queda[1]] if ultima_queda else None,
        "apodreceram": m.contas["apodreceram"], "contas": {k: c[k] for k in ("traicao", "golpe", "guerra", "campanha", "seita",
                                                                              "bruxa", "assassinato", "reduto", "queda", "fome",
                                                                              "colonia_chega", "expedicao", "comercio", "roubo")},
        "mortos_fome": m.contas["fome"],
        "ritmo": f["ritmo"], "fichas": f["fichas"], "marcos": marcos[:40],
        "citaveis": [(x["nome"], x["quem_e"]) for x in N.citaveis(m, 5)],
    }


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    saida = HERE / (sys.argv[2] if len(sys.argv) > 2 else "busca.json")
    rnd = random.SystemRandom()
    seeds = sorted({rnd.randrange(1_000, 2_000_000_000) for _ in range(n)})
    t = time.time()
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(resumo, seeds))
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(res)} ilhas em {time.time() - t:.0f}s -> {saida.name}")
    tipo = lambda x: x["fim"] + (f"/{x['fim_tipo']}" if x["fim_tipo"] else "")
    print(" fins:", dict(collections.Counter(tipo(x) for x in res)))
    longas = [x for x in res if x["dias"] >= 90 and x["fim"] != "horizonte"]
    print(f" duram 3 meses ou mais até um final: {len(longas)}")
    for x in sorted(longas, key=lambda x: -x["dias"]):
        print(f"  seed {x['seed']:>10} · {tipo(x):15s} · {x['dias']:3d} dias · vivos {x['vivos_fim']:5d} de {x['pop0']} · "
              f"d30 {x['vivos'][30]:5d} · d90 {x['vivos'][90]:5d} · pico {x['pico_zumbis']:4d} · "
              f"{', '.join(x['temperamento']) or '-'}")


if __name__ == "__main__":
    main()
