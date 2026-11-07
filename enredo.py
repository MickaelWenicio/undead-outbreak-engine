"""Roda uma ilha e imprime o enredo em resumo: fases, primeiros acontecimentos de cada tipo, protagonistas, citáveis.

uso: python enredo.py SEMENTE [SEMENTE ...]   (cada uma vira enredo_SEMENTE.txt)
"""
import collections
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import config as C
import motor
import narrativa as N

HERE = Path(__file__).resolve().parent
CHAVE = ("navio", "queda", "rei_morre", "rei", "traicao", "golpe", "guerra", "campanha", "seita", "bruxa", "assassinato",
         "ideia", "colonia_chega", "fome", "apodrece", "aprendem", "reduto", "reduto_cai", "recusa_ordem", "evacuacao",
         "portao_abre", "cheiro", "fim", "lider", "obra", "mensageiro", "boato")


def enredo(seed):
    m = motor.Mundo.novo(seed)
    while not m.fim and m.h < C.DIAS_MAX * 24:
        m.passo()
    nav = m.flags["navio"]
    out = []
    w = out.append
    s = m.serie
    w(f"SEMENTE {seed} · fim {m.fim}/{m.flags.get('fim_tipo')} · {(m.h - nav) // 24} dias depois do navio · "
      f"vivos {s[-1]['vivos']} de {s[0]['vivos']} · temperamento {', '.join(N.temperamento(m))}")
    for d in (3, 7, 14, 30, 60, 90, 120, 180, 240, 300, 360, 420, 480, 540):
        i = nav + d * 24
        if i < len(s):
            vivos_l = sorted(((len(m.H[l]) if False else 0), l) for l in m.L)
            w(f"  dia {d:3d}: vivos {s[i]['vivos']:5d} · mortos-vivos {s[i]['zumbis']:4d}")
    w("PROTAGONISTAS")
    for f in m.holofote:
        p = m.P[f["id"]]
        w(f"  {m.nm(p)} ({int(p.idade)}, {p.papel}, {f['papel']}): "
          + (f"{p.causa}, dia {(p.morte - nav) // 24}" if p.morte is not None else "VIVO no fim"))
    w("CITÁVEIS")
    for c in N.citaveis(m, 8):
        w(f"  {c['nome']} · {c['quem_e']}")
        for f in c["feitos"][:2]:
            w(f"      {f['quando']} [{f['tipo']}] {f['texto'][:170]}")
    w("LINHA DO TEMPO (acontecimentos de peso; repetições do mesmo tipo e lugar no mesmo mês são contadas, não repetidas)")
    visto = collections.Counter()
    for e in m.log:
        if e["tipo"] not in CHAVE or e["h"] < nav - 24:
            continue
        if e["tipo"] == "ideia" and e.get("ideia") in ("antidoto_falha", "pesca_mar", "hortas"):
            continue
        d = (e["h"] - nav) // 24
        k = (e["tipo"], e.get("ideia"), e["lugar"], d // 30)
        visto[k] += 1
        if visto[k] > (1 if e["tipo"] not in ("queda", "fim", "rei_morre", "colonia_chega") else 3):
            continue
        w(f"  d{d:3d} [{e['tipo']}{':' + e['ideia'] if e.get('ideia') else ''}] {e['texto'][:230]}"
          + (f"  ← {e['motivo'][:70]}" if e.get("motivo") else ""))
    mes = collections.Counter(((e["h"] - nav) // 24) // 30 for e in m.log if e["tipo"] in CHAVE and e["h"] >= nav)
    w("ACONTECIMENTOS DE PESO POR MÊS: " + " ".join(f"m{k + 1}:{v}" for k, v in sorted(mes.items())))
    morte = collections.Counter(p.causa for p in m.P if p.morte is not None and p.estado != "zumbi")
    w("CAUSAS: " + str(morte.most_common(8)))
    (HERE / f"enredo_{seed}.txt").write_text("\n".join(out), encoding="utf-8")
    return seed, len(out)


if __name__ == "__main__":
    seeds = [int(x) for x in sys.argv[1:]]
    with ProcessPoolExecutor() as ex:
        for seed, n in ex.map(enredo, seeds):
            print(seed, n, "linhas")
