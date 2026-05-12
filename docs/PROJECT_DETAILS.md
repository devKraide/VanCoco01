# VanCoco - Documentacao Detalhada

## Visao geral

O projeto e uma aplicacao interativa para apresentacao teatral com:
- visao computacional por camera
- reproducao de videos em tela preta fullscreen
- dois robos ESP32 (`CocoMag` e `CocoVision`)
- integracao por USB serial ou Bluetooth RFCOMM no Linux

O fluxo narrativo atual e:
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
- apenas `COLOR_BLUE` -> `video6.mp4`
- outras cores sao ignoradas pelo app
- depois de `video6.mp4`:
  - espera `CLOSED_FIST`
  - envia `COCOVISION:RETURN`
  - espera `COCOVISION_DONE`
  - toca `video7`
- depois entra em espera de `video8`
  - gatilho principal: ArUco marker
  - fallback opcional: `DOUBLE_CLOSED_FIST`
- depois entra em espera do final
  - espera `PRAYER_HANDS`
  - toca `video9a` ou `video9b` conforme `FINAL_OUTCOME`

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

## Comunicacao dos robos

### USB serial

Com os dois robos conectados por USB:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

Exemplo:

```bash
export COCOMAG_PORT=/dev/ttyUSB0
export COCOVISION_PORT=/dev/ttyUSB1
```

### Bluetooth RFCOMM no Linux

O projeto nao usa socket Bluetooth direto no Python. O bind RFCOMM transforma o robo em um device serial normal para o `pyserial`.

Descobrir o MAC:

```bash
bluetoothctl
power on
scan on
```

Parear e conectar:

```text
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
quit
```

Criar os devices:

```bash
sudo rfcomm bind /dev/rfcomm0 XX:XX:XX:XX:XX:XX 1
sudo rfcomm bind /dev/rfcomm1 YY:YY:YY:YY:YY:YY 1
ls -l /dev/rfcomm0 /dev/rfcomm1
```

Soltar binds antigos:

```bash
sudo rfcomm release /dev/rfcomm0
sudo rfcomm release /dev/rfcomm1
```

## Como rodar

```bash
source .venv/bin/activate
python main.py
```

Exemplo misto:

```bash
export COCOMAG_PORT=/dev/rfcomm0
export COCOVISION_PORT=/dev/ttyUSB1
source .venv/bin/activate && python main.py
```

Logs esperados:

```text
[RobotComm] COCOMAG conectado via rfcomm em /dev/rfcomm0
[RobotComm] COCOVISION conectado via serial em /dev/ttyUSB1
```

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
- `MPU6050`
- comunicacao por USB serial
- preparo para Bluetooth Classic no firmware

### CocoVision
- ESP32
- L298N
- `TCS34725`
- `MPU6050`
- I2C configurado explicitamente em:
  - `SDA = GPIO 21`
  - `SCL = GPIO 22`
- comunicacao por USB serial
- preparo para Bluetooth Classic no firmware

## Comportamento atual dos robos

### CocoMag
- `PRESENT`
  - frente `2000 ms`
  - para com desaceleracao curta
  - gira `~360 graus` usando `MPU6050`
  - para com desaceleracao curta
  - re `1500 ms`
  - para `250 ms`
  - envia `COCOMAG_DONE`
- `ACTION`
  - frente `3000 ms`
  - para com desaceleracao curta
  - gira `90 graus` usando `MPU6050`
  - para `250 ms`
  - frente `1000 ms`
  - para com desaceleracao curta
  - envia `COCOMAG_DONE`

### CocoVision
- `PRESENT`
  - frente `2000 ms`
  - para com desaceleracao curta
  - gira `~360 graus` usando `MPU6050`
  - para `250 ms`
  - re `1500 ms`
  - para com desaceleracao curta
  - envia `COCOVISION_DONE`
- `ACTION`
  - frente `1500 ms`
  - para com desaceleracao curta
  - ativa leitura continua do sensor
  - envia `COCOVISION_DONE`
- `RETURN`
  - desativa leitura do sensor
  - re `1500 ms`
  - para com desaceleracao curta
  - envia `COCOVISION_DONE`
- leitura de cor
  - continua lendo o `TCS34725`
  - envia `COLOR_RED`, `COLOR_GREEN` ou `COLOR_BLUE`
  - o app Python so reage a `COLOR_BLUE`
  - usa debounce interno de `1200 ms`

## Estrutura principal

- `main.py`: loop principal
- `vision.py`: camera e classificacao de gestos
- `gesture_mapper.py`: estabilidade de gesto
- `media_controller.py`: janela fullscreen e player embutido
- `state_manager.py`: estados operacionais do app
- `story_engine.py`: regras narrativas e transicoes
- `robot_comm.py`: comunicacao dos robos via USB serial ou RFCOMM
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

### Qt no Linux

```bash
sudo apt install -y libxcb-cursor0
```

### VLC

```bash
vlc --version
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

## Arquivos de apoio

- [BLUETOOTH_RFCOMM_GUIDE.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/BLUETOOTH_RFCOMM_GUIDE.md)
- [docs/main.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/docs/main.md)
- [docs/story_engine.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/docs/story_engine.md)
- [docs/vision.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/docs/vision.md)
- [docs/robot_comm.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/docs/robot_comm.md)
- [docs/cocomag.ino.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/docs/cocomag.ino.md)
- [docs/cocovision.ino.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/docs/cocovision.ino.md)
