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

### Evals
- Eval = dataset → execução → nota em %.
- Formas de dar a nota: código > LLM-as-judge > humano.
- É o eval que transforma "multi-agente é melhor?" numa decisão baseada em números.
- Rodar cada caso várias vezes: o LLM varia, e 2/3 é um sinal diferente de 3/3.
- **Eval também tem bug:** leia as falhas antes de concluir (o baseline deu 83% por erro do checker; o real era 98%).
- Checagem por palavra-chave é frágil ("ainda não foi concedido" contém "foi concedido").
- Baseline do projeto: 98%, com 2,7 chamadas e US$ 0,00023 por caso. Pelos números, não valeria dividir em multi-agente.

### O loop do agente na prática
- Agente = `while`: chama o LLM → se pediu tool, o **código** executa e devolve → repete; senão, responde.
- O estado é só a lista de mensagens, reenviada inteira a cada chamada (a API não guarda nada).
- Cada volta do loop é uma chamada paga: uma mensagem do usuário pode custar 2, 3 ou mais chamadas.
- A descrição da tool é um prompt: é por ela que o LLM decide quando usar.
- Erro de tool volta para o LLM como resultado; o agente se corrige em vez de quebrar.
- `max_steps` é a trava contra loop infinito.
- Tools são testadas com pytest; o comportamento do LLM precisa de eval.
- O conceito é igual em qualquer provedor; muda só o formato (tool, mensagens, stop reason).
- ⚠️ Identidade vinda do chat é entrada não confiável: dá para se passar por outra pessoa (corrigir com autenticação).

### Decisões do projeto
- **D1:** agentes divididos por capacidade e permissão, não por categoria.
- **D2:** o LLM nunca concede acesso. Ele cria a solicitação, um humano aprova e o código executa.
- **D3:** handoff para agentes que conversam com o usuário; agent-as-tool para consultas pontuais.
