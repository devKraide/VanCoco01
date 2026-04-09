# config.py

## Visao geral

`config.py` centraliza constantes, enums, dataclasses leves e parametros operacionais usados por todo o projeto.

Ele funciona como o ponto unico de configuracao estatica do sistema:
- nomes de estados
- nomes de gestos
- caminhos de videos
- comandos dos robos
- thresholds de visao
- configuracao de transporte dos robos
- flags de comportamento

O arquivo nao executa fluxo nem contem logica narrativa procedural. Seu papel e definir o vocabulário compartilhado entre os modulos.

## Papel no sistema

`config.py` garante consistencia entre os componentes do projeto.

Sem ele, cada modulo teria de repetir:
- nomes de estados
- nomes de gestos
- comandos dos robos
- paths de videos
- parametros de deteccao

Ao concentrar isso em um unico arquivo, o sistema ganha:
- menos duplicacao
- menos risco de divergencia entre modulos
- mais facilidade para ajuste antes de apresentacao

## Integracao com outros modulos

### `main.py`

Consome:
- `AppState`
- `GestureName`
- `CameraTriggerName`
- `EXIT_KEYS`
- `KEY_ACTIONS`
- `ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8`

Esses elementos orientam o loop principal e o roteamento dos gatilhos.

### `story_engine.py`

Consome:
- estados narrativos e tipos de gesto
- caminhos de videos
- comandos dos robos
- `FINAL_OUTCOME`
- `FINAL_VIDEO_PATHS`
- `COLOR_VIDEO_PATHS`
- `ROBOT_NAMES`

Esse e um dos modulos mais dependentes de `config.py`.

### `gesture_mapper.py`

Consome:
- `GestureName`
- `VideoAction`
- `VIDEO_ACTIONS`
- `GESTURE_STABLE_FRAMES`

Ou seja, `config.py` define quais gestos disparam video diretamente e qual o debounce temporal base.

### `vision.py`

Consome:
- `GestureName`
- `CameraTriggerName`
- `DETECTION_CONFIDENCE`
- `TRACKING_CONFIDENCE`
- `ARUCO_MARKER_ID`
- thresholds do gesto `PRAYER_HANDS`

### `robot_comm.py`

Consome:
- baudrates
- modos de comunicacao dos robos
- portas configuradas

Isso permite alternar entre USB serial e RFCOMM sem alterar a interface do restante do sistema.

### `media_controller.py`

Consome indiretamente os paths de video e o nome base da janela.

## Fluxo principal no arquivo

`config.py` nao tem fluxo de execucao tradicional. O "fluxo" dele e estrutural:

1. define caminhos base do projeto
2. define enums compartilhados
3. define a estrutura `VideoAction`
4. mapeia gestos para videos diretos
5. define caminhos de midia narrativa
6. define teclas e parametros operacionais
7. define comandos e configuracao de comunicacao dos robos
8. define thresholds de visao e pose

O valor pratico e que o restante do sistema importa este arquivo como fonte unica de verdade.

## Principais estruturas explicadas

### `BASE_DIR` e `MEDIA_DIR`

Definem:
- raiz local do modulo
- pasta onde os videos sao esperados

Todo path de midia e derivado desses dois valores.

### `AppState`

Enum com os estados operacionais do app.

Exemplos:
- `IDLE_BLACK_SCREEN`
- `PLAYING_VIDEO`
- `WAITING_PRESENTATION`
- `WAITING_COLOR`
- `WAITING_VIDEO9_TRIGGER`

Esses estados sao usados principalmente por `main.py` e `state_manager.py`.

### `GestureName`

Enum com os gestos reconhecidos pelo sistema.

Hoje inclui:
- `HAND_OPEN`
- `POINT`
- `V_SIGN`
- `THUMB_UP`
- `CLOSED_FIST`
- `DOUBLE_CLOSED_FIST`
- `PRAYER_HANDS`

### `CameraTriggerName`

Enum para gatilhos que nao sao simplesmente um gesto de uma mao.

Hoje cobre:
- deteccao do marker da lupa
- fallback de `video8` por gesto com duas maos

### `VideoAction`

Dataclass imutavel usada para representar um disparo simples de gesto para video.

Campos:
- `gesture`
- `video_path`

Ela e usada principalmente pelo `gesture_mapper.py`.

### `VIDEO_ACTIONS`

Mapeia gestos que disparam video diretamente.

Hoje mapeia:
- `HAND_OPEN -> video1`
- `POINT -> video2`
- `THUMB_UP -> video5`
- `CLOSED_FIST -> video7`

Nem todo passo narrativo passa por esse mapa; alguns videos sao decididos pela engine.

### `VIDEO3_PATH`, `VIDEO4_PATH`, `VIDEO5_PATH`, `VIDEO7_PATH`, `VIDEO8_PATH`

Representam videos usados por transicoes narrativas especificas.

### `COLOR_VIDEO_PATHS`

