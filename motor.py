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
    def cidade(self, L):
        return [self.L[b] for b in sorted(M.CAPITAL)] if L.id in M.CAPITAL else [L]

    def novo_id(self):
        self.gid += 1
        return self.gid

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
