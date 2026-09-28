"""Renderiza a documentação de negócio num único .docx (modelo "Documentação de Negócio").

A estrutura segue `docs/templates/Modelo - Documentacao de Negocio.docx`, na mesma
ordem de tópicos. Tudo que é extraído do PBIP (páginas, visuais, campos, medidas,
filtros, RLS) é escrito de forma determinística; a prosa vem de `_descriptions.json`.

O que **não** existe nos arquivos do projeto (owners, público-alvo, links, status,
objetivo, dúvidas frequentes…) sai com o marcador `[PREENCHER: …]` realçado em
amarelo, a menos que tenha sido informado no bloco `negocio` do `.pbidoc.json`.
"""

import os

import catalog
import docx_writer as W
import render_common as rc

PENDENTE = "(descrição pendente)"
MARCADOR = "[%s: …]" % W.PREENCHER
NOME_TEMPLATE = "template-negocio.docx"

TIPO_VISUAL = {
    "card": "Cartão",
    "cardVisual": "Cartão",
    "multiRowCard": "Cartão de várias linhas",
    "kpi": "KPI",
    "gauge": "Medidor",
    "tableEx": "Tabela",
    "pivotTable": "Matriz",
    "barChart": "Gráfico de barras empilhadas",
    "clusteredBarChart": "Gráfico de barras agrupadas",
    "hundredPercentStackedBarChart": "Gráfico de barras 100%",
    "columnChart": "Gráfico de colunas empilhadas",
    "clusteredColumnChart": "Gráfico de colunas agrupadas",
    "hundredPercentStackedColumnChart": "Gráfico de colunas 100%",
    "lineChart": "Gráfico de linhas",
    "areaChart": "Gráfico de área",
    "stackedAreaChart": "Gráfico de área empilhada",
    "lineClusteredColumnComboChart": "Gráfico de linhas e colunas",
    "lineStackedColumnComboChart": "Gráfico de linhas e colunas empilhadas",
    "ribbonChart": "Gráfico de faixas",
    "waterfallChart": "Gráfico de cascata",
    "funnel": "Funil",
    "scatterChart": "Gráfico de dispersão",
    "pieChart": "Gráfico de pizza",
    "donutChart": "Gráfico de rosca",
    "treemap": "Treemap",
    "map": "Mapa",
    "filledMap": "Mapa coropletico",
    "azureMap": "Mapa (Azure)",
    "shapeMap": "Mapa de formas",
    "decompositionTreeVisual": "Árvore de decomposição",
    "keyDriversVisual": "Principais influenciadores",
    "slicer": "Segmentação de dados",
    "advancedSlicerVisual": "Segmentação de dados",
    "listSlicer": "Segmentação de dados",
    "textSlicer": "Segmentação de dados",
}
SEGMENTACOES = ("slicer", "advancedSlicerVisual", "listSlicer", "textSlicer")

# (campo em `negocio`, rótulo do marcador, chave de fallback na raiz da config)
INFO = [
    ("link_relatorio", "link do relatório publicado no Power BI", "link_relatorio"),
    ("link_dataset", "link do modelo semântico (dataset) no Power BI", None),
    ("objetivo", "objetivo do dashboard: qual problema de negócio ele resolve", "objetivo"),
    ("owner_tecnico", "owner técnico (nome, área e e-mail)", None),
    ("owner_negocio", "owner de negócio (nome, área e e-mail)", None),
    ("publico_area", "áreas de negócio que usam o dashboard", None),
    ("publico_clientes", "cliente(s) atendidos", None),
    ("publico_perfis", "perfis de usuários (analistas, coordenadores, diretoria…)", None),
    ("propriedade", "conta/e-mail proprietário do dashboard e regra de compartilhamento", None),
    ("plataforma_origem", "sistema(s) de origem dos dados (ex.: data warehouse, ERP, planilhas)", None),
    ("data_criacao_dashboard", "data de criação do dashboard (dd/mm/aaaa)", None),
    ("data_atualizacao_dashboard", "data da última atualização do dashboard (dd/mm/aaaa)", None),
    ("frequencia_atualizacao", "frequência de atualização agendada no serviço (ex.: 1h, 3h, diária)",
     "frequencia_atualizacao"),
    ("status", "status: Em desenvolvimento, Ativo ou Descontinuado", None),
    ("duvidas_frequentes", "dúvidas frequentes dos usuários e respectivas respostas", None),
    ("filtro_padrao_obs", "filtros aplicados na origem/bases de dados, fora do Power BI", None),
]
ROTULOS = {c: r for c, r, _ in INFO}


