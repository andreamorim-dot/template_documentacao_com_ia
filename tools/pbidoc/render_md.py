"""Renderiza a documentação Markdown multi-arquivo. 100% determinístico."""

import re

import render_common as rc

ARQ_PRINCIPAL = "README.md"
ARQ_MEDIDAS = "01-medidas.md"
ARQ_TABELAS = "02-tabelas.md"
ARQ_QUERIES = "03-queries-m.md"
ARQ_MODELO = "04-modelo-relacional.md"

VOLTAR = "[⬅ **Voltar para a documentação principal**](./%s)" % ARQ_PRINCIPAL
NOTA_GERADO = (
    "> _Arquivo gerado automaticamente pela skill `pbi-doc-md` a partir dos arquivos TMDL do "
    "projeto. **Não edite este arquivo à mão** — as alterações são perdidas na próxima "
    "geração. Para ajustar textos descritivos, edite `_descriptions.json`._"
)
PENDENTE = "_(descrição pendente)_"


def _cel(texto):
    """Normaliza um valor para caber numa célula de tabela Markdown."""
    if texto is None or texto == "":
        return "—"
    s = str(texto).replace("|", "\\|")
    s = re.sub(r"\s*\n\s*", " ", s).strip()
    return s or "—"


def _codigo(texto, linguagem=""):
    corpo = (texto or "").rstrip()
    cerca = "```"
    while cerca in corpo:
        cerca += "`"
    return "%s%s\n%s\n%s" % (cerca, linguagem, corpo, cerca)


def _prosa(valor):
    return valor.strip() if valor and valor.strip() else PENDENTE


def _link(texto, arquivo, ancora):
    return "[%s](./%s#%s)" % (texto, arquivo, ancora)


def _tabela(cabecalho, linhas):
    out = ["| " + " | ".join(cabecalho) + " |",
           "|" + "|".join([" --- "] * len(cabecalho)) + "|"]
    for linha in linhas:
        out.append("| " + " | ".join(_cel(c) for c in linha) + " |")
    return "\n".join(out)


# --------------------------------------------------------------------------- README


