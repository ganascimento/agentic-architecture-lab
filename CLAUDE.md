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
- **Escada do código mínimo** (antes de escrever código novo): precisa existir? → já existe no projeto? →
  a stdlib/SDK resolve? → uma dependência já instalada resolve? → só então escrever o mínimo que funciona.
  Não vale para comentários didáticos nem para a versão "ingênua primeiro": clareza para aprender > menos linhas.
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
  - **Agentes: `gpt-6-luna`** com `reasoning_effort="none"` (no Chat Completions a Luna só faz tool calling com
    reasoning `none`; ligar reasoning exige Responses API).
  - **Classificador do routing: `gpt-4o-mini`** — ⚠️ é MAIS caro por token que a Luna; a triagem do hub já usa a Luna.
  - Envs: `AGENT_MODEL`, `AGENT_REASONING_EFFORT`, `CLASSIFIER_MODEL`.
- Rodar (venv ativo): `python -m src --arch single|routing|handoff|hub` (chat, pede login — contas em
  `src/data.py`, ex. ana/ana123) · `python -m pytest -q` (sem LLM) · `python -m evals.run --arch X [--case ...] [--runs N]`
- **Economia de tokens:** desenvolver com `--case` e `--runs 1`; eval completo (35 casos × 3) só nos marcos.
- `.env` na raiz com `OPENAI_API_KEY` (nunca commitar; está no `.gitignore`)
- Módulo 1 sem framework de agentes (de propósito); LangGraph entra no módulo 4
- Demais dependências são decididas no módulo em que aparecem (e registradas aqui)
- Docker disponível para serviços auxiliares (vector DB, observabilidade etc.)

## Fase final (depois dos 8 módulos) — NÃO fazer antes

- **Autenticação de verdade:** hash de senha (argon2/bcrypt) ou IdP (SSO/OIDC), tokens/expiração de sessão.
  (Na 1.4 o aluno pediu uma auth MÍNIMA já: contas locais com senha em texto puro em `src/data.py` + `src/auth.py`.)
- **Interface visual** (hoje é só terminal).
- Pode ser citado nas aulas como exemplo (ex.: módulo 6), mas sem implementar.

## Estrutura do repositório

```
CLAUDE.md                  # este arquivo — contexto persistente (enxuto: detalhe vai no SUMMARY/git)
notes/SUMMARY.md           # ARQUIVO ÚNICO de revisão (PT-BR): uma seção por módulo, bullets curtos + decisões
.claude/skills/linkedin-post/  # skill /linkedin-post: texto + prompt de imagem NA CONVERSA (não cria arquivo)
src/
  __main__.py              # chat no terminal: login + --arch
  config.py  auth.py       # modelos/preços · login local → Session (identidade vem daqui, nunca do chat)
  data.py                  # "sistemas" fake: contas, diretório, KB, tickets, acessos, status de sistemas
  core/agent.py            # loop genérico (Agent, ToolCall, Usage); gancho `intercept` p/ o dono tratar tools
  tools/                   # um módulo por sistema (vira servidor MCP no módulo 3); Session injetada pelo código
    knowledge tickets access account + _schema (Tool) + provenance (argumento veio do usuário?)
  architectures/           # ARCHITECTURES + Protocol ServiceDesk (chat e eval usam o mesmo)
    single · routing (+ triage) · handoff (grafo: MESH e HUB) · specialists (Suporte, Acessos, Conta)
tests/                     # sem LLM: tools, auth, architectures (inclui regras do handoff com fake tool calls)
evals/                     # cases.py (v2: 35 casos, usuário logado, incl. diálogos multi-turno), run.py,
                           # results/ (JSON por execução; v1/ = dataset antigo, não comparável)
```

## Progresso

Atualizar ao final de cada aula/entrega. Detalhe de cada aula: `notes/SUMMARY.md` e o histórico do git.

