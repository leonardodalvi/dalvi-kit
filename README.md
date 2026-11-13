# dalvi-kit

Minhas skills para o Claude Code, reunidas num plugin só.

## Instalação

No Claude Code:

```
/plugin marketplace add leonardodalvi/dalvi-kit
/plugin install dalvi-kit@leonardodalvi
```

## Skills

| Skill | Como aciona | O que faz |
| --- | --- | --- |
| `grill-me` | Só você, digitando `/dalvi-kit:grill-me` | Entrevista em rodadas que transforma uma ideia solta em decisões tomadas por você |
| `grilling` | O agente aciona sozinho, ou o `grill-me` chama | O método da entrevista: árvore de decisões, fronteira, rodadas com resposta recomendada, confirmação antes de agir |

## Estrutura

```
.claude-plugin/marketplace.json    o marketplace "leonardodalvi"
plugins/dalvi-kit/
  .claude-plugin/plugin.json       o plugin e a versão
  skills/<nome>/SKILL.md           uma pasta por skill
```

## Adicionar uma skill

1. Crie `plugins/dalvi-kit/skills/<nome>/SKILL.md` com `name` e `description`
   no frontmatter.
2. Se ela chamar outra skill do kit, cite o nome completo: `dalvi-kit:<nome>`.
   Dentro do plugin, o nome curto não é o nome da skill.
3. Suba a `version` em `plugins/dalvi-kit/.claude-plugin/plugin.json`.
4. Valide: `claude plugin validate .`
5. Faça commit e push. Em cada máquina:
   `claude plugin marketplace update leonardodalvi` e depois
   `claude plugin update dalvi-kit@leonardodalvi`.

## Créditos

`grill-me` e `grilling` vêm de
[mattpocock/skills](https://github.com/mattpocock/skills), sob licença MIT.
O aviso de copyright e a licença estão em
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
