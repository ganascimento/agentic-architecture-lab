# ia-learn — Aprendendo arquitetura de sistemas agênticos construindo um Service Desk

## Objetivo

Projeto **de estudo**. O código importa menos que o entendimento. O objetivo é dominar os fundamentos
de 8 temas a ponto de **discutir e tomar decisões de arquitetura**: quando usar, quando NÃO usar,
quais trade-offs, quais alternativas.

O veículo é um **sistema de Service Desk com agentes de IA** (triagem de chamados, base de
conhecimento, resolução N1, escalonamento, solicitações de acesso com aprovação etc.). O sistema
cresce um módulo por vez; cada módulo adiciona um conceito ao mesmo sistema.

## Como o Claude deve atuar aqui: modo professor

- **Explicar antes de codar.** Todo conceito novo começa pelo "porquê" e pelo problema que resolve,
  depois o "como". Código vem depois do modelo mental.
- **Sempre trazer o trade-off.** Para cada padrão: quando usar, quando não usar, custo (tokens,
  latência, complexidade, debugabilidade), e a alternativa mais simples.
- **Começar do mais simples.** Primeiro a versão ingênua/sem framework, depois a versão "certa".
  Assim fica claro o que o framework abstrai.
- **Código pequeno e comentado didaticamente**, em incrementos que dá pra rodar e testar.
- **Terminar cada aula com perguntas de fixação** ou um exercício curto para o aluno responder.
- **Não avançar de módulo sem o aluno dizer que fechou.** O aluno pergunta, testa, e decide quando evoluir.
- Idioma das **explicações/aulas**: português (BR). Termos técnicos em inglês quando é o termo usado no mercado.
- **Código em inglês**: nomes de pastas, arquivos, variáveis, funções, comentários, docstrings, prompts e
  dados de exemplo. O agente responde ao usuário final no idioma dele. As notas de revisão (`notes/SUMMARY.md`) ficam em PT-BR.
- Ser honesto sobre hype: dizer quando algo é imaturo, controverso ou exagerado.
- **Sempre alertar sobre falhas de segurança/arquitetura** que aparecerem nos testes ou no código (ex.: Achado 1.2),
  explicando o risco e a correção — mas, se for de autenticação/visual, só registrar na Fase final, sem implementar.

## Roadmap (ordem fixa, um por vez)

| # | Módulo | O que aprender | Entrega no Service Desk |
|---|--------|----------------|-------------------------|
| 1 | Multi-Agent Architecture | agente vs workflow, topologias (supervisor, hierárquico, handoff/swarm, pipeline), estado e contexto, quando NÃO usar | single-agent baseline → multi-agente (triagem + especialistas) em Python puro |
| 2 | A2A (Agent2Agent) | protocolo, Agent Card, tasks, comunicação entre agentes de times/serviços diferentes | um especialista vira serviço A2A independente |
| 3 | MCP (Model Context Protocol) | tools/resources/prompts, transports, MCP vs A2A vs function calling | servidor MCP do "sistema de tickets" e da base de conhecimento |
| 4 | LangGraph avançado | StateGraph, checkpointing, human-in-the-loop, interrupts, subgraphs, persistência | reescrever a orquestração em LangGraph com aprovação humana |
| 5 | Agent Builder + Registry | agentes declarativos/configuráveis, catálogo, descoberta, versionamento | registry de agentes do Service Desk |
| 6 | Segurança/Governança | prompt injection, least privilege, guardrails, PII, auditoria, aprovação | proteger solicitações de acesso e dados sensíveis |
| 7 | RAG avançado | chunking, hybrid search, reranking, query rewriting, agentic RAG, avaliação de retrieval | base de conhecimento real para o agente N1 |
| 8 | Observabilidade/Evals | tracing, métricas, LLM-as-judge, datasets de eval, regressão | tracing ponta a ponta + suíte de evals |

