"""Geração do reino de Alvor: lugares, estradas, famílias, ofícios, equipamento, líderes e protagonistas."""
import math

# ---------------- lugares: id, nome, tipo, x, y (km), população alvo, muro (0 a 3), litoral
LUGARES = [
    # capital: quatro bairros e a cidadela. Ruas internas sem muro; a cidadela tem o próprio portão.
    ("cidadela", "Cidadela de Alvor", "cidadela", 13, 23, 350, 3, False),
    ("alto", "Bairro Alto", "bairro", 14, 21.5, 800, 3, False),
    ("mercado", "Bairro do Mercado", "bairro", 15.5, 24, 1000, 3, False),
    ("porta", "Bairro da Porta", "bairro", 17.5, 23.5, 700, 3, False),
    ("cais", "Cais de Alvor", "bairro", 12.5, 26, 650, 3, True),
    # vilas
    ("valverde", "Valverde", "vila", 36, 41, 1200, 2, True),
    ("pedralva", "Pedralva", "vila", 38, 22, 1000, 2, False),
    ("ribafria", "Ribafria", "vila", 32, 5, 800, 2, True),
    # castelos, mosteiro, mina
    ("penamor", "Castelo de Penamor", "castelo", 56, 12, 150, 3, False),
    ("torrevelha", "Castelo de Torre Velha", "castelo", 24, 36, 150, 3, False),
    ("mosteiro", "Mosteiro de São Brás", "mosteiro", 47, 30, 70, 1, False),
    ("mina", "Mina da Serra Negra", "mina", 50, 5, 220, 0, False),
    # aldeias
    ("lontras", "Ribeira das Lontras", "aldeia", 71, 22, 130, 0, True),
    ("gaivota", "Praia da Gaivota", "aldeia", 66, 33, 150, 0, True),
    ("areias", "Areias", "aldeia", 63, 16, 160, 0, True),
    ("carvalhal", "Carvalhal", "aldeia", 58, 25, 210, 0, False),
    ("azinhaga", "Azinhaga", "aldeia", 53, 36, 170, 0, False),
    ("moinhos", "Moinhos de Cima", "aldeia", 44, 13, 190, 0, False),
    ("valeescuro", "Vale Escuro", "aldeia", 48, 21, 140, 0, False),
    ("covas", "Covas", "aldeia", 66, 7, 110, 0, True),
    ("cabeco", "Cabeço Alto", "aldeia", 60, 42, 120, 0, True),
    ("salgueiral", "Salgueiral", "aldeia", 41, 32, 180, 0, False),
    ("freixo", "Freixo", "aldeia", 30, 32, 200, 0, False),
    ("lagoaseca", "Lagoa Seca", "aldeia", 27, 26, 160, 0, False),
    ("fontelas", "Fontelas", "aldeia", 28, 14, 190, 0, False),
    ("souto", "Souto Maior", "aldeia", 22, 8, 150, 0, False),
    ("barrocal", "Barrocal", "aldeia", 20, 16, 170, 0, False),
    ("tojal", "Tojal", "aldeia", 7, 15, 140, 0, True),
    ("silveira", "Silveira", "aldeia", 8, 33, 150, 0, True),
    ("malhada", "Malhada", "aldeia", 46, 42, 120, 0, True),
    # ilhéu: sem gente e sem estrada; só se chega de barco, e os mortos não nadam
    ("ilheu", "Ilhéu das Gaivotas", "ilheu", 4, 42, 0, 0, True),
]
SO_POR_MAR = {"ilheu"}
CAPITAL = {"cidadela", "alto", "mercado", "porta", "cais"}
RUAS = [("cidadela", "alto"), ("cidadela", "mercado"), ("alto", "mercado"), ("mercado", "porta"), ("mercado", "cais"),
        ("alto", "porta"), ("cais", "porta")]
PORTOES_DA_CIDADE = {"porta", "cais"}          # só esses bairros têm estrada para fora
ORIGEM = "lontras"