def _template_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", NOME_TEMPLATE)


def _valor(cfg, campo):
    neg = cfg.get("negocio") or {}
    valor = neg.get(campo)
    if campo == "duvidas_frequentes":
        return [d for d in (valor or []) if isinstance(d, dict) and d.get("pergunta")]
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    fallback = next((f for c, _, f in INFO if c == campo), None)
    if fallback and isinstance(cfg.get(fallback), str) and cfg[fallback].strip():
        return cfg[fallback].strip()
    return ""


def enriquecer(cfg, man):
    """Cópia da config com o que o próprio projeto já revela.

    Num relatório conectado, o dataset (catálogo e identificador) e a plataforma de origem
    saem da conexão do relatório — não precisam virar `[PREENCHER]`. O que a pessoa
    escreveu no bloco `negocio` sempre prevalece.
    """
    novo = dict(cfg)
    neg = dict(cfg.get("negocio") or {})
    ds = (man or {}).get("projeto", {}).get("dataset") or {}
    if ds.get("catalogo"):
        if not str(neg.get("link_dataset") or "").strip():
            neg["link_dataset"] = ("Dataset %s (identificador %s) — abra pelo workspace onde "
                                   "está publicado" % (ds["catalogo"], ds.get("modelo_id") or "—"))
        if not str(neg.get("plataforma_origem") or "").strip():
            neg["plataforma_origem"] = ("Dataset Power BI %s (as fontes originais dos dados são "
                                        "definidas no dataset)" % ds["catalogo"])
    novo["negocio"] = neg
    return novo


def campos_a_preencher(cfg, man=None):
    """[(campo, rótulo)] das informações de negócio ainda sem valor na config."""
    if man is not None:
        cfg = enriquecer(cfg, man)
    return [(c, r) for c, r, _ in INFO if not _valor(cfg, c)]


def _info(cfg, campo):
    """Valor da config ou o marcador de preenchimento."""
    v = _valor(cfg, campo)
    return v if v else ("pendente", ROTULOS[campo])


def _txt(valor):
    return valor.strip() if valor and str(valor).strip() else PENDENTE


def _tipo_visual(tipo):
    if tipo in TIPO_VISUAL:
        return TIPO_VISUAL[tipo]
    return "Visual personalizado (%s)" % tipo


def _col_ref(tabela, campo):
    return "%s[%s]" % (tabela, campo)


# --------------------------------------------------------------------- dados úteis