Mapeia eventos de cor recebidos do `CocoVision` para videos:
- `COLOR_RED`
- `COLOR_GREEN`
- `COLOR_BLUE`

### `FINAL_OUTCOME` e `FINAL_VIDEO_PATHS`

Controlam o desfecho final sem depender de gesto diferente.

`PRAYER_HANDS` apenas dispara a etapa final; o video final real vem de:
- `success -> video9a`
- `failure -> video9b`

### `KEY_ACTIONS`

Atalhos de teclado para teste local.

Hoje:
- `1 -> HAND_OPEN`
- `2 -> POINT`

### `EXIT_KEYS`

Define as teclas de saida da aplicacao.

### Parametros de camera e gesto

Incluem:
- `CAMERA_INDEX`
- `CAMERA_WARMUP_FRAMES`
- `CAMERA_FRAME_WIDTH`
- `CAMERA_FRAME_HEIGHT`
- `CAMERA_BUFFER_SIZE`
- `DETECTION_CONFIDENCE`
- `TRACKING_CONFIDENCE`
- `DEBOUNCE_SECONDS`
- `GESTURE_STABLE_FRAMES`
- `VISION_PERF_LOG`
- `VISION_PERF_LOG_EVERY`

Esses valores afetam a experiencia real de deteccao.

### Parametros dos robos

Incluem:
- `ROBOT_NAMES`
- `ROBOT_COMMAND_PRESENT`
- `ROBOT_COMMAND_ACTION`
- `ROBOT_COMMAND_RETURN`
- `ROBOT_COMMAND_SCAN`
- `MOCK_VIDEO_DURATION_SECONDS`

Essas constantes padronizam o protocolo textual entre Python e firmware.

### Configuracao de transporte

Inclui:
- `COCOMAG_COMM_MODE`
- `COCOMAG_PORT`
- `COCOVISION_COMM_MODE`
- `COCOVISION_PORT`
- `COCOMAG_BAUDRATE`
- `COCOVISION_BAUDRATE`

Essa parte hoje permite:
- USB serial
- RFCOMM no Linux tratado como serial

### Configuracao de ArUco e pose

Inclui:
- `ARUCO_MARKER_ID`
- `ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8`
- thresholds de `PRAYER_HANDS`

Esses valores afetam a robustez da fase final do fluxo.

## Pontos criticos e de manutencao

### 1. Alterar enums impacta varios modulos

Qualquer mudanca em:
- `AppState`
- `GestureName`
- `CameraTriggerName`

impacta diretamente:
- `main.py`
- `story_engine.py`
- `vision.py`
- `gesture_mapper.py`

Essas mudancas devem ser feitas de forma sincronizada.

### 2. `VIDEO_ACTIONS` nao cobre todo o fluxo

Esse mapa cobre apenas os casos em que um gesto dispara um video diretamente.

Passos mais complexos continuam sendo controlados pela engine narrativa.

Ao adicionar um novo gesto, confirmar se ele:
- entra em `VIDEO_ACTIONS`
- ou deve ser tratado por `StoryEngine`

### 3. `FINAL_OUTCOME` altera o final inteiro

Esse valor e uma chave de comportamento narrativo importante.

Mudar:
- `FINAL_OUTCOME = "success"`
- ou `FINAL_OUTCOME = "failure"`

troca o video final sem alterar gesto nem fluxo.

### 4. Config de comunicacao deve ser consistente com o ambiente

No macOS:
- normalmente usar USB serial

No Linux:
- pode usar USB serial
- ou RFCOMM em `/dev/rfcomm*`

Se `COMM_MODE` e `PORT` estiverem inconsistentes, o `RobotComm` nao consegue conectar.

### 5. Thresholds de visao sao sensiveis a calibracao

Valores como:
- `DETECTION_CONFIDENCE`
- `TRACKING_CONFIDENCE`
- `GESTURE_STABLE_FRAMES`
- thresholds do `PRAYER_HANDS`

podem precisar de ajuste conforme:
- iluminacao
- camera
- distancia do ator
- maquina usada na apresentacao

### 6. Comentarios de operacao devem ficar sincronizados com o uso real

O comentario do RFCOMM e o comentario de `FINAL_OUTCOME` sao operacionais.

Se o modo de uso real mudar, esses comentarios precisam acompanhar.

## Resumo de manutencao

Ao mexer em `config.py`, pense em tres grupos:

1. vocabulário compartilhado
   - enums
   - comandos
   - nomes de gatilho

2. configuracao de operacao
   - portas
   - baudrate
   - modo serial ou rfcomm
   - outcome final

3. calibracao
   - thresholds de gesto
   - thresholds de pose
   - confianca da visao
   - resolucao da camera
   - tamanho do buffer da camera
   - telemetria opcional de performance

O arquivo funciona melhor quando continua sendo uma fonte unica, simples e previsivel de configuracao global do sistema.