NOMES_M = ["Afonso", "Sancho", "Gonçalo", "Mem", "Pêro", "Rodrigo", "Vasco", "Nuno", "Fernão", "Martim", "Lourenço",
           "Diogo", "Estêvão", "Gil", "Álvaro", "Rui", "Tomé", "Bartolomeu", "Simão", "Gaspar", "Brás", "Henrique",
           "Duarte", "João", "Lopo", "Garcia", "Paio", "Egas", "Soeiro", "Telo", "Godinho", "Ourigo", "Vicente",
           "Salvador", "Mateus", "Cristóvão", "Damião", "Jorge", "Leonel", "Ermígio", "Fradique", "Aires", "Bento",
           "Tristão", "Heitor", "Quintino", "Baltasar", "Belchior", "Clemente", "Domingos", "Fagundo", "Gomes",
           "Inácio", "Jácome", "Lucas", "Marcos", "Nicolau", "Pascoal", "Romão", "Sebastião", "Teotónio", "Valentim",
           "Zacarias", "Abel", "Anselmo", "Bernardo", "Cosme", "Elias", "Feliciano", "Graciano"]
NOMES_F = ["Leonor", "Urraca", "Teresa", "Mafalda", "Beatriz", "Inês", "Constança", "Branca", "Isabel", "Maria",
           "Catarina", "Margarida", "Joana", "Filipa", "Guiomar", "Aldonça", "Sancha", "Mécia", "Violante", "Brites",
           "Elvira", "Dórdia", "Oroana", "Goda", "Vataça", "Estefânia", "Lucrécia", "Helena", "Clara", "Madalena",
           "Ilda", "Xamena", "Paula", "Rosa", "Sara", "Águeda", "Quitéria", "Benta", "Dulce", "Úrsula", "Ana",
           "Antónia", "Bárbara", "Cecília", "Domingas", "Felícia", "Genebra", "Jerónima", "Luzia", "Marta",
           "Natália", "Olímpia", "Perpétua", "Rufina", "Serafina", "Tomásia", "Vitória", "Zulmira", "Amélia", "Carlota"]
SOBRENOMES = ["Ribeiro", "Souto", "Pereira", "Carvalho", "Mendes", "Gomes", "Teles", "Coelho", "Raposo", "Lobo",
              "Falcão", "Moura", "Viana", "Sardinha", "Correia", "Esteves", "Faria", "Garcês", "Paiva", "Alvim",
              "Dantas", "Bezerra", "Cardoso", "Leitão", "Lemos", "Prado", "Abreu", "Freire", "Guedes", "Seabra",
              "Ramalho", "Neves", "Quintas", "Bravo", "Serrão", "Pacheco", "Azevedo", "Godinho", "Macedo", "Velho",
              "Valente", "Loureiro", "Coutinho", "Rocha", "Brandão", "Teixeira", "Pinto", "Cunha", "Mota", "Lago",
              "Barros", "Cabral", "Sá", "Fonseca", "Seixas", "Vaz", "Barreto", "Cerveira", "Couto", "Fagundes",
              "Gouveia", "Lacerda", "Magalhães", "Noronha", "Ornelas", "Pimentel", "Quaresma", "Resende", "Sequeira",
              "Tavares", "Vasconcelos", "Zagalo", "Amaral", "Bettencourt", "Calado", "Drago", "Encarnação", "Farinha",
              "Galvão", "Henriques", "Jardim", "Lima", "Matos", "Nogueira", "Osório", "Peixoto", "Ramos", "Salgado"]
NOMES_ESTRANGEIROS = ["Ulric", "Bram", "Joost", "Harald", "Sten", "Wouter", "Gerrit", "Olaf", "Ivo", "Rutger",
                      "Tjaard", "Eskil", "Floris", "Gunnar", "Hidde", "Jelle", "Klaas", "Lieven", "Maarten", "Nils"]
DINASTIA = "de Alvor"

