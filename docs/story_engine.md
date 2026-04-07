# story_engine.py

## Visao geral

`story_engine.py` e o nucleo narrativo do projeto.

Ele define:
- em que etapa da historia o sistema esta
- qual gesto e valido em cada etapa
- quais eventos de robô ou camera fazem o fluxo avancar
- qual video ou comando de robô deve acontecer em seguida

Este arquivo nao toca video, nao le camera, nao abre serial e nao controla janela. Ele funciona como uma maquina de estados narrativos orientada por triggers.

## Papel no sistema

O papel de `story_engine.py` e separar a semantica narrativa da camada operacional.

Na pratica, ele responde perguntas como:
- qual gesto o sistema aceita agora?
- depois desse gesto, a historia vai para qual etapa?
- esse passo deve tocar um video ou mandar um comando ao robô?
- esse `DONE` recebido ainda vale para a etapa atual?
- essa cor ja foi usada antes ou deve ser ignorada?

Isso evita que `main.py` precise conter regras de historia espalhadas em `if/else`.

## Integracao com outros modulos

### `main.py`

E o principal consumidor da engine.

`main.py` consulta a engine para:
- validar gatilhos
- concluir um passo ativo
- consumir eventos de robô
- consumir eventos de cor
- consumir o gatilho especial do `video8`

Em outras palavras:
- `main.py` orquestra
- `story_engine.py` decide o significado narrativo

### `config.py`

Fornece quase todo o vocabulário usado pela engine:
- `GestureName`
- `CameraTriggerName`
- caminhos de video
- comandos dos robos
- nomes dos robos
- flag do fallback do `video8`
- outcome final

### `gesture_mapper.py`

Fornece o tipo `GestureResult`, que chega ate a engine ja com debounce aplicado.

### `robot_comm.py`

Fornece o tipo `RobotEvent`, que a engine consome para:
- `DONE` de robôs
- `COLOR_*`

## Fluxo principal

O fluxo interno da engine pode ser dividido em tres tipos de entrada:

1. gestos comuns
2. eventos vindos dos robôs
3. gatilhos especiais de camera/cor

Fluxo geral:

1. a engine comeca em `WAIT_HAND_OPEN`
2. `consume_trigger()` valida se o gesto recebido e o esperado para a etapa atual
3. `complete_active_step()` consome esse passo validado e faz a transicao de estado
4. dependendo da etapa:
   - retorna comando para robô
   - retorna video
   - apenas muda o estado interno
5. em estados de espera de robô, `consume_*_result()` interpreta `RobotEvent`
6. em `WAITING_COLOR`, `consume_color_event()` interpreta `COLOR_*`
7. em `WAITING_VIDEO8_TRIGGER`, `consume_video8_trigger()` aceita ArUco ou fallback configurado
8. em `WAITING_VIDEO9_TRIGGER`, `PRAYER_HANDS` dispara o video final definido por `FINAL_OUTCOME`

## Estruturas principais

### `StoryStage`

Enum que representa os estados narrativos da historia.

Estados atuais:
- `WAIT_HAND_OPEN`
- `WAIT_POINT`
- `WAITING_PRESENTATION`
- `WAITING_COCOMAG_ACTION`
- `WAITING_COCOMAG_ACTION_COMPLETION`
- `WAITING_VIDEO5_TRIGGER`
- `WAITING_COCOVISION_ACTION_COMPLETION`
- `WAITING_COLOR`
- `PLAYING_COLOR_VIDEO`
- `WAITING_VIDEO7_TRIGGER`
- `WAITING_COCOVISION_RETURN_COMPLETION`
- `WAITING_VIDEO8_TRIGGER`
- `WAITING_VIDEO9_TRIGGER`
- `LOCKED_END`

Esse enum e a base de toda a maquina narrativa.

### `StoryStep`

Dataclass imutavel que representa um passo de gesto simples.

Campos:
- `expected_gesture`
- `next_stage`

Ela e usada para modelar os passos em que a narrativa depende de um gesto unico e claro.

### `StoryTransition`

Dataclass imutavel que representa a saida operacional de uma transicao narrativa.

Campos:
- `robot_commands`
- `video_path`
- `mock_video_duration`

Essa estrutura e importante porque desacopla a engine da execucao concreta:
- a engine decide o que deveria acontecer
- `main.py` executa isso

## Estado interno da engine

### `self._stage`

Estado narrativo atual.

### `self._active_step`

Armazena um `StoryStep` que ja foi validado por um gesto, mas ainda nao foi concluido operacionalmente.

