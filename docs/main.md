# main.py

## Visao geral

`main.py` e o ponto de entrada da aplicacao e concentra a orquestracao do loop principal do `VanCoco`.

Ele conecta os modulos de:
- estado operacional
- narrativa
- visao computacional
- reproducao de video
- comunicacao com robos

O arquivo nao implementa a regra narrativa em profundidade e tambem nao implementa a deteccao de gestos ou o protocolo dos robos. O papel dele e coordenar esses modulos em tempo real.

## Papel no sistema

`main.py` e responsavel por:

- inicializar os componentes centrais do app
- manter o loop principal ativo
- atualizar UI e player de video
- ler entradas de teclado e camera
- enviar gatilhos para o `StoryEngine`
- iniciar reproducoes de video
- enviar comandos aos robos
- reagir a eventos recebidos dos robos
- trocar o estado operacional da aplicacao

Em termos práticos, este arquivo funciona como a camada de integracao do sistema.

## Conexao com outros modulos

### `config.py`

Fornece enums, flags e constantes usadas no fluxo principal:
- `AppState`
- `GestureName`
- `CameraTriggerName`
- teclas de saida
- fallback opcional do `video8`

### `state_manager.py`

Guarda o estado operacional atual da aplicacao.

Exemplos:
- `IDLE_BLACK_SCREEN`
- `PLAYING_VIDEO`
- `WAITING_COLOR`
- `WAITING_VIDEO9_TRIGGER`

`main.py` usa o `StateManager` para decidir qual handler deve rodar em cada iteracao.

### `story_engine.py`

Concentra as regras narrativas do projeto.

`main.py` nao decide sozinho o significado narrativo de um gesto. Em vez disso:
- envia o trigger para o `StoryEngine`
- recebe uma transicao
- executa os efeitos operacionais dessa transicao

Exemplos de efeito:
- tocar um video
- mandar comando para robo
- entrar em estado de espera

### `vision.py`

Entrega entradas vindas da camera:
- gesto detectado
- marker ArUco detectado

`main.py` consulta a visao apenas quando o estado atual realmente precisa de camera.

### `gesture_mapper.py`

Faz o debounce e a normalizacao dos gestos brutos antes de eles entrarem no fluxo narrativo.

`main.py` usa o mapper ao ler teclado e camera em `_read_trigger_source()`.

### `media_controller.py`

Controla:
- tela preta
- janela fullscreen
- atualizacao da UI
- player de video
- leitura de teclado
- sinal de fim de video

### `robot_comm.py`

Controla o envio e recebimento de mensagens dos robos.

`main.py` usa esse modulo para:
- enviar comandos como `PRESENT`, `ACTION`, `RETURN`
- receber eventos como `COCOMAG_DONE`, `COCOVISION_DONE`, `COLOR_*`

## Fluxo principal

O fluxo principal esta no metodo `run()`.

Cada iteracao faz, nesta ordem:

1. atualiza a UI
2. renderiza o estado visual atual
3. consome tecla do teclado
4. monta uma requisicao minima de visao baseada no estado atual
5. le entradas da camera apenas se a etapa atual exigir isso
5. trata saida (`q` ou `Esc`)
6. despacha a execucao para o handler correspondente ao `AppState`

O dispatch principal e uma sequencia de `if` baseada no estado atual da aplicacao.

Exemplos:
- `IDLE_BLACK_SCREEN` chama `_handle_idle_state()`
- `PLAYING_VIDEO` chama `_handle_playing_state()`
- `WAITING_PRESENTATION` chama `_handle_waiting_presentation_state()`
- `WAITING_COLOR` chama `_handle_waiting_color_state()`
- `WAITING_VIDEO9_TRIGGER` chama `_handle_waiting_video9_trigger_state()`

Ao sair do loop, o `finally` garante cleanup de:
- `RobotComm`
- `MediaController`
- `VisionSystem`

## Principais funcoes

### `__init__()`

Instancia os modulos principais:
- `StateManager`
- `MediaController`
- `VisionSystem`
- `GestureMapper`
- `StoryEngine`
- `RobotComm`

Essa composicao deixa explicito quais subsistemas participam da execucao do app.

### `run()`

E o coracao do arquivo.

Responsabilidades:
- manter o loop principal
- atualizar entradas e saidas
- reduzir custo de visao em estados que nao precisam de camera
- escolher qual handler executar
- garantir encerramento limpo

### `_render_current_state()`

Forca a tela preta nos estados de espera.

Isso evita lixo visual entre as fases e mantem o comportamento consistente enquanto nenhum video esta tocando.

### `_handle_idle_state()`

Trata o estado inicial e narrativo de espera.

Passos:
- le gesto/teclado
- envia para o `StoryEngine`
- se houver acao valida, pede playback ao `StateManager`
- inicia o video no `MediaController`

### `_handle_playing_state()`

Trata o momento em que um video terminou.

Esse metodo e um dos mais importantes do arquivo porque concentra as transicoes pos-video.

