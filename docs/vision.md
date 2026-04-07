# vision.py

## Visao geral

`vision.py` concentra a entrada visual do projeto.

Ele integra:
- captura de camera com OpenCV
- deteccao de maos com MediaPipe Hands
- deteccao de pose com MediaPipe Pose
- deteccao de marker ArUco com OpenCV
- classificacao dos gestos usados no fluxo narrativo

O arquivo transforma frames de camera em um objeto simples de entrada para o restante do sistema:
- gesto detectado
- marker detectado

## Papel no sistema

O papel de `vision.py` e produzir sinais visuais de alto nivel a partir da camera.

Esses sinais sao usados pelo app para:
- iniciar videos por gesto
- avancar etapas narrativas
- detectar a lupa via ArUco
- detectar o gesto final `PRAYER_HANDS`

Este modulo nao executa narrativa e nao decide estado do app. Ele apenas observa a camera e entrega classificacoes.

## Integracao com outros modulos

### `config.py`

Fornece:
- `CAMERA_INDEX`
- `CAMERA_WARMUP_FRAMES`
- `DETECTION_CONFIDENCE`
- `TRACKING_CONFIDENCE`
- `ARUCO_MARKER_ID`
- thresholds de `PRAYER_HANDS`
- `GestureName`

### `main.py`

E o principal consumidor de `VisionSystem`.

`main.py` chama:
- `read_inputs()`

e recebe:
- `gesture`
- `marker_detected`

Tambem controla o modo especial `prioritize_prayer_hands` quando o app entra em `WAITING_VIDEO9_TRIGGER`.

### `gesture_mapper.py`

Recebe o gesto bruto retornado por `vision.py` e aplica debounce temporal antes do gesto entrar no fluxo narrativo.

### `story_engine.py`

Nao conversa diretamente com a camera, mas depende semanticamente dos sinais produzidos aqui:
- gestos comuns
- `DOUBLE_CLOSED_FIST`
- `PRAYER_HANDS`
- ArUco marker

## Fluxo principal

O fluxo principal do arquivo acontece em `VisionSystem.read_inputs()`:

1. verificar se a camera esta aberta
2. capturar um frame
3. converter BGR para RGB
4. processar maos com MediaPipe Hands
5. processar pose com MediaPipe Pose
6. classificar o gesto com `_detect_gesture()`
7. detectar marker com `_detect_marker()`
8. emitir log de debug resumido
9. retornar `VisionInputs`

Esse metodo e chamado repetidamente pelo loop principal do app.

## Principais estruturas e funcoes

### `_resolve_hands_api()` e `_resolve_pose_api()`

Essas funcoes validam se a instalacao atual do MediaPipe expoe as APIs classicas:
- `mediapipe.solutions.hands`
- `mediapipe.solutions.pose`

Se nao estiverem disponiveis, levantam erro com instrucoes de reinstalacao.

Isso protege o projeto contra versoes incompatíveis da biblioteca.

### `FingerState`

Dataclass que representa o estado geometrico resumido de uma mao:
- se a mao esta completa no frame
- polegar aberto
- polegar para cima
- indicador aberto
- medio aberto
- anelar aberto
- mindinho aberto

Essa estrutura e a base da classificacao dos gestos de uma mao.

### `VisionInputs`

Dataclass retornada para o app com:
- `gesture`
- `marker_detected`

Ela e a interface principal deste modulo com o restante do sistema.

### `GestureClassifier`

Classe responsavel por classificar uma unica mao.

Ela nao sabe nada sobre:
- estado do app
- video atual
- narrativa

Ela apenas responde qual gesto aquela mao parece representar.

#### `classify()`

Recebe landmarks de uma mao e retorna:
- um `GestureName`
- ou `None`

Ordem atual de classificacao:
- `HAND_OPEN`
- `V_SIGN`
- `THUMB_UP`
- `POINT`
- `CLOSED_FIST`

Essa ordem importa, porque o primeiro gesto que casa e retornado.

#### `_extract_finger_state()`

Converte landmarks brutos da mao em `FingerState`.

O metodo usa:
- coordenadas relativas dos 21 landmarks
- distancias normalizadas pela palma
- relacoes entre ponta, articulacao intermediaria e base

Essa funcao e o centro geometrico da classificacao de gestos de uma mao.

#### `_is_thumb_extended()`

Determina se o polegar esta estendido com base na direcao lateral dele em relacao ao pulso.

#### `_is_hand_open()`

Detecta mao aberta exigindo:
- mao completa
- indicador, medio e anelar abertos
- polegar aberto ou mindinho aberto

Essa regra foi ajustada para robustez pratica com a camera real.

#### `_is_point()`

Detecta apontar para cima exigindo:
- indicador aberto
- demais dedos fechados
- sem `thumb_up`

#### `_is_v_sign()`

Detecta:
- indicador aberto
- medio aberto
- anelar e mindinho fechados
- polegar nao aberto

#### `_is_thumb_up()`

Detecta:
- polegar para cima
- demais dedos fechados

#### `_is_closed_fist()`

Detecta:
- todos os dedos fechados
- sem `thumb_up`

### `VisionSystem`

Classe principal do modulo.

