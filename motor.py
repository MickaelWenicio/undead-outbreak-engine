"""Motor do apocalipse zumbi: o reino de Alvor, com passo de uma hora.

Regras fixas do primeiro ao último dia (docs/RULES.md, config.py). Nenhum evento é posto à mão: o único papel fora do
motor é a escolha dos protagonistas, feita por regra antes de rodar.
"""
import collections
import heapq
import json
import math
from collections import Counter, defaultdict

import numpy as np

import config as C
import hierarquia as HQ
import mundo as M

VIVO, MORDIDO, ZUMBI, MORTO, DESTRUIDO = "vivo", "mordido", "zumbi", "morto", "destruido"
VIVOS = (VIVO, MORDIDO)
FORTES = ("cidadela", "castelo", "vila", "bairro")


def clamp(x, a, b):
    return max(a, min(b, x))


def contrai(nome, prep="de"):
    """'de' + 'a igreja' = 'da igreja'; 'em' + 'a torre' = 'na torre'."""
    if not nome:
        return f"{prep} um esconderijo"
    art, _, resto = nome.partition(" ")
    if art in ("a", "o", "as", "os") and resto:
        return {"de": "d", "em": "n"}[prep] + nome
    return f"{prep} {nome}"


class Pessoa:
    __slots__ = ("id", "nome", "sob", "sexo", "idade", "papel", "titulo", "a", "casa", "loc", "estado", "classe", "arma",
                 "fam", "conj", "pais", "filhos", "t_vira", "esconde", "abrigo", "cela", "op", "rancor", "fama",
                 "holofote", "morte", "causa", "viagem", "medo", "seita", "fome", "reduto", "escondido", "cheiro",
                 "suspeito", "esc_h", "zfim")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))

    def d(self):
        return {s: getattr(self, s) for s in self.__slots__}


class Lugar:
    __slots__ = ("id", "nome", "tipo", "x", "y", "muro", "litoral", "pop0", "portao_hp", "escalada", "casas", "barricadas",
                 "quebradas", "dano_portas", "comida", "lenha", "lancas", "lider", "pol", "sabe", "alerta", "estado",
                 "caiu", "moral", "medo", "preco", "fome", "seita_lider", "obra", "lutas", "barulho", "pediu_ajuda",
                 "ultimo_decreto", "invadida_em", "barricada_rua", "cerco_rua", "portao_max", "reforcado", "reduto_hp",
                 "reduto_nome", "formacao", "escorado", "ideias", "pesquisa", "ruido", "suserano", "rebelde", "gado",
                 "cavalos", "obra_muro", "recusas_rei", "ultima_ordem", "boatos")

    def __init__(self, **k):
        for s in self.__slots__:
            setattr(self, s, k.get(s))

    def d(self):
        o = {s: getattr(self, s) for s in self.__slots__}
        o["sabe"] = sorted(self.sabe)
        return o


