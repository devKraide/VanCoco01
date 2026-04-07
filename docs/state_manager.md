# state_manager.py

## Visao geral

`state_manager.py` e a camada de estado operacional da aplicacao.

Ele nao implementa a narrativa e nao interage diretamente com camera, player ou robos. O papel dele e manter um retrato compacto do estado corrente do app do ponto de vista operacional:

- qual `AppState` esta ativo
- se existe um playback em andamento
- qual gesto foi disparado por ultimo
- quando esse gesto ocorreu
- quais videos ja foram marcados como reproduzidos

Esse modulo funciona como uma pequena store de runtime para o loop principal.

## Papel no sistema

O papel de `state_manager.py` e controlar o ciclo operacional do app.

Enquanto o `StoryEngine` define o significado narrativo das etapas, o `StateManager` responde perguntas como:
- o app esta ocioso ou reproduzindo video?
- existe uma requisicao de playback ativa?
- esse gesto ainda deve ser bloqueado por debounce?
- esse video ja foi tocado antes e precisa ser ignorado?

Ele tambem fornece metodos explicitos para entrar em cada estado operacional usado por `main.py`.

## Integracao com outros modulos

### `config.py`

Fornece:
- `AppState`
- `DEBOUNCE_SECONDS`
- `GestureName`
- `VideoAction`

Esses tipos e constantes definem o contrato do modulo.

### `main.py`

E o principal consumidor do `StateManager`.

`main.py` usa este modulo para:
- ler o estado atual
- decidir qual handler executar
- iniciar playback
- trocar explicitamente para estados de espera
- finalizar playback

### `media_controller.py`

Nao fala diretamente com o `StateManager`, mas depende da coerencia dele para que o player seja acionado e encerrado no momento correto.

### `story_engine.py`

Tambem nao conversa diretamente com esse modulo, mas ambos caminham juntos:
- `StoryEngine` define o proximo significado narrativo
- `StateManager` define o estado operacional em que o app entra por causa disso

## Fluxo principal

O fluxo tipico de uso do `StateManager` e:

1. o app comeca em `IDLE_BLACK_SCREEN`
2. um gesto valido chama `request_playback()`
3. o estado passa para `PLAYING_VIDEO`
4. quando o video termina, `main.py` escolhe a proxima transicao
5. o estado passa para uma etapa de espera especifica:
   - apresentacao dos robos
   - espera de gesto
   - espera de cor
   - etc.
6. ao final de uma fase que nao cria nova espera especializada, `finish_playback()` volta o app para `IDLE_BLACK_SCREEN`

O modulo nao tem loop proprio. Ele e passivo: responde a chamadas feitas pelo orquestrador.

## Estruturas principais

### `PlaybackRequest`

Dataclass que representa uma requisicao de playback em andamento.

Campos:
- `video_path`
- `gesture`

Uso:
- quando o playback foi disparado por gesto, `gesture` pode ser preenchido
- quando o playback foi disparado pelo sistema, apenas `video_path` e necessario

Essa estrutura permite carregar o contexto minimo do playback atual sem misturar isso com o estado global inteiro.

### `StateManager`

Classe principal do modulo.

Estado interno:
- `self._state`
- `self._active_request`
- `self._last_triggered_gesture`
- `self._last_triggered_at`
- `self._played_videos`

## Principais funcoes explicadas

### `__init__()`

Inicializa:
- estado em `IDLE_BLACK_SCREEN`
- nenhuma requisicao ativa
- nenhum gesto recente
- nenhum video registrado como tocado

Esse e o ponto de partida operacional do app.

### `state`

Property de leitura do estado atual.

E usada principalmente no `main.py` para rotear o loop principal.

### `active_request`

Property de leitura da requisicao de playback atual.

Expõe o `PlaybackRequest` ativo, quando existir.

### `can_accept_gesture()`

Regra operacional simples:
- so aceita gesto novo quando o app esta em `IDLE_BLACK_SCREEN`

Esse metodo e uma barreira importante contra disparos durante video ou em fases de espera especializadas.

### `request_playback(gesture, action)`

Esse e o principal ponto de entrada para playback iniciado por gesto simples.

Fluxo interno:

1. verificar se o estado atual permite gesto
2. verificar se o video ja foi tocado antes
3. verificar debounce temporal do mesmo gesto
4. criar `PlaybackRequest`
5. mudar estado para `PLAYING_VIDEO`
6. registrar gesto e tempo
7. registrar o video como reproduzido

Se qualquer validacao falhar, retorna `False`.

Esse metodo concentra tres protecoes relevantes:
- estado correto
- debounce de gesto
- bloqueio de repeticao de video