Responsabilidades:
- abrir a camera
- manter instancias do MediaPipe
- classificar inputs de cada frame
- fazer warm-up
- liberar recursos no final

#### `__init__()`

Configura:
- `cv2.VideoCapture`
- `Hands`
- `Pose`
- `GestureClassifier`
- detector ArUco
- contadores de debug
- warm-up da camera

#### `read_inputs()`

Metodo principal do modulo.

Recebe o parametro:
- `prioritize_prayer_hands`

Esse parametro altera a prioridade de deteccao para o estado final do app.

#### `detect_gesture()`

Atalho para quem so quer o gesto sem olhar marker.

Hoje ele apenas delega para `read_inputs()`.

#### `_detect_gesture()`

Combina maos e pose para chegar no gesto final do frame.

Regras principais:

1. se `prioritize_prayer_hands` estiver ativo e a pose validar `PRAYER_HANDS`, retorna imediatamente
2. se houver duas maos e ambas forem `CLOSED_FIST`, retorna `DOUBLE_CLOSED_FIST`
3. senao, tenta classificar a primeira mao visivel como gesto de uma mao
4. se nenhum gesto de mao for valido, tenta `PRAYER_HANDS`

Esse metodo define a prioridade entre:
- gestos de uma mao
- gesto com duas maos
- gesto por pose corporal

#### `_detect_prayer_hands()`

Implementa o gesto final por pose corporal.

Criterios atuais:
- pulsos visiveis
- ombros visiveis
- pulsos proximos entre si
- ponto medio dos pulsos alinhado ao centro dos ombros
- altura dos pulsos na faixa do peito
- pulsos nao acima do nariz quando o nariz esta visivel

Esse metodo e baseado em landmarks de pose, nao em landmarks de maos.

#### `_debug_detection()`

Emite logs periodicos com:
- numero de maos detectadas
- se `PRAYER_HANDS` esta priorizado
- gesto atual
- estado resumido dos dedos da primeira mao

Esse log e util para diagnosticar:
- maos vistas mas nao classificadas
- conflitos entre gestos
- thresholds muito rigidos

#### `_detect_marker()`

Usa o detector ArUco para verificar se o marker configurado em `ARUCO_MARKER_ID` esta presente no frame.

Ele nao faz pose nem gesto; apenas responde `True` ou `False`.

#### `release()`

Libera camera e instancias do MediaPipe.

Deve ser chamado no encerramento da aplicacao.

#### `_warm_up_camera()`

Faz leituras iniciais da camera para estabilizar o dispositivo antes do uso real.

#### `_build_aruco_detector()`

Cria o detector com:
- dicionario `DICT_4X4_50`
- parametros padrao do OpenCV

## Pontos criticos e de manutencao

### 1. Ordem de classificacao importa

No `GestureClassifier`, a ordem dos `if` define prioridade entre gestos parecidos.

No `_detect_gesture()`, a ordem define prioridade entre:
- gestos de uma mao
- gesto com duas maos
- `PRAYER_HANDS`

Qualquer alteracao aqui pode mudar o comportamento real do sistema.

### 2. `PRAYER_HANDS` tem modo especial de prioridade

Fora do estado final, a pose e avaliada depois dos gestos de mao.

No estado `WAITING_VIDEO9_TRIGGER`, `main.py` ativa `prioritize_prayer_hands`, e a pose passa a ser avaliada antes.

Esse detalhe e importante para evitar que o gesto final seja "roubado" por um gesto de mao.

### 3. Thresholds sao calibracao de campo

Varios comportamentos dependem de thresholds definidos em `config.py`.

Exemplos:
- confianca de deteccao
- alcance minimo dos dedos
- thresholds de centralidade e altura do `PRAYER_HANDS`

Esses valores podem precisar de ajuste conforme:
- camera usada
- iluminacao
- distancia do ator
- enquadramento da cena

### 4. `DOUBLE_CLOSED_FIST` depende de duas maos consistentes no mesmo frame

Se apenas uma mao fechar, o fallback do `video8` nao dispara.

Esse comportamento e intencional e precisa ser preservado.

### 5. O debug atual chama metodo interno do classifier

`_debug_detection()` usa `self._classifier._extract_finger_state(...)`.

Funciona, mas e uma dependencia interna do proprio modulo. Se a estrutura do classifier mudar, o debug precisa acompanhar.

### 6. A deteccao de mao nao deve assumir perfeicao do frame

O campo `is_complete` protege contra landmarks fora da area valida.

Se essa regra for relaxada demais, aumentam falsos positivos.

### 7. ArUco e gestos sao caminhos paralelos

O marker nao depende da deteccao de maos ou pose.

Isso e bom para robustez do `video8`, mas exige manter `_detect_marker()` simples e independente.

## Resumo de manutencao

`vision.py` deve continuar como modulo de percepcao visual, nao como modulo de narrativa.

Ao evoluir este arquivo:
- manter a deteccao separada da interpretacao narrativa
- preservar a interface simples `VisionInputs`
- validar qualquer mudanca com logs reais de camera
- revisar com cuidado a ordem de prioridade dos gestos

O modulo funciona melhor quando permanece focado em uma responsabilidade: transformar frames em sinais visuais confiaveis para o restante do sistema.
