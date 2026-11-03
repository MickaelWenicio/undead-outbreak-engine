"""Ideias engenhosas dos vivos: quem tem o atributo certo PODE ter uma ideia, com chance,
e a ideia pode dar certo, dar errado ou custar vidas. Nada aqui é garantido.

Chamado pelo motor: do_dia(m) uma vez por dia e no_cerco(m, L, armados) a cada hora de cerco.
Cada ideia fica registrada em L.ideias (o que o lugar aprendeu a fazer) e no log, com quem teve a ideia.
"""
import config as C

VIVO = "vivo"


def gen(p):
    return p.a.get("genio", 5)


def ast(p):
    return p.a["astucia"]


def quem(m, L, cond, idade=(16, 75)):
    return [p for p in m.vivos_em(L.id) if p.estado == VIVO and idade[0] <= p.idade <= idade[1] and not p.cela and cond(p)]


def melhor(ps, chave):
    return max(ps, key=lambda p: (chave(p), -p.id)) if ps else None


def registra(m, L, ideia, p, texto, motivo, **dados):
    if ideia not in L.ideias:
        L.ideias.append(ideia)
    return m.ev("ideia", L.id, [p], texto, motivo=motivo, ideia=ideia, **dados)


# ---------------------------------------------------------------- todo dia
def do_dia(m):
    for L in sorted(m.L.values(), key=lambda x: x.id):
        if not m.H[L.id] or "mortos" not in L.sabe:
            continue
        dias_comida = L.comida / max(1, len(m.H[L.id]))
        cercado = bool(m.Zout[L.id]) or bool(m.Zin[L.id])
        ld = m.lider(L)
        # --- fosso com estacas em volta do muro (engenheiro ou carpinteiro esperto, sem cerco, com lenha)
        if L.muro >= 1 and "fosso" not in L.ideias and not cercado and L.lenha >= 200:
            c = quem(m, L, lambda p: gen(p) >= 8 or (ast(p) >= 8 and gen(p) >= 6))
            if c and m.r() < C.IDEIA["fosso"]:
                p = melhor(c, gen)
                L.lenha -= 200
                registra(m, L, "fosso", p, f"Em {L.nome}, {m.nm(p)} convence o povo a cavar um fosso em volta do muro e "
                         f"enterrar estacas pontudas no fundo. Os mortos não desviam de nada.", "os mortos não têm medo de cair")
        # --- fogueiras de sinal entre as fortalezas (rei ou senhor esperto)
        if not m.flags.get("sinais") and L.tipo in ("cidadela", "castelo", "vila") and ld and ast(ld) >= 7:
            if m.r() < C.IDEIA["sinais"]:
                rede = [X.id for X in m.L.values() if X.tipo in ("cidadela", "castelo", "vila", "bairro", "mosteiro")
                        and m.H[X.id]]
                m.flags["sinais"] = rede
                registra(m, L, "sinais", ld, f"Em {L.nome}, {m.nm(ld)} manda erguer fogueiras de sinal nos morros entre as fortalezas. "
                         f"Quando os mortos aparecerem em uma, as outras vão ver a fumaça no mesmo dia.",
                         "as notícias chegavam tarde demais", rede=len(rede))
        # --- reorganizar a comida: cozinha comunitária, contagem do celeiro, ração igual para todos
        if "reorganiza" not in L.ideias and ld and dias_comida < 15 and (ast(ld) >= 7 and ld.a["carisma"] >= 6 or gen(ld) >= 8):
            if m.r() < C.IDEIA["reorganiza"]:
                alvos = [X for X in m.cidade(L)] if L.id in ("cidadela",) else [L]
                for X in alvos:
                    if "reorganiza" not in X.ideias:
                        X.ideias.append("reorganiza")
                registra(m, L, "reorganiza", ld, f"Em {L.nome}, {m.nm(ld)} manda contar cada saco do celeiro e abre cozinhas comunitárias: "
                         f"todo mundo come a mesma sopa, do soldado à família de quem manda. "
                         + ("A ordem vale para a capital inteira." if len(alvos) > 1 else ""),
                         "a comida acabando e o povo desconfiado de quem come mais")
        # --- hortas dentro do muro
        if L.muro >= 1 and "hortas" not in L.ideias and dias_comida < 40:
            c = quem(m, L, lambda p: p.papel in ("campones", "pastor") and gen(p) >= 7)
            if c and m.r() < C.IDEIA["hortas"]:
                p = melhor(c, gen)
                registra(m, L, "hortas", p, f"Em {L.nome}, {m.nm(p)} começa a plantar couves e nabos nos pátios e quintais, "
                         f"dentro do muro. Os outros copiam.", "não dá mais para sair para o campo")
        # --- pesca pelo mar quando a terra está cercada
        if L.litoral and "pesca_mar" not in L.ideias and cercado:
            c = quem(m, L, lambda p: p.papel == "pescador" and (gen(p) >= 6 or ast(p) >= 7))
            if c and m.r() < C.IDEIA["pesca_mar"]:
                p = melhor(c, ast)
                registra(m, L, "pesca_mar", p, f"Com a terra cercada, {m.nm(p)} leva os barcos para pescar longe da praia. "
                         f"Os mortos ficam na areia, olhando.", "os mortos não entram no mar")
        # --- cães farejadores no portão
        if L.muro >= 1 and "caes" not in L.ideias and L.pol["portao"] in ("inspecao", "quarentena"):
            c = quem(m, L, lambda p: p.papel in ("cacador", "pastor") and (gen(p) >= 7 or ast(p) >= 7))
            if c and m.r() < C.IDEIA["caes"]:
                p = melhor(c, ast)
                registra(m, L, "caes", p, f"Em {L.nome}, {m.nm(p)} repara que os cães rosnam para quem foi mordido, "
                         f"mesmo com a ferida escondida. Os cães passam a ficar no portão.", "mordidas escondidas entrando")
        # --- amputação na primeira hora
        if "amputacao" not in L.sabe and L.lutas >= 3:
            c = quem(m, L, lambda p: p.papel in ("monge", "clerigo", "ferreiro", "criado", "idoso") and gen(p) >= 8)
            if c and m.r() < C.IDEIA["amputacao"]:
                p = melhor(c, gen)
                L.sabe.add("amputacao")
                registra(m, L, "amputacao", p, f"Em {L.nome}, {m.nm(p)} corta o braço de um mordido logo depois da mordida e "
                         f"queima o corte. Ele não vira. Daí em diante, quem é mordido na mão ou no braço tem uma chance.",
                         "ver gente boa virar sem poder fazer nada")
        # --- antídoto: um gênio começa a estudar; pode dar certo, dar errado ou soltar um morto no laboratório
        if L.pesquisa is None and "cura" not in L.sabe and L.tipo in ("cidadela", "castelo", "mosteiro", "vila", "bairro"):
            c = quem(m, L, lambda p: gen(p) >= 9 and ast(p) >= 6)
            if c and m.r() < C.IDEIA["antidoto"]:
                p = melhor(c, gen)
                L.pesquisa = {"quem": p.id, "prog": 0.0, "tentativas": 0}
                registra(m, L, "antidoto", p, f"Em {L.nome}, {m.nm(p)} pede um morto preso a correntes e começa a estudar o que "
                         f"corre no sangue deles. Quer achar um remédio para a mordida.", "a esperança de uma cura")
        if L.pesquisa:
            pesquisa(m, L)
        # --- mercado negro: a esperteza sem escrúpulo
        if "mercado_negro" not in L.ideias and dias_comida < 10:
            c = quem(m, L, lambda p: p.papel == "mercador" and ast(p) >= 8 and p.a["piedade"] <= 4)
            if c and m.r() < C.IDEIA["mercado_negro"]:
                p = melhor(c, ast)
                desvio = L.comida * 0.15
                L.comida -= desvio
                idx = registra(m, L, "mercado_negro", p, f"Em {L.nome}, {m.nm(p)} esconde sacos de grão no porão e vende pão "
                               f"a preço de ouro a quem ainda tem moedas. O povo descobre.", "lucro com a fome")
                for q in m.adultos(L.id):
                    if q.id != p.id and q.a["piedade"] >= 5:
                        m.guardar_rancor(q, p, 20, idx, f"o pão vendido a preço de ouro por {m.nm(p)} com a vila passando fome")
        # --- fuga pelo mar para o ilhéu, onde os mortos não chegam
        ilheu_ok = "ilheu" in m.L and not m.Zin["ilheu"] and m.L["ilheu"].estado != "caida"   # os barqueiros veem a praia
        if L.litoral and ilheu_ok and L.id != "ilheu" and (cercado or dias_comida < 5):
            c = quem(m, L, lambda p: p.papel == "pescador" and (gen(p) >= 6 or ast(p) >= 6))
            if c and m.r() < C.IDEIA["barcos"]:
                p = melhor(c, ast)
                vivos = [q for q in m.vivos_em(L.id) if q.estado in ("vivo", "mordido") and not q.cela]
                vao = m.amostra(vivos, min(len(vivos), int(m.rng.integers(15, 45))))
                if vao and p not in vao:
                    vao[0] = p
                if vao:
                    m.embarcar(L, vao)
                    registra(m, L, "barcos", p, f"De madrugada, {m.nm(p)} leva {m.pessoas(len(vao))} de barco de {L.nome} para "
                             f"o Ilhéu das Gaivotas. Os mortos não nadam.", "a terra tomada pelos mortos", n=len(vao))
        # --- campos de fora: com fome e o arredor limpo há dias, mandar o povo da cidade lavrar fora dos muros
        if L.tipo in ("bairro", "cidadela", "vila", "castelo") and "campos" not in L.ideias and ld and not cercado                 and (L.fome >= 2 or dias_comida < 10) and m.seguro(L) and m.flags.get("navio") is not None:
            perto = sum(len(m.Zin[T.id]) + len(m.Zout[T.id]) for T in m.L.values() if m.km(L.id, T.id) <= 12)
            if perto <= 3 and (ast(ld) >= 6 or gen(ld) >= 7 or L.fome >= 10) and m.r() < C.IDEIA["campos"]:
                registra(m, L, "campos", ld, f"Em {L.nome}, {m.nm(ld)} manda abrir os portões de dia: quem tem braço vai lavrar e "
                         f"semear os campos de fora, com guardas nos morros, e volta antes de escurecer.",
                         "a fome dentro do muro e os campos vazios lá fora", perto=perto)
        # --- recolonizar: com fome e poucos mortos por perto, mandar famílias de volta para os campos abandonados
        if ld and len(m.H[L.id]) >= 40 and (L.fome >= 3 or dias_comida < 7) and not cercado and m.flags.get("navio") is not None \
                and m.h - m.flags.get(f"colonia_{L.id}", -10**6) >= 24 * 20:
            pensa = ast(ld) >= 6 or gen(ld) >= 7 or L.fome >= 12
            alvos = sorted((m.km(L.id, T.id) + 2 * len(m.Zin[T.id]), T.id) for T in m.L.values()
                           if T.tipo in ("aldeia", "mosteiro") and T.id != L.id and not m.H[T.id] and len(m.Zin[T.id]) <= 3
                           and m.km(L.id, T.id) <= 18 and T.id != "ilheu")
            if pensa and alvos and m.r() < C.IDEIA["colonia"]:
                T = m.L[alvos[0][1]]
                vivos = [q for q in m.vivos_em(L.id) if q.estado == "vivo" and not q.cela and not q.holofote]
                fams = sorted({q.fam for q in vivos})
                m.rng.shuffle(fams)
                vao, alvo_n = [], min(C.COLONIA_MAX, int(len(vivos) * C.COLONIA_FRACAO))
                for f in fams:
                    if len(vao) >= alvo_n:
                        break
                    vao += [q for q in vivos if q.fam == f]
                armados = [q for q in vivos if q.classe >= 2 and q not in vao]
                vao += armados[:max(4, len(vao) // 10)]
                if len(vao) >= 10:
                    chefe = melhor([q for q in vao if 18 <= q.idade <= 65] or vao, lambda q: q.a["coragem"] + ast(q))
                    m.flags[f"colonia_{L.id}"] = m.h
                    carga = min(L.comida * 0.3, len(vao) * 5.0)
                    L.comida -= carga
                    g = m.partir_grupo(vao, L.id, T.id, "colonos", carga=carga)
                    if g:
                        g["chefe"] = chefe.id
                        registra(m, L, "colonia", ld, f"Com a fome em {L.nome}, {m.nm(ld)} manda {m.pessoas(len(vao))} de volta "
                                 f"para os campos de {T.nome}, abandonada desde que os mortos passaram. Vai na frente "
                                 f"{m.nm(chefe)}.", "a comida acabando e os campos vazios", n=len(vao), para=T.id,
                                 chefe=chefe.id)
        # --- caçada de limpeza: um general esperto organiza a matança de dia, em formação
        if L.tipo in ("cidadela", "castelo", "vila", "bairro") and not cercado:
            c = quem(m, L, lambda p: p.classe >= 3 and ast(p) >= 8 and p.a["coragem"] >= 7)
            if c and m.r() < C.IDEIA["cacada"]:
                cacada(m, L, melhor(c, ast))


def pesquisa(m, L):
    pq = L.pesquisa
    p = m.P[pq["quem"]]
    if p.estado != VIVO or p.loc != L.id:
        L.pesquisa = None
        return
    pq["prog"] += m.r() * gen(p) / 10 * C.ANTIDOTO_RITMO
    if m.r() < C.ANTIDOTO_ACIDENTE:
        # o morto preso solta a corrente
        m.morder(p, L.id)
        p.esconde = True
        m.ev("ideia", L.id, [p], f"Em {L.nome}, o morto preso no laboratório solta a corrente durante uma experiência. "
             f"{m.nm(p)} sai com uma mordida no braço e não conta a ninguém.", motivo="o estudo do antídoto", ideia="antidoto_acidente")
        L.pesquisa = None
        return
    if pq["prog"] >= 1.0:
        pq["tentativas"] += 1
        pq["prog"] = 0.0
        if m.r() < C.ANTIDOTO_SUCESSO:
            for X in m.cidade(L):
                X.sabe.add("cura")
            m.ev("ideia", L.id, [p], f"Em {L.nome}, depois de {pq['tentativas']} tentativas, {m.nm(p)} acha um remédio: "
                 f"uma infusão amarga que, dada nas primeiras horas, às vezes segura a mordida. Não funciona sempre.",
                 motivo="o estudo do antídoto", ideia="cura")
            L.pesquisa = None
        else:
            m.ev("ideia", L.id, [p], f"Em {L.nome}, o remédio de {m.nm(p)} falha mais uma vez: o mordido que bebeu vira do mesmo jeito. "
                 f"{m.g(p, 'Ele', 'Ela')} recomeça.", motivo="o estudo do antídoto", ideia="antidoto_falha")


def cacada(m, L, general):
    alvos = []
    for T in m.L.values():
        z = len(m.Zin[T.id])
        if T.id == L.id or m.H[T.id] or not z:
            continue
        d = m.km(L.id, T.id)
        if d <= 15:
            alvos.append((z, d, T.id))
    armados = [p for p in m.vivos_em(L.id) if p.estado == VIVO and p.classe >= 2 and 18 <= p.idade <= 55 and not p.holofote]
    if not alvos or len(armados) < 30:
        return
    alvos.sort()
    z, d, tid = alvos[0]
    if z > len(armados) * 0.7:
        return
    T = m.L[tid]
    ida = m.amostra(armados, min(len(armados) // 2, 80))
    zs = [m.P[i] for i in sorted(m.Zin[tid])]
    antes = T.formacao
    T.formacao = True
    res = m.luta_aberta(ida, zs, T, "cacada")
    T.formacao = antes
    for p in ida:          # quem volta, volta no mesmo dia
        if p.estado in ("vivo", "mordido"):
            pass
    m.ev("ideia", L.id, [general], f"{m.nm(general)} sai de {L.nome} de manhã com {len(ida)} armados em formação para limpar "
         f"{T.nome}, onde havia {m.pessoas(z, 'morto-vivo', 'mortos-vivos')}. {m.resumo_luta(res)}",
         motivo="esperar dentro do muro não ia acabar com eles", ideia="cacada",
         **{k: v for k, v in res.items() if k != "herois"})
    if "cacada" not in L.ideias:
        L.ideias.append("cacada")


# ---------------------------------------------------------------- a cada hora de cerco
def no_cerco(m, L, armados):
    lid = L.id
    n = len(m.Zout[lid])
    if n == 0:
        return
    # fosso com estacas: alguns caem e não levantam
    if "fosso" in L.ideias:
        k = int(m.rng.binomial(n, C.FOSSO_MATA))
        for zid in m.amostra(sorted(m.Zout[lid]), k):
            m.destruir(m.P[zid], "empalado no fosso")
    # corredor de matança: já montado, mata alguns por hora com pouco risco
    if "corredor" in L.ideias and armados:
        k = min(len(m.Zout[lid]), int(m.rng.binomial(len(armados), C.CORREDOR_MATA)))
        for zid in m.amostra(sorted(m.Zout[lid]), k):
            m.destruir(m.P[zid], "morto no corredor do portão")
        for p in m.amostra(armados, int(m.rng.binomial(k, 0.02))):
            m.morder(p, lid)
    n = len(m.Zout[lid])
    if n < 20 or m.flags.get(f"tatica_{lid}", -99) > m.h - 24:
        return
    chefes = [p for p in armados if p.estado == VIVO and (ast(p) >= 8 or gen(p) >= 8)]
    ld = m.lider(L)
    if ld and (ast(ld) >= 8 or gen(ld) >= 8):
        chefes.append(ld)
    if not chefes:
        return
    ch = melhor(chefes, lambda p: ast(p) + gen(p))
    r = m.r()
    if r < C.TATICA["isca"] and n >= 40:
        # barulho longe do muro: sinos e fogo num lugar vazio atraem parte do bando
        vazios = [nb for nb, km, t in m.adj[lid] if t == "estrada" and not m.H[nb]]
        if vazios:
            m.flags[f"tatica_{lid}"] = m.h
            alvo = m.escolhe(vazios)
            km, _ = m.aresta(lid, alvo)
            vao = [zid for zid in sorted(m.Zout[lid]) if m.r() < C.ISCA_LEVA]
            for zid in vao:
                m.Zout[lid].discard(zid)
                m.P[zid].loc = None
            m.hordas.append({"id": m.novo_id(), "ids": vao, "de": lid, "para": alvo, "km": km, "feito": 0.0,
                             "vel": C.VEL_ZUMBI_CAÇA, "parada": False})
            vol = m.amostra([p for p in armados if p.a["coragem"] >= 7], 3)
            mortos = [p for p in vol if m.r() < 0.5]
            for p in mortos:
                m.morrer(p, "ficou para trás depois de tocar o sino da isca", alvo)
            m.ev("ideia", lid, [ch] + vol[:1], f"{m.nm(ch)} manda {len(vol)} voluntários a cavalo até {m.L[alvo].nome} para tocar "
                 f"o sino e acender fogueiras. {len(vao)} dos {n} mortos do lado de fora correm atrás do barulho."
                 + (f" {m.pessoas(len(mortos), 'voluntário não volta', 'voluntários não voltam')}." if mortos else " Os voluntários voltam."),
                 motivo="o cerco apertando o portão", ideia="isca", n=len(vao))
            return
    if r < C.TATICA["isca"] + C.TATICA["fogo"] and L.lenha >= 80:
        m.flags[f"tatica_{lid}"] = m.h
        L.lenha -= 80
        k = int(n * (0.2 + 0.2 * m.r()))
        for zid in m.amostra(sorted(m.Zout[lid]), k):
            m.destruir(m.P[zid], "queimado com piche no portão")
        L.portao_hp -= 15      # em chamas, eles ainda batem no portão
        m.barulho(L, C.RUIDO_MAX)   # fogo, gritos e estalos: o maior barulho da ilha
        incendio = m.r() < C.FOGO_ESPALHA
        if incendio:
            L.comida *= 0.8
            L.quebradas = min(L.casas, L.quebradas + max(1, L.casas // 20))
        m.ev("ideia", lid, [ch], f"{m.nm(ch)} manda despejar piche fervente e jogar tochas sobre os mortos amontoados no portão de "
             f"{L.nome}. {k} queimam até cair; os outros continuam batendo, em chamas."
             + (" O fogo pula para os telhados de palha do lado de dentro e queima parte do celeiro." if incendio else ""),
             motivo="o portão não ia aguentar", ideia="fogo", n=k)
        return
    if r < C.TATICA["isca"] + C.TATICA["fogo"] + C.TATICA["corredor"] and "corredor" not in L.ideias and len(armados) >= 20:
        m.flags[f"tatica_{lid}"] = m.h
        L.ideias.append("corredor")
        m.ev("ideia", lid, [ch], f"Em {L.nome}, {m.nm(ch)} manda abrir só uma fresta do portão, com um corredor de carroças do "
             f"lado de dentro. Os mortos entram um de cada vez, e as lanças esperam no fim do corredor.",
             motivo="lutar com a cabeça, não só com a força", ideia="corredor")
