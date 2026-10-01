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

- Python 3.12, `.venv`. LLM: OpenAI (`openai`, Chat Completions), modelo por papel em `src/config.py`:
  **`gpt-6-luna`** com `reasoning_effort="none"` (no Chat Completions a Luna só faz tool calling com `none`).
  (gpt-4o-mini, classificador do módulo 1, é MAIS caro por token que a Luna.)
- Envs: `OPENAI_API_KEY` (no `.env`, nunca commitar), `AGENT_MODEL`, `AGENT_REASONING_EFFORT`, `ACCESS_AGENT_URL`.
- Rodar (venv ativo), dois terminais: `python -m src.services.access_a2a` (Acessos, time de IAM) e `python -m src`
  (Service Desk; login ana/ana123 etc. em `src/data.py`). `python -m pytest -q` (sem LLM) ·
  `python -m evals.run [--case ...] [--runs N]` (sobe o serviço sozinho).
- **Economia de tokens:** desenvolver com `--case` e `--runs 1`; eval completo (50 × 3, ~US$ 0,10) só nos marcos.
- Módulo 1 sem framework (de propósito). Módulo 2: `a2a-sdk[http-server]==1.1.5`, `uvicorn`, `pyjwt[crypto]` —
  versões FIXADAS (os dois lados do protocolo precisam concordar). Chave Ed25519 do Service Desk em `.keys/`
  (gerada no 1º uso, git-ignored). LangGraph entra no módulo 4. Demais dependências: no módulo em que aparecem.
- Docker disponível para serviços auxiliares (vector DB, observabilidade etc.).
- Push pelo WSL falha (askpass antigo do VS Code): usar `"/mnt/c/Program Files/Git/cmd/git.exe" push`.

## Fase final (depois dos 8 módulos) — NÃO fazer antes

- **Autenticação de verdade:** hash de senha (argon2/bcrypt) ou IdP (SSO/OIDC), tokens/expiração de sessão.
  (Na 1.4 o aluno pediu uma auth MÍNIMA já: contas locais com senha em texto puro em `src/data.py` + `src/auth.py`.)
- **IdP + token exchange** (RFC 8693) entre serviços, a partir do token do usuário (fecha a fronteira da 2.5);
  TLS entre serviços; chave privada em cofre + JWKS.
- **Interface visual** (hoje é só terminal).
- Pode ser citado nas aulas como exemplo (ex.: módulo 6), mas sem implementar.

## Estrutura do repositório

```
CLAUDE.md                  # este arquivo — contexto persistente (enxuto: detalhe vai no SUMMARY/git)
notes/SUMMARY.md           # ARQUIVO ÚNICO de revisão (PT-BR): uma seção por módulo, bullets curtos + decisões
.claude/skills/linkedin-post/  # skill /linkedin-post: texto + prompt de imagem NA CONVERSA (não cria arquivo)
src/
  __main__.py              # chat no terminal: login + Service Desk
  config.py  auth.py       # modelos/preços · login local → Session (identidade vem daqui, nunca do chat)
  identity.py              # token delegado ASSINADO p/ outros serviços (iss=service-desk, sub=usuário, aud, exp 60s)
  data.py                  # "sistemas" fake: contas/diretório, KB (pública + interna), status/incidentes, tickets
                           # (SLA, comentários de terceiros), dispositivos (CMDB), catálogo. Relógio FIXO (`NOW`)
  core/agent.py            # loop genérico (Agent, ToolCall, Usage); gancho `intercept`; `registry` de tools
  tools/                   # sistemas DO SERVICE DESK (vira MCP no módulo 3): knowledge tickets account assets
                           # catalog + _schema (Tool) + provenance (argumento veio do usuário?). Sem tools de acesso.
  architectures/           # service_desk() = HUB: handoff (grafo, triagem-agente) · specialists (Suporte, Conta,
                           # Catálogo) · remote (RemoteAgent: nó do grafo = agente de outro time via A2A, sem LLM)
  services/                # agentes de OUTROS times como serviços
    a2a_client.py          # cliente A2A no SDK (descoberta + envio com streaming + GetTask), fachada síncrona
    access_a2a/            # time de IAM: server (SDK: AccessExecutor, card c/ security scheme) · auth (verifica o
                           # token: 401 antes do protocolo) · agent (ACCESS_ROLE + ask_user) · tools · data
tests/                     # sem LLM: tools, auth, a2a, architectures (serviço A2A falso em conftest.py)
evals/                     # cases.py (50 casos; acesso checado pelo artifact A2A), run.py (regressão; sobe o
                           # serviço; custo/chamadas = nosso + remoto), results/ (fora do git: gerado a cada run)
```