def _readme(man, cfg, prosa, indices):
    est = man["estatisticas"]
    proj = man["projeto"]
    L = []
    L.append("# %s" % cfg["titulo"])
    L.append("")
    L.append("**%s**" % cfg["subtitulo"])
    L.append("")
    L.append("| | |")
    L.append("| --- | --- |")
    L.append("| **Projeto** | `%s` |" % proj["nome"])
    L.append("| **Modelo semântico** | `%s` |" % (proj["semantic_model"] or "—"))
    L.append("| **Relatório** | `%s` |" % (proj["report"] or "—"))
    L.append("| **Fontes de dados** | %s |" % _cel(", ".join(proj["fontes_dados"]) or "—"))
    L.append("| **Idioma do modelo** | %s |" % _cel(proj["culture"]))
    L.append("| **Nível de compatibilidade** | %s |" % _cel(proj["nivel_compatibilidade"]))
    if cfg.get("link_relatorio"):
        L.append("| **Link do relatório** | %s |" % _cel(cfg["link_relatorio"]))
    if cfg.get("frequencia_atualizacao"):
        L.append("| **Frequência de atualização** | %s |" % _cel(cfg["frequencia_atualizacao"]))
    L.append("| **Atualizado em** | %s |" % rc.PLACEHOLDER_DATA)
    L.append("")

    if cfg.get("objetivo"):
        L.append("## Objetivo")
        L.append("")
        L.append(cfg["objetivo"].strip())
        L.append("")

    L.append("## Visão geral")
    L.append("")
    L.append(_prosa(prosa.visao_geral()))
    L.append("")

    L.append("## O modelo em números")
    L.append("")
    L.append(_tabela(["Item", "Quantidade"], [
        ["Tabelas", est["tabelas"]],
        ["Colunas", est["colunas"]],
        ["Colunas calculadas", est["colunas_calculadas"]],
        ["Medidas DAX", est["medidas"]],
        ["Relacionamentos", est["relacionamentos"]],
        ["Parâmetros do Power Query", est["parametros"]],
        ["Perfis de segurança (RLS)", est["perfis_rls"]],
        ["Páginas do relatório", est["paginas"]],
        ["Visuais no relatório", est["visuais"]],
    ]))
    L.append("")

    L.append("## Índice")
    L.append("")
    L.append(_tabela(["Documento", "O que contém"], [
        ["**[📊 Medidas](./%s)**" % ARQ_MEDIDAS,
         "As %d medidas DAX do modelo, com descrição de negócio, regra de cálculo, "
         "código e dependências." % est["medidas"]],
        ["**[🗃️ Tabelas](./%s)**" % ARQ_TABELAS,
         "As %d tabelas, suas %d colunas, colunas calculadas e os %d perfis de "
         "segurança em nível de linha." % (est["tabelas"], est["colunas"], est["perfis_rls"])],
        ["**[🔄 Queries M](./%s)**" % ARQ_QUERIES,
         "Parâmetros, atualização incremental e o código Power Query de cada tabela, "
         "com os tratamentos aplicados passo a passo."],
        ["**[🔗 Modelo relacional](./%s)**" % ARQ_MODELO,
         "Diagrama Mermaid do esquema e as propriedades dos %d relacionamentos."
         % est["relacionamentos"]],
    ]))
    L.append("")

    L.append("### Atalhos")
    L.append("")
    for titulo, arquivo, itens in indices:
        if not itens:
            continue
        L.append("**%s**" % titulo)
        L.append("")
        L.append(" · ".join(_link("`%s`" % nome, arquivo, anc) for nome, anc in itens))
        L.append("")

    if man["relatorio"]["paginas"]:
        L.append("## Páginas do relatório")
        L.append("")
        linhas = []
        for p in man["relatorio"]["paginas"]:
            tipos = ", ".join("%s (%d)" % (t, n) for t, n in
                              sorted(p["tipos_visuais"].items(), key=lambda kv: (-kv[1], kv[0]))[:4])
            linhas.append([p["nome"], "%d × %d" % (p["largura"] or 0, p["altura"] or 0),
                           p["qtd_visuais"], tipos, "Sim" if p["oculta"] else "Não"])
        L.append(_tabela(["Página", "Dimensões", "Visuais", "Principais tipos de visual", "Oculta"],
                         linhas))
        L.append("")

    L.append("## Como esta documentação é mantida")
    L.append("")
    L.append("A documentação é regenerada automaticamente a cada `git commit` que altere os "
             "arquivos do projeto Power BI (`*.tmdl`, `*.pbir`, `*.pbip`).")
    L.append("")
    L.append("- **Estrutura, DAX e código M** são extraídos dos arquivos do projeto — sempre "
             "refletem o estado atual do modelo.")
    L.append("- **Textos descritivos** ficam em `_descriptions.json` e só são reescritos quando "
             "a definição do objeto correspondente muda.")
    L.append("- Trechos marcados como %s ainda não foram descritos; rode a skill "
             "`/pbi-doc-md` para completá-los." % PENDENTE)
    L.append("")
    L.append(NOTA_GERADO)
    L.append("")
    return "\n".join(L)


# -------------------------------------------------------------------------- medidas


def _medidas(man, prosa):
    est = man["estatisticas"]
    usados = set()
    L = [VOLTAR, "", "# Medidas", "",
         "Este documento descreve as **%d medidas DAX** do modelo `%s`." %
         (est["medidas"], man["projeto"]["nome"]), ""]

    por_tabela = {}
    for m in man["medidas"]:
        por_tabela.setdefault(m["tabela"], []).append(m)

    ancoras = {}
    for tabela in sorted(por_tabela):
        rc.slug(tabela, usados)
        for m in por_tabela[tabela]:
            ancoras[(tabela, m["nome"])] = rc.slug(m["nome"], usados)

    L.append("## Índice de medidas")
    L.append("")
    for tabela in sorted(por_tabela):
        L.append("**Tabela `%s`** — %d medidas" % (tabela, len(por_tabela[tabela])))
        L.append("")
        L.append(" · ".join("[`%s`](#%s)" % (m["nome"], ancoras[(tabela, m["nome"])])
                            for m in por_tabela[tabela]))
        L.append("")

    for tabela in sorted(por_tabela):
        L.append("---")
        L.append("")
        L.append("## %s" % tabela)
        L.append("")
        for m in por_tabela[tabela]:
            L.append("### %s" % m["nome"])
            L.append("")
            if prosa.revisar(("medida::%s::%s" % (tabela, m["nome"]))):
                L.append("> ⚠️ **Revisar:** a descrição desta medida precisa de validação humana.")
                L.append("")
            props = [["Tabela", "`%s`" % m["tabela"]],
                     ["Formato", "`%s`" % m["formato"] if m["formato"] else "—"],
                     ["Pasta de exibição", m["pasta"] or "—"],
                     ["Oculta", "Sim" if m["oculta"] else "Não"]]
            L.append(_tabela(["Propriedade", "Valor"], props))
            L.append("")
            L.append("**Descrição:** %s" % _prosa(prosa.medida(tabela, m["nome"], "descricao")))
            L.append("")
            L.append("**Regra de cálculo:** %s" % _prosa(prosa.medida(tabela, m["nome"], "regra")))
            L.append("")
            L.append("**Expressão DAX**")
            L.append("")
            L.append(_codigo(m["dax"], "dax"))
            L.append("")
            dep = m.get("depende_de") or {}
            partes = []
            if dep.get("medidas"):
                partes.append("**Medidas:** " + ", ".join("`[%s]`" % d for d in dep["medidas"]))
            if dep.get("colunas"):
                partes.append("**Colunas:** " + ", ".join("`%s`" % d for d in dep["colunas"]))
            L.append("**Depende de:** " + ("<br>".join(partes) if partes else "— (nenhuma referência direta)"))
            L.append("")

    L.append("---")
    L.append("")
    L.append(NOTA_GERADO)
    L.append("")
    L.append(VOLTAR)
    L.append("")
    return "\n".join(L), [(m["nome"], ancoras[(m["tabela"], m["nome"])]) for m in man["medidas"]]


