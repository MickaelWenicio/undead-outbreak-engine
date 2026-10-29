"""Hierarquia, ordens, traição, campanhas, animais, muralhas por decisão e boatos.
Tudo como chance pelos atributos e pela situação, nunca certeza.

- O rei manda nos alcaides e nos senhores; os senhores mandam nas aldeias da sua terra.
- Ordens do rei: esvaziar aldeias, mandar grãos, entregar homens. Cada líder obedece ou nega.
- Traição e independência ficam mais prováveis com ambição, pouca lealdade, calamidade ou brecha (rei fraco,
  morto, ou sem notícia dele).
- O rei e os generais planejam campanhas contra bandos de mortos e contra traidores.
- Os mortos matam gado e cavalos: menos comida, menos transporte.
- Os líderes decidem erguer paliçada ou trocar a paliçada por muro de pedra, com custo e tempo.
- Notícia: boatos distorcidos, líder cético, mensageiro que morre na estrada.
"""
import math

import config as C
import mundo as M

VIVO = "vivo"
SEDES = ("cidadela", "penamor", "torrevelha", "valverde", "pedralva", "ribafria")


def setup(m):
    for L in m.L.values():
        if L.id == "cidadela" or L.tipo == "ilheu":
            L.suserano = None
        elif L.id in M.CAPITAL or L.id in SEDES:
            L.suserano = "cidadela"
        else:
            L.suserano = min(SEDES, key=lambda s: (math.hypot(m.L[s].x - L.x, m.L[s].y - L.y), s))
        L.gado = float(int(L.pop0 * C.GADO_POR_PESSOA.get(L.tipo, 0.1)))
        L.cavalos = float(int(L.pop0 * C.CAVALOS_POR_PESSOA.get(L.tipo, 0.03)))


def rei(m):
    return m.lider(m.L["cidadela"])


def obedece(m, ld, L, peso_situacao=0.0):
    """Chance de obedecer: lealdade ajuda, ambição atrapalha, o próprio perigo atrapalha, rei forte ajuda."""
    r = rei(m)
    forte = (r.a["carisma"] + r.a["coragem"]) / 20 if r else 0.0
    p = 0.25 + 0.07 * ld.a["lealdade"] - 0.04 * ld.a["ambicao"] + 0.2 * forte - peso_situacao
    if L.rebelde:
        p -= 0.6
    return m.r() < max(0.03, min(0.97, p))


def vassalos(m, sede):
    return [L for L in m.L.values() if L.suserano == sede and m.H[L.id] and m.lider(L) is not None]


def ordem_chega(m, L):
    """A ordem vai a cavalo. Pode não chegar: o cavaleiro some na estrada."""
    cap = m.L["cidadela"]
    if L.id in M.CAPITAL:
        return True
    if (m.flags.get("sinais") or []) and L.id in m.flags["sinais"]:
        return m.r() < 0.95
    chance = 0.85 if cap.cavalos >= 1 else 0.55
    if m.r() < chance:
        L.ultima_ordem = m.h
        return True
    if m.r() < 0.4:
        m.ev("mensageiro", "cidadela", [], f"O cavaleiro que levava a ordem do rei para {L.nome} não chega. "
             f"Ninguém sabe se ele fugiu ou se os mortos o pegaram na estrada.")
    return False


# ---------------------------------------------------------------- dia a dia
def do_dia(m):
    r = rei(m)
    capital_sabe = "mortos" in m.L["cidadela"].sabe
    if r and capital_sabe:
        ordens_do_rei(m, r)
        campanhas(m, r)
    traicoes(m)
    muralhas(m)
    animais(m)