class Relatorio:
    """Índices do manifesto usados pelas seções."""

    def __init__(self, man):
        self.man = man
        self.conectado = man["projeto"].get("tipo") == "relatorio_conectado"
        self.extensoes = {(e["tabela"], e["nome"]): e
                          for e in man["relatorio"].get("extensoes") or []}
        self.colunas = {(t["nome"], c["nome"]): c for t in man["tabelas"] for c in t["colunas"]}
        self.medidas = {(m["tabela"], m["nome"]): m for m in man["medidas"]}
        self.medidas_por_nome = {m["nome"]: m for m in man["medidas"]}
        self.tabelas = {t["nome"]: t for t in man["tabelas"]}
        self.rotulos = {}
        for p in man["relatorio"]["paginas"]:
            for v in p.get("visuais", []):
                for c in v["campos"]:
                    chave = (c["tabela"], c["campo"])
                    rot = c.get("rotulo")
                    if rot and rot != c["campo"] and not rot.startswith(("Soma de", "Contagem de",
                                                                         "Média de", "Mín", "Máx")):
                        self.rotulos.setdefault(chave, rot)
        usados = man["relatorio"].get("campos_usados", [])
        self.colunas_usadas = [(c["tabela"], c["campo"]) for c in usados if c["tipo"] == "coluna"]
        self.medidas_usadas = [(c["tabela"], c["campo"]) for c in usados if c["tipo"] == "medida"]

    def rotulo(self, tabela, campo):
        return self.rotulos.get((tabela, campo), campo)

    def fontes_da_medida(self, medida, _vistas=None):
        """Fontes de dados (tipo/projeto) das tabelas de que a medida depende."""
        vistas = _vistas if _vistas is not None else set()
        if medida["nome"] in vistas:
            return set()
        vistas.add(medida["nome"])
        fontes = set()
        dep = medida.get("depende_de") or {}
        tabelas = {c.split("[")[0] for c in dep.get("colunas", [])}
        for nome in tabelas:
            origem = (self.tabelas.get(nome) or {}).get("origem") or {}
            if origem.get("tipo") and origem["tipo"] != "desconhecida":
                fontes.add("%s (%s)" % (origem["tipo"], origem.get("projeto")))
        for nome in dep.get("medidas", []):
            m = self.medidas_por_nome.get(nome)
            if m:
                fontes |= self.fontes_da_medida(m, vistas)
        return fontes


# ------------------------------------------------------------------------- seções


def _capa(b, cfg):
    b.titulo_capa("Dicionário de Dados %s" % cfg["titulo"])
    b.sumario()


def _informacoes(b, man, cfg, meta):
    proj = man["projeto"]
    b.heading(1, "Informações Gerais", quebra_antes=True)

    b.heading(2, "Nome do Dashboard/Relatório")
    b.paragrafo(cfg["titulo"])
    if proj.get("report"):
        b.rotulo("Arquivo do relatório", [("mono", proj["report"])])

    b.heading(2, "Link do Dashboard/Relatório")
    b.rotulo("Relatório no Power BI", _info(cfg, "link_relatorio"))
    b.rotulo("Modelo semântico (dataset) no Power BI", _info(cfg, "link_dataset"))

    b.heading(2, "Objetivo do Dashboard/Relatório")
    b.paragrafo(_info(cfg, "objetivo"))

    b.heading(2, "Owners")
    b.rotulo("Técnico", _info(cfg, "owner_tecnico"))
    b.rotulo("Negócio", _info(cfg, "owner_negocio"))

    b.heading(2, "Público-Alvo")
    b.rotulo("Área de Negócio", _info(cfg, "publico_area"))
    b.rotulo("Cliente(s)", _info(cfg, "publico_clientes"))
    b.rotulo("Perfil de Usuários", _info(cfg, "publico_perfis"))

    b.heading(2, "Propriedade do Dashboard")
    b.paragrafo(_info(cfg, "propriedade"))
    b.destaque("Ferramenta de BI")
    b.paragrafo("Power BI")
    b.destaque("Plataforma de Origem dos dados")
    b.paragrafo(_info(cfg, "plataforma_origem"))
    if proj["fontes_dados"]:
        b.rotulo("Dataset conectado" if proj.get("tipo") == "relatorio_conectado"
                 else "Fontes conectadas ao modelo", ", ".join(proj["fontes_dados"]))

    b.heading(2, "Datas")
    b.rotulo("Data Criação do Dashboard/Relatório", _info(cfg, "data_criacao_dashboard"))
    b.rotulo("Data Última Atualização do Dashboard/Relatório",
             _info(cfg, "data_atualizacao_dashboard"))
    b.rotulo("Data Criação da Documentação", meta.get("criado_em", rc.hoje()))
    b.rotulo("Data Última Atualização da Documentação", meta.get("atualizado_em", rc.hoje()))

    b.heading(2, "Frequência de Atualização")
    b.paragrafo(_info(cfg, "frequencia_atualizacao"))
    incrementais = [t["nome"] for t in man["tabelas"]
                    if (t["origem"] or {}).get("atualizacao_incremental")]
    if incrementais:
        b.rotulo("Tabelas com atualização incremental", ", ".join(incrementais))

    b.heading(2, "Status")
    b.paragrafo(_info(cfg, "status"))


