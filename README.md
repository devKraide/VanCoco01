# VanCoco

Aplicacao interativa em Python para apresentacao teatral com:
- visao computacional via camera
- tela principal fullscreen preta
- videos com audio embutidos
- integracao com `CocoMag` e `CocoVision` via USB serial
- suporte a Bluetooth Classic no Linux via dispositivos RFCOMM (`/dev/rfcomm*`)

Fluxo atual do projeto:
- `HAND_OPEN` -> `video1`
- `POINT` -> `video2`
- envia `COCOMAG:PRESENT` e `COCOVISION:PRESENT`
- espera `COCOMAG_DONE` e `COCOVISION_DONE`
- toca `video3`
- espera `V_SIGN`
- envia `COCOMAG:ACTION`
- espera `COCOMAG_DONE`
- toca `video4`
- espera `THUMB_UP`
- toca `video5`
- envia `COCOVISION:ACTION`
- espera `COCOVISION_DONE`
- entra em leitura continua de cores
- `COLOR_RED` -> `video6_red`
- `COLOR_GREEN` -> `video6_green`
- `COLOR_BLUE` -> `video6_blue`
- quando todas as cores previstas ja foram consumidas:
  - espera `CLOSED_FIST`
  - envia `COCOVISION:RETURN`
  - espera `COCOVISION_DONE`
  - toca `video7`
- depois entra em espera de `video8`
  - gatilho principal: ArUco marker configurado
  - fallback opcional: `DOUBLE_CLOSED_FIST`
  - toca `video8`
- depois entra em espera do final
  - espera `PRAYER_HANDS`
  - toca `video9a` ou `video9b` conforme `FINAL_OUTCOME`

Na fase de cor:
- o sistema pausa novas leituras enquanto o video da cor estiver rodando
- ao terminar o video, volta automaticamente para `WAITING_COLOR`
- a mesma cor nao dispara novamente
- cada video de cor toca uma unica vez por execucao
- depois de consumir todas as cores configuradas, o fluxo segue para `video7`

## Requisitos

Ambiente recomendado:
- Linux Mint atual
- Python 3.11
- `python3.11-venv`
- VLC instalado no sistema

Dependencias Python:
- `numpy==1.26.4`
- `opencv-python==4.10.0.84`
- `mediapipe==0.10.9`
- `PySide6==6.7.2`
- `python-vlc==3.0.21203`
- `pyserial==3.5`

## Instalar no Linux Mint

### 1. Dependencias de sistema

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip vlc libxcb-cursor0
```

### 2. Clonar o projeto

```bash
git clone <URL_DO_REPOSITORIO>
cd vanCoco
```

### 3. Criar ambiente virtual

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 4. Instalar dependencias Python

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

## Midia esperada

Coloque os arquivos em `midia/` com estes nomes exatos:
- `video1.mp4`
- `video2.mp4`
- `video3.mp4`
- `video4.mp4`
- `video5.mp4`
- `video6_red.mp4`
- `video6_green.mp4`
- `video6_blue.mp4`
- `video7.mp4`
- `video8.mp4`
- `video9a.mp4`
- `video9b.mp4`

Se algum video nao existir, algumas fases usam mock curto para manter o fluxo, mas o ideal e ter todos os arquivos reais.

## Comunicacao dos robos

### macOS ou USB no Linux

Com os dois robos conectados por USB:

```bash
ls /dev/cu.*
```

Ou no Linux:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

Defina as portas antes de rodar, se quiser sobrescrever o `config.py`:

```bash
export COCOMAG_PORT=/dev/cu.usbserial-XXXX
export COCOVISION_PORT=/dev/cu.usbserial-YYYY
```

No Linux, os exemplos equivalentes costumam ser:

```bash
export COCOMAG_PORT=/dev/ttyUSB0
export COCOVISION_PORT=/dev/ttyUSB1
```

Se estiver em duvida sobre qual porta e de qual robo:
- conecte apenas um robo e rode `ls /dev/ttyUSB* /dev/ttyACM*`
- conecte o outro e rode de novo
- a nova porta que apareceu e do robo que acabou de ser conectado

### Bluetooth Classic no Linux via RFCOMM

O projeto nao usa socket Bluetooth direto no Python. No Linux, a ideia e bindar o robô como um device serial RFCOMM e deixar o `pyserial` tratar tudo como porta normal.

### Guia rapido de uso no Linux

#### 1. Clonar e instalar

```bash
git clone <URL_DO_REPOSITORIO>
cd vanCoco
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