def ordens_do_rei(m, r):
    cap = m.L["cidadela"]
    # (a) esvaziar aldeias que estão no caminho dos mortos
    if m.flags.get("ordem_esvaziar", -999) < m.h - 24 * 3:
        alvo = []
        for L in m.L.values():
            if L.tipo != "aldeia" or not m.H[L.id] or L.estado == "vazia" or m.Zin[L.id]:
                continue
            perto = sum(len(h["ids"]) for h in m.hordas if h["para"] == L.id) + \
                sum(len(m.Zin[nb]) for nb, km, t in m.adj[L.id] if km <= 9)
            if perto >= 8:
                alvo.append(L)
        if alvo and m.r() < 0.3 + 0.05 * r.a["astucia"]:
            m.flags["ordem_esvaziar"] = m.h
            for L in alvo[:4]:
                if not ordem_chega(m, L):
                    continue
                ld = m.lider(L)
                destino = L.suserano if L.suserano and m.H[L.suserano] and not m.Zin[L.suserano] else m.refugio(L.id, [ld])
                if ld is None or destino is None:
                    continue
                if obedece(m, ld, L, peso_situacao=-0.1):
                    todos = [p for p in m.vivos_em(L.id) if not p.cela]
                    m.partir_grupo(todos, L.id, destino, "fuga", motivo="ordem do rei")
                    L.estado = "vazia"
                    m.ev("ordem", L.id, [ld, r], f"Por ordem de {m.nm(r)}, {m.nm(ld)} esvazia {L.nome}: {m.pessoas(len(todos))} "
                         f"seguem para {m.L[destino].nome}.", motivo="os mortos chegando perto", n=len(todos))
                else:
                    L.recusas_rei += 1
                    idx = m.ev("recusa_ordem", L.id, [ld, r], f"{m.nm(ld)} recebe a ordem do rei para esvaziar {L.nome} e "
                               f"não obedece. Diz que ninguém vai abandonar as casas e o gado.",
                               motivo=f"lealdade {ld.a['lealdade']}, ambição {ld.a['ambicao']}")
                    m.guardar_rancor(r, ld, 15, idx, f"a ordem do rei desobedecida por {m.nm(ld)} em {L.nome}")
    # (b) mandar grãos para a capital
    dias_cap = sum(m.L[b].comida for b in sorted(M.CAPITAL)) / max(1, sum(len(m.H[b]) for b in sorted(M.CAPITAL)))
    if dias_cap < 25 and m.flags.get("ordem_graos", -999) < m.h - 24 * 7:
        cands = [L for L in m.L.values() if L.suserano and L.id not in M.CAPITAL and m.H[L.id] and m.lider(L)
                 and L.comida / max(1, len(m.H[L.id])) > 40 and not m.Zin[L.id]]
        if cands:
            m.flags["ordem_graos"] = m.h
            L = max(cands, key=lambda X: (X.comida, X.id))
            ld = m.lider(L)
            if ordem_chega(m, L):
                if obedece(m, ld, L, peso_situacao=0.15 if L.fome or m.Zout[L.id] else 0.0):
                    carga = L.comida * 0.3
                    L.comida -= carga
                    mercs = [p for p in m.vivos_em(L.id) if p.estado == VIVO and 18 <= p.idade <= 55][:6]
                    g = m.partir_grupo(mercs, L.id, "porta", "comercio", carga=carga) if mercs else None
                    m.ev("ordem", L.id, [ld, r], f"{m.nm(r)} pede grãos. {m.nm(ld)} manda {int(carga)} rações de {L.nome} para "
                         f"a capital em carroças.", motivo="a capital ficando sem comida")
                else:
                    L.recusas_rei += 1
                    idx = m.ev("recusa_ordem", L.id, [ld, r], f"{m.nm(r)} pede grãos a {L.nome}. {m.nm(ld)} manda dizer que "
                               f"o celeiro está vazio. Não está.", motivo=f"ambição {ld.a['ambicao']}, a própria fome por vir")
                    m.guardar_rancor(r, ld, 25, idx, f"os grãos negados por {m.nm(ld)} quando a capital passava fome")
    # (c) entregar homens quando a capital está cercada e com poucos armados
    armados_cap = sum(1 for b in sorted(M.CAPITAL) for i in m.H[b] if m.P[i].classe >= 2)
    cercada = sum(len(m.Zout[b]) for b in sorted(M.CAPITAL))
    if cercada > armados_cap and m.flags.get("ordem_homens", -999) < m.h - 24 * 10:
        cands = [L for L in m.L.values() if L.tipo in ("castelo", "vila") and m.H[L.id] and m.lider(L) and not m.Zin[L.id]]
        if cands:
            m.flags["ordem_homens"] = m.h
            L = m.escolhe(cands)
            ld = m.lider(L)
            if ordem_chega(m, L):
                if obedece(m, ld, L, peso_situacao=0.2 if m.Zout[L.id] else 0.0):
                    sold = [p for p in m.vivos_em(L.id) if p.classe >= 3 and p.estado == VIVO][:25]
                    if sold:
                        m.partir_grupo(sold, L.id, "porta", "soldados")
                        m.ev("ordem", L.id, [ld, r], f"{m.nm(ld)} manda {len(sold)} soldados de {L.nome} para a capital "
                             f"cercada, como o rei pediu.", motivo="a capital cercada")
                else:
                    L.recusas_rei += 1
                    idx = m.ev("recusa_ordem", L.id, [ld, r], f"O rei pede homens a {L.nome}. {m.nm(ld)} não manda nenhum.",
                               motivo="guardar os soldados para a própria defesa")
                    m.guardar_rancor(r, ld, 20, idx, f"os homens negados por {m.nm(ld)} com a capital cercada")


