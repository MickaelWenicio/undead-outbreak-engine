"""Leitura do log para contar a história: quem merece ser citado pelo nome e qual é o "formato" do enredo de uma ilha.

Regra de leitura: os protagonistas aparecem mais. Fora deles, só ganha nome quem fez algo que mudou a história
(a estratégia de um general, o estudo da cura, a traição, o golpe, o último reduto). Quem só morreu, só foi
mordido ou só estava no caminho fica como papel e lugar ("um pescador de Lontras"), nunca pelo nome.

O motor continua pondo nomes no log, porque eles servem para rastrear as pessoas. Quem decide se o nome vai
para o relato é este arquivo.
"""
import collections

# peso por tipo de acontecimento: (o primeiro de "quem", que costuma ser quem agiu; os demais)
PESO = {
    "traicao": (8, 0), "golpe": (8, 3), "guerra": (7, 4), "campanha": (7, 0), "seita": (6, 0), "reduto": (6, 0),
    "surtida": (6, 0), "assassinato": (5, 5), "recusa_ordem": (5, 0), "formacao": (5, 0), "cheiro": (5, 0),
    "portao_abre": (5, 0), "recusa": (4, 0), "reforco_portao": (4, 0), "evacuacao": (4, 0), "rei": (3, 1),
    "bruxa": (3, 3), "rei_morre": (3, 0), "tregua": (6, 5), "desiste": (4, 0), "escora": (3, 0), "lider": (3, 0), "decreto": (2, 0), "obra": (2, 0), "palicada": (2, 0),
    "boato": (2, 0), "salvo": (2, 0), "execucao": (1, 2), "racao": (1, 0), "expedicao": (1, 0), "abate": (1, 0),
    "reforco": (1, 0), "ordem": (1, 0), "roubo": (1, 0),
}
# as ideias pesam conforme o tamanho do que mudam
PESO_IDEIA = {"cura": 10, "campos": 6, "cacada": 6, "isca": 6, "corredor": 6, "fogo": 5, "antidoto_acidente": 3, "antidoto_falha": 2}
PESO_IDEIA_PADRAO = 4
CORTE = 6          # abaixo disso, a pessoa não fez nada que justifique o nome


def peso_evento(e, pos):
    if e["tipo"] == "ideia":
        p = PESO_IDEIA.get(e.get("ideia"), PESO_IDEIA_PADRAO)
        return p if pos == 0 else 0
    a, b = PESO.get(e["tipo"], (0, 0))
    return a if pos == 0 else b


def pontos(log):
    """pontos[pid] = soma dos pesos; feitos[pid] = lista (peso, evento) dos acontecimentos que pesaram."""
    pts = collections.Counter()
    feitos = collections.defaultdict(list)
    vezes = collections.Counter()
    for e in log:
        for pos, pid in enumerate(e["quem"]):
            w = peso_evento(e, pos)
            if not w:
                continue
            # repetir a mesma coisa não faz de ninguém mais importante: a primeira vez vale tudo, as outras pouco
            k = (pid, e["tipo"], e.get("ideia"), pos)
            vezes[k] += 1
            if vezes[k] == 1:
                pts[pid] += w
                feitos[pid].append((w, e))
            elif vezes[k] <= 4:
                pts[pid] += 1
    return pts, feitos


def quem_e(m, p):
    casa = m.L[p.casa].nome if p.casa in m.L else "?"
    vivo = "vivo" if p.morte is None else f"{p.causa or 'morto'} no {m.quando(p.morte)}"
    return f"{int(p.idade)} anos, {p.papel}, de {casa} ({vivo})"


def citaveis(m, n=15):
    """Fora os protagonistas, as pessoas que fizeram algo que mudou a história, em ordem de peso."""
    prot = {f["id"] for f in m.holofote}
    pts, feitos = pontos(m.log)
    lista = []
    for pid, v in pts.most_common():
        if pid in prot or v < CORTE:
            continue
        p = m.P[pid]
        top = sorted(feitos[pid], key=lambda x: (-x[0], x[1]["h"]))[:3]
        lista.append({"id": pid, "nome": m.nm(p), "pontos": v, "quem_e": quem_e(m, p),
                      "feitos": [{"quando": m.quando(e["h"]), "tipo": e["tipo"], "texto": e["texto"]} for _, e in top]})
        if len(lista) >= n:
            break
    return lista


# ---------------------------------------------------------------- temperamento do reino, em palavras
TRACOS = {"fe": ("devoto", "descrente"), "genio": ("engenhoso", "de pouca invenção"), "astucia": ("astuto", "ingênuo"),
          "coragem": ("valente", "medroso"), "lealdade": ("leal à coroa", "de lealdade frouxa"),
          "ambicao": ("ambicioso", "acomodado"), "crueldade": ("duro", "brando"), "piedade": ("piedoso", "de pouca piedade")}


