# projetos/

Cada projeto Power BI (PBIP) deste repositório vive em sua própria subpasta aqui,
com o nome do projeto:

```
projetos/
├── vendas/
│   ├── vendas.pbip
│   ├── vendas.SemanticModel/
│   └── vendas.Report/
└── rh/
    ├── rh.pbip
    ├── rh.SemanticModel/
    └── rh.Report/
```

O nome da subpasta é o que aparece em `docs/<nome>/`, em `--projeto <nome>` nos
comandos do `pbidoc.py`, e em `projetos.<nome>` no `.pbidoc.json` — escolha um nome
estável (o mesmo do arquivo `.pbip`/`.SemanticModel`, em snake_case, sem espaços).

## Tipos de projeto

| Tipo | Conteúdo da pasta |
| --- | --- |
| `completo` | `<nome>.pbip`, `<nome>.SemanticModel/`, `<nome>.Report/` |
| `modelo` | `<nome>.pbip`, `<nome>.SemanticModel/` (sem relatório) |
| `relatorio_conectado` | `<nome>.pbip`, `<nome>.Report/` — **sem** `.SemanticModel`: o relatório se conecta a um dataset publicado (`definition.pbir` com `byConnection`) e não traz modelo nem dados |

O tipo é detectado automaticamente (`pbidoc.py projetos` mostra `tipo=`). Um relatório
conectado é documentado pelo que revela: conexão, páginas, visuais, filtros, medidas
definidas no relatório (com DAX), campos do dataset usados, bookmarks e navegação.
Para documentar também o dataset (tabelas, DAX, RLS), adicione o projeto dele
(`completo`/`modelo`) como outra pasta.

**Projeto local/temporário:** para que uma pasta nunca entre em commit, adicione-a ao
`.git/info/exclude` (local, sem rastro no repositório). Projetos ignorados pelo git
não aparecem no índice `docs/README.md` nem são registrados por `init`; use
`projetos/<nome>/.pbidoc.json` para a configuração deles (mesmas chaves do
`.pbidoc.json`, valendo só para o projeto).

## Adicionar um projeto

1. No Power BI Desktop, salve o `.pbix` **no formato PBIP**
   (Arquivo → Salvar como → Power BI Project) diretamente dentro de
   `projetos/<nome>/`. Isso gera `<nome>.pbip`, `<nome>.SemanticModel/` e
   `<nome>.Report/`.
2. Registre o projeto (também atualiza os já existentes):

   ```bash
   python3 tools/pbidoc/pbidoc.py init
   ```

3. Escolha os formatos do projeto em `.pbidoc.json` (`projetos.<nome>.formatos`):
   `md`, `docx` (glossário técnico) e/ou `negocio` (documentação de negócio, com as
   páginas do relatório). Para `negocio`, preencha também `projetos.<nome>.negocio`
   (owners, objetivo, público, links, status...) — o que ficar vazio sai como
   `[PREENCHER: …]` no Word. Os Word precisam dos templates locais (uma vez):

   ```bash
   python3 tools/pbidoc/make_template.py "docs/templates/Modelo - Documentacao Tecnica.docx" --modelo tecnico
   python3 tools/pbidoc/make_template.py "docs/templates/Modelo - Documentacao de Negocio.docx" --modelo negocio
   ```

4. Gere a primeira versão da documentação — acione a skill `pbi-doc-md`,
   `pbi-doc-docx` ou `pbi-doc-negocio` pedindo "documentar o projeto `<nome>`", ou rode manualmente:

   ```bash
   python3 tools/pbidoc/pbidoc.py --projeto <nome> extract
   python3 tools/pbidoc/pbidoc.py --projeto <nome> diff --escopo negocio   # ou tecnico
   # a skill escreve a prosa em .pbidoc-cache/<nome>/patch-*.json e mescla com:
   python3 tools/pbidoc/pbidoc.py merge .pbidoc-cache/<nome>/patch-*.json --limpar --escopo negocio
   python3 tools/pbidoc/pbidoc.py --projeto <nome> render --md --docx --negocio
   ```

5. A partir daí, `hooks/pre-commit` mantém `docs/<nome>/` sincronizado a cada
   commit que tocar nos arquivos do projeto — veja a instalação no `README.md` da
   raiz.

## O que nunca colocar aqui

Dados reais (bancos locais, exports, planilhas) e o cache do Power BI Desktop
(`.pbi/`, `.abf`) nunca devem entrar no repositório — o `.gitignore` já os
ignora, e a leitura deles é bloqueada mesmo que alguém os adicione por engano
(veja `.claude/skills/guardrails/SKILL.md`).