def traicoes(m):
    r = rei(m)
    navio = m.flags.get("navio")
    if navio is None or m.h - navio < 24 * 3:
        return        # sem crise, o reino segue em paz
    for L in sorted(m.L.values(), key=lambda x: x.id):
        if L.rebelde or L.suserano is None or L.id in M.CAPITAL or not m.H[L.id]:
            continue
        ld = m.lider(L)
        if ld is None or ld.a["ambicao"] < 7 or ld.a["lealdade"] > 5:
            continue
        sem_noticia = m.h - max(L.ultima_ordem or 0, navio) > 24 * 10
        brecha = r is None or (r.a["carisma"] + r.a["coragem"]) <= 8 or sem_noticia
        calamidade = L.fome >= 3 or bool(m.Zout[L.id]) or L.medo >= 60
        p = 0.002 + 0.01 * (ld.a["ambicao"] - 6) + 0.01 * (5 - ld.a["lealdade"]) + 0.02 * brecha + 0.015 * calamidade \
            + 0.01 * L.recusas_rei
        if m.r() < p:
            L.rebelde = True
            if r is None:
                motivo = "a morte do rei"
            elif m.motivo_de(ld, r.id):
                motivo = m.motivo_de(ld, r.id)
            elif sem_noticia:
                motivo = "dias sem nenhuma palavra da corte"
            elif calamidade:
                motivo = "a fome e o cerco, sem ajuda do rei"
            else:
                motivo = "a ambição de mandar sozinho"
            m.ev("traicao", L.id, [ld], f"{m.nm(ld)} declara que {L.nome} não responde mais ao rei. Fecha as portas também para os "
                 f"homens da coroa.", motivo=motivo)
            if r:
                m.guardar_rancor(r, ld, 40, len(m.log) - 1, f"a traição de {m.nm(ld)} em {L.nome}")


def forca(ps):
    return sum((1 + (p.classe >= 3) * 1.5 + (p.classe == 4)) * (0.7 + p.a.get("forca", 5) / 15) for p in ps)


