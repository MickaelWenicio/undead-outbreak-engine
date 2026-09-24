"""Parâmetros do motor (reino de Alvor). Regras fixas do primeiro ao último dia: ver docs/RULES.md."""

SEED = 1
DIAS_MAX = 600   # 20 meses: dá tempo de os últimos mortos apodrecerem
INICIO_DOY = 258            # dia do ano no começo (meados de setembro: começo do outono)
DIA_DO_NAVIO = 3            # o navio encalha no dia 3 (contando o primeiro dia como 1), à noite
HORA_DO_NAVIO = 21

# ---------------- a mordida e o levante (mordido vivo vira em no máximo 24 h)
VIRA_MORDIDO_H = (2.0, 24.0)     # mordido vivo vira entre 2 e 24 h
VIRA_MORDIDO_MODA = 7.0          # o mais comum é virar em umas 7 horas
LEVANTA_MIN = (10, 60)           # morto com o corpo inteiro levanta em 10 a 60 minutos
CORPO_INTEIRO = [0.9, 0.75, 0.55, 0.35]   # chance de o corpo ficar inteiro com 1, 2, 3, 4+ mortos em cima da vítima

# ---------------- combate (por rodada; uma briga vai até um lado cair)
# classes de luta: 0 não luta (criança, idoso, doente), 1 camponês com ferramenta, 2 milícia (lança, machado, arco),
# 3 soldado (cota de malha), 4 cavaleiro (armadura completa)
P_MATA = [0.0, 0.04, 0.08, 0.12, 0.15]    # chance de um vivo dessa classe derrubar o morto numa rodada
ARMADURA = [1.0, 1.0, 0.85, 0.5, 0.3]     # multiplica a chance de levar a mordida
P_MORDE = 0.22                            # chance de o morto morder quem ele pegou, por rodada
AJUDA_SEGURA = 0.75
DEBANDA = 0.5          # quem não é soldado foge da briga quando vê o vizinho ser mordido                       # cada ajudante segurando o morto multiplica a chance de mordida
MORTE_NA_HORA = [0.35, 0.5, 0.7, 0.8]   # chance de quem é pego morrer ali (1, 2, 3, 4+ mortos), em vez de sair mordido
CONTATO_ABERTO = 0.8     # fração dos mortos que alcançam alguém por hora em campo aberto ou rua
VITIMAS_POR_HORA = 1.5   # quantas pessoas sem defesa um morto solto pega por hora

# ---------------- movimento (km/h) e sentidos
VEL_HUMANO = 4.0
VEL_CARROCA = 3.0
VEL_CAVALO = 9.0
VEL_ZUMBI_CAÇA = 8.0       # correndo atrás de presa
VEL_ZUMBI_VAGA = 2.0
CHEIRO_KM = 4.0            # sentem gente até essa distância
BARULHO_KM = 16.0          # luta, sino ou incêndio atraem de mais longe
SAIDA_BASE = 0.2           # chance por hora de um bando sem presa partir atrás do cheiro
SEGUE_BANDO = 0.85

# ---------------- frio
FROST_INVERNO = 0.55       # chance de um dia de inverno ter geada (mortos sem presa ficam parados)
FROST_OUTONO = 0.12

# ---------------- abrigo e muralhas (pancada medida em "mortos-hora")
GENTE_POR_CASA = 5
PORTA_CASA = 4.0
PORTA_BARRICADA = 9.0
MURO = {  # nível: (vida do portão, mortos empilhados para escalar, nome)
    0: (0, 0, "nenhum"),
    1: (60, 30, "paliçada"),
    2: (300, 120, "muro da vila"),
    3: (1000, 400, "muralha da cidade"),
}
MATA_DO_MURO = 0.025        # mortos derrubados por hora por defensor armado em cima do muro
MORDIDA_NO_MURO = 0.004
TURNO_NO_MURO = 0.5
RESPOSTA_ARMADA = 0.6        # chance por hora de um armado sair de casa quando o sino toca
EMPURRAM = {0: 999, 1: 25, 2: 45, 3: 60}   # quantos mortos cabem empurrando o portão ao mesmo tempo        # fração dos armados de guarda no muro a cada hora    # chance por hora de um defensor ser mordido por quem escala

# ---------------- os mortos aprendem (dias depois do navio)
APRENDE = [(7, 1, "Os mortos passam a cercar as casas e esperar do lado de fora. Quem sai, não volta."),
           (21, 2, "Os mortos aprendem a se amontoar contra muros e paliçadas, uns por cima dos outros, até alcançar o topo."),
           (42, 3, "Os mortos passam a esperar nas estradas perto das vilas, parados entre as árvores, até alguém passar."),
           (70, 4, "Os mortos procuram o ponto mais fraco de cada muro e forçam os portões todos juntos, de noite.")]
