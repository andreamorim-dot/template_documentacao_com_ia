import { spawnSync } from "node:child_process";
import path from "node:path";

/**
 * pbi-guard — camada obrigatória de guardrails para o OpenCode.
 *
 * Espelha o hook PreToolUse do Claude Code (.claude/settings.json +
 * `tools/guardrails/check.py --hook-claude`): nunca deixa o assistente ler
 * segredos (.env, dotfiles de shell, chaves privadas) nem dados reais de um
 * projeto Power BI (.pbix, .pbi/**, planilhas, bancos tabulares) —
 * metadados (.tmdl, .pbip, .pbir, .pbism, JSONs do relatório) continuam
 * legíveis, são o insumo da documentação.
 *
 * A política é uma fonte única: `tools/guardrails/policy.py`. Este plugin
 * só delega a decisão para `check.py --hook-json`; não duplique os padrões
 * aqui. Vale para toda tool call, independentemente de qual skill (ou
 * nenhuma) está ativa.
 */
export const PbiGuard = async ({ directory }) => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = input.tool;
      const args = (output && output.args) || {};
      const payload = JSON.stringify({ tool, args });

      let resultado;
      try {
        resultado = spawnSync(
          "python3",
          [path.join(directory, "tools", "guardrails", "check.py"), "--hook-json"],
          { input: payload, encoding: "utf-8", cwd: directory }
        );
      } catch {
        return; // fail-open: nunca travar o assistente por erro do guard
      }

      if (!resultado || resultado.status !== 0 || !resultado.stdout) {
        return;
      }

      let decisao;
      try {
        decisao = JSON.parse(resultado.stdout);
      } catch {
        return;
      }

      if (decisao.deny) {
        throw new Error(decisao.reason || "Bloqueado pelos guardrails.");
      }
    },
  };
};
