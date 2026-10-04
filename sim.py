"""Linha de comando do motor (reino de Alvor).

  python sim.py init [--seed N]          cria o reino (state.json)
  python sim.py run --dias N             roda até o fim do dia N (ou até a história acabar)
  python sim.py summary                  estado atual: lugares, protagonistas, últimos acontecimentos
  python sim.py log [--de D] [--ate D] [--tipos a,b] [--todos]
  python sim.py person ID
  python sim.py ensemble [--n 100] [--dias 180]   muitas ilhas, só regras, para calibrar
  python sim.py citaveis [--n 15]        quem, fora os protagonistas, fez algo que justifica ser citado pelo nome
  python sim.py variedade [--n 100] [--dias 180]  muitas ilhas: o quanto os enredos diferem entre si
  python sim.py export caminho.json
"""
import argparse
import collections
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import config as C
import motor
import narrativa as N

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
GRANDES = {"navio", "porao", "aprende", "noticia", "decreto", "invasao", "queda", "fuga", "evacuacao", "recusa", "rei",
           "golpe", "assassinato", "seita", "palicada", "surtida", "acampamento", "aprendem", "fim", "lider", "reforco",
           "portao_abre", "emboscada", "virou_dentro", "execucao", "racao", "roubo", "rei_morre", "traicao", "guerra",
           "campanha", "bruxa", "ideia", "reduto", "reduto_cai", "reduto_sai", "cheiro", "formacao", "ordem", "recusa_ordem", "obra", "tregua", "desiste", "colonia_chega", "apodrece"}


def carregar():
    return motor.Mundo.carregar(STATE)


def cmd_init(a):
    m = motor.Mundo.novo(a.seed)
    m.salvar(STATE)
    print(f"reino criado (seed {a.seed}): {sum(len(s) for s in m.H.values())} pessoas em {len(m.L)} lugares")
    print(f"  temperamento: {', '.join(N.temperamento(m)) or 'sem traço forte'}")
    for f in m.holofote:
        p = m.P[f["id"]]
        print(f"  protagonista: {m.nm(p)} · {int(p.idade)} anos · {p.papel} · {m.L[p.loc].nome} ({f['papel']})")


def rodar_ate(m, ate_h):
    while not m.fim and m.h < ate_h:
        m.passo()


def cmd_run(a):
    m = carregar()
    t = time.time()
    rodar_ate(m, a.dias * 24)
    m.salvar(STATE)
    s = m.serie[-1]
    print(f"{m.quando()} · vivos {s['vivos']} · mordidos {s['mordidos']} · mortos-vivos {s['zumbis']} · "
          f"fim={m.fim} · {time.time() - t:.1f}s")


def cmd_summary(a):
    m = carregar()
    s = m.serie[-1] if m.serie else {"vivos": 0, "mordidos": 0, "zumbis": 0}
    print(f"== {m.quando()} · {m.estacao()} · vivos {s['vivos']} · mordidos {s['mordidos']} · mortos-vivos {s['zumbis']} "
          f"· nível dos mortos {m.nivel} · fim={m.fim}")
    print("LUGARES (vivos · fora do muro · mortos dentro/fora · muro/portão · comida em dias · medo · líder · sabe)")
    for L in m.L.values():
        v, zi, zo, fo = len(m.H[L.id]), len(m.Zin[L.id]), len(m.Zout[L.id]), len(m.Fora[L.id])
        if not (v or zi or zo or fo):
            continue
        ld = m.lider(L)
        print(f"  {L.id:11s} {L.estado:9s} vivos {v:5d} fora {fo:3d} mortos {zi:4d}/{zo:4d} muro {L.muro}/{max(0, L.portao_hp):5.0f} "
              f"comida {L.comida / max(1, v):5.1f}d medo {L.medo:3.0f} {m.nm(ld) if ld else '-':28s} {','.join(sorted(L.sabe))}")
    if m.hordas:
        print("BANDOS NA ESTRADA:", ", ".join(f"{len(h['ids'])} {h['de']}→{h['para']}{' (parado)' if h.get('parada') else ''}"
                                             for h in m.hordas if h["ids"]))
    if m.grupos:
        c = collections.Counter(g["tipo"] for g in m.grupos)
        print("GENTE NA ESTRADA:", dict(c), sum(len(g["m"]) for g in m.grupos), "pessoas")
    print(f"TEMPERAMENTO DO REINO: {', '.join(N.temperamento(m)) or 'sem traço forte'}")
    print("PROTAGONISTAS")
    for f in m.holofote:
        p = m.P[f["id"]]
        print(f"  {m.nm(p):34s} {int(p.idade):3d} anos · {p.papel:10s} · {p.estado:8s} · {p.loc or 'estrada'} · "
              f"{f['papel']}" + (f" · até {m.quando(f['ate'])}" if 'ate' in f else ""))
    cit = N.citaveis(m, 8)
    if cit:
        print("PODEM SER CITADOS PELO NOME (fora os protagonistas; o resto do log vira papel e lugar)")
        for c in cit:
            print(f"  {c['nome']:34s} {c['pontos']:3d} pts · {c['quem_e']}")
    print("CONTAS", dict(m.contas))
    print("ÚLTIMOS ACONTECIMENTOS")
    for e in [e for e in m.log if e["tipo"] in GRANDES][-15:]:
        print(f"  {m.quando(e['h']):14s} [{e['tipo']}] {e['texto'][:200]}" + (f"  ← {e['motivo'][:90]}" if e.get("motivo") else ""))