Esse detalhe e importante:
- `consume_trigger()` apenas aceita o gesto e reserva o passo
- `complete_active_step()` realmente executa a transicao

Esse desenho reduz risco de duplicacao entre "gesto aceito" e "passo concluido".

### `self._pending_robots`

Conjunto de robôs que ainda faltam responder na etapa de apresentacao simultanea.

Hoje ele e usado em `WAITING_PRESENTATION`.

### `self._consumed_colors`

Conjunto de cores que ja foram usadas na execucao atual.

Isso permite a regra:
- cada cor so pode disparar seu video uma vez

## Principais funcoes explicadas

### `__init__()`

Inicializa a maquina narrativa no estado:
- `WAIT_HAND_OPEN`

Tambem prepara os estados auxiliares:
- sem passo ativo
- sem robôs pendentes
- sem cores consumidas

### `consume_trigger()`

Recebe um `GestureResult` e decide se ele pode abrir um passo narrativo.

Regras:
- se nao houver gesto, ignora
- se ja houver passo ativo, ignora
- constrói o passo esperado para o estado atual
- compara o gesto recebido com o gesto esperado
- se bater, grava em `_active_step` e devolve o resultado

Esse metodo nao avanca o estado sozinho. Ele apenas valida o gatilho.

### `complete_active_step()`

Conclui o passo anteriormente aceito e faz a transicao real de estado.

Esse metodo e um dos mais importantes da engine.

Dependendo do novo estado, ele pode:
- preparar comandos simultaneos para os robôs
- mandar `COCOMAG:ACTION`
- mandar `COCOVISION:ACTION`
- mandar `COCOVISION:RETURN`
- devolver o video final de `PRAYER_HANDS`
- ou simplesmente retornar uma transicao vazia

Esse desenho e importante porque permite que o mesmo gesto seja primeiro validado e depois efetivamente executado.

### `consume_robot_event()`

Consumidor especifico da etapa `WAITING_PRESENTATION`.

Regras:
- so aceita eventos `DONE`
- so aceita robôs que ainda estao em `_pending_robots`
- remove cada robô conforme ele termina
- quando ambos terminam, avanca para `WAITING_COCOMAG_ACTION` e retorna `video3`

### `consume_cocomag_action_result()`

So funciona em `WAITING_COCOMAG_ACTION_COMPLETION`.

Quando recebe `COCOMAG_DONE`:
- avanca para `WAITING_VIDEO5_TRIGGER`
- retorna `video4`

### `consume_cocovision_action_result()`

So funciona em `WAITING_COCOVISION_ACTION_COMPLETION`.

Quando recebe `COCOVISION_DONE`:
- avanca para `WAITING_COLOR`

Nao retorna video aqui porque a etapa seguinte e leitura continua de cor.

### `consume_cocovision_return_result()`

So funciona em `WAITING_COCOVISION_RETURN_COMPLETION`.

Quando recebe `COCOVISION_DONE`:
- avanca para `WAITING_VIDEO8_TRIGGER`
- retorna `video7`

### `consume_video8_trigger()`

Trata a etapa especial do `video8`.

Regras:
- so funciona em `WAITING_VIDEO8_TRIGGER`
- aceita ArUco marker sempre
- aceita `DOUBLE_CLOSED_FIST` apenas se a flag estiver habilitada
- em caso valido:
  - avanca para `WAITING_VIDEO9_TRIGGER`
  - retorna `video8`

Essa funcao e um caso especial porque nao trabalha com `GestureResult`, e sim com `CameraTriggerName`.

### `consume_color_event()`

So funciona em `WAITING_COLOR`.

Regras:
- o evento precisa vir do `COCOVISION`
- a cor nao pode ter sido consumida antes
- a cor precisa existir em `COLOR_VIDEO_PATHS`

Quando aceita:
- adiciona a cor a `_consumed_colors`
- muda o estado para `PLAYING_COLOR_VIDEO`
- retorna o video correspondente

### `consume_color_video_finished()`

Usada quando um video de cor termina.

Regras:
- so funciona se a engine estiver em `PLAYING_COLOR_VIDEO`
- se todas as cores configuradas ja foram usadas:
  - vai para `WAITING_VIDEO7_TRIGGER`
- senao:
  - volta para `WAITING_COLOR`

Esse metodo e o que transforma a fase de cores em um ciclo controlado.

### `is_waiting_*()`

