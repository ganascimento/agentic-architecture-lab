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
  - (gpt-4o-mini foi o classificador do routing no módulo 1 — ⚠️ é MAIS caro por token que a Luna.)
  - Envs: `AGENT_MODEL`, `AGENT_REASONING_EFFORT`, `ACCESS_AGENT_URL` (default http://localhost:8001).
- Rodar (venv ativo), dois terminais: `python -m src.services.access_a2a` (agente de Acessos do time de IAM, A2A)
  e `python -m src` (Service Desk; pede login — contas em `src/data.py`, ex. ana/ana123).
  `python -m pytest -q` (sem LLM) · `python -m evals.run [--case ...] [--runs N]` (sobe o serviço sozinho)
- **Economia de tokens:** desenvolver com `--case` e `--runs 1`; eval completo (35 casos × 3) só nos marcos.
- `.env` na raiz com `OPENAI_API_KEY` (nunca commitar; está no `.gitignore`)
- Módulo 1 sem framework de agentes (de propósito); LangGraph entra no módulo 4
- Módulo 2: `a2a-sdk[http-server]==1.1.5` + `uvicorn` + `pyjwt[crypto]` (versões FIXADAS: os dois lados do protocolo
  precisam concordar). Chaves Ed25519 do Service Desk em `.keys/` (gerada no 1º uso, git-ignored).
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
  identity.py              # token delegado ASSINADO p/ outros serviços (iss=service-desk, sub=usuário, aud, exp 60s)
  data.py                  # "sistemas" fake: contas, diretório, KB, tickets, acessos, status de sistemas
  core/agent.py            # loop genérico (Agent, ToolCall, Usage); gancho `intercept`; `registry` de tools
  tools/                   # sistemas DO SERVICE DESK (vira MCP no módulo 3): knowledge tickets account
                           # + _schema (Tool) + provenance (argumento veio do usuário?). Sem tools de acesso.
  architectures/           # service_desk() = HUB: handoff (grafo, triagem-agente) · specialists (Suporte, Conta)
                           # · remote (RemoteAgent: nó do grafo que é agente de outro time via A2A, sem LLM)
  services/                # agentes de OUTROS times como serviços
    a2a_client.py          # cliente A2A no SDK (descoberta + envio com streaming + GetTask), fachada síncrona
    access_a2a/            # time de IAM: server (SDK: AccessExecutor, card c/ security scheme) · auth (verifica o
                           # token: 401 antes do protocolo) · agent (ACCESS_ROLE + ask_user) · tools · data
tests/                     # sem LLM: tools, auth, a2a, architectures (serviço A2A falso em conftest.py)
evals/                     # cases.py (35 casos; acesso checado pelo artifact A2A), run.py (regressão; sobe o
                           # serviço; custo/chamadas = nosso + remoto), results/ (fora do git: gerado a cada run)
```

## Organização por módulo

- **`main` = o sistema atual** (módulo em andamento). O código reflete só o estado de agora: quando um módulo
  substitui uma peça, a versão antiga SAI do `main` (sem manter tudo vivo — decisão do aluno no módulo 2).
- **Fim de módulo:** criar a branch `module-N` (para navegar no GitHub) + a tag `module-N-final` (imutável) no
  commit que fechou o módulo; o trabalho segue no `main`. Nomes de branch/tag em inglês.
  Ex.: `module-1` / `module-1-final` → commit `40f6ef3`.
- Revisitar lado a lado: `git worktree add ../ia-learn-module1 module-1-final`.
- Nada de copiar o projeto por módulo (código duplicado diverge).

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
  - [x] 2.2 A2A mínimo à mão (stdlib; substituído pelo SDK na 2.3, está no git em `f56b556`): `src/services/access_a2a/` (Agent Card + JSON-RPC `SendMessage`, síncrono,
    INPUT_REQUIRED → COMPLETED com o mesmo taskId; estado decidido pelo CÓDIGO) + `src/services/a2a_client.py`
    (descoberta + envio, `show_wire`). ⚠️ identidade ingênua proposital (`metadata.userEmail`), teste
    `test_naive_identity_is_forgeable` documenta — corrigir na 2.5. Perguntas de fixação da 2.2 em aberto.
  - [x] Reestruturação do `main` (decisão do aluno: o código reflete só o sistema atual). Só HUB; Acessos só remoto:
    nó `access` = `RemoteAgent` (sem LLM; INPUT_REQUIRED → próxima msg vai p/ a task; terminou → volta à triagem
    no próximo turno, porque o remoto não sabe transferir → triagem manda para o externo POR ÚLTIMO). A triagem
    aprende o que o Acessos faz pelo **Agent Card** (descrição da transfer vem do card). Tools/dados de acesso só
    no serviço (least privilege pela arquitetura). Artifact com texto + **dado estruturado** (`accessRequest`).
    Achado de segurança corrigido: IDOR no protocolo (contextId/taskId de outro usuário) → TaskNotFound.
    Eval: checks de acesso pelo artifact (agente opaco → perdemos visibilidade das tentativas internas; qualidade
    interna é do time de IAM). Smoke: 13/14 (15 = triagem manda trivia ao Suporte, conhecido); 3 runs casos 1/8/10:
    100%, chamadas 5.0/3.0/8.0 (≈ hub local do módulo 1). ⚠️ caso 1: Suporte devolve o MESMO assunto à triagem (ping-pong).
  - [x] /simplify do módulo 2 (sem mudar comportamento): `src/services/a2a_protocol.py` (o que os 2 lados
    compartilham: versão, estados, `text_of`, `data_of`); `start()` único para subir o serviço (eval/testes/serve);
    `AccessA2AService.usage/cost`; eval descobre o card uma vez; timeout curto na descoberta; trace do remoto guarda
    estado + dado estruturado (checks leem o dado, não texto); `REMOTE`/`remotes`/`transfers` removidos (derivados).
  - [x] **BUG do estado da task corrigido (achado de altitude):** era "nenhuma tool = está perguntando" → recusa/
    "não é comigo" deixava a task INPUT_REQUIRED para sempre (conversa presa no Acessos até `/new`). Agora: tool de
    CONTROLE `ask_user` (capturada pelo `intercept`) = INPUT_REQUIRED; default COMPLETED (falha para o lado seguro).
    Junto: `contextId` mantido entre tasks (task ≠ context); task remota terminou → volta ao hub NO MESMO TURNO
    (saiu a regra "externo por último"; custo +1 chamada da triagem); loop só conta tool com SUCESSO como `worked`.
    Efeito colateral medido: tool de perguntar barata → modelo pergunta demais (caso 10 caiu p/ 0/3) → prompt diz
    quando NÃO perguntar e "não julgue o mérito, o gestor decide" (D2). Eval acesso/multi/segurança 3 runs: 97%
    (18 = 2/3, ainda pergunta às vezes). Full 1 run: 31/35 (2, 11 = ping-pong Suporte↔triagem conhecido; 15).
  - [x] 2.3 SDK oficial (`a2a-sdk[http-server]==1.1.5` + `uvicorn`, FIXADOS no requirements). Trocou tudo (a versão à mão
    fica no git). SDK assume: JSON-RPC, TaskStore (escopado por dono → IDOR de taskId resolvido pelo SDK), tipos
    protobuf, streaming SSE, GetTask/Cancel, erros tipados. Continua NOSSO: decisão do estado (`AccessExecutor`),
    memória por (usuário, contextId) (IDOR de contexto impossível por construção), identidade (`NaiveIdentity` =
    `ServerCallContextBuilder` lendo header — a costura da 2.5). Ponte sync↔async: `asyncio.to_thread` (servidor),
    `asyncio.run` por chamada (cliente; sem keep-alive). Streaming p/ progresso + GetTask no fim (task consolidada).
    Provado: payload à mão da 2.2 funciona no servidor oficial (interop); `message/send` (v0.3) → -32601 (quebra de
    versão; `enable_v0_3_compat` resolveria). Eval acesso/multi/segurança 3 runs: 100%, custo/latência iguais.
    Fixação respondida: 1 ok; 2 metade (prova interop só no que foi exercitado); 3 recurso certo = compat v0.3 no card.
    Pendente: TTL das conversas — expirar JUNTOS `agents` e o `InMemoryTaskStore` (política nossa, nada expira sozinho).
  - [x] 2.4 Acessos como serviço A2A + eval: entregue ao longo da reestruturação/2.3 (serviço independente, card,
    eval sobe o serviço e checa pelo artifact). Eval COMPLETO (35×3, com o token da 2.5): **91% (96/105)**, 4,9 chamadas,
    US$ 0,0005/caso, 8,3 s. Falhas: 1/2/11/32 = ping-pong Suporte↔triagem (conhecido, a tratar); 15 = trivia (0/3,
    conhecido); 18 = 1/3 (o Acessos ainda julga o mérito de "colega de férias" às vezes).
  - [x] **Ping-pong Suporte↔triagem corrigido (causa raiz, 2 padrões):** (1) a triagem escrevia a nota como ROTA
    ("encaminhar para suporte de impressoras") e o Suporte não se via como destinatário → devolvia (5/8 rodadas).
    Fix: `HANDOFF_NOTE` = moldura escrita pelo CÓDIGO ("o X transferiu para VOCÊ, Y: é seu. O usuário precisa: ...")
    + campo `reason` pede a NECESSIDADE, não quem atende. (2) depois de resolver, devolvia o MESMO assunto ("identificar
    a impressora") → descrição do `transfer_to_triage` diz quando NÃO usar. Efeito colateral medido: caso 11 (2 pedidos
    do Suporte) caiu p/ 0/3 → nota = "por onde começar, não o limite" + triagem lista TODOS os pedidos do agente.
    Sem bloqueio no código (devolução legítima existe quando a triagem erra). Eval final 35×3: **93% (98/105)**,
    4,7 chamadas, 6,1 s/caso (antes 91%, 4,9, 8,3 s). Restam: 15 (trivia, 0/3) e variância 2/3 em 10/11/18/19.
  - [x] 2.5 identidade entre serviços: header ingênuo → **JWT assinado (Ed25519)** emitido pelo Service Desk
    (`src/identity.py`): assinatura = QUEM chama (iss), claims = EM NOME DE QUEM (sub), aud = URL do agente (sem
    replay em outro serviço), exp 60s (token por chamada). Assimétrico: IAM só VERIFICA (chave pública), não emite.
    Card declara `security_schemes` (Bearer JWT) → `AuthInterceptor` do SDK põe o header; `DelegatedCredentials`
    (CredentialService) emite o token. Servidor: Starlette `AuthenticationMiddleware` + `DelegatedTokenBackend`
    (`access_a2a/auth.py`): alg fixado (EdDSA), issuer na lista de confiança DO IAM, aud, exp, usuário conhecido →
    senão 401 antes do SDK. Saíram `NaiveIdentity`/`EmailUser`/`a2a_protocol.py`. Testes: sem token, header antigo,
    chave forjada, aud errado, expirado, issuer desconhecido, usuário desconhecido → 401.
    ⚠️ Fronteira que RESTA (teste documenta): o IAM crê em qualquer `sub` que o Service Desk assina → SD
    comprometido age como qualquer um. Correção: IdP + token exchange (RFC 8693) a partir do token do USUÁRIO
    (Fase final). Também: HTTP sem TLS (token pode ser capturado na rede, janela de 60s; sem `jti` anti-replay);
    chave privada em arquivo (prod: secret manager + JWKS p/ rotação); em /mnt/c o chmod 600 não vale (NTFS).
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
