# Resumo de Estudos

## Sumário

- [Módulo 1: Multi-Agent Architecture](#módulo-1-multi-agent-architecture)
  - [Agente vs Workflow](#agente-vs-workflow)
  - [Quando usar e quando não usar](#quando-usar-e-quando-não-usar)
  - [Topologias](#topologias)
  - [Supervisor vs Handoff](#supervisor-vs-handoff)
  - [Categoria não é Agente](#categoria-não-é-agente)
  - [Segurança](#segurança)
  - [Evals](#evals)
  - [O loop do agente na prática](#o-loop-do-agente-na-prática)
  - [Routing, supervisor e handoff na prática](#routing-supervisor-e-handoff-na-prática)
  - [Contexto entre agentes](#contexto-entre-agentes)
  - [Escalar para muitos agentes](#escalar-para-muitos-agentes)
  - [Código vs prompt](#código-vs-prompt)
  - [Resultado do módulo](#resultado-do-módulo)
  - [Decisões do projeto](#decisões-do-projeto)
- [Módulo 2: A2A (Agent2Agent)](#módulo-2-a2a-agent2agent)
  - [O que é A2A](#o-que-é-a2a)
  - [Agent Card](#agent-card)
  - [Skill não é tool](#skill-não-é-tool)
  - [Tasks, estados e modos](#tasks-estados-e-modos)
  - [À mão vs SDK](#à-mão-vs-sdk)
  - [Handoff sobre A2A](#handoff-sobre-a2a)
  - [Identidade entre serviços](#identidade-entre-serviços)
  - [Muitos agentes e outros times](#muitos-agentes-e-outros-times)
  - [Prompt, tools e eval (lições do módulo)](#prompt-tools-e-eval-lições-do-módulo)
  - [Resultado do módulo 2](#resultado-do-módulo-2)
  - [Decisões do módulo 2](#decisões-do-módulo-2)

---

## Módulo 1: Multi-Agent Architecture

### Agente vs Workflow
- **Agente:** o LLM decide o próximo passo. **Workflow:** o código decide.
- Se dá pra desenhar o fluxograma, é workflow.
- Padrão comum: o LLM escolhe o caminho e o código executa.

### Quando usar e quando não usar
- **Usar para:** isolar contexto, especializar (prompt/tools/modelo), separar permissões, paralelizar, dividir ownership entre times.
- **Não usar se:** um agente com poucas tools resolve, as tarefas compartilham todo o contexto, a latência é crítica ou não existe eval.
- **Custos:** mais tokens, mais latência, erro que se acumula (`0.95⁵ ≈ 77%`), debug difícil.
- **Regra:** comece com um agente, meça, e só divida quando houver um motivo concreto.

### Topologias
- **Supervisor:** um agente coordena os demais (padrão).
- **Hierárquico:** supervisores de supervisores.
- **Handoff/Swarm:** um agente passa a conversa para outro.
- **Pipeline:** ordem fixa (é um workflow).
- **Blackboard:** estado compartilhado entre os agentes.

### Supervisor vs Handoff
- **Agent-as-tool:** delega a *tarefa*, e o supervisor continua falando com o usuário.
- **Handoff:** delega a *conversa*, e o outro agente assume.
- Critério: o especialista precisa conversar com o usuário? Então use handoff.
- Decisão de design no handoff: **o que repassar** ao próximo agente.

### Categoria não é Agente
- Divida por **capacidade e permissão**, não por taxonomia do negócio.
- Categorias com as mesmas tools viram configuração (prompt, filtro de KB).

### Segurança
- `risco ≈ poder das tools × exposição a texto não confiável`
- Não dê ao LLM a tool que executa a ação crítica. Ele cria a solicitação, um humano aprova e o código executa.
- Prompt injection pode ser **direta** (pelo usuário) ou **indireta** (por KB e tickets).
- **Identidade vem do login**, injetada pelo código em cada tool. Nenhuma tool recebe e-mail do LLM.
- **IDOR:** saber o ID de um chamado não é permissão. O código confere o dono e dá o mesmo erro para "não existe" e "não é seu".
- **Ação sensível sem argumento:** `request_password_reset()` só consegue atingir a própria conta.
- **Proveniência:** o código confere se um argumento (a justificativa) veio das palavras do usuário. Pega invenção, não pega sentido.
- **In-band vs out-of-band:** assinatura em texto (`[support agent]`) pode ser falsificada pelo usuário. O certo é o fato vir do código (trace de tools).

### Evals
- Eval = dataset → execução → nota em %.
- Formas de dar a nota: código > LLM-as-judge > humano.
- É o eval que transforma "multi-agente é melhor?" numa decisão baseada em números.
- Rodar cada caso várias vezes: o LLM varia, e 2/3 é um sinal diferente de 3/3.
- **Eval também tem bug:** leia as falhas antes de concluir (o baseline deu 83% por erro do checker; o real era 98%).
- Checagem por palavra-chave é frágil ("ainda não foi concedido" contém "foi concedido").
- Baseline do projeto: 98%, com 2,7 chamadas e US$ 0,00023 por caso. Pelos números, não valeria dividir em multi-agente.
- Compare arquiteturas **na mesma janela**: a latência de um dia para o outro muda por causa da API.
- Com 18–30 casos × 3 runs, **±4 pontos é ruído**: 94% × 98% não é diferença.
- **Grave os argumentos das tools**, não só os nomes. Sem eles não dá para saber *por que* algo falhou.
- Dataset tem viés: casos de 1 turno não medem o forte do handoff. Inclua **multi-turno**.
- Cenário simples demais não diferencia arquiteturas: com 4 tools todas acertavam; com 10, a diferença apareceu.
- Ajustar olhando os mesmos casos é **overfitting**. O número sobe sem provar que generaliza.
- Custo de eval é tokens: rode subconjuntos (`--case`, `--runs 1`) e o completo só nos marcos.

### O loop do agente na prática
- Agente = `while`: chama o LLM → se pediu tool, o **código** executa e devolve → repete; senão, responde.
- O estado é só a lista de mensagens, reenviada inteira a cada chamada (a API não guarda nada).
- Cada volta do loop é uma chamada paga: uma mensagem do usuário pode custar 2, 3 ou mais chamadas.
- A descrição da tool é um prompt: é por ela que o LLM decide quando usar.
- Erro de tool volta para o LLM como resultado; o agente se corrige em vez de quebrar.
- `max_steps` é a trava contra loop infinito.
- Tools são testadas com pytest; o comportamento do LLM precisa de eval.
- O conceito é igual em qualquer provedor; muda só o formato (tool, mensagens, stop reason).
- ⚠️ Identidade vinda do chat é entrada não confiável (Achado 1.2). Resolvido na 1.4 com login + sessão injetada pelo código.
- "Agente" é configuração sobre o loop: modelo + prompt + tools. O loop genérico não deve conhecer regras de uma topologia (use um gancho).

### Routing, supervisor e handoff na prática
- **Routing (workflow):** um classificador divide e distribui; o código executa. Plano fixo antes de executar, ninguém reage ao resultado.
- **Supervisor:** um LLM lê o resultado de cada especialista e decide o próximo passo. Custa mais, mas reage ao que descobre e sintetiza.
- **Handoff:** o agente transfere a *conversa*; quem recebe fica com o usuário nos próximos turnos.
- Routing quando dá para decidir tudo antes; supervisor ou handoff quando o próximo passo depende do resultado.
- Classificador é chute forçado; triagem-*agente* pode **perguntar** antes de encaminhar. Meio-termo: classificador com rótulo `clarify`.
- Handoff é só uma tool. A troca de agente quem faz é o código.
- **Imposto da porta errada:** a cada troca de assunto, o agente atual gasta uma chamada só para transferir.
- O LLM pode chamar duas transferências em paralelo: só a primeira vale (guarda no código).

### Contexto entre agentes
- **Telefone sem fio:** toda reescrita/resumo perde algo (a triagem traduziu "lançar notas" e perdeu a justificativa).
- Repasse a **mensagem original** junto com o sub-pedido, ou a conversa inteira.
- No handoff: conversa inteira em texto, **assinada por autor**, sem as tools do outro agente (a API rejeita, e vaza informação).
- O que um agente não escreve, o próximo não sabe: transferir sem escrever gera ping-pong.
- Sem assinatura, o agente seguinte "completa" o que o colega já fez e pode contradizê-lo.
- Isolar permissões também isola informação: o N1 sem `get_user` não enxerga a causa real.

### Escalar para muitos agentes
- **Malha** (todos se conhecem): N×(N−1) transferências; agente novo mexe em todos os outros.
- **Hub-and-spoke** (triagem no centro): 2N transferências; agente novo mexe só na triagem. Empata com a malha em N=3; vence a partir de N=4.
- O hub cobra **dois saltos** por troca de assunto e depende da qualidade da triagem (ponto único de decisão).
- Especialista com prompt curto e focado segue melhor as próprias regras (Conta resolveu o "reset do colega").
- Produção costuma usar **híbrido**: triagem na entrada e transferência direta entre pares frequentes.

### Código vs prompt
- **Regra crítica vai no código:** permissão (`allowed`), dono do dado, identidade, proveniência, limites de loop.
- Esconder uma tool do LLM ≠ bloquear: ele ainda pode pedir pelo nome. O código precisa recusar.
- Prompt é **gangorra**: a regra rígida deixa o agente cauteloso demais; a branda deixa ele frouxo. Só o eval mostra onde você está.
- Validação em código garante **forma**, não **sentido**. O sentido fica com um juiz (módulo 6) ou com o humano (D2).
- Trocar o modelo muda o comportamento. "Modelo barato" se escolhe pelo preço real por token: o 4o-mini era mais caro que a Luna.

### Resultado do módulo
| | Single | Routing | Handoff malha | Handoff hub |
|---|---|---|---|---|
| Acerto geral (v2) | 90% | 91% | 89% | — |
| Vários pedidos numa mensagem | pior | **melhor** | médio | médio |
| Custo/conversa | **menor** | médio | médio | maior |
| Custo de adicionar agente | nenhum | classificador | todos os agentes | **só a triagem** |
- Neste cenário, um agente só resolve quase tudo. Multi-agente passa a valer com **muitas tools** (ambiguidade) ou **muitos agentes** (manutenção).

### Decisões do projeto
- **D1:** agentes divididos por capacidade e permissão, não por categoria.
- **D2:** o LLM nunca concede acesso. Ele cria a solicitação, um humano aprova e o código executa.
- **D3:** handoff para agentes que conversam com o usuário; agent-as-tool para consultas pontuais.
- **D4:** identidade vem da sessão autenticada, injetada pelo código. Tools não recebem identidade do LLM.
- **D5:** regras críticas (permissão, dono do dado, proveniência, limites) ficam no código, nunca só no prompt.
- **D6:** contexto entre agentes = mensagem/conversa original, assinada por autor. Nada de resumo como única fonte.
- **D7:** topologia: single por padrão; routing para vários pedidos ou pedidos ambíguos; handoff **hub** para escalar a muitos agentes; malha só com poucos agentes.
- **D8:** anti-ping-pong no código: não voltar a quem já atuou no turno, uma transferência por resposta, limite de handoffs.

---

## Módulo 2: A2A (Agent2Agent)

### O que é A2A
- Protocolo para um agente **delegar uma tarefa a outro agente**, geralmente de outro time ou serviço. Na prática é agent-as-tool pela rede.
- É **transporte**, não topologia. Dá para usar A2A dentro de um hub, de um supervisor ou de um pipeline.
- **A2A × MCP:** só use A2A se do outro lado existe um **agente** (com critério próprio). Se é uma função (buscar na KB), use tool/MCP.
- Spec **v1.0**: métodos `SendMessage`, `SendStreamingMessage`, `GetTask`, `CancelTask`...; estados `TASK_STATE_*`. Tutoriais antigos usam a v0.3 (`message/send`) e não funcionam mais.

### Agent Card
- JSON público em `/.well-known/agent-card.json`: **quem** é o agente, **onde** chamá-lo (URL + protocolo + versão), **o que** sabe fazer (skills), **recursos** (streaming, push) e **como** se autenticar (`security_schemes`).
- **Descoberta:** o cliente só conhece a URL base; o endereço das mensagens vem do card. Se o outro time mudar a rota, você não muda código.
- O card **não** diz: as tools internas, **quem** é aceito (isso é a lista de confiança do servidor) nem o formato do dado de negócio devolvido (lacuna de contrato → schema/extensão versionada, módulo 5).
- O card é uma **vitrine curada**: você publica o que escolhe, não tudo o que o agente faz.

### Skill não é tool
- **Skill** = capacidade de alto nível, escrita para **quem chama** decidir se deve chamar. **Tool** = função interna, opaca.
- Ninguém "chama uma skill": manda-se uma **mensagem em linguagem natural**, e o agente remoto escolhe as tools.
- Não há correspondência 1 para 1: uma skill usa várias tools; o time pode trocar as tools sem mudar o card.
- Escreva a skill na **língua do usuário**, com `examples` (é o que mais ajuda o LLM de quem chama). "Gerenciar solicitações de acesso" > "CRUD de solicitações".
- Helper interno (`buscar_gerente`) e controle (`ask_user`) **não** viram skill. Divida uma skill só quando a diferença importa para quem chama: permissão, prazo, público.
- No A2A você delega um **objetivo**; no MCP o **seu** LLM chama uma função com argumentos exatos.

### Tasks, estados e modos
- **Task** = uma unidade de trabalho (termina). **Context** = a conversa (continua). Mantenha o `contextId` entre tasks para o agente remoto lembrar da conversa.
- `INPUT_REQUIRED`: o remoto precisa de algo do usuário; a próxima mensagem vai para **a mesma task**.
- **O estado é contrato entre máquinas:** decida por **sinal explícito** (tool de controle `ask_user`), nunca por heurística ("não chamou tool = está perguntando" prendia a conversa quando o agente só recusava).
- Default que **falha para o lado seguro**: na dúvida, `COMPLETED` (pior caso: um salto a mais), nunca `INPUT_REQUIRED` (pior caso: usuário preso).
- Modos de entrega: **síncrono**, **streaming** (SSE, padrão em chat: mostra progresso), **polling** (`GetTask`), **webhook** (tarefa de horas; com polling de reconciliação).
- Task de acesso deve terminar rápido (`pending_approval`); a aprovação humana é **outro fluxo** (módulo 4).

### À mão vs SDK
- À mão (stdlib) serve para **ver o que passa na rede**; o SDK serve para **interoperar** com outros times.
- O SDK assume o **transporte**: JSON-RPC, erros tipados, `TaskStore` (separado por dono), streaming, `GetTask`/`Cancel`, tipos validados.
- Continua **nosso** a **semântica**: decisão do estado (`AgentExecutor.execute`), memória do agente por conversa, identidade. Nenhum SDK decide o contrato de negócio — o bug do estado teria acontecido igual com ele.
- **Interop provada:** o payload escrito à mão funcionou no servidor oficial. Prova só o que foi exercitado.
- Versões quebram (v0.3 → v1.0): **fixe a versão** dos dois lados; o card pode anunciar várias versões e o servidor manter compatibilidade (`enable_v0_3_compat`).
- Ponte síncrono↔assíncrono: `asyncio.to_thread` no servidor (senão um LLM travando congela o serviço — e até o streaming chega atrasado); `asyncio.run` no cliente.
- Mecanismo × política: o código genérico chama uma função sua (`on_progress`, `CredentialService`, `intercept`); quem usa decide o que fazer.

### Handoff sobre A2A
- O agente remoto vira um **nó do hub** (`RemoteAgent`, sem LLM do nosso lado). A triagem aprende o que ele faz **pelo card**.
- O remoto não sabe transferir: quando a task termina, **o código** devolve a conversa ao hub **no mesmo turno**.
- Agente opaco: o eval só enxerga o que o protocolo devolve (estado + dado estruturado). Artifact com **texto para o humano e dado para a máquina**.
- Least privilege pela arquitetura: tools e dados de acesso só existem dentro do serviço de IAM.

### Identidade entre serviços
- Duas perguntas: **quem está chamando?** (o serviço) e **em nome de quem?** (o usuário). Identidade no payload ou num header que qualquer um escreve = falsificável.
- Solução: **JWT assinado** (Ed25519) pelo Service Desk: assinatura = quem chama (`iss`); `sub` = usuário da sessão; `aud` = URL do agente (sem replay em outro serviço); `exp` curto (token por chamada).
- **Assimétrico > segredo compartilhado:** com HMAC quem verifica também emite; com par de chaves, verificar e assinar são poderes separados.
- O card declara o esquema (Bearer JWT); o `AuthInterceptor` do SDK põe o header; o servidor verifica **antes do protocolo** (middleware → 401): algoritmo fixo, emissor na **lista de confiança do servidor**, `aud`, `exp`, usuário conhecido.
- IDOR: `taskId` de outro usuário → o `TaskStore` do SDK (escopado por dono) resolve; `contextId` → chave `(usuário, contexto)`, impossível por construção.
- ⚠️ Fronteira que resta: o servidor crê em qualquer `sub` que o Service Desk assina. Correção real: **IdP + token exchange** (RFC 8693) a partir do token do próprio usuário. Em produção também: TLS, `jti` anti-replay, chave em cofre + JWKS para rotação.

### Muitos agentes e outros times
- O A2A expõe um agente **na fronteira**, não a organização interna. Um time com 50 tools e hub interno publica uma **fachada** com poucas skills de negócio; o hub deles fica atrás do executor.
- Vários agentes A2A só com **fronteira real** (dono, segurança ou escala diferentes). Senão, quem chama passa a conhecer o organograma do outro (acoplamento, Lei de Conway).
- Pergunta que decide: **quem deve saber rotear isso?** Quem conhece o domínio roteia.
- Muitas skills recriam o problema das muitas tools: granularidade de negócio, **Extended Agent Card** (lista completa só para autenticados), catálogo/descoberta (módulo 5).
- Mesmo time ≠ mesma arquitetura: separe por **contexto delimitado** (usuários, permissões, ciclo de vida, vocabulário). Um triage por contexto; A2A entre contextos. E não separe demais: cada agente custa operação, eval e tracing.

### Prompt, tools e eval (lições do módulo)
- **Toda tool disponível tende a ser usada.** `ask_user` fez o agente perguntar demais; `transfer_to_triage` fez devolver demais. A descrição precisa dizer **quando NÃO usar**.
- **Estrutura quem escreve é o código; o LLM só preenche o conteúdo.** A nota de handoff em texto livre ("encaminhar para suporte de impressoras") fez o destinatário não se reconhecer → ping-pong. Com a moldura do código ("transferido para VOCÊ"), sumiu.
- O agente não deve julgar o **mérito** de uma justificativa: isso é do gestor (D2).
- Eval de subconjunto confirma a correção; só o **eval completo** pega a regressão em outro lugar (caso 11).

### Resultado do módulo 2
- Hub + Acessos via A2A (com token assinado), 35 casos × 3: **93%**, 4,7 chamadas por caso (nossas + remotas), 6,1 s.
- Antes da correção do ping-pong: 91%, 4,9 chamadas, 8,3 s.
- Falhas restantes: trivia (caso 15, módulo 6) e variância 2/3 em poucos casos.
- A rede e o protocolo não pioraram a qualidade; o que mais pesou foi prompt e contrato entre agentes.

### Decisões do módulo 2
- **D9:** estado de protocolo por **sinal explícito** (tool de controle), com default que falha para o lado seguro.
- **D10:** identidade entre serviços = **token assinado** (quem chama + em nome de quem, `aud`, `exp` curto), verificado antes do protocolo. Nunca identidade no payload.
- **D11:** A2A para **agente** de outro contexto ou time, via **fachada** com skills de negócio; tool/MCP para função. Separar por contexto delimitado, não por time.
- **D12:** a **estrutura** das mensagens entre agentes (quem transferiu, para quem) é escrita pelo código; o LLM só preenche o conteúdo.