## Organização por módulo

- **`main` = o sistema atual** (módulo em andamento). O código reflete só o estado de agora: quando um módulo
  substitui uma peça, a versão antiga SAI do `main` (sem manter tudo vivo — decisão do aluno no módulo 2).
- **Fim de módulo:** criar a branch `module-N` (para navegar no GitHub) + a tag `module-N-final` (imutável) no
  commit que fechou o módulo; o trabalho segue no `main`. Nomes de branch/tag em inglês.
  Ex.: `module-1` / `module-1-final` → `40f6ef3`; `module-2` / `module-2-final` → commit de fechamento do módulo 2.
- Revisitar lado a lado: `git worktree add ../ia-learn-module1 module-1-final`.
- Nada de copiar o projeto por módulo (código duplicado diverge).

## Progresso

Atualizar ao final de cada aula/entrega. Detalhe de cada aula: `notes/SUMMARY.md` e o histórico do git.

- **Módulo atual:** 3 — MCP (Model Context Protocol). 3.1 teoria dada (2026-10-01).
  - **Preparação (2026-09-30, pedido do aluno):** domínio enriquecido, ainda em function calling (base para comparar
    com MCP): KB com artigos internos (só TI) + `get_kb_article`; incidentes/manutenção (`list_active_incidents`);
    tickets com SLA, escalonamento (só após o prazo), fechamento (resolução com proveniência), duplicado (por
    produto); `assets` (dispositivos + diagnóstico remoto); `catalog` (pré-aprovado / gestor / bloqueado,
    terceirizado, elegibilidade de troca de notebook) num **especialista novo (Catálogo)**; usuários pedro
    (terceirizado) e bruno (TI); comentário de fornecedor com **injeção plantada** (INC0003). Eval 35 → 50 casos.
  - Achados no caminho: duplicado por categoria/palavras falhou (categoria escolhida pelo LLM; PT × EN) → por
    produto; proveniência com id opaco (`SW004`) aceitava "Solicito Adobe Acrobat Pro" → `describe_request`;
    transferências paralelas ao MESMO agente perdiam um pedido (caso 11) → notas mescladas.
  - Eval completo 50×3 = **98%** (só o caso 15 falha), 4,7 chamadas, 6,6 s, US$ 0,10. Antes das 3 correções: 94%.
- [x] **Módulo 2 — A2A** (fechado pelo aluno em 2026-09-29)
  - 2.1 teoria · 2.2 A2A à mão (stdlib) · 2.3 SDK oficial (streaming, GetTask, erros tipados) · 2.4 Acessos como
    serviço A2A + eval · 2.5 identidade entre serviços (JWT Ed25519: iss/sub/aud/exp, verificado antes do protocolo).
  - No caminho: `main` só com o sistema atual (hub; Acessos remoto via `RemoteAgent`); bug do estado da task
    (heurística → tool de controle `ask_user`, default COMPLETED); `contextId` entre tasks; ping-pong Suporte↔triagem
    (nota de handoff com moldura do CÓDIGO + descrições de tool com "quando NÃO usar").
  - Resultado: eval completo 35×3 = **93%**, 4,7 chamadas, 6,1 s por caso.
  - Aluno entende bem: skill ≠ tool (skill = abstração na língua de quem chama), fachada × vários agentes,
    contexto delimitado, o que o SDK assume × o que é nosso, identidade em 2 camadas.
