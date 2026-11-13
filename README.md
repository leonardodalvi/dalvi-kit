# dalvi-kit

Minhas skills para agentes de código, reunidas num plugin só.

As skills seguem o padrão aberto [Agent Skills](https://agentskills.io), então
o mesmo repositório serve o Claude Code e outros harnesses.

## Instalação

Escolha uma forma por harness. Instalar de duas formas no mesmo harness
duplica as skills.

### Claude Code

```
/plugin marketplace add leonardodalvi/dalvi-kit
/plugin install dalvi-kit@leonardodalvi
```

### Codex

```bash
codex plugin marketplace add leonardodalvi/dalvi-kit
codex plugin add dalvi-kit@leonardodalvi
```

### GitHub Copilot (CLI e VS Code)

```bash
copilot plugin marketplace add leonardodalvi/dalvi-kit
copilot plugin install dalvi-kit@leonardodalvi
```

No VS Code, também dá para rodar **Chat: Install Plugin From Source** com
`https://github.com/leonardodalvi/dalvi-kit`.

### Gemini CLI

```bash
gemini skills install https://github.com/leonardodalvi/dalvi-kit.git --path plugins/dalvi-kit/skills
```

### Cursor, OpenCode, Windsurf, Amp e outros

```bash
npx skills@latest add leonardodalvi/dalvi-kit -a <agente>
```

Sem `-a`, o instalador pergunta para quais agentes instalar. Essa forma copia
os arquivos e não se atualiza sozinha: rode `npx skills@latest update`.

## Skills

| Skill | Como aciona | O que faz |
| --- | --- | --- |
| `grill-me` | Só você (no Claude Code, `/dalvi-kit:grill-me`) | Entrevista em rodadas que transforma uma ideia solta em decisões tomadas por você |
| `grilling` | O agente aciona sozinho, ou o `grill-me` chama | O método da entrevista: árvore de decisões, fronteira, rodadas com resposta recomendada, confirmação antes de agir |

## Estrutura

```
.claude-plugin/marketplace.json    o marketplace "leonardodalvi"
plugins/dalvi-kit/
  .claude-plugin/plugin.json       o plugin e a versão
  skills/<nome>/SKILL.md           uma pasta por skill
  skills/<nome>/agents/openai.yaml nome e regra de acionamento no Codex
```

## Adicionar uma skill

1. Crie `plugins/dalvi-kit/skills/<nome>/SKILL.md` com `name` e `description`
   no frontmatter. O `name` é igual ao nome da pasta.
2. Crie `agents/openai.yaml` ao lado, com `interface.display_name` e
   `interface.short_description`.
3. Se só você deve acionar a skill, marque nos dois arquivos:
   `disable-model-invocation: true` no `SKILL.md` (Claude Code) e
   `policy.allow_implicit_invocation: false` no `openai.yaml` (Codex).
4. Se ela chamar outra skill do kit, use o nome puro, que vale em qualquer
   harness: `Call the Skill tool with "<nome>"`. Pode acrescentar que, no
   Claude Code, ela aparece como `dalvi-kit:<nome>`.
5. Suba a `version` em `plugins/dalvi-kit/.claude-plugin/plugin.json`.
6. Valide: `claude plugin validate .` e `claude plugin validate ./plugins/dalvi-kit`.
7. Faça commit e push. No Claude Code de cada máquina:
   `claude plugin marketplace update leonardodalvi` e depois
   `claude plugin update dalvi-kit@leonardodalvi`.

## Créditos

`grill-me` e `grilling` vêm de
[mattpocock/skills](https://github.com/mattpocock/skills), sob licença MIT.
O aviso de copyright e a licença estão em
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
