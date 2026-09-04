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

## Adicionar um projeto

1. No Power BI Desktop, salve o `.pbix` **no formato PBIP**
   (Arquivo → Salvar como → Power BI Project) diretamente dentro de
   `projetos/<nome>/`. Isso gera `<nome>.pbip`, `<nome>.SemanticModel/` e
   `<nome>.Report/`.
2. Registre o projeto (também atualiza os já existentes):

   ```bash
   python3 tools/pbidoc/pbidoc.py init
   ```

3. Gere a primeira versão da documentação — acione a skill `pbi-doc-md` (ou
   `pbi-doc-docx`) pedindo "documentar o projeto `<nome>`", ou rode manualmente:

   ```bash
   python3 tools/pbidoc/pbidoc.py --projeto <nome> extract
   python3 tools/pbidoc/pbidoc.py --projeto <nome> diff
   # a skill escreve a prosa em .pbidoc-cache/<nome>/patch-*.json e mescla com:
   python3 tools/pbidoc/pbidoc.py merge .pbidoc-cache/<nome>/patch-*.json --limpar
   python3 tools/pbidoc/pbidoc.py --projeto <nome> render --md --docx
   ```

4. A partir daí, `hooks/pre-commit` mantém `docs/<nome>/` sincronizado a cada
   commit que tocar nos arquivos do projeto — veja a instalação no `README.md` da
   raiz.

## O que nunca colocar aqui

Dados reais (bancos locais, exports, planilhas) e o cache do Power BI Desktop
(`.pbi/`, `.abf`) nunca devem entrar no repositório — o `.gitignore` já os
ignora, e a leitura deles é bloqueada mesmo que alguém os adicione por engano
(veja `.claude/skills/guardrails/SKILL.md`).