def proj_conectado(man):
    return man["projeto"].get("tipo") == "relatorio_conectado"


def _filtros_aplicados(man):
    """[(onde, filtro)] dos filtros com condição no relatório e nas páginas."""
    saida = [("Relatório", f) for f in man["relatorio"].get("filtros", []) if f["aplicado"]]
    for p in man["relatorio"]["paginas"]:
        saida.extend(("Página %s" % p["nome"], f) for f in p.get("filtros", []) if f["aplicado"])
    return saida


def _desc_filtro(f):
    return "%s: %s" % (_col_ref(f["tabela"], f["campo"]), f["condicao"] or "condição avançada")


def _objetivo_regras(b, man, cfg, prosa):
    b.heading(1, "Objetivo e Regras de Negócio", quebra_antes=True)
    b.paragrafo(_info(cfg, "objetivo"))

    b.paragrafo("Regras de negócio identificadas nos arquivos do projeto:", negrito=True)
    regras = 0
    for onde, f in _filtros_aplicados(man):
        b.item("%s — filtro fixo em %s" % (onde, _desc_filtro(f)))
        regras += 1
    visuais_filtrados = sum(1 for p in man["relatorio"]["paginas"] for v in p.get("visuais", [])
                            if any(f["aplicado"] for f in v["filtros"]))
    if visuais_filtrados:
        b.item("%d visual(is) possuem filtros próprios, detalhados em Estrutura do "
               "Dashboard/Relatório." % visuais_filtrados)
        regras += 1
    if proj_conectado(man):
        b.item("Este projeto contém apenas o relatório: a segurança em nível de linha (RLS), as "
               "consultas e o código das medidas do dataset são definidos no dataset de origem "
               "e não estão disponíveis aqui.")
        regras += 1
    if man["perfis_rls"]:
        b.item("O acesso aos dados é restrito por segurança em nível de linha (RLS), com %d "
               "perfil(is): %s." % (len(man["perfis_rls"]),
                                    ", ".join(r["nome"] for r in man["perfis_rls"])))
        regras += 1
    incrementais = [t["nome"] for t in man["tabelas"]
                    if (t["origem"] or {}).get("atualizacao_incremental")]
    if incrementais:
        b.item("Atualização incremental nas tabelas %s: apenas a janela recente de dados é "
               "recarregada a cada atualização." % ", ".join(incrementais))
        regras += 1
    revisar = [m for m in man["medidas"] if prosa.revisar(catalog.key_medida(m["tabela"], m["nome"]))]
    for m in revisar:
        b.item(["Ponto de atenção na medida %s: descrição marcada para revisão humana." % m["nome"]])
        regras += 1
    if not regras:
        b.paragrafo("Nenhum filtro fixo, regra de segurança ou atualização incremental foi "
                    "encontrado nos arquivos do projeto.")
    b.paragrafo(["Outras regras de negócio: ",
                 ("pendente", "regras de negócio que não estão expressas nos arquivos do "
                              "projeto e pontos de atenção relevantes")])

    b.heading(2, "Dúvidas frequentes")
    duvidas = _valor(cfg, "duvidas_frequentes")
    if duvidas:
        for d in duvidas:
            b.paragrafo(d["pergunta"], negrito=True)
            b.paragrafo(d.get("resposta") or ("pendente", "resposta desta dúvida"))
    else:
        b.paragrafo(("pendente", ROTULOS["duvidas_frequentes"]))


