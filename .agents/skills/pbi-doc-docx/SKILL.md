---
name: pbi-doc-docx
description: >-
  Gera ou atualiza a documentação TÉCNICA de um projeto Power BI (PBIP) num único
  arquivo .docx em docs/<projeto>/ (glossário de dados: tabelas, colunas, medidas,
  queries M, RLS; ou, num relatório conectado a dataset, páginas, visuais, medidas de
  relatório e campos usados), seguindo o template visual configurado pela equipe
  (fontes e cores herdadas do documento-modelo local, ou a paleta neutra padrão).
  Para a documentação de negócio use a skill pbi-doc-negocio. Use ao pedir "gerar o glossário de dados em Word/docx",
  "documentação do Power BI em docx", ou quando um pre-commit disparar a
  atualização da documentação em Word.
---

# pbi-doc-docx — glossário técnico de dados em .docx

## O que esta skill faz (e o que ela NÃO faz)

Toda a extração e toda a formatação são feitas por scripts Python determinísticos em
`tools/pbidoc/`. **Seu único trabalho é escrever a prosa de negócio** em
`_descriptions.json` — o mesmo arquivo usado pela skill `pbi-doc-md`. Rodar as duas
skills **não** duplica custo: a prosa já escrita é reaproveitada integralmente.

O `.docx` é produzido a partir de `tools/pbidoc/assets/template-tecnico.docx` (gerado
localmente, não versionado — veja o Passo 0), que preserva byte a byte o tema, o
cabeçalho com logotipo e o rodapé do documento de referência de cada equipe. Fontes
e cores do corpo do texto vêm da paleta neutra padrão de `docx_writer.py`, a menos
que `.pbidoc.json` defina `estilo_docx` (veja `reference/estrutura.md`).

**Você NUNCA:**

- tenta montar o `.docx` por conta própria, nem instala bibliotecas (`python-docx`,
  `pandoc`, `libreoffice`) — nada disso é necessário nem permitido aqui;
- edita arquivos dentro de `docs/` além de `_descriptions.json`;
- altera qualquer arquivo do projeto Power BI (`*.tmdl`, `*.pbir`, `*.pbip`, `*.pbism`);
- altera `_model.json`, `_meta.json`, o template ou os scripts em `tools/pbidoc/`;
- reescreve descrições cujo hash não mudou;
- lê arquivos TMDL diretamente — todo o contexto necessário vem de `changes.json`.

## Guardrails (obrigatório, não depende desta skill estar ativa)

Os mesmos guardrails de `pbi-doc-md` valem aqui: nunca ler segredos (`.env`,
dotfiles de shell, chaves) nem **dados reais** de qualquer projeto Power BI
(`.pbix`, `.pbit`, `.abf`, `.pbi/**`, planilhas/bancos tabulares) — inclusive o
próprio documento de referência do glossário, se ele acabar guardado dentro do
repositório: `.docx` não é um dos formatos bloqueados por padrão, mas nunca
copie dados de linhas de tabela para dentro da prosa. Metadados de estrutura
continuam livres. Se uma leitura for negada, é o comportamento esperado — relate e
siga. Veja `.claude/skills/guardrails/SKILL.md`.

## Passo 0 — Escolher o projeto e conferir o template

Um repositório pode ter vários projetos PBIP, cada um numa subpasta de `projetos/`.
Descubra quais existem e escolha um (pergunte ao usuário se houver mais de um e o
pedido for ambíguo, exceto em modo pre-commit):

```bash
python3 tools/pbidoc/pbidoc.py projetos
```

Se `.pbidoc.json` não existir, rode `python3 tools/pbidoc/pbidoc.py init`.

Confirme que `tools/pbidoc/assets/template-tecnico.docx` existe. Se não existir, gere-o
a partir do documento-modelo (`docs/templates/Modelo - Documentacao Tecnica.docx`, ou
um da própria equipe no mesmo formato); o template gerado nunca é versionado:

```bash
python3 tools/pbidoc/make_template.py "docs/templates/Modelo - Documentacao Tecnica.docx" --modelo tecnico
```

## Passo 0b — Identificar o tipo do projeto (obrigatório)

A listagem do Passo 0 traz `tipo=` para cada projeto (o mesmo valor aparece em `diff`,
`status` e em `changes.json` → `tipo_projeto`). **Leia `../pbi-doc-md/reference/tipos-de-projeto.md`**: ele define os tipos
e as regras de prosa de cada um. Nunca deduza o tipo pelo nome da pasta — use o `tipo=`.

