# VanCoco

Aplicacao interativa em Python para apresentacao teatral com:
- visao computacional via camera
- tela principal fullscreen preta
- videos com audio embutidos
- integracao serial com `CocoMag` e `CocoVision`

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

Na fase de cor:
- o sistema pausa novas leituras enquanto o video da cor estiver rodando
- ao terminar o video, volta automaticamente para `WAITING_COLOR`
- a mesma cor nao dispara novamente
- cada video de cor toca uma unica vez por execucao

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

Se algum video nao existir, algumas fases usam mock curto para manter o fluxo, mas o ideal e ter todos os arquivos reais.

## Portas seriais

Com os dois robos conectados:

```bash
ls /dev/cu.*
```

Defina as portas antes de rodar:

```bash
export COCOMAG_SERIAL_PORT=/dev/cu.usbserial-XXXX
export COCOVISION_SERIAL_PORT=/dev/cu.usbserial-YYYY
```

## Como rodar

```bash
source .venv/bin/activate
python main.py
```

Ou em uma linha:

```bash
export COCOMAG_SERIAL_PORT=/dev/cu.usbserial-XXXX
export COCOVISION_SERIAL_PORT=/dev/cu.usbserial-YYYY
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

## Hardware atual

### CocoMag
- ESP32
- L298N
- 2 motores
- servo `SG90` no `D13`
- comunicacao via USB Serial

### CocoVision
- ESP32
- L298N
- sensor `TCS34725`
- I2C configurado explicitamente em:
  - `SDA = GPIO 21`
  - `SCL = GPIO 22`
- comunicacao via USB Serial

## Estrutura principal

- `main.py`: loop principal
- `vision.py`: camera e classificacao de gestos
- `gesture_mapper.py`: conversao gesto -> acao
- `media_controller.py`: janela fullscreen e player embutido
- `state_manager.py`: estados operacionais do app
- `story_engine.py`: regras narrativas e transicoes
- `robot_comm.py`: serial do `CocoMag` e `CocoVision`
- `firmware/cocomag/cocomag.ino`: firmware do `CocoMag`
- `firmware/cocovision/cocovision.ino`: firmware do `CocoVision`

## Observacoes importantes

- OpenCV fica restrito a visao computacional.
- A camada de apresentacao usa `PySide6`.
- O video com audio roda via `python-vlc`.
- Durante video ou acao de robo, o sistema bloqueia novos inputs indevidos.
- A fase de cor permanece ouvindo `COLOR_*` ate consumir uma cor nova valida.

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