def _estrutura(b, man, prosa, rel):
    b.heading(1, "Estrutura do Dashboard/Relatório", quebra_antes=True)
    paginas = man["relatorio"]["paginas"]
    if not paginas:
        b.paragrafo("O projeto não possui relatório (pasta *.Report) associado ao modelo.")
        return
    b.paragrafo("O relatório possui %d página(s), apresentadas abaixo na ordem de navegação."
                % len(paginas))
    for p in paginas:
        titulo = p["nome"]
        if p.get("tipo") == "Tooltip":
            titulo += " (dica de ferramenta)"
        elif p.get("oculta"):
            titulo += " (oculta)"
        b.heading(2, titulo)
        b.item(_txt(prosa.pagina(p["nome"])), rotulo="Descrição")

        visuais = [v for v in p.get("visuais", [])
                   if v["tipo"] not in catalog.DECORATIVOS and v["tipo"] not in SEGMENTACOES
                   and v["campos"]]
        b.item("Principais visualizações")
        linhas = []
        for v in visuais:
            campos = ", ".join(rel.rotulo(c["tabela"], c["campo"]) for c in v["campos"])
            nome = v["titulo"] or _tipo_visual(v["tipo"])
            texto = "%s (%s): %s" % (nome, _tipo_visual(v["tipo"]), campos) if v["titulo"] \
                else "%s: %s" % (nome, campos)
            filtros = [f for f in v["filtros"] if f["aplicado"]]
            if filtros:
                texto += " — filtro do visual: " + "; ".join(_desc_filtro(f) for f in filtros)
            if texto not in linhas:
                linhas.append(texto)
        for texto in linhas or ["Nenhum visual de dados nesta página."]:
            b.item(texto, nivel=1)

        medidas = []
        for v in p.get("visuais", []):
            for c in v["campos"]:
                if c["tipo"] == "medida":
                    rot = rel.rotulo(c["tabela"], c["campo"])
                    item = rot if rot == c["campo"] else "%s (%s)" % (rot, c["campo"])
                    if item not in medidas:
                        medidas.append(item)
        b.item("Indicadores apresentados")
        for m in medidas or ["Nenhuma medida exibida nesta página."]:
            b.item(m, nivel=1)

        segmentacoes = []
        for v in p.get("visuais", []):
            if v["tipo"] in SEGMENTACOES:
                for c in v["campos"]:
                    rot = rel.rotulo(c["tabela"], c["campo"])
                    if rot not in segmentacoes:
                        segmentacoes.append(rot)
        if segmentacoes:
            b.item("Filtros disponíveis na página")
            for s in segmentacoes:
                b.item(s, nivel=1)


def _tipo_coluna(rel, tabela, campo):
    if rel.conectado:
        return "definido no dataset (não disponível neste projeto)"
    return rc.tipo_rotulo(rel.colunas[(tabela, campo)]["tipo"])


def _titulo_medida(rel, tabela, nome):
    rot = rel.rotulo(tabela, nome)
    return rot if rot == nome else "%s (%s)" % (rot, nome)


def _titulos_unicos(itens, titulo):
    """{item: título} garantindo títulos únicos: se dois itens gerarem o mesmo título,
    ambos recebem o nome da tabela como complemento."""
    contagem = {}
    for it in itens:
        contagem[titulo(it).lower()] = contagem.get(titulo(it).lower(), 0) + 1
    return {it: titulo(it) if contagem[titulo(it).lower()] == 1
            else "%s — %s" % (titulo(it), it[0]) for it in itens}