# -------------------------------------------------------------------------- tabelas


def _tabelas(man, prosa):
    est = man["estatisticas"]
    usados = set()
    ancoras = {t["nome"]: rc.slug(t["nome"], usados) for t in man["tabelas"]}

    L = [VOLTAR, "", "# Tabelas", "",
         "As **%d tabelas** do modelo `%s`, com suas %d colunas (%d calculadas)." %
         (est["tabelas"], man["projeto"]["nome"], est["colunas"], est["colunas_calculadas"]), ""]

    L.append("## Índice de tabelas")
    L.append("")
    linhas = []
    for t in man["tabelas"]:
        papel = rc.PAPEL_ROTULO.get(prosa.tabela(t["nome"], "papel"), prosa.tabela(t["nome"], "papel") or "—")
        linhas.append(["[`%s`](#%s)" % (t["nome"], ancoras[t["nome"]]), papel,
                       t["qtd_colunas"], t["qtd_colunas_calculadas"],
                       prosa.tabela(t["nome"], "descricao", PENDENTE)])
    L.append(_tabela(["Tabela", "Papel", "Colunas", "Calculadas", "Descrição"], linhas))
    L.append("")

    for t in man["tabelas"]:
        L.append("---")
        L.append("")
        L.append("## %s" % t["nome"])
        L.append("")
        if prosa.revisar("tabela::%s" % t["nome"]):
            L.append("> ⚠️ **Revisar:** a descrição desta tabela precisa de validação humana.")
            L.append("")
        L.append("**Descrição:** %s" % _prosa(prosa.tabela(t["nome"], "descricao")))
        L.append("")
        L.append("**Grão:** %s" % _prosa(prosa.tabela(t["nome"], "grao")))
        L.append("")
        origem = t["origem"] or {}
        objetos = ", ".join("`%s`" % o for o in origem.get("objetos_sql", [])) or (
            "`%s.%s`" % (origem.get("schema"), origem.get("objeto"))
            if origem.get("objeto") else "—")
        props = [
            ["Papel no modelo", rc.PAPEL_ROTULO.get(prosa.tabela(t["nome"], "papel"),
                                                    prosa.tabela(t["nome"], "papel") or "—")],
            ["Origem", origem.get("tipo") or "—"],
            ["Projeto/base", "`%s`" % origem["projeto"] if origem.get("projeto") else "—"],
            ["Objeto de origem", objetos],
            ["Modo de armazenamento", t["modo_armazenamento"] or "—"],
            ["Consulta nativa (SQL)", "Sim" if origem.get("consulta_nativa") else "Não"],
            ["Atualização incremental", "Sim" if origem.get("atualizacao_incremental") else "Não"],
            ["Colunas", t["qtd_colunas"]],
            ["Colunas calculadas", t["qtd_colunas_calculadas"]],
            ["Oculta", "Sim" if t["oculta"] else "Não"],
            ["Query M", "[Ver código e tratamentos](./%s#%s)" % (ARQ_QUERIES, rc.slug(t["nome"]))],
        ]
        L.append(_tabela(["Propriedade", "Valor"], props))
        L.append("")

        if t["colunas"]:
            L.append("### Colunas de `%s`" % t["nome"])
            L.append("")
            linhas = []
            for c in t["colunas"]:
                linhas.append([
                    "`%s`" % c["nome"],
                    rc.tipo_rotulo(c["tipo"]),
                    "`%s`" % c["formato"] if c["formato"] else "—",
                    "Calculada" if c["calculada"] else ("`%s`" % c["coluna_origem"]
                                                        if c["coluna_origem"] else "—"),
                    prosa.coluna(t["nome"], c["nome"], PENDENTE),
                ])
            L.append(_tabela(["Coluna", "Tipo", "Formato", "Origem", "Descrição"], linhas))
            L.append("")

        calculadas = [c for c in t["colunas"] if c["calculada"]]
        if calculadas:
            L.append("### Colunas calculadas de `%s`" % t["nome"])
            L.append("")
            for c in calculadas:
                L.append("#### `%s`" % c["nome"])
                L.append("")
                L.append("**Descrição:** %s" % _prosa(prosa.coluna(t["nome"], c["nome"])))
                L.append("")
                L.append(_codigo(c["dax"], "dax"))
                L.append("")

        if t["hierarquias"]:
            L.append("### Hierarquias de `%s`" % t["nome"])
            L.append("")
            for h in t["hierarquias"]:
                L.append("- **%s:** %s" % (h["nome"], " → ".join("`%s`" % n["coluna"]
                                                                for n in h["niveis"])))
            L.append("")

    if man["perfis_rls"]:
        L.append("---")
        L.append("")
        L.append("## Segurança em nível de linha (RLS)")
        L.append("")
        L.append("O modelo define **%d perfis** de segurança. Cada perfil aplica um filtro DAX "
                 "por tabela, avaliado no contexto do usuário autenticado."
                 % len(man["perfis_rls"]))
        L.append("")
        L.append(_tabela(["Perfil", "Permissão", "Tabelas filtradas", "Descrição"],
                         [[ "`%s`" % r["nome"], r["permissao_modelo"] or "—",
                            len(r["permissoes"]), prosa.rls(r["nome"], PENDENTE)]
                          for r in man["perfis_rls"]]))
        L.append("")
        for r in man["perfis_rls"]:
            L.append("### Perfil `%s`" % r["nome"])
            L.append("")
            L.append("**Descrição:** %s" % _prosa(prosa.rls(r["nome"])))
            L.append("")
            L.append("**Permissão no modelo:** `%s`" % (r["permissao_modelo"] or "—"))
            L.append("")
            for p in r["permissoes"]:
                L.append("<details>")
                L.append("<summary>Filtro aplicado em <code>%s</code></summary>" % p["tabela"])
                L.append("")
                L.append(_codigo(p["dax"], "dax"))
                L.append("")
                L.append("</details>")
                L.append("")

    L.append("---")
    L.append("")
    L.append(NOTA_GERADO)
    L.append("")
    L.append(VOLTAR)
    L.append("")
    return "\n".join(L), [(t["nome"], ancoras[t["nome"]]) for t in man["tabelas"]]