class Mundo:
    def __init__(self):
        self.P, self.L, self.adj = [], {}, defaultdict(list)
        self.H, self.Zin, self.Zout = defaultdict(set), defaultdict(set), defaultdict(set)
        self.Fora, self.mordidos, self.quarentena = defaultdict(set), set(), {}   # gente acampada do lado de fora de um portão fechado
        self.grupos, self.hordas, self.timers, self.corpos, self.porao = [], [], [], [], []
        self.log, self.serie, self.diario = [], [], []
        self.h, self.seed, self.rng, self.gid, self.seq = 0, None, None, 0, 0
        self.flags, self.fim, self.holofote, self.nivel, self.geada, self.limpo = {}, None, [], 0, False, 0
        self.contas = Counter()
        self._recusas = {}

    # ------------------------------------------------------------------ utilidades
    def r(self):
        return float(self.rng.random())

    def escolhe(self, seq):
        return seq[int(self.rng.integers(len(seq)))]

    def amostra(self, seq, k):
        k = min(k, len(seq))
        if k <= 0:
            return []
        idx = self.rng.choice(len(seq), size=k, replace=False)
        return [seq[i] for i in sorted(idx)]

    def dia(self, h=None):
        return (self.h if h is None else h) // 24 + 1

    def hora(self, h=None):
        return (self.h if h is None else h) % 24

    def estacao(self):
        doy = (C.INICIO_DOY + self.h // 24) % 365
        if 80 <= doy < 172:
            return "primavera"
        if 172 <= doy < 264:
            return "verao"
        if 264 <= doy < 355:
            return "outono"
        return "inverno"

    def quando(self, h=None):
        h = self.h if h is None else h
        return f"dia {self.dia(h)}, {self.hora(h):02d}h"

    def nm(self, p):
        if p is None:
            return "?"
        return f"{p.titulo + ' ' if p.titulo else ''}{p.nome} {p.sob}".strip()

    def g(self, p, m, f):
        return f if p.sexo == "f" else m

    def pessoas(self, n, um="pessoa", varias="pessoas"):
        return f"1 {um}" if n == 1 else f"{n} {varias}"

    def ev(self, tipo, lugar, quem, texto, motivo=None, **dados):
        quem = [q for q in quem if q is not None]
        e = {"h": self.h, "tipo": tipo, "lugar": lugar, "quem": [q.id for q in quem], "texto": texto}
        if motivo:
            e["motivo"] = motivo
        e.update(dados)
        self.log.append(e)
        peso = {"queda": 6, "golpe": 8, "assassinato": 8, "decreto": 2, "recusa": 5, "heroi": 6, "execucao": 3,
                "virou_dentro": 3, "levanta": 3, "fuga": 1, "sacrificio": 8, "rei": 6, "seita": 5}.get(tipo, 1)
        for q in quem:
            q.fama = (q.fama or 0) + peso
        return len(self.log) - 1

    def vivos_em(self, lid):
        return [self.P[i] for i in sorted(self.H[lid])]

    def adultos(self, lid):
        return [p for p in self.vivos_em(lid) if 16 <= p.idade <= 70]

    def lider(self, L):
        p = self.P[L.lider] if L.lider is not None else None
        return p if p is not None and p.estado in VIVOS and p.loc == L.id else None

    def parentes(self, p):
        ids = set(p.filhos or []) | set(p.pais or [])
        if p.conj is not None:
            ids.add(p.conj)
        return [self.P[i] for i in sorted(ids)]

    def relacao(self, p, q):
        if q.id == p.conj:
            return self.g(q, "o marido", "a esposa")
        if q.id in (p.filhos or []):
            return self.g(q, "o filho", "a filha")
        if q.id in (p.pais or []):
            return self.g(q, "o pai", "a mãe")
        return "um parente"

    # ------------------------------------------------------------------ criação do reino
    @classmethod
    def novo(cls, seed=C.SEED):
        m = cls()
        m.seed = seed
        m.rng = np.random.Generator(np.random.PCG64(seed))
        for lid, nome, tipo, x, y, pop, muro, lit in M.LUGARES:
            hp = C.MURO[muro][0]
            m.L[lid] = Lugar(id=lid, nome=nome, tipo=tipo, x=x, y=y, muro=muro, litoral=lit, pop0=pop, portao_hp=hp,
                             escalada=0.0, casas=max(1, pop // C.GENTE_POR_CASA), barricadas=0, quebradas=0,
                             dano_portas=0.0, comida=0.0, lenha=float(pop) * 0.4, lancas=0.0, lider=None,
                             pol={"portao": "aberto", "mordidos": "cuidar", "corpos": "velar", "racao": 1.0,
                                  "defender": False},
                             sabe=set(), alerta=None, estado="normal", caiu=None, moral=60.0, medo=0.0, preco=1.0,
                             fome=0, seita_lider=None, obra=0.0, lutas=0, barulho=-99, pediu_ajuda=False,
                             ultimo_decreto=-99, invadida_em=None, barricada_rua=0.0, cerco_rua=False, portao_max=hp,
                             reforcado=False, reduto_hp=0.0, reduto_nome=None, formacao=False, escorado=False,
                             ideias=[], pesquisa=None, ruido=0.0, suserano=None, rebelde=False, gado=0.0,
                             cavalos=0.0, obra_muro=None, recusas_rei=0, ultima_ordem=None, boatos=0)
        for a, b, km, tipo in M.estradas(M.LUGARES):
            m.adj[a].append((b, km, tipo))
            m.adj[b].append((a, km, tipo))
        # o temperamento do reino: desvios sorteados na média de alguns atributos de toda a gente
        m.flags["cultura"] = {k: round(float(clamp(m.rng.normal(0.0, C.CULTURA_DESVIO), -C.CULTURA_MAX, C.CULTURA_MAX)), 2)
                              for k in C.CULTURA_ATRIBUTOS}
        m.populacao()
        HQ.setup(m)
        m.escolher_protagonistas()
        return m

    def nova_pessoa(self, lid, fam, sob, sexo, idade, papel, titulo=None, nome=None):
        pool = M.NOMES_F if sexo == "f" else M.NOMES_M
        cult = self.flags.get("cultura", {})
        a = {k: int(clamp(round(self.rng.normal(5.5 + cult.get(k, 0.0), 2.0)), 1, 10)) for k in M.ATRIBUTOS}
        if papel in ("soldado", "cavaleiro"):
            a["coragem"] = min(10, a["coragem"] + 2)
            a["lealdade"] = min(10, a["lealdade"] + 1)
            a["forca"] = min(10, a["forca"] + 2)
        if papel in ("lenhador", "mineiro", "ferreiro", "estivador"):
            a["forca"] = min(10, a["forca"] + 2)
        if papel in ("carpinteiro", "ferreiro"):
            a["genio"] = min(10, a["genio"] + 2)
        if idade < 14:
            a["forca"] = max(1, a["forca"] - 4)
        elif idade > 62:
            a["forca"] = max(1, a["forca"] - 3)
        if papel in ("clerigo", "monge"):
            a["fe"] = min(10, a["fe"] + 3)
            a["piedade"] = min(10, a["piedade"] + 2)
        arma = {"soldado": 2, "cavaleiro": 3, "nobre": 3, "lenhador": 1, "cacador": 1, "mineiro": 1, "ferreiro": 1}.get(papel, 0)
        p = Pessoa(id=len(self.P), nome=nome or self.escolhe(pool), sob=sob, sexo=sexo, idade=float(idade), papel=papel,
                   titulo=titulo, a=a, casa=lid, loc=lid, estado=VIVO, classe=0, arma=arma, fam=fam, conj=None, pais=[],
                   filhos=[], t_vira=None, esconde=None, abrigo=False, cela=False, op=float(self.rng.normal(15, 20)),
                   rancor=[], fama=0, holofote=False, morte=None, causa=None, viagem=None, medo=0.0, seita=False, fome=0,
                   reduto=False, escondido=False, cheiro=-1, suspeito=-1, esc_h=None, zfim=None)
        if papel == "nobre" and sexo == "m" and 18 <= idade <= 55:
            p.classe = 4
        else:
            p.classe = M.classe_de(papel, idade, sexo, arma)
        self.P.append(p)
        if lid is not None:
            self.H[lid].add(p.id)
        return p

    def familia(self, lid, pesos, sob=None, adultos_papel=None, titulo=None, nobre=False):
        r = self.r()
        sob = sob or self.escolhe(M.SOBRENOMES)
        fam = len(self.P)
        papeis, ws = list(pesos), np.array(list(pesos.values()), float)

        def papel_adulto(sexo):
            if adultos_papel and not (sexo == "f" and adultos_papel in ("soldado", "cavaleiro", "mineiro")):
                return adultos_papel
            for _ in range(6):
                pp = papeis[int(self.rng.choice(len(papeis), p=ws / ws.sum()))]
                if sexo == "f" and pp in ("soldado", "estivador", "mineiro"):
                    continue
                return pp
            return "campones"
        membros = []
        if r < 0.14:
            sexo = "m" if self.r() < 0.6 else "f"
            membros.append(self.nova_pessoa(lid, fam, sob, sexo, self.rng.integers(17, 60), papel_adulto(sexo), titulo))
            return membros
        ih = int(self.rng.integers(20, 56))
        pai = self.nova_pessoa(lid, fam, sob, "m", ih, papel_adulto("m"), titulo if nobre else None)
        mae = self.nova_pessoa(lid, fam, sob, "f", clamp(ih + int(self.rng.integers(-8, 4)), 17, 60),
                               "nobre" if nobre else papel_adulto("f"), "Dona" if nobre else None)
        pai.conj, mae.conj = mae.id, pai.id
        membros += [pai, mae]
        nf = 0 if r < 0.3 else int(self.rng.integers(1, 4))
        for _ in range(nf):
            idade = int(self.rng.integers(0, max(1, min(mae.idade - 16, 24))))
            sexo = "m" if self.r() < 0.5 else "f"
            pp = ("nobre" if nobre else (papel_adulto(sexo) if idade >= 16 else "crianca"))
            f = self.nova_pessoa(lid, fam, sob, sexo, idade, pp, ("Dom" if sexo == "m" else "Dona") if nobre and idade >= 14 else None)
            f.pais = [pai.id, mae.id]
            pai.filhos.append(f.id)
            mae.filhos.append(f.id)
            membros.append(f)
        if self.r() < 0.18:
            sexo = "m" if self.r() < 0.45 else "f"
            v = self.nova_pessoa(lid, fam, sob, sexo, int(self.rng.integers(62, 82)), "idoso")
            v.filhos.append(pai.id)
            pai.pais.append(v.id)
            membros.append(v)
        return membros

    def populacao(self):
        for L in self.L.values():
            pesos = M.oficios(L.tipo, L.litoral)
            if L.tipo == "cidadela":
                rei = self.familia(L.id, pesos, sob=M.DINASTIA, adultos_papel="nobre", titulo="Dom", nobre=True)
                rei[0].titulo, rei[0].papel = ("Rei" if rei[0].sexo == "m" else "Rainha"), "rei"
                rei[0].idade = float(self.rng.integers(44, 60))
                if len(rei) > 1:
                    rei[1].titulo, rei[1].papel = ("Rainha" if rei[1].sexo == "f" else "Dom"), "rainha"
                for f in rei[2:]:
                    if f.papel == "nobre":
                        f.idade = float(self.rng.integers(14, 26))
                if not any(f.idade >= 14 and f.pais for f in rei):     # garante um herdeiro
                    h = self.nova_pessoa(L.id, rei[0].fam, M.DINASTIA, "m", int(self.rng.integers(16, 24)), "nobre", "Dom")
                    h.pais = [rei[0].id] + ([rei[1].id] if len(rei) > 1 else [])
                    rei[0].filhos.append(h.id)
                L.lider = rei[0].id
                for _ in range(10):
                    self.familia(L.id, pesos, adultos_papel="nobre", titulo="Dom", nobre=True)
                for _ in range(28):
                    c = self.nova_pessoa(L.id, len(self.P), self.escolhe(M.SOBRENOMES), "m", int(self.rng.integers(19, 46)),
                                         "cavaleiro", "Sir" if False else None)
                    c.classe = 4
            guarnicao = {"cidadela": 70, "bairro": 22, "vila": 18, "castelo": 20}.get(L.tipo, 0)
            for _ in range(guarnicao):
                self.familia(L.id, pesos, adultos_papel="soldado")
            if L.tipo == "castelo":
                sen = self.familia(L.id, pesos, adultos_papel="nobre", titulo="Dom", nobre=True)
                L.lider = sen[0].id
                for _ in range(8):
                    c = self.nova_pessoa(L.id, len(self.P), self.escolhe(M.SOBRENOMES), "m", int(self.rng.integers(19, 46)),
                                         "cavaleiro")
                    c.classe = 4
            if L.pop0 == 0:
                continue
            while len(self.H[L.id]) < L.pop0:
                self.familia(L.id, pesos)
            L.comida = len(self.H[L.id]) * C.ESTOQUE_INICIAL_DIAS["capital" if L.tipo == "bairro" else L.tipo]
            if L.lider is None:
                cands = sorted(self.adultos(L.id), key=lambda p: (-(p.a["carisma"] + p.a["astucia"] +
                                                                    (4 if p.papel in ("nobre", "clerigo", "monge", "mercador") else 0)
                                                                    + p.idade / 15), p.id))
                if L.tipo == "mosteiro":
                    cands = [p for p in cands if p.papel == "monge"] or cands
                L.lider = cands[0].id
                ld = cands[0]
                ld.titulo = {"vila": "alcaide", "bairro": "meirinho", "mosteiro": "abade", "mina": "capataz",
                             "aldeia": None}.get(L.tipo, ld.titulo)
            if L.tipo in ("cidadela", "castelo"):
                L.lancas = 40.0
            elif L.tipo in ("vila", "bairro"):
                L.lancas = 15.0

    def escolher_protagonistas(self):
        """Regra fixa, antes de rodar: cinco pessoas em lugares e papéis diferentes, sorteadas entre as elegíveis."""
        regras = [
            ("soldado da porta da capital", lambda p: p.loc == "porta" and p.papel == "soldado" and 18 <= p.idade <= 30),
            ("mãe de uma aldeia perto da origem", lambda p: p.loc in ("areias", "carvalhal", "gaivota") and p.sexo == "f"
             and 24 <= p.idade <= 45 and p.filhos),
            ("monge do mosteiro", lambda p: p.loc == "mosteiro" and p.papel == "monge" and 20 <= p.idade <= 60),
            ("herdeiro do trono", lambda p: p.loc == "cidadela" and p.sob == M.DINASTIA and p.pais and 14 <= p.idade <= 26),
            ("mercador de Valverde", lambda p: p.loc == "valverde" and p.papel == "mercador" and 24 <= p.idade <= 52),
        ]
        for rotulo, ok in regras:
            cands = [p for p in self.P if ok(p) and not p.holofote]
            if cands:
                p = self.escolhe(cands)
                p.holofote = True
                self.holofote.append({"id": p.id, "papel": rotulo, "desde": 0})

    # ------------------------------------------------------------------ grafo
    def preparar_grafo(self):
        ids = sorted(self.L)
        self._ix = {l: i for i, l in enumerate(ids)}
        n = len(ids)
        INF = 1e9
        d = [[INF] * n for _ in range(n)]
        nx = [[None] * n for _ in range(n)]
        for a in ids:
            i = self._ix[a]
            d[i][i] = 0
            nx[i][i] = a
            for b, km, _ in self.adj[a]:
                j = self._ix[b]
                if km < d[i][j]:
                    d[i][j], nx[i][j] = km, b
        for k in range(n):
            for i in range(n):
                dik = d[i][k]
                if dik >= INF:
                    continue
                for j in range(n):
                    if dik + d[k][j] < d[i][j]:
                        d[i][j] = dik + d[k][j]
                        nx[i][j] = nx[i][k]
        self._dist, self._next, self._ids = d, nx, ids

    def km(self, a, b):
        return self._dist[self._ix[a]][self._ix[b]]

    def proximo(self, a, b):
        return self._next[self._ix[a]][self._ix[b]]

    def aresta(self, a, b):
        for nb, km, tipo in self.adj[a]:
            if nb == b:
                return km, tipo
        return None, None

    # ------------------------------------------------------------------ o passo de uma hora
    def passo(self):
        if not hasattr(self, "_ix"):
            self.preparar_grafo()
        if self.h % 24 == 0:
            self.novo_dia()
        if self.dia() == C.DIA_DO_NAVIO and self.hora() == C.HORA_DO_NAVIO and not self.flags.get("navio"):
            self.navio()
        self.solta_porao()
        self.relogios()
        self.mortos_agem()
        self.andar_hordas()
        self.andar_grupos()
        self.vivos_reagem()
        self.registrar()
        self.h += 1
        self.checar_fim()

    # ------------------------------------------------------------------ origem
    def navio(self):
        self.flags["navio"] = self.h
        L = self.L[M.ORIGEM]
        mar = []
        for i in range(3):
            p = self.nova_pessoa(L.id, -1, "", "m", int(self.rng.integers(20, 50)), "estrangeiro",
                                 nome=self.escolhe(M.NOMES_ESTRANGEIROS))
            p.sob = ""
            self.morder(p, L.id, conta=False)
            p.esconde, p.abrigo = False, True
            mar.append(p)
        quando = self.h + int(self.rng.integers(3, 8))
        for i in range(6):
            z = self.nova_pessoa(None, -1, "", "m", int(self.rng.integers(20, 50)), "estrangeiro",
                                 nome=self.escolhe(M.NOMES_ESTRANGEIROS))
            z.sob, z.estado, z.loc = "", ZUMBI, L.id
            self.porao.append((quando, z.id))
        self.ev("navio", L.id, mar, f"Na noite do dia {self.dia()}, um navio sem bandeira bate nas pedras de {L.nome}. "
                f"Três marinheiros feridos chegam à praia pedindo ajuda numa língua que ninguém entende. "
                f"Os pescadores levam os três para dentro de casa. No porão, alguma coisa bate contra as tábuas.")

    def solta_porao(self):
        if not self.porao:
            return
        prontos = [z for h, z in self.porao if h <= self.h]
        if prontos:
            self.porao = [(h, z) for h, z in self.porao if h > self.h]
            L = self.L[M.ORIGEM]
            for zid in prontos:
                self.Zin[L.id].add(zid)
            self.ev("porao", L.id, [], f"De madrugada, as tábuas do porão cedem. {len(prontos)} homens saem do navio "
                    f"correndo pela praia de {L.nome}, direto para as casas.", n=len(prontos))

    # ------------------------------------------------------------------ mordida, morte, virada, levante
    def alimenta(self, lid, quanto):
        """Comida dos mortos de um lugar no dia; repartida entre eles no apodrecer()."""
        if lid in self.L:
            pool = self.flags.setdefault("comida_z", {})
            pool[lid] = pool.get(lid, 0.0) + quanto

    def morder(self, p, lid, conta=True):
        if p.estado == MORDIDO:
            return
        self.alimenta(lid, C.COMIDA_MORDIDA)
        p.estado = MORDIDO
        self.mordidos.add(p.id)
        p.t_vira = self.h + float(self.rng.triangular(C.VIRA_MORDIDO_H[0], C.VIRA_MORDIDO_MODA, C.VIRA_MORDIDO_H[1]))
        p.esconde = None
        self.seq += 1
        heapq.heappush(self.timers, (math.ceil(p.t_vira), self.seq, "vira", p.id))
        if conta:
            self.contas["mordidos"] += 1

    def morrer(self, p, causa, lid, levanta_chance=0.0, destino=None):
        """Tira p dos vivos. Se o corpo ficou inteiro (levanta_chance), ele levanta em 10 a 60 minutos: no lugar
        (registro de corpo, que os vivos ainda podem destruir) ou, na estrada e fora do muro, direto no bando (destino)."""
        if p.loc is not None:
            self.H[p.loc].discard(p.id)
            self.Fora[p.loc].discard(p.id)
        if p.viagem is not None:
            self.sair_do_grupo(p)
        self.mordidos.discard(p.id)
        if causa in C.COMIDO:
            self.alimenta(lid, 1.0)
        if (p.papel == "rei" or (p.titulo in ("Rei", "Rainha") and p.papel != "rainha")) and p.estado in VIVOS:
            onde = self.L[lid].nome if lid in self.L else "na estrada"
            self.ev("rei_morre", lid if lid in self.L else None, [p],
                    f"{self.nm(p)} morre {('em ' + onde) if lid in self.L else onde}: {causa}.", causa=causa)
        p.estado, p.morte, p.causa = MORTO, self.h, causa
        p.abrigo = p.cela = False
        self.contas["mortos"] += 1
        if levanta_chance > 0 and self.r() < levanta_chance:
            if destino is not None:
                p.estado = ZUMBI
                self.contas["levantaram"] += 1
                destino(p)
            elif lid is not None:
                self.corpos.append({"id": p.id, "lugar": lid, "h": self.h + 1})
        self.passa_o_fio(p)

    def destruir(self, z, causa):
        for lid in (z.loc,):
            if lid is not None:
                self.Zin[lid].discard(z.id)
                self.Zout[lid].discard(z.id)
        z.estado, z.causa = DESTRUIDO, causa
        if z.morte is None:
            z.morte = self.h
        self.contas["destruidos"] += 1
        self.flags["ultima_baixa_z"] = causa

    def transformar(self, p, onde_txt=None):
        if (p.papel == "rei" or (p.titulo in ("Rei", "Rainha") and p.papel != "rainha")) and p.estado in VIVOS:
            onde = self.L[p.loc].nome if p.loc in self.L else "na estrada"
            self.ev("rei_morre", p.loc if p.loc in self.L else None, [p],
                    f"{self.nm(p)} se levanta morto {('em ' + onde) if p.loc in self.L else onde}. O reino fica sem rei.")
        self.mordidos.discard(p.id)
        lid = p.loc
        if lid is not None and p.id in self.Fora[lid]:
            self.Fora[lid].discard(p.id)
            p.estado, p.t_vira = ZUMBI, None
            p.morte = p.morte if p.morte is not None else self.h
            self.Zout[lid].add(p.id)
            return
        if p.viagem is not None:
            g = self.grupo(p.viagem)
            self.sair_do_grupo(p)
            p.estado, p.morte, p.t_vira = ZUMBI, p.morte if p.morte is not None else self.h, None
            if g:
                p.loc = None
                self.virou_na_estrada(p, g)
            return
        if lid is None:
            return
        self.H[lid].discard(p.id)
        L = self.L[lid]
        p.estado, p.t_vira = ZUMBI, None
        if p.morte is None:
            p.morte = self.h
        p.causa = p.causa or "virou morto-vivo"
        if p.suspeito >= self.h and L.pol.get("caserna"):
            p.cela = True     # dormia na caserna trancada com os outros que lutaram
        if p.cela:
            p.cela = False
            if self.r() < 0.85:
                self.destruir(p, "abatido na cela ao virar")
                self.contas["cela"] += 1
                if "mordida" not in L.sabe:
                    self.aprender(L, "mordida", f"Em {L.nome}, um mordido preso na cela vira morto-vivo. Agora todos sabem "
                                                f"o que a mordida faz.")
                return
        self.Zin[lid].add(p.id)
        escondia = bool(p.esconde)
        self.contas["virou_dentro" if escondia else "virou"] += 1
        if self.vivos_em(lid):
            if "mordida" not in L.sabe:
                self.aprender(L, "mordida", f"Em {L.nome}, {self.nm(p)} se levanta morto no meio da própria família. "
                                            f"Ninguém sabia que a mordida fazia isso.", [p])
            if p.abrigo:     # virou dentro de uma casa fechada: a casa vira armadilha
                vizinhos = [q for q in self.vivos_em(lid) if q.abrigo][:C.GENTE_POR_CASA]
                for q in vizinhos:
                    q.abrigo = False
            if escondia and (p.holofote or self.contas["virou_dentro"] <= 3 or L.tipo in FORTES):
                self.ev("virou_dentro", lid, [p], f"Em {L.nome}, {self.nm(p)} se levanta morto. "
                        f"Tinha escondido a mordida.", motivo="mordida escondida")
            if escondia:
                self.medidas_contra_escondidos(L, p)
        p.abrigo = False

    def medidas_contra_escondidos(self, L, quem_virou):
        ld = self.lider(L)
        if ld is None:
            return
        novas = []
        if not L.pol.get("caserna") and quem_virou.suspeito >= self.h - 24 and (ld.a["astucia"] >= 7 or ld.classe >= 3) \
                and self.r() < 0.5:
            L.pol["caserna"] = True
            novas.append("quem lutar com os mortos dorme trancado na caserna, com guarda na porta, até passar um dia")
        if not L.pol.get("revista") and ld.a["astucia"] >= 6 and self.r() < 0.4:
            L.pol["revista"] = True
            novas.append("todo mundo é revistado duas vezes por dia, de manhã e de noite, à procura de mordidas")
        if novas:
            self.ev("decreto", L.id, [ld], f"Em {L.nome}, depois que {self.nm(quem_virou)} virou lá dentro, {self.nm(ld)} decide: "
                    + "; ".join(novas) + ".", motivo=f"{self.nm(quem_virou)} escondeu a mordida")

    def revista(self):
        """Duas vezes por dia, onde há revista: a mordida escondida pode ser achada antes de virar."""
        for pid in sorted(self.mordidos):
            p = self.P[pid]
            if p.esconde and p.loc in self.L and pid in self.H[p.loc] and self.L[p.loc].pol.get("revista") \
                    and self.r() < C.REVISTA_ACHA:
                L = self.L[p.loc]
                p.esconde = False
                self.contas["achados_na_revista"] += 1
                self.aplicar_politica_mordido(p, L, achado="na revista")

    def virou_na_estrada(self, z, g):
        """Quem vira no meio de um grupo em viagem ataca os companheiros ali mesmo."""
        vivos = [self.P[i] for i in g["m"] if self.P[i].estado in VIVOS]
        hd = {"id": self.novo_id(), "ids": [z.id], "de": g["de"], "para": g["para"], "km": g["km"],
              "feito": g["feito"], "vel": C.VEL_ZUMBI_CAÇA, "parada": False}
        res = self.luta_aberta(vivos, [z], None, "estrada", destino=lambda q: hd["ids"].append(q.id))
        hd["ids"] = [i for i in hd["ids"] if self.P[i].estado == ZUMBI]
        if hd["ids"]:
            self.hordas.append(hd)
        if res["mortos"] + res["mordidos"] and (g.get("holofote") or len(vivos) >= 6):
            self.ev("virou", None, [z], f"Na estrada de {self.L[g['de']].nome} para {self.L[g['para']].nome}, "
                    f"{self.nm(z)} vira morto-vivo no meio do grupo. {self.resumo_luta(res)}")

    def relogios(self):
        while self.timers and self.timers[0][0] <= self.h:
            _, _, tipo, pid = heapq.heappop(self.timers)
            p = self.P[pid]
            if tipo == "vira" and p.estado == MORDIDO:
                self.transformar(p)
        if self.corpos:
            pend = []
            levantou = Counter()
            for c in self.corpos:
                if c["h"] > self.h:
                    pend.append(c)
                    continue
                p = self.P[c["id"]]
                if p.estado != MORTO:
                    continue
                lid = c["lugar"]
                if lid is None:
                    p.estado = ZUMBI
                    continue
                L = self.L[lid]
                caos = bool(self.Zin[lid])
                vivos = self.H[lid]
                if vivos and not caos and "levanta" in L.sabe and L.pol["corpos"] != "velar" and self.r() < 0.92:
                    p.causa = (p.causa or "") + "; cabeça cortada antes de levantar"
                    self.contas["corpos_cuidados"] += 1
                    continue
                p.estado, p.loc = ZUMBI, lid
                self.Zin[lid].add(p.id)
                levantou[lid] += 1
                self.contas["levantaram"] += 1
                if vivos and not caos and "levanta" not in L.sabe:
                    self.aprender(L, "levanta", f"Em {L.nome}, os mortos se levantam durante o velório, no meio "
                                                f"de quem rezava por eles.", [p])
            self.corpos = pend

    # ------------------------------------------------------------------ conhecimento e alerta
    def cidade(self, L):
        return [self.L[b] for b in sorted(M.CAPITAL)] if L.id in M.CAPITAL else [L]

    def sinal(self, L):
        """Fogueiras de sinal: a fumaça avisa as outras fortalezas da rede no mesmo dia."""
        rede = self.flags.get("sinais") or []
        if L.id in rede:
            for lid in rede:
                X = self.L[lid]
                if X.alerta is None and self.H[lid]:
                    X.alerta = self.h
                    X.sabe.add("mortos")
                    self.decidir_politica(X, "ao ver a fumaça das fogueiras de sinal")

    def aprender(self, L, coisa, texto, quem=()):
        self.sinal(L)
        novo = coisa not in L.sabe
        for X in self.cidade(L):
            X.sabe.add(coisa)
            X.sabe.add("mortos")
            if X.alerta is None:
                X.alerta = self.h
            if X.tipo == "bairro" and X.barricada_rua == 0 and not self.Zin[X.id]:
                X.barricada_rua = C.BARRICADA_RUA
        if novo:
            self.barulho(L, 4)
            self.ev("aprende", L.id, list(quem), texto, saber=coisa)
            self.decidir_politica(L, f"depois de {'ver' if coisa != 'noticia' else 'ouvir'} o que aconteceu")

    def ensinar(self, L, sabe, de_quem):
        sabe = HQ.ouvir(self, L, set(sabe), de_quem)
        novos = set(sabe) - L.sabe
        if not novos:
            return
        for X in self.cidade(L):
            X.sabe |= set(sabe)
            if X.alerta is None:
                X.alerta = self.h
            if X.tipo == "bairro" and X.barricada_rua == 0 and not self.Zin[X.id]:
                X.barricada_rua = C.BARRICADA_RUA
        if len(novos) >= 1 and ("mortos" in novos or "mordida" in novos):
            self.ev("noticia", L.id, [], f"{de_quem} {'chegam' if de_quem.startswith('Os ') else 'chega'} a {L.nome} com a notícia: "
                    + self.texto_noticia(novos), saber=sorted(novos))
        self.decidir_politica(L, "depois da notícia")

    def texto_noticia(self, sabe):
        partes = []
        if "mortos" in sabe:
            partes.append("os mortos estão andando e atacando gente")
        if "mordida" in sabe:
            partes.append("quem é mordido vira um deles em poucas horas")
        if "levanta" in sabe:
            partes.append("quem morre nos dentes deles se levanta logo depois")
        if "cabeca" in sabe:
            partes.append("só param quando a cabeça é destruída")
        return "; ".join(partes) + "."

    # ------------------------------------------------------------------ política dos líderes
    def decidir_politica(self, L, porque):
        ld = self.lider(L)
        if ld is None:
            return
        a = ld.a
        antes = dict(L.pol)
        sabe = L.sabe
        if "mordida" in sabe:
            if a["crueldade"] >= 6 or (a["astucia"] >= 6 and a["piedade"] <= 6):
                L.pol["mordidos"] = "executar"
            elif a["piedade"] >= 8 and a["fe"] >= 7:
                L.pol["mordidos"] = "cuidar"
            else:
                L.pol["mordidos"] = "isolar"
            if (a["astucia"] + (10 - a["piedade"])) >= 13:
                L.pol["portao"] = "fechado"
            elif a["astucia"] >= 5:
                L.pol["portao"] = "quarentena"
            else:
                L.pol["portao"] = "inspecao"
        elif "mortos" in sabe:
            L.pol["portao"] = "inspecao" if a["astucia"] >= 5 else "aberto"
        if "levanta" in sabe:
            L.pol["corpos"] = "velar" if (a["fe"] >= 9 and a["piedade"] >= 8) else "queimar"
        if "mortos" in sabe:
            L.pol["defender"] = True
        if L.pol != antes and self.h - L.ultimo_decreto >= 2:
            L.ultimo_decreto = self.h
            txt = []
            if L.pol["portao"] != antes["portao"]:
                txt.append({"fechado": "ninguém entra", "inspecao": "quem chega é revistado no portão",
                            "quarentena": "quem chega espera um dia inteiro do lado de fora antes de entrar",
                            "aberto": "os portões ficam abertos para quem fugir"}[L.pol["portao"]])
            if L.pol["mordidos"] != antes["mordidos"]:
                txt.append({"executar": "todo mordido morre antes de virar", "isolar": "todo mordido vai para a cela",
                            "cuidar": "os mordidos ficam com a família e com os curandeiros"}[L.pol["mordidos"]])
            if L.pol["corpos"] != antes["corpos"]:
                txt.append({"queimar": "os mortos têm a cabeça cortada e são queimados na hora",
                            "velar": "os mortos serão velados e enterrados como manda a Igreja"}[L.pol["corpos"]])
            if txt:
                self.ev("decreto", L.id, [ld], f"Em {L.nome}, {self.nm(ld)} decide, {porque}: " + "; ".join(txt) + ".")

    # ------------------------------------------------------------------ mortos agem
    def mortos_agem(self):
        for lid in sorted(self.L):
            if self.Zout[lid]:
                if self.H[lid]:
                    self.cerco(lid)
                else:
                    self.Zin[lid] |= self.Zout[lid]
                    self.Zout[lid].clear()
            if self.Zin[lid]:
                visiveis = any(not self.P[i].escondido for i in self.H[lid])
                if visiveis:
                    self.ataque_dentro(lid)
                else:
                    if self.H[lid]:
                        self.procurar_escondidos(self.L[lid], self.vivos_em(lid))
                    self.marcar_queda(lid)
                    self.partir(lid)

    def marcar_queda(self, lid):
        L = self.L[lid]
        if L.estado not in ("caida", "vazia") and L.caiu is None and L.invadida_em is not None:
            # um lugar que já estava vazio (todos tinham saído ou morrido antes) não "cai": só fica vazio
            recente = [d["lugares"].get(lid, [0, 0])[0] for d in self.diario[-3:]]
            if not self.H[lid] and recente and not any(recente):
                L.estado = "vazia"
                return
            L.estado, L.caiu = "caida", self.h
            self.ev("queda", lid, [], f"{L.nome} cai. Não sobra ninguém vivo lá dentro, só os mortos.",
                    zumbis=len(self.Zin[lid]))

    def barulho(self, L, intensidade):
        """Briga, grito, pancada no portão, sino, fogo: quanto mais alto, de mais longe chama os mortos."""
        if self.h - L.barulho > 3:
            L.ruido = 0.0
        L.barulho = self.h
        L.ruido = min(C.RUIDO_MAX, max(L.ruido, intensidade))

    def nivel_porta(self):
        return C.PORTA_APRENDE[self.nivel]

    def cerco(self, lid):
        L = self.L[lid]
        if self.Fora[lid]:      # quem acampou do lado de fora é o primeiro a ser pego
            fora = [self.P[i] for i in sorted(self.Fora[lid])]
            zs0 = [self.P[i] for i in self.amostra(sorted(self.Zout[lid]), max(1, len(fora)))]
            res = self.luta_aberta(fora, zs0, L, "acampamento", destino=lambda q: self.Zout[lid].add(q.id))
            if res["mortos"] + res["mordidos"] >= 3:
                self.ev("acampamento", lid, [], f"Do lado de fora do portão fechado de {L.nome}, os mortos alcançam os que "
                        f"esperavam para entrar. {self.resumo_luta(res)}", **{k: v for k, v in res.items() if k != "herois"})
        I.no_cerco(self, L, [p for p in self.vivos_em(lid) if p.classe >= 2 and p.estado == VIVO and not p.cela])
        zs = sorted(self.Zout[lid])
        n = len(zs)
        if n == 0:
            return
        hp, limiar, nome_muro = C.MURO[L.muro]
        if "fosso" in L.ideias:
            limiar = int(limiar * 1.5)
        if L.cerco_rua:
            hp, limiar, nome_muro = C.BARRICADA_RUA, C.BARRICADA_RUA_ESCALA, "barricada da rua"
        vivos = self.vivos_em(lid)
        armados = [p for p in vivos if p.classe >= 2 and not p.cela and p.estado == VIVO]
        defensores = [p for p in armados if self.r() < C.TURNO_NO_MURO]
        if L.alerta is None:
            self.aprender(L, "mortos", f"Em {L.nome}, os vigias veem gente correndo para o muro. Não são vivos.")
        self.barulho(L, 1 + len(self.Zout[lid]) / 25)
        fator = 1.0 if "cabeca" in L.sabe else 0.6
        k = int(self.rng.binomial(len(defensores), min(0.9, C.MATA_DO_MURO * fator))) if defensores else 0
        for zid in self.amostra(zs, k):
            self.destruir(self.P[zid], f"derrubado do alto do {nome_muro}")
        escalando = self.nivel >= 2 and n >= limiar * 0.5
        if escalando and defensores:
            nm = int(self.rng.binomial(len(defensores), C.MORDIDA_NO_MURO * min(3.0, n / max(1, limiar))))
            for p in self.amostra(defensores, nm):
                self.morder(p, lid)
        n = len(self.Zout[lid])
        if n == 0:
            return
        empurram = min(n, C.EMPURRAM[L.muro if not L.cerco_rua else 1])
        if L.cerco_rua:
            L.barricada_rua -= empurram * (1.5 if self.nivel >= 4 else 1.0) * 0.6
            rompeu = L.barricada_rua <= 0
        else:
            L.portao_hp -= empurram * (1.5 if self.nivel >= 4 else 1.0) * C.MURO_DANO[L.muro]
            rompeu = L.portao_hp <= 0
        mult = C.ESCALA_POR_DEFENSOR[1 if L.cerco_rua else L.muro]
        if not rompeu and self.nivel >= 2 and n >= limiar and n >= mult * max(1, len(defensores)):
            if self.r() < min(0.6, 0.05 + 0.3 * (n / limiar - 1)):
                rompeu = "escalada"
        if not rompeu and L.pol.get("defender") and armados and n <= 0.35 * len(armados):
            ld = self.lider(L)
            if ld and ld.a["coragem"] >= 5:
                res = self.luta_aberta(armados, [self.P[i] for i in sorted(self.Zout[lid])], L, "surtida")
                ja = self.flags.setdefault("surtidas", {})
                ja[lid] = ja.get(lid, 0) + 1
                # a primeira saída de cada lugar entra no log; as rotineiras, só se forem grandes ou custarem gente
                if ja[lid] == 1 or n >= 10 or res["mortos"] + res["mordidos"] >= 2:
                    self.ev("surtida", lid, [ld], f"{self.nm(ld)} abre os portões de {L.nome} e sai com "
                            f"{len(armados)} armados contra {'o único morto' if n == 1 else f'os {n} mortos'} do lado de fora. "
                            f"{self.resumo_luta(res)}", z0=n, **res)
                return
        if rompeu == True and not L.cerco_rua and armados and len(armados) >= 8 and self.r() < 0.5 and not L.escorado:
            # o portão está cedendo: os armados jogam o corpo contra ele, e as mãos passam pelas frestas
            ld = self.lider(L)
            escora = self.amostra(armados, min(len(armados), 30))
            L.portao_hp = 25.0 * len(escora) / 10
            L.escorado = True
            mord = self.amostra(escora, int(self.rng.binomial(len(escora), 0.12)))
            for q in mord:
                self.morder(q, lid)
            self.ev("escora", lid, [ld], f"O portão de {L.nome} começa a ceder. {len(escora)} homens jogam o corpo contra as "
                    f"tábuas para segurar. Pelas frestas, as mãos dos mortos alcançam {self.pessoas(len(mord), 'deles', 'deles')}.",
                    motivo="o portão cedendo", n=len(escora), mordidos=len(mord))
            rompeu = False
        if rompeu:
            como = "escalam o " + nome_muro if rompeu == "escalada" else "derrubam o portão"
            self.Zin[lid] |= self.Zout[lid]
            self.Zout[lid].clear()
            if L.cerco_rua:
                L.barricada_rua, L.cerco_rua = 0.0, False
            else:
                L.portao_hp = 0
            L.invadida_em = L.invadida_em or self.h
            L.estado = "invadida"
            self.ev("invasao", lid, [], f"Os mortos {como} de {L.nome}. São {n} do lado de dentro.", z0=n)

    def ataque_dentro(self, lid):
        L = self.L[lid]
        zs = [self.P[i] for i in sorted(self.Zin[lid])]
        vivos = self.vivos_em(lid)
        if L.pol.get("defender") and L.tipo in ("vila", "bairro", "cidadela", "castelo"):
            for p in vivos:
                if p.abrigo and p.estado == VIVO and p.classe >= 2 and self.r() < C.RESPOSTA_ARMADA:
                    p.abrigo = False
        if L.invadida_em is None:
            L.invadida_em = self.h
            L.estado = "invadida"
        if "mortos" not in L.sabe:
            self.aprender(L, "mortos", f"Em {L.nome}, gente morta ataca os vizinhos no meio da rua.")
        L.medo = min(100, L.medo + 15)
        self.procurar_escondidos(L, vivos)
        vivos = [p for p in vivos if p.estado in VIVOS]
        expostos = [p for p in vivos if not p.abrigo and not p.cela and not p.escondido]
        confusos = "mordida" not in L.sabe    # sem saber o que é, os vizinhos acodem em vez de correr
        lutam = [p for p in expostos if p.classe >= 3 or (p.classe >= 1 and (self.enfrenta(p, L) or confusos))]
        self.formar(L, lutam)
        civis = [p for p in expostos if p not in set(lutam)]
        Z = len(zs)
        alcance = Z if L.tipo in ("aldeia", "mosteiro", "mina") else max(1, int(round(Z * C.CONTATO_ABERTO)))
        ativos = self.amostra(zs, alcance)
        res = {"z_mortos": 0, "mortos": 0, "mordidos": 0, "herois": []}
        livres = list(ativos)
        if lutam and ativos:
            ne = min(len(ativos), len(lutam))
            engajados, livres = ativos[:ne], ativos[ne:]
            times = [[] for _ in range(ne)]
            for i, p in enumerate(self.amostra(lutam, len(lutam))):
                if i < ne * 4:
                    times[i % ne].append(p)
            for z, time in zip(engajados, times):
                self.luta_time(time, z, L, res, len(zs))
        alvos = [p for p in civis if p.estado == VIVO]
        multidao = min(3, max(0, Z // max(1, len(vivos))))
        if not expostos and L.casas - L.quebradas <= 0:
            for p in vivos:              # não sobrou porta inteira: quem estava trancado fica à vista
                p.abrigo = p.cela = False
            expostos = list(vivos)
        if not expostos and not [p for p in vivos if p.abrigo or p.cela]:
            return
        if L.reduto_nome is None or L.reduto_hp <= 0:
            for p in vivos:              # sem reduto de pé, a marca de reduto não protege ninguém
                p.reduto = False
        self.talvez_reduto(L, vivos, lutam, Z)
        alvos = [p for p in alvos if not p.reduto and not p.escondido]
        batendo = []
        for z in livres:
            if z.estado != ZUMBI:
                continue
            if alvos:
                nv = int(self.rng.poisson(C.VITIMAS_POR_HORA))
                for v in self.amostra(alvos, nv):
                    self.atacado(v, L, res, multidao)
                    alvos.remove(v)
            else:
                L.dano_portas += self.nivel_porta()
                batendo.append(z)
        self.quebrar_portas(L, res, batendo)
        L.lutas += len(lutam) and 1
        if L.lutas >= 6 and "cabeca" not in L.sabe:
            self.aprender(L, "cabeca", f"Em {L.nome}, os que lutam aprendem do jeito mais duro: braço cortado não para "
                                       f"um morto. Só a cabeça.")
        self.barulho(L, 2 + (res["mortos"] + res["mordidos"] + res["z_mortos"]) / 3 + Z / 15)
        if res["mortos"] + res["mordidos"] + res["z_mortos"] >= 4 or res["herois"]:
            self.ev("ataque", lid, res["herois"], f"Em {L.nome}, {self.pessoas(Z, 'morto-vivo', 'mortos-vivos')} "
                    f"dentro do lugar. {self.resumo_luta(res)}", z0=Z, h0=len(vivos), **{k: v for k, v in res.items()
                                                                                         if k != "herois"})

    def luta_time(self, time, z, L, res, multidao_total, destino=None):
        """Um time de 1 a 4 vivos contra um morto, rodada a rodada, até um lado cair. O morto não recua.
        Força pesa no golpe; soldados em formação (escudo com escudo) levam menos mordidas e derrubam mais."""
        fator = 1.0 if (L is None or "cabeca" in L.sabe) else 0.6
        form = L is not None and L.formacao and any(q.classe >= 3 for q in time)
        for q in time:
            q.suspeito = self.h + 24
        if form:
            fator *= C.FORMACAO_MATA
        vivos = [p for p in time if p.estado in VIVOS]
        for _ in range(40):
            if not vivos or z.estado != ZUMBI:
                break
            pk = 1.0
            for p in vivos:
                pk *= 1 - min(0.9, C.P_MATA[p.classe] * fator * (0.7 + p.a.get("forca", 5) / 15))
            pk = 1 - pk
            alvo = vivos[0]
            pb = C.P_MORDE * C.ARMADURA[alvo.classe] * (C.AJUDA_SEGURA ** (len(vivos) - 1)) * (C.FORMACAO_MORDE if form else 1)
            mata, morde = self.r() < pk, self.r() < pb
            if morde:
                multidao = min(3, max(0, multidao_total // 6))
                if self.r() < C.MORTE_NA_HORA[multidao] * 0.6:
                    self.morrer(alvo, "morto lutando contra os mortos", L.id if L else None,
                                C.CORPO_INTEIRO[min(3, multidao)], destino)
                    res["mortos"] += 1
                else:
                    self.morder(alvo, L.id if L else None)
                    res["mordidos"] += 1
                vivos = [p for p in vivos if p.estado == VIVO]
                if vivos and max(q.classe for q in vivos) <= 2:
                    vivos = [q for q in vivos if self.r() > C.DEBANDA]
                    if not vivos:
                        break         # todo mundo correu: o morto continua de pé
            if mata:
                self.destruir(z, "destruído em luta")
                res["z_mortos"] += 1
                if len(time) == 1 and time[0].estado in VIVOS and self.r() < 0.04:
                    res["herois"].append(time[0])
                break

    def enfrenta(self, p, L, base=9):
        """Lutar ou correr: coragem e força contra o medo. Armado ajuda; defender a família também."""
        nota = p.a["coragem"] + p.a.get("forca", 5) / 2 + (1.5 if p.classe >= 2 else 0) - (L.medo / 40 if L else 0)
        if L is not None and L.pol.get("defender") and p.classe >= 2:
            nota += 2
        return nota + self.r() * 2 >= base

    def formar(self, L, lutam):
        """Com um oficial e pelo menos seis soldados, eles se formam em linha. Nem sempre alguém pensa nisso."""
        if L.formacao or L.tipo not in ("vila", "bairro", "cidadela", "castelo"):
            return
        soldados = [p for p in lutam if p.classe >= 3]
        oficiais = [p for p in soldados if p.classe == 4 or (p.a["carisma"] >= 7 and p.a["coragem"] >= 6)]
        if len(soldados) >= 6 and oficiais and self.r() < 0.35:
            of = max(oficiais, key=lambda q: (q.a["carisma"] + q.a["astucia"], -q.id))
            L.formacao = True
            self.ev("formacao", L.id, [of], f"Em {L.nome}, {self.nm(of)} junta {len(soldados)} soldados no meio da rua e forma "
                    f"uma linha, escudo com escudo, lanças para fora. Os mortos batem na parede de escudos.",
                    motivo="os mortos estão dentro e alguém pensou em lutar junto")

    def atacado(self, v, L, res, multidao):
        if self.r() < C.MORTE_NA_HORA[multidao]:
            self.morrer(v, "morto pelos mortos-vivos", L.id, C.CORPO_INTEIRO[multidao])
            res["mortos"] += 1
        else:
            self.morder(v, L.id)
            res["mordidos"] += 1

    def procurar_escondidos(self, L, vivos):
        """Os mortos farejam. Quem está escondido pode passar despercebido; o cheiro disfarçado ajuda muito."""
        for p in vivos:
            if not p.escondido:
                continue
            chance = C.ACHA_ESCONDIDO * (1.3 - 0.06 * p.a["astucia"]) * (C.CHEIRO_DISFARCA if p.cheiro >= self.h else 1)
            horas = self.h - (p.esc_h if p.esc_h is not None else self.h)
            chance *= 1 + horas / 24          # sede, fome, choro de criança: cada dia escondido pesa mais
            if self.r() < chance or horas > 24 * C.ESCONDIDO_MAX_DIAS:
                p.escondido = False           # foi achado, ou teve de sair atrás de água
                p.abrigo = False

    def talvez_reduto(self, L, vivos, lutam, Z):
        if L.reduto_nome is not None or Z < 8 or len(lutam) * 1.5 > Z:
            return
        lideres = [p for p in vivos if p.estado == VIVO and not p.abrigo and 18 <= p.idade <= 65
                   and p.a["coragem"] >= 7 and p.a["astucia"] >= 5]
        if not lideres or self.r() > 0.3:
            return
        ch = max(lideres, key=lambda q: (q.a["coragem"] + q.a["astucia"] + q.a["carisma"], -q.id))
        fam = [q for q in vivos if q.fam == ch.fam and q.estado == VIVO]
        outros = [q for q in vivos if q.estado == VIVO and not q.abrigo and q.fam != ch.fam]
        dentro = (fam + self.amostra(outros, 40))[:45]
        nome = {"mosteiro": "a capela", "castelo": "a torre de menagem", "cidadela": "a torre do rei",
                "bairro": "a igreja do bairro", "vila": "a torre da igreja"}.get(L.tipo, "a igreja")
        L.reduto_nome = nome
        carp = sum(1 for q in dentro if q.papel == "carpinteiro")
        L.reduto_hp = C.REDUTO_HP + 10 * carp
        for q in dentro:
            q.abrigo, q.reduto = True, True
        self.ev("reduto", L.id, [ch], f"Com os mortos nas ruas de {L.nome}, {self.nm(ch)} junta {self.pessoas(len(dentro))} "
                f"dentro {contrai(nome)} e tranca a porta com bancos e vigas.", motivo="os mortos tomaram as ruas", n=len(dentro))

    def quebrar_portas(self, L, res, batendo=()):
        batendo = [z for z in batendo if z.estado == ZUMBI]
        no_reduto = [p for p in self.vivos_em(L.id) if p.reduto]
        so_reduto = bool(no_reduto) and all(p.reduto for p in self.vivos_em(L.id) if p.abrigo)
        if so_reduto and L.reduto_nome and L.reduto_hp > 0 and batendo:
            L.reduto_hp -= len(batendo) * self.nivel_porta()
            if L.reduto_hp <= 0:
                presos = [p for p in self.vivos_em(L.id) if p.reduto]
                for p in presos:
                    p.abrigo, p.reduto = False, False
                self.ev("reduto_cai", L.id, presos[:1], f"A porta {contrai(L.reduto_nome)} em {L.nome} cede. Lá dentro "
                        f"{'estava' if len(presos) == 1 else 'estavam'} {self.pessoas(len(presos))}.", n=len(presos))
            return
        while True:
            inteiras = L.casas - L.quebradas
            if inteiras <= 0:
                break
            hp = C.PORTA_BARRICADA if L.barricadas > L.quebradas else C.PORTA_CASA
            if L.dano_portas < hp:
                break
            L.dano_portas -= hp
            L.quebradas += 1
            dentro = [p for p in self.vivos_em(L.id) if (p.abrigo or p.cela) and not p.reduto and not p.escondido]
            casa = self.amostra(dentro, C.GENTE_POR_CASA)
            if not casa:
                break
            for p in casa:
                p.abrigo = p.cela = False
            self.barulho(L, 3)
            z = batendo.pop(0) if batendo else None
            if z is None:
                continue
            # a porta cede: quem está dentro não tem para onde correr
            lutadores = [p for p in casa if p.classe >= 1][:4]
            if lutadores:
                self.luta_time(lutadores, z, L, res, len(self.Zin[L.id]))
            if z.estado == ZUMBI:
                for v in [p for p in casa if p.estado == VIVO]:
                    if self.r() < 0.75:
                        self.atacado(v, L, res, 0)
                batendo.append(z)

    def luta_aberta(self, vivos, zs, L, contexto, destino=None):
        """Luta fora de muros: cada morto contra um time; mortos sem time pegam quem não luta."""
        res = {"z_mortos": 0, "mortos": 0, "mordidos": 0, "herois": []}
        vivos = [p for p in vivos if p.estado in VIVOS]
        lutam = [p for p in vivos if p.classe >= 2 and self.enfrenta(p, L, base=7) or p.classe >= 3 or
                 (p.classe == 1 and self.enfrenta(p, L, base=10))]
        civis = [p for p in vivos if p not in set(lutam)]
        civis.sort(key=lambda q: (0 if (q.idade < 12 or q.idade > 60) else 1, q.id))   # os mais lentos primeiro
        zs = [z for z in zs if z.estado == ZUMBI]
        ne = min(len(zs), len(lutam))
        times = [[] for _ in range(ne)]
        for i, p in enumerate(self.amostra(lutam, len(lutam))):
            if i < ne * 4:
                times[i % ne].append(p)
        for z, time in zip(zs[:ne], times):
            self.luta_time(time, z, L, res, len(zs), destino)
        for z in zs[ne:]:
            for _ in range(2 if self.r() < 0.5 else 1):
                if z.estado != ZUMBI or not civis:
                    break
                v = civis.pop(0)
                if v.estado == VIVO:
                    lid = L.id if L else None
                    if self.r() < 0.5:
                        self.morrer(v, "morto pelos mortos-vivos", lid, 0.8, destino)
                        res["mortos"] += 1
                    else:
                        self.morder(v, lid)
                        res["mordidos"] += 1
        if L is not None:
            res["herois"] = res["herois"][:1]
        return res

    def resumo_luta(self, res):
        p = []
        if res.get("mortos"):
            p.append(f"{self.pessoas(res['mortos'], 'vivo morre', 'vivos morrem')}")
        if res.get("mordidos"):
            p.append(f"{self.pessoas(res['mordidos'], 'é mordido', 'são mordidos')}".replace("1 é", "1 é"))
        if res.get("z_mortos"):
            p.append(f"{self.pessoas(res['z_mortos'], 'morto-vivo cai', 'mortos-vivos caem')}")
        txt = (", ".join(p[:-1]) + " e " + p[-1]) if len(p) > 1 else (p[0] if p else "ninguém cai")
        return txt[0].upper() + txt[1:] + "."

    # ------------------------------------------------------------------ bandos sem presa vão atrás do cheiro
    def alvo_por_cheiro(self, lid):
        L = self.L[lid]
        best, bs = None, 0.0
        for T in self.L.values():
            gente = sum(1 for i in self.H[T.id] if not self.P[i].escondido and self.P[i].cheiro < self.h) + len(self.Fora[T.id])
            if T.id == lid:
                continue
            d = math.hypot(T.x - L.x, T.y - L.y)
            ruido = T.ruido if self.h - T.barulho <= 3 else 0.0
            raio_cheiro = C.CHEIRO_KM * (1.4 if self.nivel >= 3 else 1.0)
            raio_ruido = C.RUIDO_KM_POR_PONTO * ruido
            if not ((gente and d <= raio_cheiro) or (ruido and d <= raio_ruido)):
                continue
            s = (math.sqrt(gente) if d <= raio_cheiro else 0) + ruido * 0.8
            s = s / (1 + d) ** 1.3
            if s > bs:
                best, bs = T.id, s
        return best

    def partir(self, lid):
        if self.geada and self.estacao() == "inverno":
            return
        zs = sorted(self.Zin[lid])
        if not zs:
            return
        alvo = self.alvo_por_cheiro(lid)
        if alvo is None:
            # sem cheiro nem ruído: parte do bando sai vagando pela ilha; pode achar alguém, ou não
            if self.r() > C.VAGA_HORA or not self.adj[lid]:
                return       # no ilhéu não há estrada: os mortos ficam presos lá
            nb, km, tipo = self.escolhe(self.adj[lid])
            vao = [z for z in zs if self.r() < C.VAGA_FRACAO]
            if not vao:
                return
            for z in vao:
                self.Zin[lid].discard(z)
                self.P[z].loc = None
            self.hordas.append({"id": self.novo_id(), "ids": vao, "de": lid, "para": nb, "km": km, "feito": 0.0,
                                "vel": C.VEL_ZUMBI_VAGA, "parada": False, "vagando": True})
            return
        else:
            if self.r() > min(0.95, C.SAIDA_BASE + 0.15 * self.nivel + 0.4):
                return
            nb = self.proximo(lid, alvo)
            km, tipo = self.aresta(lid, nb)
            vel = C.VEL_ZUMBI_CAÇA if self.km(lid, alvo) <= C.CHEIRO_KM * 1.5 else C.VEL_ZUMBI_VAGA * 2
        if nb is None:
            return
        vao = [z for z in zs if self.r() < C.SEGUE_BANDO]
        if not vao:
            return
        for z in vao:
            self.Zin[lid].discard(z)
            self.P[z].loc = None
        self.hordas.append({"id": self.novo_id(), "ids": vao, "de": lid, "para": nb, "km": km, "feito": 0.0,
                            "vel": vel, "parada": False})

    def novo_id(self):
        self.gid += 1
        return self.gid

    def andar_hordas(self):
        fica, atual = [], self.hordas
        self.hordas = []
        for hd in atual:
            hd["ids"] = [i for i in hd["ids"] if self.P[i].estado == ZUMBI]
            if not hd["ids"]:
                continue
            if hd.get("parada"):
                if self.h - hd.get("desde", self.h) > 24 * 5:   # emboscada desiste depois de uns dias
                    hd["parada"] = False
                else:
                    for g in list(self.grupos):
                        if {g["de"], g["para"]} == {hd["de"], hd["para"]} and g["m"] and self.r() < 0.8:
                            self.encontro(g, hd)
                    hd["ids"] = [i for i in hd["ids"] if self.P[i].estado == ZUMBI]
                    if hd["ids"]:
                        fica.append(hd)
                    continue
            hd["feito"] += hd["vel"]
            for g in self.grupos:
                if g.get("acabou") or {g["de"], g["para"]} != {hd["de"], hd["para"]}:
                    continue
                pos_g = g["feito"] if g["de"] == hd["de"] else g["km"] - g["feito"]
                if abs(pos_g - hd["feito"]) <= hd["vel"] + g["vel"]:
                    self.encontro(g, hd)
            hd["ids"] = [i for i in hd["ids"] if self.P[i].estado == ZUMBI]
            if not hd["ids"]:
                continue
            if hd["feito"] >= hd["km"]:
                self.chegada_horda(hd)
            else:
                fica.append(hd)
        self.hordas = fica + self.hordas      # as emboscadas criadas nesta hora entram no fim

    def chegada_horda(self, hd):
        dest = hd["para"]
        L = self.L[dest]
        km, tipo = self.aresta(hd["de"], dest)
        externo = tipo != "rua"
        for i in hd["ids"]:
            self.P[i].loc = dest
        if tipo == "rua" and self.H[dest] and L.barricada_rua > 0 and not self.Zin[dest]:
            self.Zout[dest] |= set(hd["ids"])
            L.cerco_rua = True
            return
        if self.H[dest] and L.muro > 0 and externo and L.portao_hp > 0 and L.estado != "invadida":
            self.Zout[dest] |= set(hd["ids"])
            if L.alerta is None:
                self.aprender(L, "mortos", f"Os vigias de {L.nome} veem um bando correndo pela estrada, direto para o portão.")
        else:
            self.Zin[dest] |= set(hd["ids"])
            if not self.H[dest] and self.nivel >= 3 and self.r() < C.EMBOSCADA[self.nivel]:
                # lugar vazio: parte do bando fica esperando na estrada de saída
                viz = [nb for nb, _, t in self.adj[dest] if t == "estrada"]
                if viz:
                    nb = self.escolhe(viz)
                    km2, _ = self.aresta(dest, nb)
                    ids = [i for i in hd["ids"] if self.r() < 0.6]
                    if ids:
                        for i in ids:
                            self.Zin[dest].discard(i)
                            self.P[i].loc = None
                        self.hordas.append({"id": self.novo_id(), "ids": ids, "de": dest, "para": nb, "km": km2,
                                            "feito": km2 * 0.3, "vel": C.VEL_ZUMBI_CAÇA, "parada": True,
                                            "desde": self.h})

    # ------------------------------------------------------------------ grupos de vivos na estrada
    def grupo(self, gid):
        return next((g for g in self.grupos if g["id"] == gid), None)

    def sair_do_grupo(self, p):
        g = self.grupo(p.viagem)
        if g and p.id in g["m"]:
            g["m"].remove(p.id)
        p.viagem = None

    def partir_grupo(self, membros, de, para, tipo, carga=0.0, sabe=None, motivo=None):
        if not membros or para is None or para == de:
            return None
        nb = self.proximo(de, para)
        if nb is None:
            return None
        km, _ = self.aresta(de, nb)
        vel = (C.VEL_CAVALO if self.L[de].cavalos >= 1 else C.VEL_HUMANO) if tipo == "mensageiro" else \
            (C.VEL_CARROCA if tipo in ("comercio", "retorno") else C.VEL_HUMANO)
        g = {"id": self.novo_id(), "m": [p.id for p in membros], "de": de, "para": nb, "destino": para, "km": km,
             "feito": 0.0, "vel": vel, "tipo": tipo, "carga": carga, "sabe": sorted(sabe or self.L[de].sabe),
             "holofote": any(p.holofote for p in membros), "motivo": motivo}
        for p in membros:
            self.H[de].discard(p.id)
            p.loc, p.viagem, p.abrigo = None, g["id"], False
        self.grupos.append(g)
        return g

    def encontro(self, g, hd):
        vivos = [self.P[i] for i in g["m"] if self.P[i].estado in VIVOS]
        zs = [self.P[i] for i in hd["ids"] if self.P[i].estado == ZUMBI]
        if not vivos or not zs:
            return
        if hd.get("parada") is False and self.r() > 0.85:
            return
        if all(p.cheiro >= self.h for p in vivos) and self.r() < 0.7:
            return      # todos com o cheiro dos mortos: o bando passa ao lado
        res = self.luta_aberta(vivos, zs, None, "estrada", destino=lambda q: hd["ids"].append(q.id))
        g["m"] = [i for i in g["m"] if self.P[i].estado in VIVOS]
        if g["tipo"] == "mensageiro" and not [i for i in g["m"] if self.P[i].estado in VIVOS]:
            self.ev("mensageiro", None, vivos[:1], f"O mensageiro que saiu de {self.L[g['de']].nome} rumo a "
                    f"{self.L[g['destino']].nome} é alcançado pelos mortos na estrada. A notícia não chega.")
            return
        if res["mortos"] + res["mordidos"] >= 1 and (g.get("holofote") or len(vivos) >= 4 or g["tipo"] == "mensageiro"):
            quem = self.L[g["de"]].nome
            self.ev("emboscada" if hd.get("parada") else "estrada", None, [self.P[i] for i in g["m"][:3]],
                    f"Na estrada que sai de {quem}, {self.pessoas(len(vivos), 'pessoa', 'pessoas')} "
                    f"({ {'fuga': 'fugindo', 'comercio': 'com uma carroça de mercadoria', 'mensageiro': 'a cavalo', 'soldados': 'soldados', 'retorno': 'voltando'}.get(g['tipo'], 'viajando') }) "
                    f"dão de cara com {self.pessoas(len(zs), 'morto-vivo', 'mortos-vivos')}. {self.resumo_luta(res)}",
                    **{k: v for k, v in res.items() if k != "herois"})

    def andar_grupos(self):
        fica, atual = [], self.grupos
        self.grupos = []
        for g in atual:
            g["m"] = [i for i in g["m"] if self.P[i].estado in VIVOS and self.P[i].viagem == g["id"]]
            if not g["m"]:
                continue
            g["feito"] += g["vel"]
            if g["feito"] >= g["km"]:
                self.chegada_grupo(g)
                if g.get("segue"):
                    fica.append(g)
            else:
                fica.append(g)
        self.grupos = fica + self.grupos

    def chegada_grupo(self, g):
        dest = g["para"]
        L = self.L[dest]
        membros = [self.P[i] for i in g["m"]]
        g["segue"] = False
        sabe_de = set(g["sabe"])
        # chegou ao destino intermediário: se não é o destino final e o lugar não oferece abrigo, segue viagem
        km_, tipo_ = self.aresta(g["de"], dest)
        volta_pra_casa = g["tipo"] == "retorno" and g.get("casa") == dest
        if tipo_ == "rua" and dest == g["destino"] and not self.Zin[dest] and not volta_pra_casa:
            for p in membros:
                self.entrar(p, dest)
            return
        # quem volta para a própria cidade passa pelos portões dela (o portão da capital conhece os seus);
        # só o lugar murado de fora obriga a parar no portão
        mesma_cidade = g.get("casa") in M.CAPITAL and dest in M.CAPITAL
        if dest != g["destino"] and L.muro > 0 and tipo_ != "rua" and self.H[dest] and not self.Zin[dest] \
                and g["tipo"] in ("fuga", "retorno") and not (g["tipo"] == "retorno" and mesma_cidade):
            # ninguém atravessa um lugar murado sem passar pelo portão: ou entra, ou fica do lado de fora
            g["destino"] = dest
        if dest != g["destino"]:
            nb = self.proximo(dest, g["destino"])
            km, _ = self.aresta(dest, nb)
            if (self.H[dest] or self.Zin[dest]) and "mortos" in sabe_de:
                self.ensinar(L, {"mortos"}, "Gente de passagem")
            g.update({"de": dest, "para": nb, "km": km, "feito": 0.0, "segue": True})
            if self.Zin[dest] and not self.H[dest]:
                # passar por um lugar tomado: os mortos de lá vêm atrás
                zs = [self.P[i] for i in self.amostra(sorted(self.Zin[dest]), 6)]
                res = self.luta_aberta(membros, zs, L, "passagem")
                g["m"] = [i for i in g["m"] if self.P[i].estado in VIVOS]
            return
        # destino final
        if g["tipo"] == "barco":
            L.comida += g["carga"]
            for p in membros:
                self.entrar(p, dest)
            L.sabe |= set(g["sabe"])
            if L.alerta is None:
                L.alerta = self.h
            if L.lider is None or self.lider(L) is None:
                self.novo_lider(L, "os primeiros a desembarcar precisavam de alguém no comando")
            return
        if g["tipo"] == "expedicao":
            zs = [self.P[i] for i in sorted(self.Zin[dest])]
            n0 = len(membros)
            res = self.luta_aberta(membros, zs[:max(1, int(len(zs) * 0.4))], L, "expedicao") if zs else \
                {"z_mortos": 0, "mortos": 0, "mordidos": 0, "herois": []}
            vivos = [p for p in membros if p.estado in VIVOS]
            casa_ = self.L[g["casa"]]
            por_homem = C.EXP_CARGA_CARROCA if casa_.cavalos + casa_.gado >= 2 else C.EXP_CARGA_HOMEM
            carga = min(L.comida, len(vivos) * por_homem)
            L.comida -= carga
            casa = self.L[g["casa"]]
            self.ev("expedicao", dest, vivos[:1], f"A expedição de {casa.nome} chega a {L.nome}"
                    + (f" e encontra {self.pessoas(len(zs), 'morto-vivo', 'mortos-vivos')}. {self.resumo_luta(res)}" if zs else ".")
                    + (f" Voltam {len(vivos)} de {n0}, com {int(carga)} rações." if vivos else " Ninguém volta."),
                    **{k: v for k, v in res.items() if k != "herois"})
            if vivos:
                for p in vivos:
                    p.viagem = None
                g2 = self.partir_grupo(vivos, dest, g["casa"], "retorno", carga=carga)
                if g2:
                    g2["casa"] = g["casa"]
                    for p in vivos:
                        self.H[dest].discard(p.id)
            return
        if g["tipo"] == "retorno" and g.get("casa") == dest:
            L.comida += g["carga"]
            for p in membros:
                if p.estado == MORDIDO and not p.esconde and "mordida" in L.sabe:
                    self.entrar(p, dest)
                    self.aplicar_politica_mordido(p, L, achado="na volta")
                else:
                    self.entrar(p, dest)
            return
        if g["tipo"] == "colonos" and not self.H[dest]:
            if self.Zin[dest]:
                zs = [self.P[i] for i in sorted(self.Zin[dest])]
                res = self.luta_aberta(membros, zs, L, "colonos")
                membros = [p for p in membros if p.estado in VIVOS]
            else:
                res = None
            if membros and not self.Zin[dest]:
                L.comida += g.get("carga", 0.0)
                for p in membros:
                    self.entrar(p, dest)
                L.sabe |= set(g["sabe"])
                L.alerta = L.alerta or self.h
                L.estado = "normal"
                L.medo = 30.0
                L.reduto_nome = None
                if "colonia" not in L.ideias:
                    L.ideias.append("colonia")
                ld = self.P[g["chefe"]] if g.get("chefe") is not None else None
                if ld is not None and ld.estado in VIVOS and ld.loc == dest:
                    L.lider = ld.id
                else:
                    self.novo_lider(L, "os colonos precisavam de alguém no comando")
                self.ev("colonia_chega", dest, membros[:1], f"{self.pessoas(len(membros), 'colono chega', 'colonos chegam')} a "
                        f"{L.nome}, vazia desde que os mortos passaram. "
                        + (self.resumo_luta(res) + " " if res else "") + "Os campos ainda estão lá.", n=len(membros))
                return
            if membros:
                outro = self.refugio(dest, membros)
                if outro:
                    self.partir_grupo_existente(g, dest, outro)
            return
        if self.Zin[dest] and not self.H[dest]:
            zs = [self.P[i] for i in self.amostra(sorted(self.Zin[dest]), 8)]
            self.luta_aberta(membros, zs, L, "chegada")
            vivos = [p for p in membros if p.estado in VIVOS]
            if vivos:
                outro = self.refugio(dest, vivos)
                if outro:
                    self.partir_grupo_existente(g, dest, outro)
            return
        if g["tipo"] == "mensageiro":
            for p in membros:
                self.entrar(p, dest)
            self.ensinar(L, sabe_de, f"Um mensageiro a cavalo")
            if g.get("pedido"):
                self.pedido_de_ajuda(L, g["pedido"])
            return
        if g["tipo"] == "comercio":
            L.comida += g["carga"]
            for p in membros:
                self.entrar(p, dest)
            if sabe_de - L.sabe:
                self.ensinar(L, sabe_de, "Um mercador")
            return
        if g["tipo"] == "soldados":
            for p in membros:
                self.entrar(p, dest)
            self.ev("reforco", dest, membros[:1], f"Chegam a {L.nome} {self.pessoas(len(membros), 'soldado', 'soldados')} "
                    f"mandados pelo rei.", n=len(membros))
            return
        # refugiados ou retorno: o portão decide
        self.no_portao(g, membros, L)

    def partir_grupo_existente(self, g, de, para):
        nb = self.proximo(de, para)
        if nb is None:
            return
        km, _ = self.aresta(de, nb)
        g.update({"de": de, "para": nb, "destino": para, "km": km, "feito": 0.0, "segue": True})

    def embarcar(self, L, membros):
        T = self.L["ilheu"]
        km = math.hypot(T.x - L.x, T.y - L.y)
        g = {"id": self.novo_id(), "m": [p.id for p in membros], "de": L.id, "para": "ilheu", "destino": "ilheu", "km": km,
             "feito": 0.0, "vel": 5.0, "tipo": "barco", "carga": min(L.comida * 0.1, len(membros) * 10.0),
             "sabe": sorted(L.sabe), "holofote": any(p.holofote for p in membros), "motivo": "fuga pelo mar"}
        L.comida -= g["carga"]
        for p in membros:
            self.H[L.id].discard(p.id)
            p.loc, p.viagem, p.abrigo, p.escondido, p.reduto = None, g["id"], False, False, False
        self.grupos.append(g)

    def entrar(self, p, lid):
        p.viagem, p.loc, p.abrigo, p.reduto = None, lid, False, False
        self.H[lid].add(p.id)

    def no_portao(self, g, membros, L):
        pol = L.pol["portao"] if L.muro > 0 else "aberto"
        ld = self.lider(L)
        sabe = set(g["sabe"])
        if not self.H[L.id]:
            for p in membros:
                self.entrar(p, L.id)
            return
        if pol == "fechado" and L.estado != "invadida":
            dentro_parentes = [(p, q) for p in membros for q in self.parentes(p) if q.loc == L.id and q.estado in VIVOS]
            self._recusas.setdefault(L.id, []).append((membros, dentro_parentes, ld))
            outro = self.refugio(L.id, membros, excluir={L.id})
            if outro:
                self.partir_grupo_existente(g, L.id, outro)
            else:
                g["segue"] = False
                for p in membros:              # ficam acampados do lado de fora, sem muro
                    p.viagem, p.loc, p.abrigo = None, L.id, False
                    self.Fora[L.id].add(p.id)
            if sabe - L.sabe:
                self.ensinar(L, sabe, "Os que ficaram do lado de fora gritam")
            return
        if pol == "quarentena" and L.estado != "invadida":
            for p in membros:
                p.viagem, p.loc, p.abrigo = None, L.id, False
                self.Fora[L.id].add(p.id)
                self.quarentena[p.id] = self.h
            if sabe - L.sabe:
                self.ensinar(L, sabe, "Os que esperam do lado de fora")
            return
        barrados = []
        for p in membros:
            if p.estado == MORDIDO:
                visto = (not p.esconde) or (pol == "inspecao" and self.r() < (0.9 if "caes" in L.ideias else C.DETECTA_INSPECAO))
                if visto and "mordida" in L.sabe:
                    barrados.append(p)
                    continue
            self.entrar(p, L.id)
        for p in barrados:
            self.entrar(p, L.id)
            self.aplicar_politica_mordido(p, L, achado="no portão")
        if sabe - L.sabe:
            self.ensinar(L, sabe, "Os refugiados")
        if len(membros) >= 20 and L.tipo != "aldeia":
            self.ev("refugiados", L.id, [], f"{self.pessoas(len(membros), 'refugiado entra', 'refugiados entram')} em {L.nome}.",
                    n=len(membros))

    def refugio(self, de, membros, excluir=()):
        """Escolhe o lugar mais seguro alcançável: muro, gente, comida, sem mortos dentro."""
        melhor, bs = None, -1e9
        for T in self.L.values():
            if T.id in excluir or T.id == de or self.Zin[T.id] or not self.H[T.id]:
                continue
            if T.tipo == "cidadela":
                continue
            d = self.km(de, T.id)
            if d > 40:
                continue
            s = T.muro * 12 + math.log1p(len(self.H[T.id])) * 3 - d * 0.5 - len(self.Zout[T.id]) * 0.3 \
                - (8 if T.pol["portao"] == "fechado" else 0)
            if s > bs:
                melhor, bs = T.id, s
        return melhor

    # ------------------------------------------------------------------ vivos reagem
    def registrar_recusas(self):
        for lid, lista in sorted(self._recusas.items()):
            L = self.L[lid]
            ld = lista[-1][2]
            n = sum(len(m) for m, _, _ in lista)
            pares = [par for _, ps, _ in lista for par in ps]
            idx = self.ev("recusa", lid, [ld] + lista[0][0][:2],
                          f"{self.pessoas(n, 'pessoa chega', 'pessoas chegam')} ao portão de {L.nome} fugindo. "
                          f"{self.nm(ld) if ld else 'O portão'} não abre."
                          + (f" Do lado de dentro, {self.nm(pares[0][1])} ouve {self.relacao(pares[0][1], pares[0][0])} "
                             f"chamando lá fora." if pares else ""),
                          motivo=f"portão fechado por ordem de {self.nm(ld)}" if ld else "portão fechado", n=n)
            if ld:
                for p, q in pares:
                    self.guardar_rancor(q, ld, 45, idx)
                for membros, _, _ in lista:
                    for p in membros:
                        self.guardar_rancor(p, ld, 35, idx)
        self._recusas = {}

    def soltar_quarentena(self):
        if not self.quarentena:
            return
        prontos = [pid for pid, h0 in self.quarentena.items() if self.h - h0 >= 24]
        entraram = Counter()
        for pid in sorted(prontos):
            del self.quarentena[pid]
            p = self.P[pid]
            if p.estado != VIVO or p.loc is None or pid not in self.Fora[p.loc]:
                continue
            L = self.L[p.loc]
            if self.Zin[L.id]:
                continue
            self.Fora[L.id].discard(pid)
            self.H[L.id].add(pid)
            entraram[L.id] += 1
        for lid, n in entraram.items():
            if n >= 10:
                self.ev("quarentena", lid, [], f"Depois de um dia inteiro esperando do lado de fora, "
                        f"{self.pessoas(n, 'pessoa entra', 'pessoas entram')} em {self.L[lid].nome}.", n=n)

    def vivos_reagem(self):
        self.registrar_recusas()
        self.soltar_quarentena()
        if self.hora() in (6, 18):
            self.revista()
        hora = self.hora()
        for lid in sorted(self.L):
            L = self.L[lid]
            if not self.H[lid]:
                continue
            if not self.Zin[lid]:
                saiu = [self.P[i] for i in sorted(self.H[lid]) if self.P[i].escondido]
                if saiu:
                    for q in saiu:
                        q.escondido = False
                    if len(saiu) >= 3:
                        self.ev("esconderijo", lid, saiu[:1], f"Os mortos vão embora de {L.nome}. "
                                f"{self.pessoas(len(saiu), 'pessoa sai', 'pessoas saem')} de porões e sótãos, onde ficaram "
                                f"sem respirar enquanto eles passavam.", n=len(saiu))
                if L.reduto_nome and any(self.P[i].reduto for i in self.H[lid]):
                    for i in self.H[lid]:
                        self.P[i].reduto = False
                    self.ev("reduto_sai", lid, [], f"Os mortos deixam {L.nome}. Quem estava trancado {contrai(L.reduto_nome, 'em')} sai.")
                    L.reduto_nome = None
            if not self.Zin[lid] and hora in (21, 6):
                noite = hora == 21
                for pid in self.H[lid]:
                    q = self.P[pid]
                    if q.cela:
                        continue
                    # à noite todos vão para casa, menos a guarda; de dia saem para trabalhar
                    q.abrigo = noite and not (q.classe >= 3 and self.r() < 0.4) or (q.estado == MORDIDO and q.esconde)
            if self.Zin[lid]:
                self.panico(L)
            elif L.alerta is not None:
                self.preparar(L)
            self.mordidos_decidem(L)
        self.rei_decide()

    def panico(self, L):
        vivos = self.vivos_em(L.id)
        expostos = [p for p in vivos if not p.abrigo and not p.cela and not p.escondido]
        cap = max(0, (L.casas - L.quebradas) * C.GENTE_POR_CASA - sum(1 for p in vivos if p.abrigo))
        # famílias decidem: correr para fora ou trancar-se em casa
        fams = defaultdict(list)
        for p in expostos:
            fams[p.fam].append(p)
        saem = []
        disfarce_novo = []
        for p in expostos:
            if p.escondido or p.classe >= 3:
                continue
            if p.a["astucia"] + p.a.get("genio", 5) >= 15 and p.cheiro < self.h                     and self.r() < C.IDEIA_CHEIRO * math.exp(self.flags.get("cultura", {}).get("genio", 0.0)):
                p.cheiro = self.h + 72
                disfarce_novo.append(p)
        if disfarce_novo and not self.flags.get(f"cheiro_{L.id}"):
            self.flags[f"cheiro_{L.id}"] = self.h
            q = disfarce_novo[0]
            self.ev("cheiro", L.id, [q], f"Em {L.nome}, {self.nm(q)} percebe que os mortos acham as pessoas pelo cheiro. "
                    f"{self.g(q, 'Ele', 'Ela')} esfrega no corpo o sangue de um morto caído e passa a andar entre eles sem ser {self.g(q, 'notado', 'notada')}.",
                    motivo="os mortos farejam")
        for fam, ps in sorted(fams.items()):
            chefe = max(ps, key=lambda q: q.idade)
            if chefe.classe >= 3 and len(ps) == 1:
                continue
            entende = "mordida" in L.sabe or L.medo >= 60
            if self.r() < C.FOGE_CHANCE * (1.4 if L.tipo == "aldeia" else 0.8) * (1.0 if entende else 0.15):
                saem.append(ps)
            elif entende and cap <= 0 and self.r() < 0.15 + 0.04 * chefe.a["astucia"]:
                for p in ps:      # sem casa inteira para trancar: porão, sótão, palheiro
                    p.escondido = True
                    p.esc_h = self.h
            elif cap > 0:
                for p in ps:
                    if cap > 0 and self.r() < 0.7:
                        p.abrigo = True
                        cap -= 1
        if saem:
            n = 0
            destinos = Counter()
            for ps in saem:
                para = self.refugio(L.id, ps)
                if para is None:
                    continue
                # a capital: quem está num bairro tenta a cidadela antes
                if L.tipo == "bairro" and self.L["cidadela"].pol["portao"] != "fechado" and self.H["cidadela"] \
                        and not self.Zin["cidadela"]:
                    para = "cidadela"
                if self.Zout[L.id]:
                    zs = [self.P[i] for i in self.amostra(sorted(self.Zout[L.id]), 3)]
                    self.luta_aberta(ps, zs, L, "saida")
                    ps = [p for p in ps if p.estado in VIVOS]
                if ps:
                    g = self.partir_grupo(ps, L.id, para, "fuga")
                    n += len(ps)
                    soltos = sorted(self.Zin[L.id])
                    k = int(self.rng.binomial(len(soltos), C.PERSEGUE)) if g and soltos else 0
                    k = min(k, len(ps) * 2)
                    if k:
                        atras = self.amostra(soltos, k)
                        for zid in atras:
                            self.Zin[L.id].discard(zid)
                            self.P[zid].loc = None
                        self.hordas.append({"id": self.novo_id(), "ids": atras, "de": L.id, "para": g["para"], "km": g["km"],
                                            "feito": 0.0, "vel": C.VEL_ZUMBI_CAÇA, "parada": False})
                    destinos[self.L[para].nome] += len(ps)
            if n >= 8:
                d = ", ".join(f"{v} para {k}" for k, v in destinos.most_common(3))
                self.ev("fuga", L.id, [], f"{self.pessoas(n, 'pessoa foge', 'pessoas fogem')} de {L.nome} no meio do ataque: {d}.",
                        n=n)

    def preparar(self, L):
        """Lugar em alerta, ainda sem mortos dentro: barricadas, armas, mensageiros e, se for fraco, retirada."""
        ld = self.lider(L)
        perto = [h for h in self.hordas if h["para"] == L.id] + [None] * len(self.Zout[L.id])
        viu = L.invadida_em is not None or bool(self.Zout[L.id]) or any(h["para"] == L.id for h in self.hordas)
        if ld and not L.pediu_ajuda and L.tipo not in ("cidadela", "bairro") and (viu or L.tipo in ("vila", "castelo", "mosteiro")):
            L.pediu_ajuda = True
            cav = [p for p in self.adultos(L.id) if p.classe >= 1 and p.idade < 45 and not p.holofote]
            if cav:
                m = self.escolhe(cav)
                g = self.partir_grupo([m], L.id, "porta", "mensageiro", sabe=L.sabe)
                if g:
                    g["pedido"] = L.id
        if "mordida" in L.sabe and L.tipo == "aldeia" and ld:
            ameaca = sum(len(h["ids"]) for h in self.hordas if h["para"] == L.id and h["km"] - h["feito"] <= 8)
            perto = sum(len(self.Zin[nb]) for nb, km, _ in self.adj[L.id] if km <= 7 and not self.H[nb])
            if (ameaca >= 3 or perto >= 5) and self.r() < 0.08 + 0.02 * (10 - ld.a["coragem"]):
                destino = self.refugio(L.id, self.vivos_em(L.id))
                if destino:
                    todos = [p for p in self.vivos_em(L.id) if not p.cela]
                    self.partir_grupo(todos, L.id, destino, "fuga", motivo="retirada")
                    L.estado = "vazia"
                    self.ev("evacuacao", L.id, [ld], f"{self.nm(ld)} manda esvaziar {L.nome}: "
                            f"{self.pessoas(len(todos))} saem para {self.L[destino].nome} levando o que conseguem carregar.",
                            motivo="mortos perto" if ameaca else "vizinhos caídos", n=len(todos))
                    return

    def mordidos_decidem(self, L):
        for pid in sorted(self.mordidos):
            p = self.P[pid]
            if p.loc != L.id or p.viagem is not None or p.esconde is not None or pid not in self.H[L.id]:
                continue
            if "mordida" not in L.sabe:
                p.esconde = False          # não sabe que é grave: conta, e é cuidado em casa
                p.abrigo = True
                continue
            pol = L.pol["mordidos"]
            chance = C.ESCONDE_BASE - (0.2 if ("amputacao" in L.sabe or "cura" in L.sabe) else 0) \
                + {"executar": 0.35, "isolar": 0.15, "cuidar": -0.1}[pol] \
                + (10 - p.a["piedade"]) * 0.02 + (10 - p.a["lealdade"]) * 0.015 - p.a["coragem"] * 0.01
            if self.r() < clamp(chance, 0.05, 0.85):
                p.esconde = True
                p.abrigo = True
            else:
                p.esconde = False
                self.aplicar_politica_mordido(p, L, achado="contou")

    def aplicar_politica_mordido(self, p, L, achado):
        pol = L.pol["mordidos"]
        ld = self.lider(L)
        salva = None
        if "amputacao" in L.sabe and self.r() < C.AMPUTACAO_SALVA:
            salva = "amputacao"
        elif "cura" in L.sabe and self.r() < C.CURA_SALVA:
            salva = "cura"
        if salva:
            p.estado, p.esconde, p.t_vira = VIVO, None, None
            self.mordidos.discard(p.id)
            if salva == "amputacao":
                p.classe = max(0, p.classe - 1)
                p.arma = max(0, (p.arma or 0) - 1)
            self.contas["salvos_" + salva] += 1
            if p.holofote or self.contas["salvos_" + salva] <= 2:
                self.ev("salvo", L.id, [p], f"Em {L.nome}, {self.nm(p)} é {self.g(p, 'mordido', 'mordida')} e "
                        + ("tem o braço cortado e o corte queimado em seguida. Sobrevive, sem o braço, e não vira."
                           if salva == "amputacao" else "toma o remédio amargo nas primeiras horas. Não vira."),
                        motivo=salva)
            return
        if pol == "executar":
            self.morrer(p, "executado por estar mordido", L.id)
            self.contas["executados"] += 1
            for q in self.parentes(p):
                if q.estado in VIVOS and q.loc == L.id and ld and q.a["piedade"] >= 6:
                    self.guardar_rancor(q, ld, 25, None, f"a execução de {self.relacao(q, p)}, {self.nm(p)}")
            if p.holofote or self.contas["executados"] <= 2 or (ld and self.contas["executados"] % 25 == 0):
                self.ev("execucao", L.id, [p, ld], f"Em {L.nome}, {self.nm(p)} é {self.g(p, 'executado', 'executada')} "
                        f"antes de virar.", motivo=f"decreto de {self.nm(ld)}" if ld else "decreto")
        elif pol == "isolar":
            p.cela = True
            p.abrigo = False
        else:
            p.abrigo = True

    # ------------------------------------------------------------------ o rei
    def rei_decide(self):
        C_ = self.L["cidadela"]
        rei = self.lider(C_)
        if rei is None or "mortos" not in C_.sabe or self.flags.get("rei_fechou"):
            return
        self.flags["rei_fechou"] = self.h
        bairros = [self.L[b] for b in sorted(M.CAPITAL)]
        for B in bairros:
            B.sabe |= C_.sabe
            if B.alerta is None:
                B.alerta = self.h
            self.decidir_politica(B, "por ordem do rei")
        abre = rei.a["piedade"] >= 7 and rei.a["astucia"] <= 6
        for b in sorted(M.PORTOES_DA_CIDADE):
            self.L[b].pol["portao"] = "inspecao" if abre else "fechado"
        self.ev("rei", "cidadela", [rei], f"{self.nm(rei)} manda fechar Alvor. "
                + ("Os portões da cidade só abrem para quem passar pela revista."
                   if abre else "Ninguém mais entra na capital, nem quem vem fugindo."),
                motivo="a notícia dos mortos chegou à corte")

    def pedido_de_ajuda(self, L_capital_bairro, origem):
        rei = self.lider(self.L["cidadela"])
        O = self.L[origem]
        if rei is None or self.flags.get(f"ajuda_{origem}"):
            return
        self.flags[f"ajuda_{origem}"] = self.h
        manda = rei.a["piedade"] + rei.a["coragem"] >= 12 and O.tipo in ("vila", "castelo", "mosteiro")
        if manda:
            sold = [p for p in self.vivos_em("cidadela") + self.vivos_em("porta") if p.papel == "soldado" and p.estado == VIVO]
            ida = self.amostra(sold, min(30, len(sold) // 4))
            for p in ida:
                self.H[p.loc].discard(p.id)
                p.loc = "porta"
                self.H["porta"].add(p.id)
            if ida:
                self.partir_grupo(ida, "porta", origem, "soldados")
                self.ev("rei", "cidadela", [rei], f"{self.nm(rei)} manda {len(ida)} soldados para {O.nome}, "
                        f"que pediu socorro.", motivo=f"pedido de socorro de {O.nome}")
        elif O.tipo in ("vila", "castelo", "mosteiro"):
            self.ev("rei", "cidadela", [rei], f"O pedido de socorro de {O.nome} chega à corte. {self.nm(rei)} não manda ninguém.",
                    motivo="o rei guarda os soldados para a capital")

    # ------------------------------------------------------------------ o dia: economia, obras, intrigas
    def novo_dia(self):
        est = self.estacao()
        self.geada = self.r() < (C.FROST_INVERNO if est == "inverno" else C.FROST_OUTONO if est == "outono" else 0)
        if self.flags.get("navio") is not None:
            dias = (self.h - self.flags["navio"]) / 24
            for d, nv, txt in C.APRENDE:
                if dias >= d and self.nivel < nv:
                    self.nivel = nv
                    self.ev("aprendem", None, [], txt, nivel=nv)
        self.apodrecer()
        for L in self.L.values():
            if self.H[L.id]:
                self.economia(L)
        self.acampados()
        I.do_dia(self)
        HQ.do_dia(self)
        self.intrigas()
        self.diario.append({"dia": self.dia(), "lugares": {l: [len(self.H[l]), len(self.Zin[l]) + len(self.Zout[l])]
                                                         for l in self.L if self.H[l] or self.Zin[l] or self.Zout[l]}})

    def apodrecer(self):
        """O prazo de cada morto-vivo. Comida reparte o ganho entre os mortos do lugar; o inverno conserva."""
        if self.flags.get("navio") is None:
            return
        pool = self.flags.get("comida_z", {})
        for lid in sorted(pool):
            zs = sorted(self.Zin[lid] | self.Zout[lid])
            if zs and pool[lid] > 0:
                ganho = min(C.PODRE_GANHO_MAX_DIA, pool[lid] / len(zs) * C.PODRE_POR_VITIMA) * 24
                for i in zs:
                    z = self.P[i]
                    if z.zfim is not None:
                        z.zfim += ganho
        self.flags["comida_z"] = {}
        inverno = self.estacao() == "inverno"
        ids = sorted(set().union(*self.Zin.values(), *self.Zout.values(), *[set(h["ids"]) for h in self.hordas]))
        caem = collections.Counter()
        for i in ids:
            z = self.P[i]
            if z.estado != ZUMBI:
                continue
            if z.zfim is None:
                a, moda, b = C.PODRIDAO_DIAS
                z.zfim = (z.morte if z.morte is not None else self.h) + float(self.rng.triangular(a, moda, b)) * 24
            if inverno:
                z.zfim += 12          # no frio o corpo conserva: o prazo anda pela metade
            if z.zfim <= self.h:
                onde = z.loc
                if onde is None:
                    for h in self.hordas:
                        if i in h["ids"]:
                            h["ids"].remove(i)
                            onde = h["para"]
                            break
                self.destruir(z, "apodreceu de vez")
                self.contas["apodreceram"] += 1
                caem[onde] += 1
        n = sum(caem.values())
        if not n:
            return
        if not self.flags.get("podre_primeiro"):
            self.flags["podre_primeiro"] = self.h
            dias = (self.h - self.flags["navio"]) // 24
            self.ev("apodrece", None, [], f"{dias} dias depois do navio, os mortos-vivos começam a cair sozinhos. A pele "
                    f"solta dos ossos, as pernas não sustentam mais o corpo. {self.pessoas(n, 'morto cai', 'mortos caem')} "
                    f"hoje e não se levanta{'m' if n > 1 else ''} mais.", n=n)
            self.flags["podre_base"] = len(ids)
            return
        # marcos: metade caiu, um quarto de pé, cem de pé, dez de pé, nenhum de pé (contando também os destruídos)
        resta = len(ids) - n
        base_n = self.flags.get("podre_base", len(ids))
        feitos = self.flags.setdefault("podre_marcos", [])
        for marco, limite, txt in (("metade", base_n // 2, "Metade dos mortos que andavam quando a podridão começou já caiu."),
                                   ("quarto", base_n // 4, "Só um quarto dos mortos ainda anda."),
                                   ("cem", 100, "Restam menos de cem mortos-vivos de pé em toda a ilha."),
                                   ("dez", 10, "Restam menos de dez mortos-vivos de pé em toda a ilha.")):
            if marco not in feitos and resta < limite:
                feitos.append(marco)
                lugares = ", ".join(self.L[l].nome for l, _ in caem.most_common(2) if l in self.L)
                self.ev("apodrece", None, [], f"{txt} Hoje {'cai mais um' if n == 1 else f'caem mais {n}'}, podres"
                        + (f", a maior parte em {lugares}" if lugares else "") + f". Restam {resta}.", n=n, resta=resta,
                        marco=marco)

    def acampados(self):
        for lid in sorted(self.Fora):
            if not self.Fora[lid]:
                continue
            L = self.L[lid]
            ps = [self.P[i] for i in sorted(self.Fora[lid]) if i not in self.quarentena]
            if not ps:
                continue
            ld = self.lider(L)
            if L.pol["portao"] not in ("fechado", "quarentena") or (ld and ld.a["piedade"] >= 7 and self.r() < 0.3):
                for p in ps:
                    self.Fora[lid].discard(p.id)
                    self.H[lid].add(p.id)
                self.ev("portao_abre", lid, [ld], f"{self.nm(ld) if ld else 'O portão'} deixa entrar os "
                        f"{self.pessoas(len(ps))} que esperavam do lado de fora de {L.nome}.", n=len(ps))
            elif self.r() < 0.5:
                outro = self.refugio(lid, ps, excluir={lid})
                if outro:
                    for p in ps:
                        self.Fora[lid].discard(p.id)
                        self.H[lid].add(p.id)
                    self.partir_grupo(ps, lid, outro, "fuga")

    def seguro(self, L):
        if self.Zin[L.id] or self.Zout[L.id]:
            return False
        return not any(h["para"] == L.id and h["feito"] > h["km"] - 6 for h in self.hordas)

    def economia(self, L):
        vivos = self.vivos_em(L.id)
        n = len(vivos)
        est = self.estacao()
        mult = INV = C.INVERNO_MULT if est == "inverno" else 1.0
        if (self.dia() - 1) % 365 <= C.COLHEITA_DIAS[1]:     # toda colheita de setembro, não só a primeira
            mult = C.COLHEITA_MULT
        prod = 0.0
        if not self.seguro(L):
            if "hortas" in L.ideias:
                prod += sum(0.35 for p in vivos if p.papel in ("campones", "pastor") and p.estado == VIVO)
            if "pesca_mar" in L.ideias:
                prod += sum(C.PRODUZ["pescador"] * 0.7 for p in vivos if p.papel == "pescador" and p.estado == VIVO)
        if "campos" in L.ideias and self.seguro(L) and L.medo < 70 and L.tipo in ("bairro", "cidadela", "vila", "castelo"):
            # lavradores improvisados: metade dos adultos sai de dia para os campos de fora, a 60% de um camponês
            prod += sum(C.PRODUZ["campones"] * C.CAMPOS_RENDE * mult for p in vivos
                        if p.estado == VIVO and 16 <= p.idade <= 60 and not p.cela and p.papel not in ("campones", "pastor", "pescador")) * 0.5
        if L.tipo == "ilheu":
            prod += sum(1.2 for p in vivos if p.estado == VIVO and 14 <= p.idade <= 65)
        elif self.seguro(L) and L.medo < 70:
            for p in vivos:
                if p.estado == VIVO and 14 <= p.idade <= 65 and not p.cela:
                    base = C.PRODUZ.get(p.papel, 0.0)
                    if "colonia" in L.ideias and p.papel not in ("pescador", "pastor"):
                        base = max(base, C.PRODUZ["campones"] * C.COLONO_RENDE)
                    if p.papel == "pastor":
                        base *= min(1.0, L.gado / max(1.0, 8.0 * sum(1 for q in vivos if q.papel == "pastor")))
                    if p.papel == "pescador":
                        prod += base * (0.6 if est == "inverno" else 1.0)
                    else:
                        prod += base * mult
            L.lenha += sum(C.LENHA_POR_LENHADOR for p in vivos if p.papel == "lenhador")
        L.comida += prod
        gasto = n * C.CONSUMO * L.pol["racao"] * (0.85 if "reorganiza" in L.ideias else 1.0)
        L.comida -= gasto
        if L.comida < 0:
            L.comida = 0.0
            L.fome += 1
        else:
            L.fome = max(0, L.fome - 1)
        if L.fome >= 7:
            mortos = []
            for q in vivos:
                fraco = q.idade < 6 or q.idade > 65
                if self.r() < (0.04 if fraco else (0.012 if L.fome >= 14 else 0.004)):
                    mortos.append(q)
            for q in mortos:
                self.morrer(q, "fome", L.id)
            if mortos:
                self.contas["fome"] += len(mortos)
                if len(mortos) >= 3:
                    self.ev("fome", L.id, mortos[:1], f"Em {L.nome}, {self.pessoas(len(mortos), 'pessoa morre', 'pessoas morrem')} "
                            f"de fome. Faz {L.fome} dias que o celeiro está vazio.", n=len(mortos))
        if (L.fome >= 2 or L.comida / max(1, n) < 3) and not self.Zin[L.id]:
            self.expedicao(L, vivos)
        dias = L.comida / max(1, n)
        L.preco = round(clamp(14 / max(0.5, dias), 0.5, 25), 2)
        ld = self.lider(L)
        if ld and dias < 12 and L.pol["racao"] == 1.0:
            L.pol["racao"] = 0.75
            self.ev("racao", L.id, [ld], f"Em {L.nome}, a comida dá para {int(dias)} dias. {self.nm(ld)} corta a ração "
                    f"para três quartos.", dias=round(dias, 1))
        elif ld and dias < 5 and L.pol["racao"] > 0.5:
            L.pol["racao"] = 0.5
            self.ev("racao", L.id, [ld], f"Em {L.nome}, sobra comida para {int(dias)} dias. A ração cai para a metade.",
                    dias=round(dias, 1))
        # portão e barricada consertados todo dia, se houver lenha e gente
        if L.muro > 0 and "mortos" in L.sabe and not L.reforcado and not self.Zin[L.id] and L.lenha >= 150:
            engenhosos = [q for q in vivos if q.estado == VIVO and 16 <= q.idade <= 70 and
                          (q.a.get("genio", 5) >= 8 or (q.a["astucia"] >= 8 and q.a.get("genio", 5) >= 6))]
            if engenhosos and self.r() < C.IDEIA_REFORCO:
                q = self.escolhe(engenhosos)
                L.reforcado = True
                L.portao_max = C.MURO[L.muro][0] * C.REFORCO_MULT
                L.portao_hp = max(0.0, L.portao_hp) + C.MURO[L.muro][0] * (C.REFORCO_MULT - 1)
                L.lenha -= 150
                self.ev("reforco_portao", L.id, [q], f"Em {L.nome}, {self.nm(q)} tem a ideia de reforçar o portão por dentro "
                        f"com troncos atravessados e as grades de ferro do celeiro. O povo trabalha a noite inteira.",
                        motivo="o medo de os mortos derrubarem o portão")
        if L.muro > 0 and not self.Zin[L.id] and L.estado != "caida":
            cheio = L.portao_max or C.MURO[L.muro][0]
            falta = cheio - max(0.0, L.portao_hp)
            if falta > 0 and L.lenha > 0:
                conserto = min(falta, C.CONSERTO_DIA, L.lenha * 3)
                L.portao_hp = max(0.0, L.portao_hp) + conserto
                L.lenha -= conserto / 3
        if L.tipo == "bairro" and "mortos" in L.sabe and not self.Zin[L.id] and L.barricada_rua < C.BARRICADA_RUA and L.lenha > 0:
            conserto = min(C.BARRICADA_RUA - L.barricada_rua, C.CONSERTO_DIA, L.lenha * 3)
            L.barricada_rua += conserto
            L.lenha -= conserto / 3
        # barricadas e paliçada: quem sabe dos mortos se prepara
        if "mortos" in L.sabe and self.seguro(L):
            falta = L.casas - L.barricadas
            pode = int(min(falta, L.lenha // C.BARRICADA_LENHA, sum(1 for p in vivos if p.classe >= 1) // 3))
            if pode > 0:
                L.barricadas += pode
                L.lenha -= pode * C.BARRICADA_LENHA
            if False:   # paliçada agora é decisão do líder, com custo e tempo (hierarquia.muralhas)
                trabalho = sum(1 for p in vivos if p.classe >= 1 and p.estado == VIVO)
                usa = min(L.lenha, trabalho * 2.0)
                L.obra += usa
                L.lenha -= usa
                if L.obra >= C.PALICADA_LENHA:
                    L.muro, L.portao_hp, L.obra = 1, C.MURO[1][0], 0.0
                    self.ev("palicada", L.id, [ld], f"{L.nome} termina uma paliçada de troncos em volta das casas. "
                            f"Foi feita pelos próprios moradores, sem ajuda de ninguém.", n=n)
            ferreiros = sum(1 for p in vivos if p.papel == "ferreiro" and p.estado == VIVO)
            L.lancas += ferreiros * C.LANCA_POR_FERREIRO
            if L.lancas >= 1:
                novos = [p for p in vivos if p.classe == 1 and p.a["coragem"] >= 5 and 16 <= p.idade <= 55]
                for p in novos[:int(L.lancas)]:
                    p.classe, p.arma = 2, 1
                    L.lancas -= 1
        # comércio: quem tem sobra manda carroça para vizinho com falta, se a estrada parece segura
        if self.seguro(L) and dias > 25 and n > 30 and L.cavalos + L.gado >= 2:
            for nb, km, tipo in self.adj[L.id]:
                T = self.L[nb]
                if tipo != "estrada" or not self.H[nb] or not self.seguro(T):
                    continue
                if T.comida / max(1, len(self.H[nb])) < 8:
                    mercs = [p for p in vivos if p.papel in ("mercador", "campones") and p.estado == VIVO and 18 <= p.idade <= 55]
                    if mercs:
                        carga = min(L.comida * 0.2, len(self.H[nb]) * 6)
                        L.comida -= carga
                        g = self.partir_grupo(self.amostra(mercs, 2), L.id, nb, "comercio", carga=carga)
                        if g and self.r() < 0.3:
                            self.ev("comercio", L.id, [], f"Uma carroça sai de {L.nome} com comida para vender em "
                                    f"{T.nome}, onde o pão já custa {T.preco:.0f} vezes o preço de antes.", carga=round(carga))
                    break

    def expedicao(self, L, vivos):
        """Sem comida, um grupo armado sai para buscar nos lugares abandonados, mesmo com os mortos por perto."""
        if self.flags.get(f"exp_{L.id}", -99) > self.h - 72:
            return
        alvos = []
        for T in self.L.values():
            if T.id == L.id or self.H[T.id] or T.comida < 150:
                continue
            d = self.km(L.id, T.id)
            if d <= 18:
                alvos.append((d + len(self.Zin[T.id]) * 0.05, T.id))
        if not alvos:
            return
        alvos.sort()
        bravos = [q for q in vivos if q.estado == VIVO and q.classe >= 2 and 16 <= q.idade <= 55 and not q.holofote
                  and q.a["coragem"] >= 5]
        if len(bravos) < 4:
            return
        precisa = len(vivos) * C.CONSUMO * 3            # comida de três dias para o lugar inteiro
        por_homem = C.EXP_CARGA_CARROCA if L.cavalos + L.gado >= 2 else C.EXP_CARGA_HOMEM
        k = int(min(len(bravos), C.EXP_MAX, max(12, precisa / por_homem)))
        ida = self.amostra(bravos, k)
        self.flags[f"exp_{L.id}"] = self.h
        g = self.partir_grupo(ida, L.id, alvos[0][1], "expedicao")
        if g:
            g["casa"] = L.id
            ld = self.lider(L)
            self.ev("expedicao", L.id, [ld] + ida[:1], f"Sem comida, {self.nm(ld) if ld else 'o povo'} manda {len(ida)} homens armados "
                    f"buscar mantimentos em {self.L[alvos[0][1]].nome}, onde não sobrou ninguém vivo.",
                    motivo=f"fome há {L.fome} dias" if L.fome else "o celeiro quase vazio", n=len(ida))

    def registrar(self):
        vivos = sum(len(s) for s in self.H.values()) + sum(len(g["m"]) for g in self.grupos) + \
            sum(len(s) for s in self.Fora.values())
        mord = len(self.mordidos)
        zs = sum(len(s) for s in self.Zin.values()) + sum(len(s) for s in self.Zout.values()) + \
            sum(len(h["ids"]) for h in self.hordas)
        self.serie.append({"h": self.h, "vivos": vivos, "mordidos": mord, "zumbis": zs})

    def checar_fim(self):
        s = self.serie[-1]
        if self.flags.get("navio") is None:
            return
        if s["vivos"] == 0:
            self.fim = "derrota"
            self.ev("fim", None, [], f"No {self.quando()}, não resta ninguém vivo no reino de Alvor.")
            return
        if s["zumbis"] == 0 and s["mordidos"] == 0 and not self.corpos and not self.porao:
            self.limpo += 1
            if self.limpo >= 72:
                self.fim = "vitoria"
                tempo = self.flags.get("ultima_baixa_z") == "apodreceu de vez"
                self.flags["fim_tipo"] = "tempo" if tempo else "luta"
                self.ev("fim", None, [], f"No {self.quando()}, fazem três dias que nenhum morto anda pela ilha"
                        + (": os últimos caíram sozinhos, podres. " if tempo else ". ")
                        + f"Restam {s['vivos']} pessoas vivas.", vivos=s["vivos"], final=self.flags["fim_tipo"])
        else:
            self.limpo = 0
        if self.h >= C.DIAS_MAX * 24 and not self.fim:
            self.fim = "horizonte"
            meses = (self.h - self.flags["navio"]) // (24 * 30)
            self.ev("fim", None, [], f"{meses} meses depois do navio, o reino tem {s['vivos']} vivos e {s['zumbis']} mortos-vivos.",
                    vivos=s["vivos"], zumbis=s["zumbis"])

    # ------------------------------------------------------------------ salvar e carregar
    def salvar(self, path):
        d = {"seed": self.seed, "h": self.h, "gid": self.gid, "seq": self.seq, "flags": self.flags, "fim": self.fim,
             "holofote": self.holofote, "nivel": self.nivel, "geada": self.geada, "limpo": self.limpo,
             "contas": dict(self.contas), "rng": self.rng.bit_generator.state,
             "P": [p.d() for p in self.P], "L": [L.d() for L in self.L.values()],
             "adj": {k: v for k, v in self.adj.items()},
             "H": {k: sorted(v) for k, v in self.H.items() if v}, "Zin": {k: sorted(v) for k, v in self.Zin.items() if v},
             "Zout": {k: sorted(v) for k, v in self.Zout.items() if v},
             "Fora": {k: sorted(v) for k, v in self.Fora.items() if v}, "mordidos": sorted(self.mordidos),
             "quarentena": {str(k): v for k, v in self.quarentena.items()},
             "grupos": self.grupos, "hordas": self.hordas, "timers": self.timers, "corpos": self.corpos,
             "porao": self.porao, "log": self.log, "serie": self.serie, "diario": self.diario}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)

    @classmethod
    def carregar(cls, path):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        m = cls()
        m.seed, m.h, m.gid, m.seq, m.flags, m.fim = d["seed"], d["h"], d["gid"], d["seq"], d["flags"], d["fim"]
        m.holofote, m.nivel, m.geada, m.limpo = d["holofote"], d["nivel"], d["geada"], d["limpo"]
        m.contas = Counter(d["contas"])
        m.rng = np.random.Generator(np.random.PCG64())
        m.rng.bit_generator.state = d["rng"]
        m.P = [Pessoa(**p) for p in d["P"]]
        for Ld in d["L"]:
            L = Lugar(**Ld)
            L.sabe = set(Ld["sabe"])
            m.L[L.id] = L
        m.adj = defaultdict(list, {k: [tuple(x) for x in v] for k, v in d["adj"].items()})
        m.H = defaultdict(set, {k: set(v) for k, v in d["H"].items()})
        m.Zin = defaultdict(set, {k: set(v) for k, v in d["Zin"].items()})
        m.Zout = defaultdict(set, {k: set(v) for k, v in d["Zout"].items()})
        m.Fora = defaultdict(set, {k: set(v) for k, v in d["Fora"].items()})
        m.mordidos = set(d["mordidos"])
        m.quarentena = {int(k): v for k, v in d.get("quarentena", {}).items()}
        m.grupos, m.hordas, m.corpos = d["grupos"], d["hordas"], d["corpos"]
        m.timers = [tuple(t) for t in d["timers"]]
        heapq.heapify(m.timers)
        m.porao = [tuple(x) for x in d["porao"]]
        m.log, m.serie, m.diario = d["log"], d["serie"], d["diario"]
        return m