PORTA_APRENDE = [1.0, 1.3, 1.4, 1.5, 1.7]   # eficiência para quebrar portas por nível
EMBOSCADA = [0.0, 0.0, 0.0, 0.35, 0.45]     # chance extra de um grupo na estrada cruzar com mortos (nível 3+)

# ---------------- vivos: o que sabem, como reagem
DETECTA_INSPECAO = 0.55    # inspeção no portão acha a mordida
ESCONDE_BASE = 0.35        # chance base de esconder a mordida (sobe com medo e com a política de execução)
FOGE_CHANCE = 0.35         # chance por hora de uma família sair correndo de um lugar invadido
NOTICIA_ATRASO_H = 2       # um mensageiro a cavalo leva a notícia; refugiados contam ao chegar
ALERTA_SINO = True

# ---------------- economia (rações por dia)
CONSUMO = 1.0
PRODUZ = {"campones": 1.6, "pescador": 2.2, "cacador": 1.8, "pastor": 1.5, "monge": 1.1,
          # na cidade, quem não planta ganha a comida com o ofício (o mercado abstrai a compra)
          "artesao": 0.7, "mercador": 0.9, "estivador": 0.8, "criado": 0.5, "ferreiro": 0.7, "carpinteiro": 0.7}
COLHEITA_DIAS = (0, 25)     # a colheita do outono rende mais nos primeiros dias de cada ano da história
COLHEITA_MULT = 2.2
INVERNO_MULT = 0.35
# o reino começa logo depois da colheita de setembro: o celeiro está cheio para o ano (a capital depende do campo)
ESTOQUE_INICIAL_DIAS = {"ilheu": 0, "capital": 90, "cidadela": 240, "vila": 150, "aldeia": 200, "castelo": 200, "mosteiro": 200, "mina": 60}
LENHA_POR_LENHADOR = 3.0
BARRICADA_LENHA = 4.0        # lenha para barricar uma porta
PALICADA_LENHA = 600.0       # lenha para erguer uma paliçada (nível 0 → 1)
LANCA_POR_FERREIRO = 1.5     # lanças por dia por ferreiro (ferro da mina permitindo)

# ---------------- política e intrigas
GOLPE_RAIVA = -25            # opinião média abaixo disso abre espaço para golpe
RANCOR_MATA = 70             # rancor que leva alguém cruel a matar
CULTO_DESESPERO = 55         # medo médio que faz o povo seguir um pregador

# ---------------- capital: barricadas nas ruas entre os bairros (montadas quando a cidade sabe dos mortos)
BARRICADA_RUA = 150.0       # vida da barricada de carroças e entulho
BARRICADA_RUA_ESCALA = 40   # mortos amontoados que passam por cima dela

# ---------------- fortalezas: mortos não têm ferramenta; portão de castelo quase não cede, e é consertado
MURO_DANO = {0: 1.0, 1: 0.6, 2: 0.3, 3: 0.08}            # dano por morto empurrando, por hora
ESCALA_POR_DEFENSOR = {0: 1, 1: 3, 2: 4, 3: 10}         # para escalar, precisam ser tantas vezes os defensores no muro
CONSERTO_DIA = 120.0                                    # vida de portão consertada por dia, gastando lenha

# ---------------- inteligência dos vivos (chances pelos atributos, nunca certeza)
FORMACAO_MATA = 1.25        # soldados em linha derrubam mais
FORMACAO_MORDE = 0.55       # e levam menos mordidas (escudo com escudo)
IDEIA_REFORCO = 0.25        # chance por dia de alguém engenhoso propor reforçar o portão
REFORCO_MULT = 1.6          # portão reforçado aguenta 60% mais
REDUTO_HP = 40.0            # porta de igreja ou torre trancada (mortos-hora)
ACHA_ESCONDIDO = 0.07       # chance por hora de os mortos acharem quem está escondido
CHEIRO_DISFARCA = 0.35      # com o cheiro dos mortos no corpo, a chance de ser achado cai para 35%
IDEIA_CHEIRO = 0.00015        # chance por hora de alguém muito esperto ter a ideia do cheiro

# ---------------- perseguição: os mortos correm mais que quem foge
PERSEGUE = 0.15            # fração dos mortos soltos que vai atrás de cada grupo que foge

# ---------------- ideias engenhosas (ideias.py): chance por dia, para quem tem o atributo
IDEIA = {"fosso": 0.06, "sinais": 0.04, "reorganiza": 0.12, "hortas": 0.08, "pesca_mar": 0.2, "caes": 0.05,
         "amputacao": 0.015, "antidoto": 0.01, "mercado_negro": 0.1, "barcos": 0.15, "cacada": 0.05, "colonia": 0.12, "campos": 0.1}
