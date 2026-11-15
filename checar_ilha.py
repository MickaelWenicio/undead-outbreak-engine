"""Procura no log de uma ilha os sinais de defeito já conhecidos, antes de ela ser usada.

uso: python checar_ilha.py SEMENTE [SEMENTE ...]
Nada aqui prova que está tudo certo; só aponta o que já deu errado antes.
"""
import collections
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import config as C
import motor
import mundo as M


def checar(seed):
    m = motor.Mundo.novo(seed)
    while not m.fim and m.h < C.DIAS_MAX * 24:
        m.passo()
    nav = m.flags["navio"]
    D = lambda h: (h - nav) // 24
    alertas = []
    log = m.log
    # 1. expedição que volta e é barrada no portão logo depois
    ex = [e for e in log if e["tipo"] == "expedicao" and e["texto"].startswith("A expedição")]
    rec = [e for e in log if e["tipo"] == "recusa"]
    barr = sum(1 for e in ex if any(0 < r["h"] - e["h"] <= 8 and r["lugar"] in M.CAPITAL for r in rec))
    if barr:
        alertas.append(f"{barr} de {len(ex)} expedições barradas num portão da capital logo depois de voltar")
    # 2. golpes no mesmo lugar com menos de GOLPE_PAUSA_DIAS
    ult = {}
    for e in log:
        if e["tipo"] == "golpe":
            if e["lugar"] in ult and e["h"] - ult[e["lugar"]] < 24 * C.GOLPE_PAUSA_DIAS:
                alertas.append(f"golpes seguidos em {m.L[e['lugar']].nome} no dia {D(e['h'])}")
            ult[e["lugar"]] = e["h"]
    # 3. cascata de mordidas escondidas (mais de 12 viradas por dentro num lugar em 24 h)
    vd = collections.defaultdict(list)
    for e in log:
        if e["tipo"] == "virou_dentro":
            vd[e["lugar"]].append(e["h"])
    for lid, hs in vd.items():
        for i in range(len(hs)):
            j = i
            while j < len(hs) and hs[j] - hs[i] < 24:
                j += 1
            if j - i > 12:
                alertas.append(f"cascata: {j - i} viradas por dentro em 24 h em {m.L[lid].nome} (dia {D(hs[i])}) — conferir a causa")
                break
    # 4. mordido pelo morto do laboratório que aparece vivo depois
    for e in log:
        if e.get("ideia") == "antidoto_acidente":
            p = m.P[e["quem"][0]]
            depois = [x for x in log if p.id in x["quem"] and x["h"] > e["h"] + 30 and x["tipo"] not in ("virou_dentro",)]
            if depois and p.causa not in (None,) and "amput" not in (p.causa or ""):
                pass
            salvo = any(x["tipo"] == "salvo" and p.id in x["quem"] for x in log)
            if depois and not salvo:
                alertas.append(f"{m.nm(p)} foi mordido no laboratório no dia {D(e['h'])} e aparece depois sem ter sido salvo")
    # 5. vivos que passaram mais de 3 dias escondidos (não deveria acontecer)
    # (o motor agora limita; checamos pelos eventos de esconderijo com gente saindo após muito tempo, se houver)
    # 6. gente viva no fim num lugar com mortos dentro
    for L in m.L.values():
        if m.H[L.id] and m.Zin[L.id]:
            alertas.append(f"no fim, {len(m.H[L.id])} vivos e {len(m.Zin[L.id])} mortos dentro de {L.nome}")
    # 6b. repetição sem aprender: o mesmo tipo de ação, no mesmo lugar, com o mesmo resultado, muitas vezes
    rep = collections.Counter()
    for e in log:
        if e["tipo"] in ("guerra", "surtida", "expedicao", "campanha") or (e["tipo"] == "ideia" and e.get("ideia") == "cacada"):
            chave = (e["tipo"], e["lugar"], e.get("resultado"), re.sub(r"\d+", "N", e["texto"])[:60])
            rep[chave] += 1
    for (t, lid, res, txt), k in rep.most_common(3):
        if k >= 6 and t in ("guerra", "campanha"):
            alertas.append(f"repetição: {k}× '{txt}…' em {m.L[lid].nome if lid in m.L else '-'}")
    # 7. textos com placeholders
    for e in log:
        if "None" in e["texto"] or re.search(r"\b0 pessoas\b", e["texto"]):
            alertas.append(f"texto estranho no dia {D(e['h'])}: {e['texto'][:90]}")
            break
    return seed, alertas


if __name__ == "__main__":
    seeds = [int(x) for x in sys.argv[1:]]
    with ProcessPoolExecutor() as ex:
        for seed, al in ex.map(checar, seeds):
            print(f"semente {seed}: " + ("nenhum sinal de defeito conhecido" if not al else f"{len(al)} alerta(s)"))
            for a in al[:12]:
                print("   -", a)