# -------------------------------------------------------------------------- queries


def _queries(man, prosa):
    usados = set()
    ancoras = {t["nome"]: rc.slug(t["nome"], usados) for t in man["tabelas"] if t["particoes"]}
    incrementais = [t for t in man["tabelas"] if (t["origem"] or {}).get("atualizacao_incremental")]

    L = [VOLTAR, "", "# Queries M (Power Query)", "",
         "Código Power Query de cada tabela do modelo `%s` e os tratamentos aplicados." %
         man["projeto"]["nome"], ""]

    if man["parametros"]:
        L.append("## Parâmetros")
        L.append("")
        L.append("Parâmetros do Power Query usados pelas consultas do modelo.")
        L.append("")
        L.append(_tabela(["Parâmetro", "Tipo", "Valor atual", "Obrigatório", "Função"],
                         [["`%s`" % p["nome"], p["tipo"] or "—", "`%s`" % p["valor"],
                           "Sim" if p["obrigatorio"] else "Não",
                           prosa.parametro(p["nome"], p["descricao_tmdl"] or PENDENTE)]
                          for p in man["parametros"]]))
        L.append("")

    if incrementais:
        L.append("## Atualização incremental")
        L.append("")
        L.append("As tabelas abaixo usam os parâmetros `RangeStart` e `RangeEnd` para restringir "
                 "a janela de dados lida da origem, permitindo que o Power BI atualize apenas as "
                 "partições afetadas em vez de recarregar a tabela inteira.")
        L.append("")
        for t in incrementais:
            L.append("- **`%s`** — %s" % (t["nome"], _prosa(prosa.m(t["nome"], "resumo"))))
        L.append("")

    L.append("## Consultas por tabela")
    L.append("")
    L.append(" · ".join("[`%s`](#%s)" % (n, a) for n, a in ancoras.items()))
    L.append("")

    for t in man["tabelas"]:
        if not t["particoes"]:
            continue
        L.append("---")
        L.append("")
        L.append("## %s" % t["nome"])
        L.append("")
        L.append("**Resumo:** %s" % _prosa(prosa.m(t["nome"], "resumo")))
        L.append("")
        origem = t["origem"] or {}
        objetos = ", ".join("`%s`" % o for o in origem.get("objetos_sql", [])) or (
            "`%s.%s`" % (origem.get("schema"), origem.get("objeto"))
            if origem.get("objeto") else "—")
        L.append(_tabela(["Propriedade", "Valor"], [
            ["Origem", origem.get("tipo") or "—"],
            ["Projeto/base", "`%s`" % origem["projeto"] if origem.get("projeto") else "—"],
            ["Objeto de origem", objetos],
            ["Modo", t["modo_armazenamento"] or "—"],
            ["Consulta nativa (SQL)", "Sim" if origem.get("consulta_nativa") else "Não"],
            ["Atualização incremental", "Sim" if origem.get("atualizacao_incremental") else "Não"],
            ["Definição da tabela", "[Ver colunas](./%s#%s)" % (ARQ_TABELAS, rc.slug(t["nome"]))],
        ]))
        L.append("")

        for part in t["particoes"]:
            if len(t["particoes"]) > 1:
                L.append("### Partição `%s`" % part["nome"])
                L.append("")
            if part["passos"]:
                L.append("#### Tratamentos aplicados")
                L.append("")
                for i, passo in enumerate(part["passos"], 1):
                    L.append("%d. **`%s`** — %s" %
                             (i, passo["nome"], _prosa(prosa.passo(t["nome"], passo["nome"]))))
                L.append("")
            L.append("#### Código M")
            L.append("")
            L.append(_codigo(part["codigo_m"], "powerquery"))
            L.append("")
            for i, sql in enumerate(part["sql"], 1):
                L.append("#### Consulta SQL nativa%s" %
                         ("" if len(part["sql"]) == 1 else " %d" % i))
                L.append("")
                L.append(_codigo(sql, "sql"))
                L.append("")

    L.append("---")
    L.append("")
    L.append(NOTA_GERADO)
    L.append("")
    L.append(VOLTAR)
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- modelo