## Stack (proposta — confirmar/ajustar a cada módulo)

- Python 3.12, ambiente virtual em `.venv`
- LLM (OpenAI, SDK `openai`, Chat Completions) — um modelo por papel, em `src/config.py`:
  - **Agente (conversa + tools): `gpt-6-luna`** com `reasoning_effort="none"` (decisão do aluno, por ora).
    Atenção: no Chat Completions a Luna só faz tool calling com reasoning `none`; ligar reasoning exige Responses API.
  - **Classificação/roteamento: `gpt-4o-mini`** (entra na 1.3, triagem).
  - Envs: `AGENT_MODEL`, `AGENT_REASONING_EFFORT`, `CLASSIFIER_MODEL`.
- Rodar: `.venv/bin/python -m src` (chat) · `.venv/bin/python -m pytest -q` (testes sem LLM)
- `.env` na raiz com `OPENAI_API_KEY` (nunca commitar; está no `.gitignore`)
- Módulo 1 sem framework de agentes (de propósito); LangGraph entra no módulo 4
- Demais dependências são decididas no módulo em que aparecem (e registradas abaixo)
- Docker disponível para serviços auxiliares (vector DB, observabilidade etc.)

## Fase final (depois dos 8 módulos) — NÃO fazer antes

Decisão do aluno: durante os módulos o foco é só arquitetura de agentes. Estas coisas ficam para o fim:
- **Autenticação:** identidade do usuário vem da sessão autenticada, não do chat (corrige o Achado 1.2 —
  impersonação via e-mail digitado). Tools deixam de receber `email` como argumento do LLM.
- **Interface visual** (hoje é só terminal).
- Pode ser citado nas aulas como exemplo (ex.: módulo 6), mas sem implementar.

## Estrutura do repositório

```
CLAUDE.md                  # este arquivo — contexto persistente
notes/SUMMARY.md            # ARQUIVO ÚNICO de revisão: sumário no topo, uma seção por módulo,
                           # bullets curtíssimos (só o essencial) + decisões do projeto no fim de cada módulo
.claude/skills/linkedin-post/  # skill /linkedin-post: gera texto + prompt de imagem NA CONVERSA (não cria arquivo)
src/                       # código do sistema (cresce a cada módulo)
tests/
```

## Progresso

Atualizar esta seção ao final de cada aula/entrega.

- **Módulo atual:** 1 — Multi-Agent Architecture
- [x] 1.1 Fundamentos teóricos (agente, workflow, topologias, quando usar/não usar) — resumo em `notes/SUMMARY.md`
- [ ] 1.2 Baseline: single-agent de Service Desk (Python puro + Claude) — *código pronto (`src/agent.py`, `tools.py`, `data.py`), aguardando aluno rodar*
- [ ] 1.3 Mini-eval (~15 casos, checagem por código) do baseline → quebrar em multi-agente (supervisor + especialistas) → comparar acerto × custo × latência
- [ ] 1.4 Variação: handoff/peer-to-peer e comparação de topologias
- [ ] 1.5 Fechamento: decisões consolidadas em `notes/SUMMARY.md`

## Decisões de arquitetura registradas

Registradas também em `notes/SUMMARY.md`.
- D1 agentes divididos por capacidade/permissão, não por categoria
- D2 LLM nunca executa concessão de acesso; só cria solicitação → aprovação humana → código executa
- D3 handoff para quem conversa; agent-as-tool para consulta pontual
- **Achado 1.2:** identidade vem do chat — o usuário digitou o e-mail de outra pessoa (carlos@) e o agente
  abriu solicitação em nome dela. Fica como está (exemplo didático); correção vai para a Fase final.

## Dúvidas do aluno (histórico)

- [1.1] O que é **handoff**? → explicado (transferência do controle da conversa vs. agent-as-tool)
- [1.1] O que são **evals**? → explicado em nível introdutório (aprofundar no módulo 8)