def cmd_log(a):
    m = carregar()
    tipos = set(a.tipos.split(",")) if a.tipos else None
    for e in m.log:
        d = e["h"] // 24 + 1
        if d < a.de or d > a.ate:
            continue
        if tipos and e["tipo"] not in tipos:
            continue
        if not a.todos and not tipos and e["tipo"] not in GRANDES:
            continue
        print(f"{m.quando(e['h']):14s} [{e['tipo']}] {e['texto']}" + (f"\n{'':16s}motivo: {e['motivo']}" if e.get("motivo") else ""))


def cmd_person(a):
    m = carregar()
    p = m.P[a.pid]
    print(f"{p.id} {m.nm(p)} · {p.sexo} · {p.idade:.0f} anos · {p.papel} · classe {p.classe} · {p.estado}"
          + (f" ({p.causa}, {m.quando(p.morte)})" if p.morte is not None else ""))
    print(f"  em {p.loc} · casa {p.casa} · atributos {p.a} · fama {p.fama} · opinião do líder {p.op:.0f}")
    for q in m.parentes(p):
        print(f"  {m.relacao(p, q)}: {m.nm(q)} ({q.estado})")
    for r in p.rancor:
        print(f"  rancor de {m.nm(m.P[r[0]])}: {r[1]} · {r[3] or ''}")
    for e in m.log:
        if p.id in e["quem"]:
            print(f"  {m.quando(e['h']):14s} [{e['tipo']}] {e['texto'][:220]}")


def cmd_citaveis(a):
    m = carregar()
    print("Fora os protagonistas, só estes fizeram algo que justifica ser citado pelo nome. Os outros nomes do log")
    print("servem para rastrear; no relato, viram papel e lugar (\"um pescador de Lontras\").")
    for c in N.citaveis(m, a.n):
        print()
        print(f"{c['nome']} · {c['pontos']} pts · {c['quem_e']}")
        for f in c["feitos"]:
            print(f"  {f['quando']:14s} [{f['tipo']}] {f['texto'][:230]}")


def formato_ilha(args):
    seed, dias = args
    m = motor.Mundo.novo(seed)
    rodar_ate(m, dias * 24)
    f = N.formato(m)
    f["seed"] = seed
    return f