def _mermaid(man):
    rels = man["relacionamentos"]
    envolvidas = {}
    for r in rels:
        envolvidas.setdefault(r["tabela_origem"], set()).add(r["coluna_origem"])
        envolvidas.setdefault(r["tabela_destino"], set()).add(r["coluna_destino"])

    tipos = {}
    for t in man["tabelas"]:
        for c in t["colunas"]:
            tipos[(t["nome"], c["nome"])] = c["tipo"]

    L = ["erDiagram"]
    for tabela in sorted(envolvidas):
        L.append("    %s {" % tabela)
        for col in sorted(envolvidas[tabela]):
            tipo = (tipos.get((tabela, col)) or "coluna").replace(" ", "_")
            L.append("        %s %s" % (tipo, re.sub(r"[^\w]", "_", col)))
        L.append("    }")
    for r in rels:
        esq = "||" if r["cardinalidade_origem"] == "one" else "}o"
        dir_ = "||" if r["cardinalidade_destino"] == "one" else "o{"
        traco = "--" if r["ativo"] else ".."
        rotulo = r["coluna_origem"] if r["coluna_origem"] == r["coluna_destino"] else \
            "%s → %s" % (r["coluna_origem"], r["coluna_destino"])
        if not r["ativo"]:
            rotulo += " (inativo)"
        L.append('    %s %s%s%s %s : "%s"' %
                 (r["tabela_origem"], esq, traco, dir_, r["tabela_destino"], rotulo))
    return "\n".join(L)