#### 2. Escolher o modo de conexao

Voce pode usar:
- USB serial
- Bluetooth Classic via RFCOMM

Pode misturar os dois, por exemplo:
- `CocoMag` por RFCOMM
- `CocoVision` por USB

#### 3. Descobrir portas USB

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

#### 4. Descobrir o MAC Bluetooth do ESP32

Voce pode pegar o MAC:
- pelo log do proprio ESP32 no monitor serial
- ou pelo Linux depois de parear

Com `bluetoothctl`:

```bash
bluetoothctl
power on
scan on
```

Quando aparecer o dispositivo, anote o MAC, por exemplo:

```text
Device A8:42:E3:91:36:1A COCOMAG
```

Depois:

```text
scan off
pair A8:42:E3:91:36:1A
trust A8:42:E3:91:36:1A
connect A8:42:E3:91:36:1A
quit
```

#### 5. Criar o device RFCOMM

Exemplo para o `CocoMag`:

```bash
sudo rfcomm bind /dev/rfcomm0 A8:42:E3:91:36:1A 1
```

Se quiser ligar os dois por Bluetooth:

```bash
sudo rfcomm bind /dev/rfcomm0 XX:XX:XX:XX:XX:XX 1
sudo rfcomm bind /dev/rfcomm1 YY:YY:YY:YY:YY:YY 1
```

Validar:

```bash
ls -l /dev/rfcomm0 /dev/rfcomm1
```

Se precisar soltar antes de rebinder:

```bash
sudo rfcomm release /dev/rfcomm0
sudo rfcomm release /dev/rfcomm1
```

#### 6. Configurar o projeto

Opcao A: editar o `config.py`

Exemplo misto:

```python
COCOMAG_COMM_MODE = "rfcomm"
COCOMAG_PORT = "/dev/rfcomm0"

COCOVISION_COMM_MODE = "serial"
COCOVISION_PORT = "/dev/ttyUSB1"
```

Opcao B: sobrescrever por variavel de ambiente

```bash
export COCOMAG_PORT=/dev/rfcomm0
export COCOVISION_PORT=/dev/ttyUSB1
```

#### 7. Rodar

```bash
source .venv/bin/activate
python main.py
```

#### 8. Logs esperados

Exemplo:

```text
[RobotComm] COCOMAG conectado via rfcomm em /dev/rfcomm0
[RobotComm] COCOVISION conectado via serial em /dev/ttyUSB1
```

Se falhar, o app nao deve travar. Ele loga o erro e cai para mock naquele robo.

Exemplo:

```bash
sudo rfcomm bind /dev/rfcomm0 XX:XX:XX:XX:XX:XX 1
sudo rfcomm bind /dev/rfcomm1 YY:YY:YY:YY:YY:YY 1
```

Depois configure:

```python
COCOMAG_COMM_MODE = "rfcomm"
COCOMAG_PORT = "/dev/rfcomm0"

COCOVISION_COMM_MODE = "rfcomm"
COCOVISION_PORT = "/dev/rfcomm1"
```

## Como rodar

```bash
source .venv/bin/activate
python main.py
```

Ou em uma linha:

```bash
export COCOMAG_PORT=/dev/cu.usbserial-XXXX
export COCOVISION_PORT=/dev/cu.usbserial-YYYY
source .venv/bin/activate && python main.py
```

Exemplo Linux com `CocoMag` em RFCOMM e `CocoVision` em USB:

```bash
export COCOMAG_PORT=/dev/rfcomm0
export COCOVISION_PORT=/dev/ttyUSB1
source .venv/bin/activate && python main.py
```

## Controles

- `1` toca `video1`
- `2` toca `video2`
- `q` sai
- `Esc` sai

## Gestos usados