Os metodos de consulta:
- `is_waiting_cocomag_action()`
- `is_waiting_video5_trigger()`
- `is_waiting_cocovision_action_completion()`
- `is_waiting_color()`
- `is_waiting_video7_trigger()`
- `is_waiting_video8_trigger()`
- `is_waiting_video9_trigger()`

servem como interface limpa para `main.py`.

Eles evitam que o orquestrador precise conhecer diretamente os detalhes internos da engine.

### `_build_current_step()`

Metodo privado que traduz o estado narrativo atual em um `StoryStep`, quando a etapa atual depende de um gesto unico.

Mapeamento atual:
- `WAIT_HAND_OPEN -> HAND_OPEN -> WAIT_POINT`
- `WAIT_POINT -> POINT -> WAITING_PRESENTATION`
- `WAITING_COCOMAG_ACTION -> V_SIGN -> WAITING_COCOMAG_ACTION_COMPLETION`
- `WAITING_VIDEO5_TRIGGER -> THUMB_UP -> WAITING_COCOVISION_ACTION_COMPLETION`
- `WAITING_VIDEO7_TRIGGER -> CLOSED_FIST -> WAITING_COCOVISION_RETURN_COMPLETION`
- `WAITING_VIDEO9_TRIGGER -> PRAYER_HANDS -> LOCKED_END`

Se o estado atual nao depender de gesto simples, retorna `None`.

## Fluxo narrativo atual representado pela engine

A sequencia atual codificada aqui e:

1. `HAND_OPEN`
2. `POINT`
3. apresentacao simultanea dos robôs
4. `video3`
5. `V_SIGN`
6. acao do `CocoMag`
7. `video4`
8. `THUMB_UP`
9. acao do `CocoVision`
10. leitura de cores
11. `CLOSED_FIST`
12. retorno do `CocoVision`
13. `video7`
14. gatilho especial de `video8`
15. `PRAYER_HANDS`
16. video final por `FINAL_OUTCOME`

## Pontos criticos e de manutencao

### 1. Separacao entre aceitar gesto e concluir passo

O par:
- `consume_trigger()`
- `complete_active_step()`

e essencial para a arquitetura atual.

Se essa separacao for removida sem cuidado, o sistema pode:
- disparar transicoes duplicadas
- aceitar gestos no frame errado
- misturar validacao com execucao

### 2. A engine depende de estados coerentes no `main.py`

Ela nao toca player nem estado operacional diretamente.

Se `main.py` nao respeitar a transicao retornada, o fluxo quebra mesmo que a engine esteja correta.

### 3. A fase de cores tem semantica especial

Ela usa:
- `_consumed_colors`
- `PLAYING_COLOR_VIDEO`
- retorno a `WAITING_COLOR`

Esse e um dos blocos mais delicados do arquivo, porque mistura:
- evento continuo vindo do robô
- memoria de historico
- condicao de saida da fase

### 4. `LOCKED_END` e um estado terminal narrativo

Depois que a engine entra em `LOCKED_END`, nao existe novo passo narrativo simples previsto.

Qualquer extensao apos o final exigira:
- novo estado
- ajuste no `_build_current_step()`
- ajuste nas transicoes especiais

### 5. `FINAL_OUTCOME` altera o comportamento final sem mudar gesto

Isso e bom para controle narrativo, mas exige cuidado:
- o gesto final continua sendo o mesmo
- o resultado visual final vem de config

Quem mantiver o sistema precisa entender essa separacao.

### 6. O fallback de `video8` e governado por flag

`ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8` altera a semantica de `consume_video8_trigger()`.

Se a flag for desligada:
- o ArUco continua funcionando
- o fallback gestual deixa de valer

Essa dependencia e intencional e precisa ser mantida clara.

### 7. O conjunto `ROBOT_NAMES` controla a espera simultanea

Na apresentacao dos robôs, a engine usa `set(ROBOT_NAMES)`.

Se esse conjunto mudar em `config.py`, a logica de apresentacao simultanea muda automaticamente.

Isso e poderoso, mas tambem uma fonte potencial de efeitos colaterais.

## Resumo de manutencao

`story_engine.py` deve continuar sendo a camada de semantica narrativa do projeto.

Ao evoluir este arquivo:
- manter a narrativa declarativa por estados
- evitar mover regras de historia para `main.py`
- preservar a separacao entre gesto aceito e passo concluido
- testar com cuidado qualquer mudanca em:
  - fase de cor
  - transicoes de robô
  - gatilhos especiais (`video8`, `video9`)

Este modulo funciona melhor quando continua sendo uma maquina de estados pequena, previsivel e sem efeitos colaterais operacionais diretos.
