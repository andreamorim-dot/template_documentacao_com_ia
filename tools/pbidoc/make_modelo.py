#!/usr/bin/env python3
"""Gera o documento-modelo "Modelo - Documentacao Tecnica.docx".

O modelo é produzido pelo **mesmo renderizador** do glossário técnico
(`render_docx.py`), alimentado por um projeto fictício cujos textos são instruções
de preenchimento ("Descreva…") seguidas de um exemplo. Assim a estrutura, a ordem
dos tópicos, o índice e a formatação das tabelas do modelo são exatamente os do
documento gerado — não há uma segunda definição que possa divergir.

Uso:
    python3 make_modelo.py [destino.docx]
    (padrão: docs/templates/Modelo - Documentacao Tecnica.docx)
    python3 make_modelo.py --tipo relatorio [destino.docx]
    (padrão: docs/templates/Modelo - Documentacao de Relatorio.docx — relatório conectado)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render_docx  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESTINO_PADRAO = os.path.join(RAIZ, "docs", "templates", "Modelo - Documentacao Tecnica.docx")
DESTINO_RELATORIO = os.path.join(RAIZ, "docs", "templates", "Modelo - Documentacao de Relatorio.docx")

SQL_FATO = ("SELECT id_matricula, id_curso, dt_matricula, status\n"
            "FROM `projeto.dataset.matriculas`\n"
            "WHERE deletado = FALSE")

M_FATO = ('let\n'
          '    Fonte = GoogleBigQuery.Database(),\n'
          '    Consulta = Value.NativeQuery(Fonte{[Name="projeto"]}[Data], "SELECT ..."),\n'
          '    TiposAlterados = Table.TransformColumnTypes(Consulta, {{"dt_matricula", type date}}),\n'
          '    FiltroIncremental = Table.SelectRows(TiposAlterados, each [dt_matricula] >= RangeStart'
          ' and [dt_matricula] < RangeEnd)\n'
          'in\n'
          '    FiltroIncremental')

M_DIM = ('let\n'
         '    Fonte = GoogleBigQuery.Database(),\n'
         '    Cursos = Fonte{[Name="projeto"]}[Data]{[Name="dataset"]}[Data]{[Name="cursos"]}[Data],\n'
         '    Renomeadas = Table.RenameColumns(Cursos, {{"nome", "Curso"}})\n'
         'in\n'
         '    Renomeadas')

DAX_MATRICULAS = ("DISTINCTCOUNT ( matriculas[id_matricula] )")
DAX_ATIVOS = ("CALCULATE (\n"
              "    [Nº de Matrículas],\n"
              "    matriculas[status] = \"Ativo\"\n"
              ")")
DAX_RLS = ("VAR usuario = USERPRINCIPALNAME ()\n"
           "RETURN [email_responsavel] = usuario")


def _col(nome, tipo, origem=None, calculada=False, dax=None):
    return {"nome": nome, "tipo": "calculada" if calculada else tipo,
            "calculada": calculada, "coluna_origem": None if calculada else (origem or nome),
            "dax": dax}


def manifesto():
    fato_cols = [
        _col("id_matricula", "int64"),
        _col("id_curso", "int64"),
        _col("dt_matricula", "dateTime"),
        _col("status", "string"),
        _col("ano_matricula", None, calculada=True, dax="YEAR ( matriculas[dt_matricula] )"),
    ]
    dim_cols = [
        _col("id_curso", "int64"),
        _col("Curso", "string", origem="nome"),
        _col("modalidade", "string"),
    ]
    tabelas = [
        {"nome": "matriculas", "modo_armazenamento": "import", "qtd_colunas": len(fato_cols),
         "colunas": fato_cols,
         "origem": {"tipo": "Google BigQuery", "projeto": "projeto",
                    "objetos_sql": ["projeto.dataset.matriculas"],
                    "consulta_nativa": True, "atualizacao_incremental": True},
         "particoes": [{"passos": [{"nome": "Fonte"}, {"nome": "Consulta"},
                                   {"nome": "TiposAlterados"}, {"nome": "FiltroIncremental"}],
                        "codigo_m": M_FATO, "sql": [SQL_FATO]}]},
        {"nome": "cursos", "modo_armazenamento": "import", "qtd_colunas": len(dim_cols),
         "colunas": dim_cols,
         "origem": {"tipo": "Google BigQuery", "projeto": "projeto", "schema": "dataset",
                    "objeto": "cursos", "consulta_nativa": False,
                    "atualizacao_incremental": False},
         "particoes": [{"passos": [{"nome": "Fonte"}, {"nome": "Cursos"},
                                   {"nome": "Renomeadas"}],
                        "codigo_m": M_DIM, "sql": []}]},
        {"nome": "Medidas", "modo_armazenamento": "import", "qtd_colunas": 0, "colunas": [],
         "origem": {"tipo": "desconhecida"}, "particoes": []},
    ]
    medidas = [
        {"nome": "Nº de Matrículas", "tabela": "Medidas", "formato": "#,0", "pasta": "Matrículas",
         "dax": DAX_MATRICULAS,
         "depende_de": {"medidas": [], "colunas": ["matriculas[id_matricula]"]}},
        {"nome": "Nº de Ativos", "tabela": "Medidas", "formato": "#,0", "pasta": "Matrículas",
         "dax": DAX_ATIVOS,
         "depende_de": {"medidas": ["Nº de Matrículas"], "colunas": ["matriculas[status]"]}},
    ]
    return {
        "projeto": {"nome": "nome_do_projeto", "pbip": "nome_do_projeto.pbip",
                    "semantic_model": "nome_do_projeto.SemanticModel",
                    "report": "nome_do_projeto.Report",
                    "fontes_dados": ["Google BigQuery (projeto)"], "culture": "pt-BR",
                    "nivel_compatibilidade": "1600"},
        "tabelas": tabelas,
        "medidas": medidas,
        "relacionamentos": [
            {"tabela_origem": "matriculas", "coluna_origem": "id_curso",
             "tabela_destino": "cursos", "coluna_destino": "id_curso",
             "cardinalidade_origem": "many", "cardinalidade_destino": "one",
             "filtro_cruzado": "singleDirection", "ativo": True},
        ],
        "parametros": [
            {"nome": "RangeStart", "tipo": "DateTime", "valor": "#datetime(2024, 1, 1, 0, 0, 0)",
             "descricao_tmdl": None},
            {"nome": "RangeEnd", "tipo": "DateTime", "valor": "#datetime(2025, 1, 1, 0, 0, 0)",
             "descricao_tmdl": None},
        ],
        "perfis_rls": [
            {"nome": "Responsavel", "permissao_modelo": "read",
             "permissoes": [{"tabela": "cursos", "dax": DAX_RLS}]},
        ],
        "relatorio": {"paginas": [
            {"nome": "Visão Geral", "largura": 1280, "altura": 720, "qtd_visuais": 6,
             "tipos_visuais": {"card": 2, "clusteredBarChart": 1, "slicer": 3}},
            {"nome": "Detalhamento", "largura": 1280, "altura": 720, "qtd_visuais": 3,
             "tipos_visuais": {"tableEx": 1, "slicer": 2}},
        ]},
        "estatisticas": {"tabelas": 3, "colunas": 8, "colunas_calculadas": 1, "medidas": 2,
                         "relacionamentos": 1, "parametros": 2, "perfis_rls": 1, "paginas": 2,
                         "visuais": 9, "tabelas_auto_data": 0, "relacionamentos_auto_data": 0},
    }


def descricoes():
    o = {
        "visao_geral": {"texto": (
            "Descreva em dois ou três parágrafos o que o modelo representa, quais processos de "
            "negócio ele cobre e como as tabelas se organizam (fatos, dimensões e tabelas "
            "auxiliares). Exemplo: o modelo acompanha o ciclo das matrículas em cursos, da "
            "inscrição à conclusão.\n\n"
            "Explique também a origem dos dados e a estratégia de atualização. Exemplo: os dados "
            "vêm do data warehouse no Google BigQuery e as tabelas de fato usam atualização "
            "incremental.")},
        "tabela::matriculas": {
            "descricao": "Descreva o que a tabela registra e para que é usada. Exemplo: registra "
                         "cada matrícula de aluno em um curso, com data e status.",
            "grao": "Informe o que uma linha representa. Exemplo: uma linha por matrícula",
            "papel": "fato"},
        "tabela::cursos": {
            "descricao": "Descreva a dimensão. Exemplo: catálogo dos cursos oferecidos, com nome "
                         "e modalidade.",
            "grao": "Exemplo: uma linha por curso", "papel": "dimensao"},
        "tabela::Medidas": {
            "descricao": "Tabela sem dados que apenas agrupa as medidas DAX do modelo.",
            "grao": "Não se aplica", "papel": "medidas"},
        "coluna::matriculas.id_matricula": {"descricao": "Descreva a coluna. Exemplo: "
                                                         "identificador único da matrícula"},
        "coluna::matriculas.id_curso": {"descricao": "Exemplo: chave para a tabela cursos"},
        "coluna::matriculas.dt_matricula": {"descricao": "Exemplo: data em que a matrícula "
                                                         "foi realizada"},
        "coluna::matriculas.status": {"descricao": "Exemplo: situação atual da matrícula "
                                                   "(Ativo, Concluído, Cancelado)"},
        "coluna::matriculas.ano_matricula": {"descricao": "Descreva a regra da coluna calculada. "
                                                          "Exemplo: ano extraído da data da "
                                                          "matrícula"},
        "coluna::cursos.id_curso": {"descricao": "Exemplo: identificador único do curso"},
        "coluna::cursos.Curso": {"descricao": "Exemplo: nome do curso exibido no relatório"},
        "coluna::cursos.modalidade": {"descricao": "Exemplo: modalidade de oferta (EaD, "
                                                   "presencial)"},
        "medida::Medidas::Nº de Matrículas": {
            "descricao": "Descreva o que o indicador mede. Exemplo: volume total de matrículas "
                         "realizadas.",
            "regra": "Descreva o cálculo em linguagem de negócio. Exemplo: contagem distinta do "
                     "identificador da matrícula."},
        "medida::Medidas::Nº de Ativos": {
            "descricao": "Exemplo: quantidade de matrículas com status Ativo no momento da "
                         "consulta.",
            "regra": "Exemplo: aplica o filtro de status Ativo sobre o Nº de Matrículas."},
        "m::matriculas": {
            "resumo": "Resuma o que a query faz. Exemplo: lê as matrículas não excluídas do "
                      "BigQuery e restringe a janela de datas para a atualização incremental.",
            "passos": {
                "Fonte": "Explique cada etapa. Exemplo: conecta ao Google BigQuery.",
                "Consulta": "Exemplo: executa a consulta SQL nativa na origem.",
                "TiposAlterados": "Exemplo: converte a data da matrícula para o tipo data.",
                "FiltroIncremental": "Exemplo: mantém apenas o intervalo entre RangeStart e "
                                     "RangeEnd."}},
        "m::cursos": {
            "resumo": "Exemplo: lê a tabela de cursos e renomeia as colunas para o padrão do "
                      "relatório.",
            "passos": {"Fonte": "Exemplo: conecta ao Google BigQuery.",
                       "Cursos": "Exemplo: navega até a tabela de cursos.",
                       "Renomeadas": "Exemplo: renomeia a coluna nome para Curso."}},
        "parametro::RangeStart": {"descricao": "Descreva a função do parâmetro. Exemplo: início "
                                               "da janela da atualização incremental"},
        "parametro::RangeEnd": {"descricao": "Exemplo: fim da janela da atualização "
                                             "incremental"},
        "rls::Responsavel": {"descricao": "Descreva quem usa o perfil e o que ele restringe. "
                                          "Exemplo: cada responsável vê apenas os cursos sob "
                                          "sua gestão."},
    }
    return {"schema_version": 1, "projeto": "nome_do_projeto", "objetos": o}


def cfg():
    return {
        "titulo": "[NOME DO PROJETO]",
        "subtitulo": "Documentação Técnica do Modelo de Dados",
        "elaborado_por": "[Nome de quem elaborou]",
        "revisado_por": "[Nome de quem revisou]",
        "link_relatorio": "[Link do relatório publicado no Power BI]",
        "frequencia_atualizacao": "[Ex.: diária, às 6h]",
        "objetivo": ("Descreva por que o documento existe e a quem ele se destina. Exemplo: "
                     "descrever o modelo de dados do projeto para que regras de negócio, origem "
                     "dos dados e cálculos sejam compreendidos da mesma forma por todos. Este "
                     "modelo mostra a estrutura, a ordem dos tópicos e a formatação que o "
                     "pbidoc gera automaticamente a partir do projeto PBIP."),
    }


# ------------------------------------------------------------ modelo do relatório conectado


def _campo_v(tabela, campo, tipo="coluna", papel="Values", rotulo=None, agregacao=None):
    return {"tabela": tabela, "campo": campo, "tipo": tipo, "extensao": False, "papel": papel,
            "rotulo": rotulo or campo, "agregacao": agregacao}


def _visual(tipo, titulo, campos, filtros=(), ordenacao=(), extra=None):
    v = {"id": "v", "tipo": tipo, "titulo": titulo, "campos": list(campos),
         "ordenacao": list(ordenacao), "filtros": list(filtros), "oculto": False, "grupo": None,
         "tooltip_pagina": None}
    v.update(extra or {})
    return v


def manifesto_relatorio():
    """Relatório conectado fictício: as mesmas estruturas que o extrator produz."""
    filtro = {"tabela": "vendas", "campo": "status", "tipo_campo": "coluna",
              "tipo_filtro": "Categorical", "aplicado": True, "condicao": "exceto Cancelado",
              "criado_como": "User", "oculto": False, "bloqueado": False}
    pagina1 = {
        "id": "p1", "nome": "Visão Geral", "tipo": "Padrao", "oculta": False, "largura": 1280,
        "altura": 720, "exibicao": "FitToPage", "drillthrough": None, "qtd_grupos": 0,
        "grupos": [], "ordem": 0, "hash": "p1", "qtd_visuais": 4, "tipos_visuais": {},
        "filtros": [filtro],
        "visuais": [
            _visual("textbox", None, [], extra={"texto": "Painel de Vendas\nVisão Geral"}),
            _visual("slicer", "Período", [_campo_v("calendario", "data")],
                    extra={"segmentacao": {"modo": "Between", "cabecalho": "Período",
                                           "sync": "periodo"}}),
            _visual("card", "Total vendido",
                    [_campo_v("medidas", "total_vendido", "medida", rotulo="Total vendido")]),
            _visual("clusteredColumnChart", "Vendas por região",
                    [_campo_v("regioes", "regiao", papel="Category"),
                     _campo_v("medidas", "total_vendido", "medida", "Y")],
                    ordenacao=[{"tabela": "medidas", "campo": "total_vendido",
                                "direcao": "decrescente"}]),
        ],
    }
    pagina2 = {
        "id": "p2", "nome": "Detalhe do Cliente", "tipo": "Padrao", "oculta": False,
        "largura": 1280, "altura": 720, "exibicao": "FitToPage", "qtd_grupos": 0, "grupos": [],
        "drillthrough": {"tipo": "Drillthrough", "escopo": "CrossReport",
                         "campos": [_campo_v("clientes", "cliente")]},
        "ordem": 1, "hash": "p2", "qtd_visuais": 1, "tipos_visuais": {}, "filtros": [],
        "visuais": [_visual("tableEx", "Pedidos do cliente",
                            [_campo_v("clientes", "cliente"), _campo_v("vendas", "id_pedido"),
                             _campo_v("vendas", "valor", agregacao="Soma")])],
    }
    ext = {"tabela": "medidas", "nome": "ticket_medio", "dax": "DIVIDE ( [total_vendido], "
           "DISTINCTCOUNT ( vendas[id_pedido] ) )", "tipo_dado": "Double", "formato": "#,0.00",
           "pasta": "Vendas", "colunas_citadas": ["vendas[id_pedido]"],
           "medidas_citadas": ["total_vendido"], "hash": "e1"}
    usados = [
        {"tabela": "calendario", "campo": "data", "tipo": "coluna", "origem": "dataset",
         "paginas": ["Visão Geral"]},
        {"tabela": "clientes", "campo": "cliente", "tipo": "coluna", "origem": "dataset",
         "paginas": ["Detalhe do Cliente"]},
        {"tabela": "medidas", "campo": "total_vendido", "tipo": "medida", "origem": "dataset",
         "paginas": ["Visão Geral"]},
        {"tabela": "medidas", "campo": "ticket_medio", "tipo": "medida", "origem": "extensao",
         "paginas": ["Visão Geral"]},
        {"tabela": "regioes", "campo": "regiao", "tipo": "coluna", "origem": "dataset",
         "paginas": ["Visão Geral"]},
        {"tabela": "vendas", "campo": "id_pedido", "tipo": "coluna", "origem": "dataset",
         "paginas": ["Detalhe do Cliente"]},
        {"tabela": "vendas", "campo": "status", "tipo": "coluna", "origem": "dataset",
         "paginas": ["Visão Geral"]},
        {"tabela": "vendas", "campo": "valor", "tipo": "coluna", "origem": "dataset",
         "paginas": ["Detalhe do Cliente"]},
    ]
    dataset = {"referencia": "byConnection",
               "servidor": "powerbi://api.powerbi.com/v1.0/myorg/Datasets",
               "catalogo": "nome_do_dataset", "modelo_id": "00000000-0000-0000-0000-000000000000",
               "modo_acesso": "readonly", "seguranca": "ClaimsToken", "caminho": None,
               "tabelas": ["calendario", "clientes", "medidas", "regioes", "vendas", "produtos"]}
    rel = {
        "paginas": [pagina1, pagina2], "total_visuais": 5, "filtros": [],
        "campos_usados": usados, "extensoes": [ext],
        "bookmarks": [{"id": "b1", "nome": "Visão do gestor", "pagina_id": "p1",
                       "pagina": "Visão Geral", "visuais_alvo": ["v"], "apenas_alvos": True,
                       "ordem": 0}],
        "tema": {"base": "CY24SU10", "personalizado": "TemaCorporativo",
                 "cores": ["#1F77B4", "#FF7F0E", "#2CA02C"]},
        "configuracoes": {"useEnhancedTooltips": True, "exportDataMode": "AllowSummarized"},
        "sync_groups": [{"grupo": "periodo", "paginas": ["Visão Geral"]}],
        "alertas": [{"tipo": "extensao_sem_uso_em_visual", "pagina": None, "visual": None,
                     "detalhe": "Exemplo: a medida de relatório 'ticket_medio' não aparece em "
                                "nenhum visual nem filtro."}],
    }
    return {
        "schema_version": 1,
        "projeto": {"nome": "nome_do_relatorio", "pasta": "nome_do_relatorio",
                    "tipo": "relatorio_conectado", "pbip": "nome_do_relatorio.pbip",
                    "semantic_model": None, "report": "nome_do_relatorio.Report",
                    "dataset": dataset, "nivel_compatibilidade": None, "culture": None,
                    "fontes_dados": ["Dataset nome_do_dataset (Power BI)"],
                    "inteligencia_tempo_automatica": False},
        "tabelas": [], "medidas": [], "relacionamentos": [], "parametros": [], "perfis_rls": [],
        "relatorio": rel,
        "estatisticas": {"tabelas": 0, "colunas": 0, "colunas_calculadas": 0, "medidas": 0,
                         "relacionamentos": 0, "relacionamentos_auto_data": 0,
                         "tabelas_auto_data": 0, "parametros": 0, "perfis_rls": 0,
                         "tabelas_dataset": 6, "paginas": 2, "visuais": 5, "extensoes": 1,
                         "bookmarks": 1, "alertas": 1},
    }


def descricoes_relatorio():
    o = {
        "visao_geral": {"texto": "Descreva o que o relatório mostra e para quem. Exemplo: painel "
                                 "de acompanhamento de vendas, com totais, evolução e detalhe "
                                 "por cliente.\n\nDescreva de onde vêm os dados. Exemplo: o "
                                 "relatório se conecta ao dataset publicado e não contém dados "
                                 "próprios."},
        "pagina::Visão Geral": {"descricao": "Descreva o que a página apresenta e a análise que "
                                             "ela permite. Exemplo: apresenta o total vendido e "
                                             "as vendas por região, com filtro por período."},
        "pagina::Detalhe do Cliente": {"descricao": "Descreva a página. Exemplo: lista os "
                                                    "pedidos de um cliente, acessada por "
                                                    "drillthrough."},
        "medida::medidas::ticket_medio": {
            "descricao": "Descreva o que a medida calcula. Exemplo: calcula o valor médio por "
                         "pedido.",
            "regra": "Explique a regra em linguagem de negócio. Exemplo: divide o total vendido "
                     "pela quantidade de pedidos distintos."},
        "medida::medidas::total_vendido": {
            "descricao": "Descreva a medida do dataset pelo que o relatório mostra. Exemplo: "
                         "soma o valor das vendas no período filtrado."},
        "coluna::calendario.data": {"descricao": "Data de referência da venda"},
        "coluna::clientes.cliente": {"descricao": "Nome do cliente"},
        "coluna::regioes.regiao": {"descricao": "Região de atuação da venda"},
        "coluna::vendas.id_pedido": {"descricao": "Identificador do pedido"},
        "coluna::vendas.status": {"descricao": "Situação do pedido"},
        "coluna::vendas.valor": {"descricao": "Valor do pedido"},
    }
    return {"schema_version": 1, "projeto": "nome_do_relatorio", "objetos": o}


def cfg_relatorio():
    return {
        "titulo": "[NOME DO RELATÓRIO]",
        "subtitulo": "Documentação Técnica do Relatório",
        "elaborado_por": "[Nome de quem elaborou]",
        "revisado_por": "[Nome de quem revisou]",
        "link_relatorio": "[Link do relatório publicado no Power BI]",
        "frequencia_atualizacao": "[Ex.: diária, às 6h]",
        "objetivo": ("Descreva por que o documento existe e a quem ele se destina. Este modelo "
                     "mostra a estrutura, a ordem dos tópicos e a formatação que o pbidoc gera "
                     "automaticamente para um relatório conectado a um dataset."),
    }


def build_relatorio(destino):
    import render_docx_relatorio
    meta = {"criado_em": "01/01/2000", "atualizado_em": "02/01/2000"}
    with tempfile.TemporaryDirectory() as tmp:
        nome = render_docx_relatorio.render(manifesto_relatorio(), cfg_relatorio(),
                                            descricoes_relatorio(), tmp, meta)
        gerado = os.path.join(tmp, nome or "")
        if not nome or not os.path.isfile(gerado):
            raise SystemExit("Falha ao gerar o modelo de relatório.")
        os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
        with open(gerado, "rb") as src, open(destino, "wb") as dst:
            dst.write(src.read())
    return destino


def build(destino):
    meta = {"criado_em": "01/01/2000", "atualizado_em": "02/01/2000"}
    with tempfile.TemporaryDirectory() as tmp:
        nome = render_docx.render(manifesto(), cfg(), descricoes(), tmp, meta)
        gerado = os.path.join(tmp, nome or "")
        if not nome or not os.path.isfile(gerado):
            raise SystemExit("Falha ao gerar o modelo técnico.")
        os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
        with open(gerado, "rb") as src, open(destino, "wb") as dst:
            dst.write(src.read())
    return destino


def main(argv):
    argv = list(argv)
    tipo = "tecnico"
    if "--tipo" in argv:
        i = argv.index("--tipo")
        if i + 1 >= len(argv) or argv[i + 1] not in ("tecnico", "relatorio"):
            raise SystemExit("--tipo deve ser tecnico ou relatorio")
        tipo = argv[i + 1]
        del argv[i:i + 2]
    if tipo == "relatorio":
        destino = argv[0] if argv else DESTINO_RELATORIO
        build_relatorio(destino)
    else:
        destino = argv[0] if argv else DESTINO_PADRAO
        build(destino)
    print("Modelo gravado em %s" % destino)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