def temperamento(m, corte=0.8):
    """Os traços que se destacam no reino sorteado, do mais forte ao mais fraco. Ex.: ['devoto', 'leal à coroa']."""
    cult = m.flags.get("cultura", {})
    fortes = sorted(((abs(v), k, v) for k, v in cult.items() if abs(v) >= corte), reverse=True)
    return [TRACOS[k][0 if v > 0 else 1] for _, k, v in fortes if k in TRACOS]


# ---------------------------------------------------------------- formato do enredo (para medir variedade)
CAPITAL = {"cidadela", "alto", "mercado", "porta", "cais"}


def formato(m):
    """Os marcos de uma ilha, em fichas comparáveis entre ilhas."""
    navio = m.flags.get("navio", 0)
    c = collections.Counter(e["tipo"] for e in m.log)
    ideias = collections.Counter(e.get("ideia") for e in m.log if e["tipo"] == "ideia")
    quedas = [e for e in m.log if e["tipo"] == "queda"]
    caidos = {e["lugar"] for e in quedas}
    tipo_de = {L.id: L.tipo for L in m.L.values()}
    fichas = set()
    # como termina e quando
    fim = m.fim or "aberto"
    dia_fim = (m.h - navio) // 24
    fichas.add(f"fim:{fim}")
    if fim == "vitoria":
        fichas.add("vitoria:" + ("cedo" if dia_fim <= 20 else "media" if dia_fim <= 60 else "tarde"))
    # tamanho do estrago
    s0 = m.serie[0]["vivos"] if m.serie else 1
    perda = 1 - (m.serie[-1]["vivos"] if m.serie else 0) / s0
    fichas.add("perda:" + ("pouca" if perda < 0.25 else "metade" if perda < 0.6 else "grande" if perda < 0.95 else "quase_toda"))
    # o que caiu
    if "cidadela" in caidos:
        fichas.add("cai:cidadela")
    if caidos & (CAPITAL - {"cidadela"}):
        fichas.add("cai:bairro_capital")
    for t in ("castelo", "vila", "mosteiro", "mina"):
        if any(tipo_de.get(l) == t for l in caidos):
            fichas.add(f"cai:{t}")
    n_aldeias = sum(1 for l in caidos if tipo_de.get(l) == "aldeia")
    fichas.add("aldeias_caidas:" + ("0" if n_aldeias == 0 else "1-3" if n_aldeias <= 3 else "4-9" if n_aldeias <= 9 else "10+"))
    # intriga, política e ideias
    for t in ("traicao", "golpe", "assassinato", "guerra", "campanha", "seita", "bruxa", "surtida", "reduto", "formacao",
              "portao_abre", "recusa_ordem", "cheiro", "evacuacao", "obra"):
        if c[t]:
            fichas.add(f"ev:{t}")
    for i in ideias:
        if i:
            fichas.add(f"ideia:{i}")
    if c["fome"]:
        fichas.add("fome")
    if any(e["tipo"] == "rei_morre" or (e["tipo"] == "rei" and "herda a coroa" in e["texto"]) for e in m.log):
        fichas.add("rei_morre")
    vivos_prot = sum(1 for f in m.holofote if m.P[f["id"]].morte is None)
    fichas.add(f"protagonistas_vivos:{min(vivos_prot, 3)}{'+' if vivos_prot >= 3 else ''}")
    # quando a história acontece: acontecimentos de peso e quedas por fase (dias contados do navio)
    fases = ((0, 7), (8, 14), (15, 30), (31, 60), (61, 120), (121, 9999))
    def fase(h):
        d = (h - navio) // 24
        return next(f"{a}-{b if b < 9999 else 'fim'}" for a, b in fases if a <= d <= b)
    ritmo = collections.Counter()
    for e in m.log:
        if e["h"] < navio:
            continue
        w = peso_evento(e, 0) if e["quem"] else 0
        if w >= 4 or e["tipo"] in ("queda", "invasao", "fim"):
            ritmo[fase(e["h"])] += 1
    vivos_em = {}
    for d in (7, 14, 30, 60, 120, 180):
        i = navio + d * 24
        vivos_em[d] = m.serie[i]["vivos"] if i < len(m.serie) else (m.serie[-1]["vivos"] if m.serie else 0)
    return {"fichas": sorted(fichas), "fim": fim, "dia_fim": dia_fim, "perda": round(perda, 3),
            "caidos": sorted(caidos), "ideias": dict(ideias), "contas_ev": {k: c[k] for k in PESO if c[k]},
            "ritmo": dict(ritmo), "vivos": vivos_em, "pop0": s0, "temperamento": temperamento(m),
            "cultura": m.flags.get("cultura", {})}