def _modelo(man, prosa):
    est = man["estatisticas"]
    L = [VOLTAR, "", "# Modelo relacional", "",
         "Esquema de relacionamentos do modelo `%s`: **%d relacionamentos** entre "
         "**%d tabelas**." % (man["projeto"]["nome"], est["relacionamentos"], est["tabelas"]), ""]

    L.append("## Diagrama")
    L.append("")
    L.append("> O diagrama mostra apenas as colunas que participam de relacionamentos. "
             "Linhas tracejadas indicam relacionamentos **inativos** (usados via `USERELATIONSHIP`).")
    L.append("")
    L.append(_codigo(_mermaid(man), "mermaid"))
    L.append("")

    L.append("## Relacionamentos detalhados")
    L.append("")
    L.append("O diagrama Mermaid não expressa direção de filtro nem filtro de segurança; "
             "a tabela abaixo completa essas informações.")
    L.append("")
    linhas = []
    for i, r in enumerate(man["relacionamentos"], 1):
        linhas.append([
            i,
            "`%s[%s]`" % (r["tabela_origem"], r["coluna_origem"]),
            "`%s[%s]`" % (r["tabela_destino"], r["coluna_destino"]),
            rc.cardinalidade(r),
            rc.filtro_rotulo(r["filtro_cruzado"]),
            rc.filtro_rotulo(r["filtro_seguranca"]) if r["filtro_seguranca"] else "—",
            "✅ Ativo" if r["ativo"] else "⛔ Inativo",
        ])
    L.append(_tabela(["#", "Origem", "Destino", "Cardinalidade", "Filtro cruzado",
                      "Filtro de segurança", "Estado"], linhas))
    L.append("")

    bidir = [r for r in man["relacionamentos"] if r["filtro_cruzado"] == "bothDirections"]
    inativos = [r for r in man["relacionamentos"] if not r["ativo"]]
    L.append("### Pontos de atenção")
    L.append("")
    L.append("- **Filtro cruzado bidirecional:** %d de %d relacionamentos. Filtros bidirecionais "
             "propagam contexto nos dois sentidos e podem gerar ambiguidade ou impacto de "
             "desempenho em modelos grandes." % (len(bidir), len(man["relacionamentos"])))
    if inativos:
        L.append("- **Relacionamentos inativos:** %s. Só entram em vigor dentro de "
                 "`CALCULATE` com `USERELATIONSHIP`." %
                 ", ".join("`%s[%s]` → `%s[%s]`" % (r["tabela_origem"], r["coluna_origem"],
                                                    r["tabela_destino"], r["coluna_destino"])
                           for r in inativos))
    else:
        L.append("- **Relacionamentos inativos:** nenhum.")
    if est["tabelas_auto_data"]:
        L.append("- **Tabelas de data automáticas:** o Power BI gerou %d tabelas ocultas "
                 "(`LocalDateTable_*` / `DateTableTemplate_*`) e %d relacionamentos "
                 "correspondentes, um para cada coluna de data do modelo. Elas foram omitidas "
                 "desta documentação por não terem significado de negócio. Para eliminá-las, "
                 "desative *Opções → Carregar dados → Data/hora automática*."
                 % (est["tabelas_auto_data"], est["relacionamentos_auto_data"]))
    L.append("")

    papeis = {}
    for t in man["tabelas"]:
        papel = prosa.tabela(t["nome"], "papel") or "nao_classificada"
        papeis.setdefault(papel, []).append(t["nome"])
    if papeis:
        L.append("## Tabelas por papel")
        L.append("")
        for papel in sorted(papeis):
            rotulo = rc.PAPEL_ROTULO.get(papel, "Não classificada")
            L.append("- **%s:** %s" % (rotulo, ", ".join("`%s`" % n for n in sorted(papeis[papel]))))
        L.append("")

    L.append("---")
    L.append("")
    L.append(NOTA_GERADO)
    L.append("")
    L.append(VOLTAR)
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------- API


def render(man, cfg, descriptions):
    prosa = rc.Prosa(descriptions)
    md_medidas, idx_medidas = _medidas(man, prosa)
    md_tabelas, idx_tabelas = _tabelas(man, prosa)
    md_queries = _queries(man, prosa)
    md_modelo = _modelo(man, prosa)
    indices = [("Tabelas", ARQ_TABELAS, idx_tabelas),
               ("Medidas", ARQ_MEDIDAS, idx_medidas)]
    return {
        ARQ_PRINCIPAL: _readme(man, cfg, prosa, indices),
        ARQ_MEDIDAS: md_medidas,
        ARQ_TABELAS: md_tabelas,
        ARQ_QUERIES: md_queries,
        ARQ_MODELO: md_modelo,
    }