- **Módulo atual:** 2 — A2A (Agent2Agent). Plano: 2.1 teoria · 2.2 A2A mínimo à mão (Agent Card + SendMessage síncrono)
  · 2.3 SDK oficial (tasks, INPUT_REQUIRED, streaming) · 2.4 Acessos vira serviço A2A + eval · 2.5 identidade entre serviços.
  - [x] 2.1 teoria (spec **v1.0**: métodos `SendMessage`/`GetTask`..., estados MAIÚSCULOS; tutoriais antigos usam
    `message/send` da v0.3 — referência é o SDK/spec da versão instalada). Correção dada: A2A é DELEGAÇÃO (≈ agent-as-tool),
    não handoff; é transporte, não topologia. Aluno acertou: KB = MCP (tool), A2A só com agente do outro lado;
    identidade no texto viola D4 → refinado em 2 camadas (quem chama = credencial do serviço; em nome de quem = token
    delegado) + justificativa repassada perde proveniência (fronteira de confiança). Modos: síncrono, streaming (padrão
    em chat), polling, webhook (tarefa longa, com polling de reconciliação). Recomendado: task de acesso termina rápido
    (`pending_approval`); aprovação é outro fluxo (módulo 4).
  - [ ] 2.2 — **PRÓXIMO**
- [x] **Módulo 1 — Multi-Agent Architecture** (fechado pelo aluno em 2026-09-27)
  - 1.1 teoria · 1.2 single-agent · 1.3 eval + routing · 1.4 handoff (malha e hub) + auth + tools novas · 1.5 SUMMARY.
  - Resultados-chave (eval v2): single ~90% e o mais barato; routing melhor em vários pedidos/ambíguos (+~20% custo);
    malha a mais barata entre as multi, mas a mais exposta a injection; hub mais caro (2 saltos por troca de assunto),
    porém agente novo mexe só na triagem (2N × N(N−1) transfers). Veredito: single por padrão; hub para escalar.
  - Aluno entende bem: single, routing, handoff (agente ativo fala direto com o usuário; hub ≠ supervisor).
    Supervisor ficou só na teoria.

## Pendências encaminhadas (retomar no módulo indicado)

- **Módulo 2 (A2A):** um especialista (sugestão: Acessos ou Conta) vira serviço; handoff entre processos.
- **Módulo 4 (LangGraph):** implementar o **supervisor** (agent-as-tool + síntese) e comparar "à mão × framework";
  human-in-the-loop para a aprovação da D2.
- **Módulo 5 (Registry):** `AgentSpec` + grafo do handoff já são quase declarativos; unificar o texto "o que cada
  agente trata" (hoje repetido na triagem do routing e nos SPECS) e as regras comuns de `_ROUTED`/`_TEAM`.
- **Módulo 6 (Segurança):** nota de handoff gerada pelo CÓDIGO a partir do trace (out-of-band; hoje a assinatura
  `[x agent]` é in-band); checagem de SENTIDO da justificativa (LLM-as-judge — proveniência só pega invenção, teste
  `xfail`); injection que vira solicitação via transfer (caso 12 no handoff); triagem do hub respondeu trivia (caso 15).
- **Módulo 8 (Evals):** negação por frase no checker (hoje janela de 35 chars); medir `cached_tokens`; eval em
  paralelo (processos, por causa do `data` global); LLM-as-judge para contradições entre agentes.
- Comportamento conhecido: Suporte abre chamado de impressora antes de orientar a limpeza (KB003); agentes tentam
  `create_access_request` com justificativa vazia antes de perguntar (o código barra).

## Decisões de arquitetura registradas

Registradas também em `notes/SUMMARY.md`.
- D1 agentes divididos por capacidade/permissão, não por categoria
- D2 LLM nunca executa concessão de acesso; só cria solicitação → aprovação humana → código executa
- D3 handoff para quem conversa; agent-as-tool para consulta pontual
- D4 identidade da sessão injetada pelo código; tools não recebem identidade do LLM (resolveu o Achado 1.2)
- D5 regras críticas no código (permissão, dono, proveniência, limites), nunca só no prompt
- D6 contexto entre agentes = original/conversa assinada, nunca só resumo
- D7 topologia: single padrão; routing p/ multi-pedido/ambíguo; handoff hub p/ muitos agentes; malha só com poucos
- D8 anti-ping-pong no código (sem volta no turno, 1 transfer por resposta, limite)

## Dúvidas do aluno (histórico)

- [1.1] handoff × agent-as-tool; o que são evals (aprofundar no módulo 8)
- [1.3] routing não é supervisor (plano fixo, ninguém reage ao resultado)
- [1.4] N1 ≠ triagem; por que triagem-AGENTE (pode perguntar) × classificador; hub ≠ supervisor
  (especialista fala direto, resposta não passa pela triagem); malha × hub (quando usar cada um)