Ele pode:
- voltar para leitura de cor
- enviar comandos a robos
- entrar em espera de um novo gesto
- finalizar a reproducao

Tambem contem o ramo especial dos videos de cor, que podem retornar para `WAITING_COLOR` em vez de encerrar a narrativa.

### `_handle_waiting_presentation_state()`

Espera os `DONE` da apresentacao simultanea dos robos e, quando a engine liberar, inicia o video seguinte.

### `_handle_waiting_cocomag_action_state()`

Espera especificamente `V_SIGN`.

Quando detecta:
- conclui o passo narrativo ativo
- envia comando para o `CocoMag`
- entra em espera da conclusao da acao

### `_handle_waiting_cocomag_action_completion_state()`

Espera o `COCOMAG_DONE` da fase individual do `CocoMag` e inicia o proximo video.

### `_handle_waiting_video5_trigger_state()`

Espera `THUMB_UP` e dispara `video5`.

### `_handle_waiting_cocovision_action_completion_state()`

Espera o `COCOVISION_DONE` que encerra a acao inicial do `CocoVision`, limpa eventos antigos de cor e libera a fase de leitura.

### `_handle_waiting_color_state()`

Espera eventos `COLOR_*`.

Quando uma cor nova e aceita:
- bloqueia novas leituras temporariamente
- limpa eventos antigos da fila
- inicia o video correspondente

### `_handle_waiting_video7_trigger_state()`

Espera `CLOSED_FIST` para iniciar o retorno do `CocoVision`.

### `_handle_waiting_cocovision_return_completion_state()`

Espera o `DONE` do retorno do `CocoVision` e entao toca `video7`.

### `_handle_waiting_video8_trigger_state()`

Trata o gatilho do `video8`.

Aceita:
- ArUco marker
- fallback opcional `DOUBLE_CLOSED_FIST`

### `_handle_waiting_video9_trigger_state()`

Espera `PRAYER_HANDS`.

Quando o gesto chega:
- conclui o passo ativo
- escolhe o video final vindo da engine
- inicia a reproducao final

### `_read_trigger_source()`

Faz a ponte entre:
- teclado
- gesto vindo da camera

O teclado tem prioridade. Se nao houver tecla mapeada, usa o gesto vindo da visao.

### `_build_vision_request()`

Traduz o estado operacional atual em uma requisicao minima para a pipeline de visao.

Esse metodo define:
- se a visao deve rodar ou nao
- qual gesto e esperado
- se ArUco deve ser verificado
- se `PRAYER_HANDS` deve ter prioridade
- se duas maos sao realmente necessarias

Esse metodo e importante para performance, especialmente no Linux.

### `_read_video8_trigger_source()`

Trata o caso especial de `video8`, que nao depende apenas de gesto comum.

Ele converte:
- marker ArUco
- fallback `DOUBLE_CLOSED_FIST`

em um trigger compreensivel para o `StoryEngine`.

## Pontos criticos e manutencao

### 1. `main.py` nao deve virar a camada de regra narrativa

Ao adicionar fases novas, a logica de significado do gesto deve continuar no `StoryEngine`.

`main.py` deve permanecer como camada de orquestracao.

### 2. `_handle_playing_state()` e o ponto mais sensivel do arquivo

Esse metodo concentra a maior parte das transicoes apos termino de video.

Qualquer alteracao aqui pode afetar varias fases ao mesmo tempo.

Sempre validar:
- fim de video comum
- fim de video de cor
- transicao para esperas de robos
- retorno correto ao estado neutro

### 3. Handlers devem permanecer pequenos e específicos

O padrao atual e bom:
- um handler por estado relevante
- cada handler com uma responsabilidade principal

Ao expandir o fluxo, manter esse padrao facilita debug e leitura.

### 4. Eventos de cor exigem cuidado

`WAITING_COLOR` tem regras especiais:
- limpar eventos antigos
- bloquear novas cores durante playback
- voltar para leitura apos o video

Esse ramo precisa continuar coerente com `RobotComm`, `StateManager` e `StoryEngine`.

### 5. Gatilhos especiais devem continuar isolados

Hoje existem dois casos mais especiais:
- `video8` com ArUco e fallback
- `video9` com `PRAYER_HANDS`

Novos gatilhos nao devem ser misturados genericamente com os gestos comuns se a semantica for diferente.

### 6. Fechamento limpo e obrigatorio

O `finally` do `run()` garante liberacao de:
- comunicacao com robos
- recursos da janela/player
- camera

Nao remover esse padrao.

## Resumo de manutencao

Quando adicionar um novo passo narrativo, o caminho esperado e:

1. criar ou reaproveitar um `AppState`
2. adicionar o handler correspondente em `main.py`
3. ligar o handler no `run()`
4. manter a regra do fluxo no `StoryEngine`
5. validar transicao de fim de video em `_handle_playing_state()`

Esse arquivo funciona melhor quando continua sendo um coordenador fino entre modulos especializados.