TATICA = {"isca": 0.03, "fogo": 0.03, "corredor": 0.02}   # chance por hora de cerco, para quem é esperto
ISCA_LEVA = 0.55          # fração do bando que corre atrás da isca
FOGO_ESPALHA = 0.25       # chance de o fogo do portão pegar nos telhados de dentro
FOSSO_MATA = 0.01         # fração do bando que cai nas estacas por hora
CORREDOR_MATA = 0.05      # mortos por armado por hora no corredor do portão
AMPUTACAO_SALVA = 0.3     # chance de salvar quem contou a mordida, onde se sabe amputar
CURA_SALVA = 0.45         # chance de o remédio segurar a mordida, onde ele existe
ANTIDOTO_RITMO = 0.03     # progresso médio por dia do estudo (um gênio leva uns 1 a 3 meses por tentativa)
ANTIDOTO_ACIDENTE = 0.006 # chance por dia de o morto preso escapar no laboratório
ANTIDOTO_SUCESSO = 0.35   # chance de cada tentativa dar certo

# ---------------- ruído e vagar
RUIDO_MAX = 10.0           # o maior barulho (fogo e piche, briga grande)
RUIDO_KM_POR_PONTO = 2.2    # cada ponto de ruído chama mortos de mais 2,2 km (10 pontos: 22 km)
VAGA_HORA = 0.1            # chance por hora de um bando sem cheiro nem ruído soltar gente para vagar
VAGA_FRACAO = 0.35         # fração do bando que sai vagando de cada vez

REVISTA_ACHA = 0.6          # chance de a revista achar uma mordida escondida

# ---------------- hierarquia, animais, obras e boatos (hierarquia.py)
GADO_POR_PESSOA = {"aldeia": 0.6, "vila": 0.25, "castelo": 0.3, "bairro": 0.03, "cidadela": 0.05, "mosteiro": 0.5, "mina": 0.1}
CAVALOS_POR_PESSOA = {"aldeia": 0.04, "vila": 0.05, "castelo": 0.15, "bairro": 0.02, "cidadela": 0.2, "mosteiro": 0.05, "mina": 0.05}
ZUMBI_MATA_ANIMAIS = 0.2    # animais mortos por morto-vivo por hora, num lugar tomado
RACOES_POR_ANIMAL = 40.0
OBRA_PALICADA = 1500.0      # dias de trabalho de uma pessoa
OBRA_MURO = 9000.0
OBRA_LENHA = {1: 600.0, 2: 900.0}
BOATO_DISTORCE = 0.35       # chance de a primeira notícia de segunda mão chegar torcida

# ---------------- temperamento do reino (variedade entre ilhas)
CULTURA_ATRIBUTOS = ("fe", "genio", "astucia", "coragem", "lealdade", "ambicao", "crueldade", "piedade")
CULTURA_DESVIO = 1.0        # desvio da média de cada atributo, sorteado por ilha (escala de 1 a 10)
CULTURA_MAX = 2.0
SEITA_CHANCE = 0.006        # chance por dia de um pregador juntar seguidores, onde o medo passou do limite

ESCONDIDO_MAX_DIAS = 3       # ninguém aguenta mais que uns 3 dias escondido sem água

# ---------------- validade dos mortos-vivos
PODRIDAO_DIAS = (200, 260, 295)  # prazo de cada morto a partir de quando se levanta: mínimo, mais comum, máximo
PODRE_POR_VITIMA = 4.0          # dias a mais por pessoa comida (repartidos entre os mortos do lugar)
COMIDA_MORDIDA = 0.25           # uma mordida vale um quarto de pessoa comida
COMIDA_ANIMAL = 0.25            # um bicho vale um quarto de pessoa
PODRE_GANHO_MAX_DIA = 3.0       # nenhum morto ganha mais que 3 dias de prazo num dia de banquete
PODRE_LOG_MIN = 25              # dias com menos quedas que isso não entram no log, só nas contas
COMIDO = ("morto pelos mortos-vivos", "morto lutando contra os mortos", "ficou para trás depois de tocar o sino da isca")

# ---------------- fome do segundo ato
EXP_MAX = 60                 # homens numa expedição de comida
EXP_CARGA_HOMEM = 25.0       # rações que um homem carrega nas costas
EXP_CARGA_CARROCA = 60.0     # rações por homem quando há carroça e animal de tração
COLONIA_FRACAO = 0.3         # parte do povo que vai recolonizar
COLONIA_MAX = 200
COLONO_RENDE = 0.7           # quem não é do campo planta a 70% de um camponês
GOLPE_PAUSA_DIAS = 25        # depois de um golpe, o lugar passa pelo menos isso sem outro
CAMPOS_RENDE = 0.6          # gente da cidade lavrando fora dos muros rende 60% de um camponês