def _dicionario(b, man, prosa, rel):
    b.heading(1, "Dicionário de dados", quebra_antes=True)
    if rel.conectado:
        existentes, faltantes = list(rel.colunas_usadas), []
    else:
        existentes = [c for c in rel.colunas_usadas if c in rel.colunas]
        faltantes = [c for c in rel.colunas_usadas if c not in rel.colunas]
    if not existentes:
        b.paragrafo("Nenhuma coluna do modelo é exibida no relatório.")
    else:
        b.paragrafo("Dimensões (colunas) que aparecem no relatório — em visuais, segmentações "
                    "de dados e filtros.")
    # Um título por rótulo: colunas diferentes exibidas com o mesmo rótulo ("Aluno",
    # "Cargo"…) ficam agrupadas numa tabela sob um único título, nunca em títulos repetidos.
    grupos = {}
    for tabela, campo in sorted(existentes, key=lambda c: (rel.rotulo(*c).lower(), c)):
        grupos.setdefault(rel.rotulo(tabela, campo).lower(), []).append((tabela, campo))
    for colunas in grupos.values():
        rotulo = rel.rotulo(*colunas[0])
        b.heading(2, b.titulo_livre(rotulo, "campo"))
        if len(colunas) == 1:
            tabela, campo = colunas[0]
            b.paragrafo(_txt(prosa.coluna(tabela, campo)))
            b.paragrafo(["Campo: ", ("mono", _col_ref(tabela, campo)),
                         " · Tipo: %s" % _tipo_coluna(rel, tabela, campo)], sz=20)
            continue
        b.paragrafo("Campos diferentes exibidos no relatório com o rótulo “%s”:" % rotulo)
        b.tabela(["Campo", "Descrição", "Tipo"],
                 [[W.Mono(_col_ref(t, c)), _txt(prosa.coluna(t, c)), _tipo_coluna(rel, t, c)]
                  for t, c in colunas],
                 pesos=[3, 5, 2] if rel.conectado else [3, 6, 1], sz=20)
    if faltantes:
        b.paragrafo("Campos referenciados pelo relatório que não existem no modelo: %s."
                    % ", ".join(_col_ref(*c) for c in faltantes), italico=True)


def _medidas_conectado(b, man, prosa, rel):
    """Relatório conectado: medidas de relatório (com DAX) + medidas do dataset (só nome)."""
    usadas = list(rel.medidas_usadas) or list(rel.extensoes)
    if not usadas:
        b.paragrafo("O relatório não usa medidas.")
        return
    b.paragrafo("Medidas que aparecem no relatório. As definidas no próprio relatório trazem o "
                "cálculo; as do dataset têm o código no dataset de origem.")
    titulos = _titulos_unicos(usadas, lambda c: _titulo_medida(rel, *c))
    for tabela, nome in sorted(usadas, key=lambda c: rel.rotulo(*c).lower()):
        ext = rel.extensoes.get((tabela, nome))
        chave = catalog.key_medida(tabela, nome)
        b.heading(2, b.titulo_livre(titulos[(tabela, nome)], "medida"))
        b.item(_txt(prosa.medida(tabela, nome, "descricao")), rotulo="Definição", num_id=1,
               leve=True)
        regra = prosa.medida(tabela, nome, "regra")
        if ext:
            b.item(_txt(regra), rotulo="Regra de Cálculo", num_id=1, leve=True)
            b.item("Medida definida no relatório", rotulo="Origem", num_id=1, leve=True)
            b.codigo(ext["dax"])
        else:
            b.item(regra or "Definida no dataset; o código DAX não está disponível neste projeto.",
                   rotulo="Regra de Cálculo", num_id=1, leve=True)
        if prosa.revisar(chave):
            b.item("Descrição marcada para revisão humana — validar antes de publicar.",
                   rotulo="Ponto de atenção", num_id=1, leve=True)


def _medidas(b, man, prosa, rel):
    b.heading(1, "Medidas", quebra_antes=True)
    if rel.conectado:
        _medidas_conectado(b, man, prosa, rel)
        return
    usadas = [rel.medidas[c] for c in rel.medidas_usadas if c in rel.medidas]
    if usadas:
        b.paragrafo("Campos calculados (medidas DAX) que aparecem no relatório.")
        medidas = sorted(usadas, key=lambda m: m["nome"].lower())
    else:
        b.paragrafo("O relatório não exibe medidas; abaixo estão todas as medidas do modelo.")
        medidas = man["medidas"]
    varias_fontes = len(man["projeto"]["fontes_dados"]) > 1
    titulos = _titulos_unicos([(m["tabela"], m["nome"]) for m in medidas],
                              lambda c: _titulo_medida(rel, *c))
    for m in medidas:
        chave = catalog.key_medida(m["tabela"], m["nome"])
        b.heading(2, b.titulo_livre(titulos[(m["tabela"], m["nome"])], "medida"))
        b.item(_txt(prosa.medida(m["tabela"], m["nome"], "descricao")),
               rotulo="Definição", num_id=1, leve=True)
        b.item(_txt(prosa.medida(m["tabela"], m["nome"], "regra")),
               rotulo="Regra de Cálculo", num_id=1, leve=True)
        if varias_fontes:
            fontes = sorted(rel.fontes_da_medida(m))
            b.item(", ".join(fontes) if fontes else "—", rotulo="Plataforma", num_id=1, leve=True)
        if prosa.revisar(chave):
            b.item("Descrição marcada para revisão humana — validar antes de publicar.",
                   rotulo="Ponto de atenção", num_id=1, leve=True)