- `completo` / `modelo` (modelo semântico local): siga os passos normalmente.
- `relatorio_conectado` (só o relatório, ligado a um dataset que **não** está no
  repositório): gera `<TÍTULO> - Documentação do Relatório.docx` (mesmo conteúdo do Markdown de relatório conectado). O template é `template-relatorio.docx` (gerado com `make_template.py "docs/templates/Modelo - Documentacao de Relatorio.docx" --modelo relatorio`; se faltar, o `template-tecnico.docx` serve). Aplicam-se as regras de prosa do relatório conectado; não invente tipos, DAX ou relacionamentos do dataset.

## Passo 1 — Extrair o modelo (sem custo de tokens)

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> extract
```

## Passo 2 — Descobrir o que precisa de descrição

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> diff --escopo tecnico
```

Em execução de pre-commit (argumento `--precommit`), acrescente `--limite 120`.

**Leia `.pbidoc-cache/<nome>/changes.json`** e decida pelo campo `resumo`:

| Situação | Ação |
| --- | --- |
| `total_a_escrever` é `0` | pule direto para o Passo 5 |
| `modo` é `completo` | descreva todos os itens da lista |
| `modo` é `incremental` | descreva **apenas** os itens listados em `itens` |

## Passo 3 — Escrever as descrições em lotes

Leia **`../pbi-doc-md/reference/estilo.md`** antes de escrever a primeira palavra.
É o mesmo guia normativo usado pela skill Markdown — os dois formatos compartilham
a mesma prosa, então o estilo é obrigatoriamente o mesmo.

Escreva arquivos de lote em `.pbidoc-cache/<nome>/patch-NN.json`, com no máximo 60
objetos por arquivo:

```json
{
  "objetos": {
    "tabela::pedidos": {
      "descricao": "…",
      "grao": "Uma linha por pedido",
      "papel": "fato"
    },
    "medida::Medidas::qtd_pedidos": { "descricao": "…", "regra": "…" }
  }
}
```

Regras do lote:

- Use a `chave` **exatamente** como aparece em `changes.json`.
- Preencha exatamente os campos listados em `campos` — nada além.
- **Não inclua o campo `hash`**: ele é carimbado na mesclagem.
- Sem base para descrever? Use `"revisar": true` com os campos vazios.
- Cubra **todos** os itens de `changes.json`, em quantos lotes forem necessários.

## Passo 4 — Mesclar

```bash
python3 tools/pbidoc/pbidoc.py merge .pbidoc-cache/<nome>/patch-*.json --limpar --escopo tecnico
```

Leia os avisos e corrija apenas os itens apontados.

## Passo 5 — Renderizar o .docx

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> render --docx
```

Gera `docs/<nome>/<TÍTULO> - Glossário de Dados.docx`. A ordem das seções e a
formatação estão descritas em `reference/estrutura.md` — não as altere.

Para gerar os dois formatos de uma vez (a prosa é a mesma):

```bash
python3 tools/pbidoc/pbidoc.py --projeto <nome> render --md --docx
```

## Passo 6 — Relatar

Informe em no máximo 5 linhas: qual projeto, quantos objetos foram descritos, o
caminho do `.docx` gerado e quantos itens ficaram com `"revisar": true`
(`python3 tools/pbidoc/pbidoc.py --projeto <nome> status --escopo tecnico`). Não cole trechos do
documento.

Se o projeto for `relatorio_conectado`, diga em uma frase o que **não** pôde ser documentado por estar no dataset (tabelas e tipos, DAX das medidas do dataset, relacionamentos, RLS, Power Query) e cite os alertas de qualidade mais relevantes que `status` mostrou.

## Modo pre-commit

Quando acionada automaticamente pelo hook (prompt contendo `--precommit`): o
projeto já vem indicado — não pergunte; sem exploração do repositório, sem
perguntas, respeitando `limite_itens_precommit`, e saída final em uma linha:
`pbidoc: N descrições atualizadas`.

## Se algo falhar

- `Template ausente` → gere-o com `make_template.py` (Passo 0).
- `Nenhum projeto encontrado` → confira se o PBIP está em `projetos/<nome>/` e se
  há uma pasta `*.SemanticModel` e/ou `*.Report`.
- Avisos de `chave inexistente` → você inventou uma chave; use as de `changes.json`.
- Uma leitura foi negada por segredo/dado real → correto, veja a seção Guardrails.
- Qualquer outro erro nos scripts: **relate e pare**. Não tente produzir o `.docx`
  de outro jeito.