- `HAND_OPEN`
- `POINT`
- `V_SIGN`
- `THUMB_UP`
- `CLOSED_FIST`
- `DOUBLE_CLOSED_FIST` como fallback opcional do `video8`
- `PRAYER_HANDS` para disparar o video final

## Hardware atual

### CocoMag
- ESP32
- L298N
- 2 motores
- servo `SG90` no `D13`
- comunicacao por USB serial
- preparo para Bluetooth Classic no firmware

### CocoVision
- ESP32
- L298N
- sensor `TCS34725`
- I2C configurado explicitamente em:
  - `SDA = GPIO 21`
  - `SCL = GPIO 22`
- comunicacao por USB serial
- preparo para Bluetooth Classic no firmware

## Comportamento atual dos robos

### CocoMag
- `PRESENT`
  - frente `900 ms`
  - para `250 ms`
  - gira a direita `700 ms`
  - para `250 ms`
  - re `800 ms`
  - para `250 ms`
  - envia `COCOMAG_DONE`
- `ACTION`
  - frente `900 ms`
  - para `250 ms`
  - gira servo no `D13` para `90 graus`
  - espera `700 ms`
  - volta servo para `0 grau`
  - para `250 ms`
  - envia `COCOMAG_DONE`

### CocoVision
- `PRESENT`
  - frente `900 ms`
  - para `250 ms`
  - gira a direita `700 ms`
  - para `250 ms`
  - re `800 ms`
  - para `250 ms`
  - envia `COCOVISION_DONE`
- `ACTION`
  - frente `900 ms`
  - para `250 ms`
  - ativa leitura continua do sensor
  - envia `COCOVISION_DONE`
- `RETURN`
  - desativa leitura do sensor
  - re `900 ms`
  - para `250 ms`
  - envia `COCOVISION_DONE`
- leitura de cor
  - continua lendo o `TCS34725`
  - envia `COLOR_RED`, `COLOR_GREEN` ou `COLOR_BLUE`
  - usa debounce interno de `1200 ms`

## Estrutura principal

- `main.py`: loop principal
- `vision.py`: camera e classificacao de gestos
- `gesture_mapper.py`: conversao gesto -> acao
- `media_controller.py`: janela fullscreen e player embutido
- `state_manager.py`: estados operacionais do app
- `story_engine.py`: regras narrativas e transicoes
- `robot_comm.py`: comunicacao dos robos via USB serial ou RFCOMM tratado como serial
- `firmware/cocomag/cocomag.ino`: firmware do `CocoMag`
- `firmware/cocovision/cocovision.ino`: firmware do `CocoVision`

## Observacoes importantes

- OpenCV fica restrito a visao computacional.
- A camada de apresentacao usa `PySide6`.
- O video com audio roda via `python-vlc`.
- Durante video ou acao de robo, o sistema bloqueia novos inputs indevidos.
- A fase de cor permanece ouvindo `COLOR_*` ate consumir uma cor nova valida.
- No Linux, RFCOMM deve ser criado antes de rodar o app, para que o Python leia `/dev/rfcomm*` como serial normal.

## Solucao de problemas

### MediaPipe

```bash
python -m pip uninstall -y mediapipe
python -m pip install mediapipe==0.10.9
```

### Qt / plugin no Linux

```bash
sudo apt install -y libxcb-cursor0
```

### VLC

```bash
vlc --version
```

Se precisar:

```bash
sudo apt install -y vlc
```

### Porta serial ocupada

Se aparecer `Resource busy`, feche:
- Serial Monitor da Arduino IDE
- qualquer terminal com `screen`, `minicom` ou monitor serial

### RFCOMM nao criou `/dev/rfcomm0`

Verifique:
- se o dispositivo foi pareado no `bluetoothctl`
- se o MAC esta correto
- se o canal RFCOMM e `1`

Comandos uteis:

```bash
bluetoothctl devices
rfcomm
```

## GitHub

Antes de subir:
- nao versione `.venv/`
- nao versione `__pycache__/`
- confirme os videos em `midia/`
- mantenha este `README.md` atualizado junto com o fluxo real

Sugestao minima de `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
```