ATRIBUTOS = ("coragem", "piedade", "ambicao", "astucia", "crueldade", "lealdade", "carisma", "fe", "forca", "genio")


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def estradas(lugares):
    """Liga cada lugar fora da capital aos 3 vizinhos mais próximos (até 19 km) e garante que tudo se conecte.
    A capital só se liga ao resto pelos bairros com portão."""
    pos = {l[0]: (l[3], l[4]) for l in lugares}
    fora = [l[0] for l in lugares if l[0] not in CAPITAL and l[0] not in SO_POR_MAR]
    nos = fora + sorted(PORTOES_DA_CIDADE)
    E = set()
    for a in nos:
        viz = sorted((b for b in nos if b != a and not (a in CAPITAL and b in CAPITAL)), key=lambda b: dist(pos[a], pos[b]))
        for b in viz[:3]:
            if dist(pos[a], pos[b]) <= 19 or b == viz[0]:
                E.add(tuple(sorted((a, b))))
    # conexão garantida (árvore mínima por cima)
    grupos = {n: n for n in nos}

    def raiz(n):
        while grupos[n] != n:
            n = grupos[n]
        return n
    for a, b in E:
        grupos[raiz(a)] = raiz(b)
    pares = sorted(((dist(pos[a], pos[b]), a, b) for i, a in enumerate(nos) for b in nos[i + 1:]
                    if not (a in CAPITAL and b in CAPITAL)))
    for d, a, b in pares:
        if raiz(a) != raiz(b):
            E.add(tuple(sorted((a, b))))
            grupos[raiz(a)] = raiz(b)
    out = [(a, b, round(dist(pos[a], pos[b]) * 1.25, 1), "estrada") for a, b in sorted(E)]
    for a, b in RUAS:
        tipo = "portao" if "cidadela" in (a, b) else "rua"
        out.append((a, b, 0.6, tipo))
    return out


def oficios(tipo, litoral):
    """Distribuição de ofícios dos adultos comuns por tipo de lugar (pesos)."""
    if tipo == "cidadela":
        return {"criado": 5, "soldado": 4, "artesao": 1, "clerigo": 0.3}
    if tipo == "bairro":
        base = {"artesao": 4, "mercador": 2, "campones": 1.5, "soldado": 0.8, "criado": 1.5, "clerigo": 0.3, "ferreiro": 0.3,
                "carpinteiro": 0.6}
        if litoral:
            base.update(pescador=3, estivador=2)
        return base
    if tipo == "vila":
        base = {"campones": 4, "artesao": 2, "mercador": 1, "soldado": 0.6, "ferreiro": 0.3, "carpinteiro": 0.5,
                "clerigo": 0.15, "lenhador": 0.6, "pastor": 0.6}
        if litoral:
            base.update(pescador=2.5)
        return base
    if tipo == "castelo":
        return {"soldado": 4, "criado": 3, "campones": 2, "ferreiro": 0.3}
    if tipo == "mosteiro":
        return {"monge": 8, "criado": 1, "campones": 1}
    if tipo == "mina":
        return {"mineiro": 8, "ferreiro": 0.5, "lenhador": 0.6}
    base = {"campones": 8, "lenhador": 1.2, "pastor": 1.2, "cacador": 0.6, "carpinteiro": 0.3, "ferreiro": 0.15, "clerigo": 0.08}
    if litoral:
        base.update(pescador=5)
    return base


def classe_de(papel, idade, sexo, arma):
    """Classe de luta: 0 não luta, 1 camponês com ferramenta, 2 milícia, 3 soldado, 4 cavaleiro."""
    if idade < 14 or idade > 66:
        return 0
    if papel in ("cavaleiro",):
        return 4
    if papel in ("soldado",):
        return 3
    if papel in ("lenhador", "mineiro", "cacador", "ferreiro") or arma >= 1:
        return 2
    if papel in ("criado", "clerigo", "monge", "mercador") and sexo == "f":
        return 0 if idade > 55 else 1
    return 1