def cmd_variedade(a):
    t = time.time()
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(formato_ilha, [(s, a.dias) for s in range(a.de, a.de + a.n)]))
    (HERE / "variedade.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(res)
    print(f"{n} ilhas, {a.dias} dias ({time.time() - t:.0f}s)")
    print(" fins:", dict(collections.Counter(x["fim"] for x in res)))
    for fim in ("vitoria", "derrota"):
        ds = sorted(x["dia_fim"] for x in res if x["fim"] == fim)
        if ds:
            print(f"  dia da {fim} depois do navio: quartis {ds[len(ds) // 4]} / {ds[len(ds) // 2]} / {ds[3 * len(ds) // 4]}"
                  f" (de {ds[0]} a {ds[-1]})")
    freq = collections.Counter(fi for x in res for fi in x["fichas"])
    print(" com que frequência cada marco aparece (marco em quase todas ou em quase nenhuma não dá variedade):")
    for fi, k in sorted(freq.items()):
        print(f"   {fi:28s} {100 * k / n:4.0f}%")
    sets = [set(x["fichas"]) for x in res]
    jac = lambda A, B: 1 - len(A & B) / max(1, len(A | B))
    dist = [jac(sets[i], sets[j]) for i in range(n) for j in range(i + 1, n)]
    viz = [min(jac(sets[i], sets[j]) for j in range(n) if j != i) for i in range(n)]
    print(f" distância entre enredos (0 = iguais, 1 = nada em comum): média {statistics.mean(dist):.2f} · "
          f"vizinho mais parecido, mediana {statistics.median(viz):.2f} · gêmeas exatas {sum(1 for v in viz if v == 0)}")
    forma = collections.Counter(
        (x["fim"], next(fi for fi in x["fichas"] if fi.startswith("perda:")), "cidadela" if "cai:cidadela" in x["fichas"] else "-",
         "intriga" if any(fi in x["fichas"] for fi in ("ev:traicao", "ev:golpe", "ev:guerra", "ev:assassinato")) else "-")
        for x in res)
    print(f" formas grossas (fim, perda, cidadela, intriga): {len(forma)} diferentes; as mais comuns:")
    for k, v in forma.most_common(8):
        print(f"   {v:3d}  {' · '.join(k)}")
    curtas = sum(1 for x in res if x["fim"] == "vitoria" and x["dia_fim"] <= 20 and x["perda"] < 0.1)
    print(f" ilhas curtas demais (vitória até o dia 20 com menos de 10% de perda): {curtas}")
    print(" quando a história acontece (acontecimentos de peso e quedas, por fase em dias depois do navio):")
    for fa in ("0-7", "8-14", "15-30", "31-60", "61-120", "121-fim"):
        ks = sorted(x["ritmo"].get(fa, 0) for x in res)
        print(f"   dias {fa:8s} mediana {ks[n // 2]:3d} · quartil de cima {ks[3 * n // 4]:3d} · "
              f"ilhas com algo {100 * sum(1 for k in ks if k) / n:3.0f}%")
    hz = [x for x in res if x["fim"] == "horizonte"]
    if hz:
        print(f" nas {len(hz)} ilhas que chegam aos 6 meses:")
        for d in (14, 30, 60, 120, 180):
            v = sorted(x["vivos"][str(d)] if str(d) in x["vivos"] else x["vivos"][d] for x in hz)
            print(f"   vivos no dia {d:3d}: quartis {v[len(v) // 4]} / {v[len(v) // 2]} / {v[3 * len(v) // 4]}")


def uma_ilha(args):
    seed, dias = args
    m = motor.Mundo.novo(seed)
    rodar_ate(m, dias * 24)
    pop0 = m.serie[0]["vivos"] if m.serie else 0
    zs = [x["zumbis"] for x in m.serie]
    pico = max(zs) if zs else 0
    hp = zs.index(pico) if zs else 0
    quedas = [e for e in m.log if e["tipo"] == "queda"]
    invasoes = [e for e in m.log if e["tipo"] == "invasao"]
    navio = m.flags.get("navio", 0)
    sem_zumbi = sum(1 for x in m.serie if x["h"] > navio + 72 and x["zumbis"] == 0)
    contagio_saiu = any(e["lugar"] != "lontras" for e in quedas + invasoes) or \
        any(x["zumbis"] for x in m.serie if False)
    lugares_tocados = {e["lugar"] for e in m.log if e["tipo"] in ("ataque", "invasao", "queda") and e["lugar"]}
    cap_caiu = any(e["lugar"] in ("porta", "cais", "mercado", "alto") and e["tipo"] in ("queda",) for e in m.log)
    cid_caiu = any(e["lugar"] == "cidadela" and e["tipo"] == "queda" for e in m.log)
    cap_invadida = any(e["lugar"] in ("porta", "cais", "mercado", "alto", "cidadela") and e["tipo"] in ("invasao", "ataque")
                       for e in m.log)
    c = collections.Counter(e["tipo"] for e in m.log)
    s = m.serie[-1]

    def no_dia(d, k):
        i = d * 24
        if i < len(m.serie):
            return m.serie[i][k]
        return s[k] if m.fim == "derrota" or k == "vivos" else 0
    return {"seed": seed, "fim": m.fim or "aberto", "h": m.h, "vivos": s["vivos"], "zumbis": s["zumbis"], "pop0": pop0,
            "pico": pico, "pico_dia": hp // 24 + 1, "quedas": len(quedas),
            "quedas_semana": sum(1 for e in quedas if e["h"] - navio <= 7 * 24),
            "lugares_tocados": len(lugares_tocados), "saiu_da_origem": len(lugares_tocados - {"lontras"}) > 0,
            "cap_ameacada": cap_invadida or any(e["tipo"] == "acampamento" for e in m.log if e["lugar"] in ("porta", "cais")),
            "cap_caiu": cap_caiu, "cidadela_caiu": cid_caiu, "horas_sem_zumbi": sem_zumbi,
            "golpes": c["golpe"], "assassinatos": c["assassinato"], "recusas": c["recusa"], "seitas": c["seita"],
            "mortos": m.contas["mortos"], "mordidos": m.contas["mordidos"],
            **{f"vivos_d{d}": no_dia(d, "vivos") for d in (14, 30, 60, 120)},
            **{f"zumbis_d{d}": no_dia(d, "zumbis") for d in (14, 30, 60, 120)}}


def cmd_ensemble(a):
    t = time.time()
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(uma_ilha, [(s, a.dias) for s in range(1, a.n + 1)]))
    (HERE / "ensemble.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(res)
    pct = lambda k: 100 * sum(1 for x in res if x[k]) / n
    print(f"{n} ilhas, {a.dias} dias, só regras ({time.time() - t:.0f}s)")
    print(" fins:", dict(collections.Counter(x["fim"] for x in res)))
    print(f" saiu da origem: {pct('saiu_da_origem'):.0f}% · 2+ quedas na 1ª semana: "
          f"{100 * sum(1 for x in res if x['quedas_semana'] >= 2) / n:.0f}%")
    picos = [x["pico"] / x["pop0"] for x in res]
    print(f" pico de mortos-vivos / população: mediana {statistics.median(picos):.0%} (de {min(picos):.0%} a {max(picos):.0%}) "
          f"· dia do pico mediano {statistics.median(x['pico_dia'] for x in res)}")
    perdas = [1 - x["vivos"] / x["pop0"] for x in res]
    print(f" perdidos no fim: mediana {statistics.median(perdas):.0%} · capital ameaçada {pct('cap_ameacada'):.0f}% · "
          f"um bairro da capital caiu {pct('cap_caiu'):.0f}% · cidadela caiu {pct('cidadela_caiu'):.0f}%")
    print(f" horas sem nenhum morto-vivo depois do 3º dia: mediana {statistics.median(x['horas_sem_zumbi'] for x in res)}")
    for d in (14, 30, 60, 120):
        v = sorted(x[f"vivos_d{d}"] / x["pop0"] for x in res)
        z = sorted(x[f"zumbis_d{d}"] for x in res)
        print(f" dia {d:3d}: vivos (quartis) {v[len(v) // 4]:.0%} / {v[len(v) // 2]:.0%} / {v[3 * len(v) // 4]:.0%} · "
              f"mortos-vivos (quartis) {z[len(z) // 4]} / {z[len(z) // 2]} / {z[3 * len(z) // 4]}")
    print(f" golpes {statistics.mean(x['golpes'] for x in res):.1f} · assassinatos {statistics.mean(x['assassinatos'] for x in res):.1f}"
          f" · recusas no portão {statistics.mean(x['recusas'] for x in res):.1f} · seitas {statistics.mean(x['seitas'] for x in res):.1f}")


def cmd_export(a):
    m = carregar()
    Path(a.path).write_text(json.dumps({"meta": {"seed": m.seed, "h": m.h, "fim": m.fim}, "eventos": m.log, "serie": m.serie,
                                        "holofote": m.holofote, "diario": m.diario,
                                        "citaveis": N.citaveis(m, 30), "formato": N.formato(m)}, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--seed", type=int, default=C.SEED); s.set_defaults(f=cmd_init)
    s = sub.add_parser("run"); s.add_argument("--dias", type=int, required=True); s.set_defaults(f=cmd_run)
    s = sub.add_parser("summary"); s.set_defaults(f=cmd_summary)
    s = sub.add_parser("log"); s.add_argument("--de", type=int, default=1); s.add_argument("--ate", type=int, default=9999)
    s.add_argument("--tipos"); s.add_argument("--todos", action="store_true"); s.set_defaults(f=cmd_log)
    s = sub.add_parser("person"); s.add_argument("pid", type=int); s.set_defaults(f=cmd_person)
    s = sub.add_parser("ensemble"); s.add_argument("--n", type=int, default=100); s.add_argument("--dias", type=int, default=C.DIAS_MAX)
    s.set_defaults(f=cmd_ensemble)
    s = sub.add_parser("export"); s.add_argument("path"); s.set_defaults(f=cmd_export)
    s = sub.add_parser("citaveis"); s.add_argument("--n", type=int, default=15); s.set_defaults(f=cmd_citaveis)
    s = sub.add_parser("variedade"); s.add_argument("--n", type=int, default=100); s.add_argument("--de", type=int, default=1)
    s.add_argument("--dias", type=int, default=C.DIAS_MAX); s.set_defaults(f=cmd_variedade)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