def campanhas(m, r):
    if m.flags.get("campanha", -999) > m.h - 24 * 6:
        return
    armados = [p for b in sorted(M.CAPITAL) for p in m.vivos_em(b) if p.classe >= 2 and p.estado == VIVO and 18 <= p.idade <= 55
               and not p.holofote]
    if len(armados) < 60 or any(m.Zin[b] for b in sorted(M.CAPITAL)):
        return
    generais = [p for p in armados if p.classe >= 3 and p.a["astucia"] >= 7]
    gen = max(generais, key=lambda p: (p.a["astucia"] + p.a["coragem"], -p.id)) if generais else None
    # contra traidores
    falhas = m.flags.setdefault("falhas_cerco", {})
    largados = m.flags.setdefault("cerco_largado", {})
    rebeldes = [L for L in m.L.values() if L.rebelde and m.H[L.id] and m.km("porta", L.id) <= 35 and L.id not in largados]
    if rebeldes and gen and m.r() < 0.05 + 0.02 * (r.a["crueldade"] + r.a["ambicao"]) / 2:
        tamanho = min(len(armados) // 2, 120)

        def chances(L):
            defs_ = [p for p in m.vivos_em(L.id) if p.classe >= 2 and p.estado == VIVO]
            return (forca(armados[:tamanho]) * (1 + gen.a["astucia"] / 20)) / max(1.0, forca(defs_) * (1 + 0.5 * L.muro))
        # um general escolhe o alvo pelas chances e pelo que já perdeu ali, não pela ordem da lista
        cands = sorted(rebeldes, key=lambda L: (falhas.get(L.id, 0), -chances(L), m.km("porta", L.id), L.id))
        L = cands[0]
        insiste = 2 + (gen.a["coragem"] >= 8) + (r.a["crueldade"] >= 7) + (r.a["ambicao"] >= 8) - (gen.a["astucia"] >= 8)
        if falhas.get(L.id, 0) >= insiste:
            # depois de tantos ataques perdidos: desistir, ou negociar uma trégua (possibilidades, pelo temperamento)
            largados[L.id] = m.h
            ld = m.lider(L)
            if ld and m.r() < 0.3 + 0.04 * gen.a["astucia"] + 0.03 * ld.a["astucia"]:
                L.suserano = None
                m.ev("tregua", L.id, [gen, ld], f"Depois de {falhas[L.id]} ataques perdidos contra {L.nome}, {m.nm(gen)} manda "
                     f"um mensageiro em vez de soldados. {m.nm(ld)} aceita uma trégua: {L.nome} se governa sozinha, e a estrada "
                     f"fica aberta para os dois lados.", motivo="ataques que só custavam homens")
            else:
                m.ev("desiste", L.id, [gen], f"Depois de {falhas[L.id]} ataques perdidos contra {L.nome}, {m.nm(gen)} desiste. "
                     f"Os homens que sobraram ficam na capital.", motivo="ataques que só custavam homens")
            return
        if gen.a["astucia"] >= 7 and chances(L) < 0.8:
            return      # um general esperto não ataca um muro que não pode tomar
        m.flags["campanha"] = m.h
        ld = m.lider(L)
        ida = m.amostra(armados, tamanho)
        defs = [p for p in m.vivos_em(L.id) if p.classe >= 2 and p.estado == VIVO]
        fa = forca(ida) * (0.8 + 0.4 * m.r()) * (1 + gen.a["astucia"] / 20)
        fd = forca(defs) * (1 + 0.5 * L.muro) * (0.8 + 0.4 * m.r())
        motivo = f"a traição de {m.nm(ld)}" if ld else "a traição"
        if fa > fd:
            for p in m.amostra(defs, int(len(defs) * 0.3)):
                m.morrer(p, f"morto pelos homens do rei em {L.nome}", L.id)
            for p in m.amostra(ida, int(len(ida) * 0.1)):
                m.morrer(p, f"morto tomando {L.nome}", L.id)
            if ld and ld.estado == VIVO:
                m.morrer(ld, "enforcado por traição ao rei", L.id)
            L.rebelde = False
            L.recusas_rei = 0
            m.novo_lider(L, "o traidor foi enforcado e a coroa escolheu outro")
            falhas.pop(L.id, None)
            enf = m.g(ld, "enforcado", "enforcada") if ld else "enforcado"
            m.ev("guerra", L.id, [gen, ld], f"{m.nm(gen)} marcha com {len(ida)} homens do rei contra {L.nome}. Depois de um dia "
                 f"de luta, os portões abrem. {m.nm(ld) if ld else 'O traidor'} é {enf} na praça.", motivo=motivo,
                 resultado="tomada")
        else:
            for p in m.amostra(ida, int(len(ida) * 0.35)):
                m.morrer(p, f"morto no ataque a {L.nome}", L.id)
            falhas[L.id] = falhas.get(L.id, 0) + 1
            vez = {1: "", 2: " pela segunda vez", 3: " pela terceira vez", 4: " pela quarta vez"}.get(falhas[L.id], f" pela {falhas[L.id]}ª vez")
            m.ev("guerra", L.id, [gen, ld], f"{m.nm(gen)} ataca {L.nome}{vez} com {len(ida)} homens do rei, mas o muro e os "
                 f"defensores seguram. Um terço dos atacantes não volta.", motivo=motivo, resultado="repelido")
        return
    # contra bandos de mortos: um plano, não só força
    alvos = []
    for T in m.L.values():
        z = len(m.Zin[T.id])
        if z >= 15 and not m.H[T.id] and m.km("porta", T.id) <= 25:
            alvos.append((z, T.id))
    if alvos and gen and m.r() < 0.04 + 0.01 * gen.a["astucia"]:
        alvos.sort()
        z, tid = alvos[0]
        if z > len(armados) * 0.6:
            return
        m.flags["campanha"] = m.h
        T = m.L[tid]
        ida = m.amostra(armados, min(len(armados) // 2, 150))
        plano = m.escolhe(["atrair os mortos com fogo para um vale estreito e fechar a saída",
                           "cercar a aldeia de dia, quando eles estão parados, e entrar em formação pelos dois lados",
                           "soltar porcos amarrados como isca e esperar com as lanças atrás de carroças"])
        antes = T.formacao
        T.formacao = True
        zs = [m.P[i] for i in sorted(m.Zin[tid])]
        res = m.luta_aberta(ida, zs, T, "campanha")
        T.formacao = antes
        m.ev("campanha", tid, [gen, r], f"{m.nm(r)} manda {m.nm(gen)} limpar {T.nome} com {len(ida)} homens. O plano: {plano}. "
             f"{m.resumo_luta(res)}", motivo="os mortos acampados perto da capital",
             **{k: v for k, v in res.items() if k != "herois"})


def muralhas(m):
    for L in sorted(m.L.values(), key=lambda x: x.id):
        if not m.H[L.id] or "mortos" not in L.sabe or m.Zin[L.id]:
            continue
        ld = m.lider(L)
        if ld is None:
            continue
        vivos = [p for p in m.vivos_em(L.id) if p.estado == VIVO and 16 <= p.idade <= 60 and not p.cela]
        if L.obra_muro is None:
            alvo = 1 if L.muro == 0 else (2 if L.muro == 1 and len(vivos) >= 60 else None)
            if alvo is None or L.tipo in ("bairro", "cidadela", "ilheu"):
                continue
            ideia = ld.a["astucia"] + ld.a.get("genio", 5) + (3 if m.Zout[L.id] or L.medo >= 40 else 0)
            if m.r() < 0.02 * max(0, ideia - 9) * (0.5 if alvo == 2 else 1.0):
                custo = C.OBRA_PALICADA if alvo == 1 else C.OBRA_MURO
                L.obra_muro = {"alvo": alvo, "falta": custo, "lenha": C.OBRA_LENHA[alvo], "desde": m.h}
                m.ev("obra", L.id, [ld], f"{m.nm(ld)} manda erguer {'uma paliçada de troncos' if alvo == 1 else 'um muro de pedra no lugar da paliçada'} "
                     f"em volta de {L.nome}. Todo mundo que pode carregar trabalha.", motivo="os mortos chegando cada vez mais perto")
            continue
        o = L.obra_muro
        if m.Zout[L.id] or not m.seguro(L):
            continue
        usa_lenha = min(L.lenha, o["lenha"] * 0.1)
        L.lenha -= usa_lenha
        o["lenha"] -= usa_lenha
        o["falta"] -= len(vivos) * 1.0
        if o["falta"] <= 0 and o["lenha"] <= 1:
            L.muro = o["alvo"]
            L.portao_max = C.MURO[L.muro][0]
            L.portao_hp = L.portao_max
            dias = (m.h - o["desde"]) // 24
            L.obra_muro = None
            m.ev("obra", L.id, [ld], f"{L.nome} termina {'a paliçada' if L.muro == 1 else 'o muro de pedra'} depois de {dias} dias "
                 f"de trabalho.", motivo="a obra mandada por " + m.nm(ld))


def animais(m):
    for L in m.L.values():
        z = len(m.Zin[L.id])
        if z and (L.gado > 0 or L.cavalos > 0):
            # sem gente à vista, os mortos atacam o curral e a estrebaria
            mortos = min(L.gado, z * C.ZUMBI_MATA_ANIMAIS)
            cav = min(L.cavalos, z * C.ZUMBI_MATA_ANIMAIS * 0.3)
            L.gado -= mortos
            L.cavalos -= cav
            m.alimenta(L.id, (mortos + cav) * C.COMIDA_ANIMAL)
            if mortos >= 15 and not m.flags.get(f"gado_{L.id}"):
                m.flags[f"gado_{L.id}"] = m.h
                m.ev("animais", L.id, [], f"Em {L.nome}, os mortos invadem os currais. Bois, cabras e cavalos caem um atrás do outro. "
                     f"Quem sobreviver vai ter menos leite, menos carne e menos carroças.", n=int(mortos))
        ld = m.lider(L)
        if ld and L.fome >= 1 and L.gado >= 10 and m.H[L.id]:
            abate = L.gado * 0.25
            L.gado -= abate
            L.comida += abate * C.RACOES_POR_ANIMAL
            if not m.flags.get(f"abate_{L.id}"):
                m.flags[f"abate_{L.id}"] = m.h
                m.ev("abate", L.id, [ld], f"Com a fome apertando, {m.nm(ld)} manda abater {int(abate)} cabeças de gado em {L.nome}. "
                     f"A carne dura umas semanas; o leite acaba.", motivo=f"fome há {L.fome} dias")


# ---------------------------------------------------------------- boatos e ceticismo
def ouvir(m, L, sabe, de_quem):
    """Decide como um lugar recebe a notícia. Volta o conjunto que ele passa a saber (pode ser um boato errado)."""
    fonte_fraca = de_quem in ("Gente de passagem", "Os refugiados", "Um mercador", "Os que esperam do lado de fora",
                              "Os que ficaram do lado de fora gritam")
    ld = m.lider(L)
    if "mortos" in sabe and "mortos" not in L.sabe and fonte_fraca and ld is not None:
        L.boatos += 1
        if L.boatos == 1 and ld.a["astucia"] >= 7 and ld.a["fe"] <= 5 and m.r() < 0.5:
            m.ev("boato", L.id, [ld], f"Em {L.nome}, chega a história de mortos que andam. {m.nm(ld)} ri: diz que é conversa "
                 f"de gente assustada e manda todo mundo voltar ao trabalho.", motivo="ceticismo")
            return set()
        if m.r() < C.BOATO_DISTORCE:
            versao = "bruxaria" if ld.a["fe"] >= 7 and m.r() < 0.6 else m.escolhe(["peste", "loucos"])
            texto = {"peste": "uma peste que deixa as pessoas violentas antes de matar",
                     "bruxaria": "bruxaria: alguém lançou uma maldição sobre os mortos da costa",
                     "loucos": "um bando de loucos que morde quem encontra"}[versao]
            m.ev("boato", L.id, [ld], f"Em {L.nome}, a notícia chega torcida: dizem que é {texto}.", motivo="boato", versao=versao)
            if versao == "peste":
                L.pol["mordidos"] = "isolar"
            elif versao == "loucos":
                L.pol["mordidos"] = "isolar"
                L.pol["portao"] = "inspecao" if L.muro else L.pol["portao"]
            elif versao == "bruxaria":
                bruxas(m, L, ld)
            L.alerta = L.alerta or m.h
            return {"boato_" + versao}
    return set(sabe)


def bruxas(m, L, ld):
    """Com a notícia de maldição, um líder de muita fé procura a bruxa. Quem paga é uma mulher sem culpa."""
    cands = [p for p in m.vivos_em(L.id) if p.sexo == "f" and p.idade >= 40 and p.estado == VIVO and p.id != ld.id]
    if not cands or m.r() > 0.5:
        return
    v = m.escolhe(cands)
    m.morrer(v, "queimada como bruxa", L.id)
    idx = m.ev("bruxa", L.id, [v, ld], f"Em {L.nome}, {m.nm(ld)} manda queimar {m.nm(v)} como bruxa, culpada pela maldição. "
               f"Ela não tinha nada a ver com os mortos.", motivo="o boato de bruxaria")
    for q in m.parentes(v):
        if q.estado == VIVO and q.loc == L.id:
            m.guardar_rancor(q, ld, 60, idx, f"a fogueira de {m.relacao(q, v)}, {m.nm(v)}, acusada de bruxaria")