- [x] **Módulo 1 — Multi-Agent Architecture** (fechado pelo aluno em 2026-09-27)
  - 1.1 teoria · 1.2 single-agent · 1.3 eval + routing · 1.4 handoff (malha e hub) + auth + tools novas · 1.5 SUMMARY.
  - Veredito (eval v2): single ~90% e o mais barato; routing melhor em vários pedidos; hub mais caro, mas agente novo
    mexe só na triagem. Single por padrão; hub para escalar. Supervisor ficou só na teoria (→ módulo 4).

## Pendências encaminhadas (retomar no módulo indicado)

- **Módulo 3 (MCP):** as tools do Service Desk (`src/tools/`: knowledge, tickets, account, assets, catalog) viram
  servidores MCP; comparar MCP × A2A × function calling na prática. Ganchos já no domínio: KB/incidentes como
  **resources** (tool × resource), `force_new` (confirmação por flag do LLM) × **elicitation**, diagnóstico como
  operação lenta → **progress**, fronteira de servidor por sistema (quem é dono de qual dado), 18 tools → custo de
  contexto/seleção de tools, identidade do usuário no servidor MCP (D4/D10 de novo).
- **Módulo 4 (LangGraph):** **supervisor** (agent-as-tool + síntese), comparar "à mão × framework"; human-in-the-loop
  para a aprovação da D2 (a task de acesso termina em `pending_approval`; aprovar é outro fluxo).
- **Módulo 5 (Registry):** `AgentSpec` + grafo do handoff quase declarativos; unificar "o que cada agente trata";
  **contrato do dado estruturado** do artifact (`accessRequest` não está descrito no card → schema/extensão
  versionada); catálogo/descoberta quando houver muitos agentes remotos; Extended Agent Card.
- **Módulo 6 (Segurança):** injeção indireta em comentário de terceiro (INC0003, caso 40 — hoje só a proveniência
  do `close_ticket` segura; prompt de propósito sem defesa); artigo público aponta p/ interno (KB003 → KB017, PIN);
  triagem responde trivia (caso 15, 0/3); checagem de SENTIDO da justificativa
  (LLM-as-judge; proveniência só pega invenção, teste `xfail`); assinatura `[x agent]` ainda in-band; TTL das
  conversas no serviço de IAM (`agents` + `InMemoryTaskStore` nunca expiram — expirar juntos).
- **Módulo 7 (RAG):** busca da KB por palavra (viés de artigo longo); duplicado de ticket por similaridade de
  sentido (hoje lista de produtos); filtro de permissão (artigo interno) DENTRO do retrieval.
- **Módulo 8 (Evals/Observabilidade):** tracing distribuído entre serviços (propagar `traceparent` no A2A: o agente
  remoto é opaco); negação por frase no checker; `cached_tokens`; eval em paralelo; LLM-as-judge.
- Comportamento conhecido: Suporte abre chamado de impressora antes de orientar a limpeza (KB003); o Acessos às
  vezes julga o mérito da justificativa (caso 18, 2/3) apesar do prompt.

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
- D9 estado de protocolo por sinal explícito (tool de controle), default que falha para o lado seguro
- D10 identidade entre serviços = token assinado (quem chama + em nome de quem, aud, exp curto), verificado antes
  do protocolo; nunca identidade no payload
- D11 A2A para AGENTE de outro contexto/time (fachada com skills de negócio); tool/MCP para função; separar por
  contexto delimitado, não por time
- D12 estrutura das mensagens entre agentes (quem transferiu para quem) escrita pelo código; o LLM só o conteúdo

## Dúvidas do aluno (histórico)

- [1.1] handoff × agent-as-tool; o que são evals (aprofundar no módulo 8)
- [1.3] routing não é supervisor (plano fixo, ninguém reage ao resultado)
- [1.4] N1 ≠ triagem; por que triagem-AGENTE (pode perguntar) × classificador; hub ≠ supervisor
  (especialista fala direto, resposta não passa pela triagem); malha × hub (quando usar cada um)
- [2.x] skill × tool (achava que skill espelhava as tools); onde vai a URL (vem do card); `WhichOneof`; quem chama o
  `get_credentials` (o SDK, via `AuthInterceptor`); `to_thread` e `on_progress`; como expor um time com 50 tools
  (fachada) e agentes do mesmo time em contextos diferentes (contexto delimitado)