def _filtros_seguranca(b, man, cfg, prosa):
    b.heading(1, "Filtros e Segurança", quebra_antes=True)
    b.heading(2, "Filtro Padrão")
    aplicados = _filtros_aplicados(man)
    if aplicados:
        for onde, f in aplicados:
            b.item("%s — %s" % (onde, _desc_filtro(f)))
    else:
        b.paragrafo("Nenhum filtro fixo aplicado no nível do relatório ou das páginas.")
    livres = [f for f in man["relatorio"].get("filtros", []) if not f["aplicado"]]
    if livres:
        b.paragrafo("Campos disponíveis no painel de filtros do relatório, sem valor aplicado: %s."
                    % ", ".join(_col_ref(f["tabela"], f["campo"]) for f in livres))
    b.rotulo("Filtros nas bases de dados", _info(cfg, "filtro_padrao_obs"))

    b.heading(2, "RLS (Segurança)")
    if proj_conectado(man):
        b.paragrafo("A segurança em nível de linha (RLS) é definida no dataset de origem e não "
                    "está disponível neste projeto.")
        b.rotulo("Perfis e usuários/grupos de cada perfil",
                 [("pendente", "perfis de RLS do dataset e atribuição de usuários/grupos, "
                               "configurados no serviço do Power BI")])
        return
    if not man["perfis_rls"]:
        b.paragrafo("O modelo não define segurança em nível de linha (RLS).")
        return
    b.paragrafo("O modelo define %d perfil(is) de segurança em nível de linha. Cada perfil "
                "filtra as tabelas listadas de acordo com o usuário autenticado."
                % len(man["perfis_rls"]))
    for r in man["perfis_rls"]:
        b.item(_txt(prosa.rls(r["nome"])), rotulo=r["nome"])
        b.item("Tabelas filtradas: %s" % ", ".join(p["tabela"] for p in r["permissoes"]),
               nivel=1)
    b.rotulo("Usuários e grupos de cada perfil",
             [("pendente", "atribuição de usuários/grupos aos perfis, configurada no serviço "
                           "do Power BI")])


# ---------------------------------------------------------------------------- API


def render(man, cfg, descriptions, destino, meta):
    template = _template_path()
    if not os.path.isfile(template):
        raise SystemExit(
            "Template ausente: %s\nGere-o com:\n"
            "  python3 tools/pbidoc/make_template.py "
            "\"docs/templates/Modelo - Documentacao de Negocio.docx\" --modelo negocio" % template)

    prosa = rc.Prosa(descriptions)
    rel = Relatorio(man)
    W.aplicar_estilo(cfg.get("estilo_docx"))
    cfg = enriquecer(cfg, man)
    cfg = enriquecer(cfg, man)
    b = W.BodyNegocio()
    _capa(b, cfg)
    _informacoes(b, man, cfg, meta)
    _objetivo_regras(b, man, cfg, prosa)
    _estrutura(b, man, prosa, rel)
    _dicionario(b, man, prosa, rel)
    _medidas(b, man, prosa, rel)
    _filtros_seguranca(b, man, cfg, prosa)

    nome = "%s - Documentação de Negócio.docx" % cfg["titulo"]
    os.makedirs(destino, exist_ok=True)
    caminho = os.path.join(destino, nome)
    corpo = b.xml()
    if W.inalterado(template, caminho, corpo):
        return None
    W.gravar(template, caminho, corpo)
    return nome