### `start_system_playback(video_path)`

Usado quando o playback nao vem diretamente de um gesto simples aceito por `request_playback()`.

Exemplos:
- videos disparados por transicao de robô
- video de cor
- video final

Esse metodo:
- cria `PlaybackRequest` sem gesto associado
- muda o estado para `PLAYING_VIDEO`

### `enter_waiting_presentation()`

Transiciona para a fase de espera da apresentacao simultanea dos robôs.

Limpa `active_request` antes de mudar o estado.

### `enter_waiting_cocomag_action()`

Entra na fase que espera o gesto `V_SIGN`.

### `enter_waiting_cocomag_action_completion()`

Entra na fase em que o app aguarda o `COCOMAG_DONE`.

### `enter_waiting_video5_trigger()`

Entra na fase de espera do `THUMB_UP`.

### `enter_waiting_cocovision_action_completion()`

Entra na fase de espera do `COCOVISION_DONE` apos `ACTION`.

### `enter_waiting_color()`

Entra na fase de leitura continua de cor.

### `enter_waiting_video7_trigger()`

Entra na fase de espera do `CLOSED_FIST`.

### `enter_waiting_cocovision_return_completion()`

Entra na espera do `COCOVISION_DONE` apos `RETURN`.

### `enter_waiting_video8_trigger()`

Entra na fase de espera do gatilho do `video8`.

### `enter_waiting_video9_trigger()`

Entra na fase final de espera do `PRAYER_HANDS`.

### `finish_playback()`

Finaliza o playback atual e devolve o app para:
- `IDLE_BLACK_SCREEN`

Esse metodo e usado quando a narrativa nao leva a outro estado operacional especializado.

### `_is_debounced(gesture)`

Implementa o debounce temporal do mesmo gesto.

Logica:
- compara o gesto atual com o ultimo gesto disparado
- mede o tempo desde o ultimo disparo
- retorna `True` se ainda estiver dentro de `DEBOUNCE_SECONDS`

Importante:
- esse debounce e operacional
- ele complementa, e nao substitui, o debounce por frames do `gesture_mapper.py`

### `_was_already_played(action)`

Verifica se o `video_path` daquela `VideoAction` ja foi tocado antes.

Essa e a protecao usada para evitar repetir certos videos disparados por gesto simples na mesma execucao.

## Pontos criticos e de manutencao

### 1. `StateManager` nao substitui o `StoryEngine`

Esse modulo guarda estado operacional, nao semantica narrativa.

Se regras de historia forem movidas para ca, o acoplamento do sistema aumenta e a manutencao piora.

### 2. O debounce aqui e diferente do `gesture_mapper.py`

Existem duas camadas diferentes:

- `gesture_mapper.py`: debounce por estabilidade de frames
- `state_manager.py`: debounce temporal entre disparos aceitos

Essas camadas se complementam.

Alterar uma delas sem considerar a outra pode deixar o sistema:
- duro demais
- ou permissivo demais

### 3. `_played_videos` afeta apenas `request_playback()`

Esse conjunto bloqueia videos disparados via `VideoAction`.

Ele nao e a unica protecao de repeticao do projeto, porque:
- videos de cor seguem outra logica
- videos disparados pela engine podem nao passar por esse caminho

Quem mantiver o sistema precisa entender esse escopo.

### 4. Os metodos `enter_waiting_*` sao deliberadamente repetitivos

Eles parecem simples, mas isso e intencional.

Cada metodo:
- limpa `active_request`
- entra em um estado especifico

Esse desenho deixa o `main.py` mais legivel e evita strings ou estados espalhados.

### 5. O estado inicial e sempre `IDLE_BLACK_SCREEN`

Esse contrato precisa permanecer estavel, porque o restante do app assume esse ponto de partida visual e operacional.

### 6. O modulo nao persiste nada

Todo o estado mantido aqui e somente em memoria de execucao.

Ao reiniciar a aplicacao:
- debounce zera
- videos reproduzidos zeram
- estado volta para idle

Isso e coerente com o uso de apresentacao atual.

## Resumo de manutencao

`state_manager.py` funciona como uma store operacional enxuta.

Ao evoluir este modulo:
- manter foco em estado operacional
- nao mover narrativa para ca
- preservar a separacao entre:
  - gesto aceito
  - playback ativo
  - estado de espera

Se um novo estado operacional for introduzido no app, a extensao natural deste arquivo e:

1. adicionar o novo `AppState` em `config.py`
2. criar um novo metodo `enter_waiting_*` aqui, se fizer sentido
3. integrar esse estado no `main.py`

O modulo funciona melhor quando continua pequeno, previsivel e explicitamente alinhado com o loop principal.
