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
