# VanCoco

VanCoco e um sistema interativo para apresentacao/competicao OBR. A aplicacao
Python coordena a narrativa, le gestos pela camera, reproduz videos em tela
cheia, conversa com os robos CocoMag e CocoVision por Bluetooth/RFCOMM e aceita
um fallback central por USB.

Sistema alvo de operacao: Ubuntu 24.04 LTS.

## Visao Geral

O projeto combina software de palco, visao computacional e robos embarcados:

- `main.py`: ponto de entrada e orquestrador do loop principal.
- `vision.py`: captura da camera, MediaPipe Hands/Pose e ArUco.
- `gesture_mapper.py`: estabilizacao temporal dos gestos antes da narrativa.
- `story_engine.py`: regras narrativas, videos, comandos e respostas esperadas.
- `state_manager.py`: estado operacional do app.
- `media_controller.py`: janela fullscreen, tela preta, overlay e VLC/libVLC.
- `robot_comm.py`: comunicacao serial/RFCOMM com CocoMag, CocoVision e fallback.
- `firmware/cocomag/cocomag.ino`: firmware do CocoMag.
- `firmware/cocovision/cocovision.ino`: firmware do CocoVision.
- `firmware/centralfallback/centralfallback.ino`: gatilho central por USB.

O Python e o dono da narrativa. Os robos executam comandos e respondem eventos;
eles nao decidem o fluxo completo da apresentacao.

## Arquitetura

### Python/main app

`main.py` inicializa camera, player, narrativa e comunicacao com os robos. Em
cada ciclo ele atualiza a UI, le entradas, aplica a state machine e executa os
efeitos: tocar video, enviar comando ou aguardar retorno.

### Visao computacional

`vision.py` usa OpenCV e MediaPipe para produzir sinais de alto nivel:

- gestos de uma mao;
- `DOUBLE_CLOSED_FIST`;
- `PRAYER_HANDS` por pose;
- marker ArUco para a etapa do video 8.

A visao so roda os detectores necessarios para o estado atual. O debounce e o
latch ficam em `gesture_mapper.py`.

### VLC/midia

`media_controller.py` cria uma janela fullscreen com PySide6 e acopla um player
VLC persistente ao widget nativo. Os videos esperados ficam em `midia/`:

```text
video1.mp4
video2.mp4
video3.mp4
video4.mp4
video5.mp4
video6.mp4
video7.mp4
video8.mp4
video9a.mp4
video9b.mp4
```

### Overlay operacional

O overlay existe para operacao e debug durante ensaio/competicao:

- `CAMERA_AND_LOGS`: estados que esperam gesto ou marker; mostra preview e logs.
- `LOGS_ONLY`: estados que esperam robos, cor ou retorno; sem preview de camera.
- `HIDDEN`: durante reproducao de video; video fica limpo para apresentacao.

### Fallback central

O fallback central e um Arduino Nano via USB. Ele envia a linha
`CENTRAL_FALLBACK_TRIGGER`; o Python interpreta esse pulso de acordo com o estado
atual e injeta o proximo evento esperado. O fallback nao pula a state machine.

### CocoMag

CocoMag e um ESP32 com motores, servo e MPU. Ele recebe comandos textuais,
executa rotinas fisicas e responde `COCOMAG_DONE`. O servo e parte da rotina
fisica do CocoMag, principalmente na acao.

### CocoVision

CocoVision e um ESP32 com motores, MPU e sensor de cor. Ele recebe comandos,
executa movimentos, entra na fase de leitura de cor e envia `COCOVISION_DONE`
ou eventos `COLOR_*`.

## Como Rodar No Ubuntu

### 1. Instalar dependencias do sistema

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip vlc libvlc-bin libxcb-cursor0 bluez v4l-utils
sudo usermod -aG dialout $USER
```

Depois de adicionar o usuario ao grupo `dialout`, faca logout/login antes de
usar portas seriais sem `sudo`.

### 2. Baixar o projeto

```bash
git clone <URL_DO_REPOSITORIO>
cd vanCoco
```

### 3. Criar ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

### 4. Criar portas RFCOMM

Pareie os ESP32 uma vez com `bluetoothctl`. Depois, em cada sessao de
apresentacao:

```bash
bluetoothctl devices Paired
sudo rfcomm release /dev/rfcomm0
sudo rfcomm release /dev/rfcomm1
sudo rfcomm bind /dev/rfcomm0 <MAC_COCOMAG> 1
sudo rfcomm bind /dev/rfcomm1 <MAC_COCOVISION> 1
ls -l /dev/rfcomm0 /dev/rfcomm1
```

Padrao recomendado:

- CocoMag: `/dev/rfcomm0`
- CocoVision: `/dev/rfcomm1`

### 5. Configurar fallback central

Conecte o Arduino Nano por USB e identifique a porta:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
dmesg | tail -n 30
```

### 6. Rodar

```bash
source .venv/bin/activate
export COCOMAG_PORT=/dev/rfcomm0
export COCOVISION_PORT=/dev/rfcomm1
export CENTRAL_FALLBACK_PORT=/dev/ttyUSB0
python3 main.py
```

Use `q` ou `Esc` para sair.

## Dependencias Principais

Python:

- `opencv-python`
- `mediapipe`
- `PySide6`
- `python-vlc`
- `pyserial`
- `numpy`

Sistema:

- VLC/libVLC;
- webcam compativel com OpenCV/V4L2;
- Bluetooth funcional no Ubuntu;
- acesso a portas seriais (`dialout`);
- ESP32 pareados para CocoMag e CocoVision;
- Arduino Nano USB para fallback central.

## Bluetooth/RFCOMM

### Pareamento

```bash
bluetoothctl
power on
agent on
default-agent
scan on
pair <MAC_DO_ESP32>
trust <MAC_DO_ESP32>
connect <MAC_DO_ESP32>
quit
```

Repita para CocoMag e CocoVision.

### Teste isolado

Com as portas criadas:

```bash
source .venv/bin/activate
python3 rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:PRESENT
python3 rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:ACTION
python3 rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:PRESENT
python3 rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:ACTION --listen-seconds 8
python3 rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:RETURN
```

Veja tambem [BLUETOOTH_RFCOMM_GUIDE.md](BLUETOOTH_RFCOMM_GUIDE.md).

## Fluxo Da Apresentacao

| Etapa | Entrada esperada | Video | Comando enviado | Resposta esperada |
| --- | --- | --- | --- | --- |
| Inicio | `HAND_OPEN` | `video1.mp4` | - | fim do video |
| Segundo gesto | `POINT` | `video2.mp4` | - | fim do video |
| Apresentacao dos robos | fim do `video2` | - | `COCOMAG:PRESENT`, `COCOVISION:PRESENT` | `COCOMAG_DONE`, `COCOVISION_DONE` |
| Pos-apresentacao | ambos `DONE` | `video3.mp4` | - | fim do video |
| Acao CocoMag | `V_SIGN` | - | `COCOMAG:ACTION` | `COCOMAG_DONE` |
| Pos-CocoMag | `COCOMAG_DONE` | `video4.mp4` | - | fim do video |
| Video 5 | `THUMB_UP` | `video5.mp4` | - | fim do video |
| Video 6 | `CLOSED_FIST` | `video6.mp4` | - | fim do video |
| Acao CocoVision | fim do `video6` | - | `COCOVISION:ACTION` | `COCOVISION_DONE` |
| Cor | `COLOR_BLUE` | `video7.mp4` | opcional `COCOVISION:COLOR_CONFIRMED` em fallback | fim do video |
| Retorno CocoVision | fim do `video7` | - | `COCOVISION:RETURN` | `COCOVISION_DONE` |
| Video 8 | ArUco/lupa ou `DOUBLE_CLOSED_FIST` | `video8.mp4` | - | fim do video |
| Final | `PRAYER_HANDS` | `video9a.mp4` ou `video9b.mp4` | - | fim do video |

O video final e escolhido por `FINAL_OUTCOME` em `config.py`.

## Gestos

- `HAND_OPEN`: mao aberta para iniciar o primeiro video.
- `POINT`: indicador levantado para o segundo video.
- `V_SIGN`: sinal de vitoria para liberar a acao do CocoMag.
- `THUMB_UP`: polegar para disparar o video 5.
- `CLOSED_FIST`: punho fechado para disparar o video 6.
- `DOUBLE_CLOSED_FIST`: dois punhos como alternativa ao marker na etapa do video 8.
- `PRAYER_HANDS`: maos em oracao para disparar o final.

Os gestos passam por estabilizacao temporal. Se um gesto falhar, mantenha a mao
parada por alguns frames e confira o overlay antes de mudar thresholds.

## Firmware

### Comandos comuns

- `PRESENT`: rotina de apresentacao do robo.
- `ACTION`: rotina principal de acao.
- `RESET`: retorna o robo para estado seguro/esperado quando suportado.

### CocoMag

O CocoMag executa `PRESENT` e `ACTION`, usa MPU para giros e aciona o servo na
rotina mecanica. A resposta principal para o Python e `COCOMAG_DONE`.

Se o servo espasmar, priorize checagem fisica: alimentacao, GND comum, cabo,
fixacao mecanica e estado de reset antes de alterar software.

### CocoVision

O CocoVision executa `PRESENT`, `ACTION` e `RETURN`, usa MPU para giros e sensor
TCS34725 para cor. Respostas principais:

- `COCOVISION_DONE`
- `COCOVISION_COLOR=COLOR_*`
- `COLOR_RED`, `COLOR_GREEN`, `COLOR_BLUE`

O Python usa `COLOR_BLUE` no fluxo atual.

## Troubleshooting

### Robo ausente

- Confira bateria e chave geral.
- Confira se o ESP32 esta pareado e confiavel (`trust`) no Ubuntu.
- Recrie o bind RFCOMM.
- Confira `COCOMAG_PORT` e `COCOVISION_PORT`.
- Rode `rfcomm_serial_probe.py` antes da apresentacao completa.

### Gesto nao reconhecido

- Confira se a camera abriu e se o overlay mostra a mao.
- Mantenha a mao dentro da ROI.
- Evite movimentos rapidos; o gesto precisa ficar estavel.
- Para `POINT` frontal, pequenos angulos da mao podem melhorar os landmarks.
- Nao ajuste thresholds durante competicao sem teste rapido dos outros gestos.

### Video engasgando

- Confirme que VLC/libVLC esta instalado.
- Feche apps pesados antes da apresentacao.
- Prefira rodar em tomada, nao bateria em modo economia.
- O player e persistente, mas cada inicio de video ainda troca midia e processa UI.
- Se o engasgo for leve e previsivel, evite mudar VLC antes da apresentacao.

### VLC logs

Logs como `VLC_MEDIA_SET`, `VLC_PLAY_START` e `VLC_STOP_NO_RELEASE` ajudam a
confirmar que o player recebeu a midia. Se VLC nao abrir, valide:

```bash
vlc --version
source .venv/bin/activate
python3 -c "import vlc; print(vlc.__version__)"
```

### Bluetooth

```bash
bluetoothctl devices Paired
bluetoothctl info <MAC_DO_ESP32>
sudo rfcomm release /dev/rfcomm0
sudo rfcomm bind /dev/rfcomm0 <MAC_DO_ESP32> 1
ls -l /dev/rfcomm0
```

Se a porta ficou presa, desligue o robo, libere a porta, ligue novamente e faca
novo bind.

### Servo espasmando

- Verifique alimentacao separada/adequada para servo.
- Confirme GND comum.
- Verifique conector, cabo e interferencia mecanica.
- Rode `RESET` antes de repetir a rotina.
- Evite diagnosticar servo apenas pelo app; teste o firmware/robo isolado.

### Fallback central

- Confirme a porta com `ls -l /dev/ttyUSB* /dev/ttyACM*`.
- Confirme `CENTRAL_FALLBACK_PORT`.
- O sinal esperado e `CENTRAL_FALLBACK_TRIGGER`.
- O fallback injeta o evento esperado do estado atual; se usado fora de hora, pode ser rejeitado.

## Git E Release

- `main`: linha principal.
- `main-recovery`: branch de recuperacao conhecida no repositorio.
- `obr-stable-v1`: tag estavel existente para marco de competicao.
- `v1.1`: usar como tag de evolucao somente depois de validar em hardware.

Regra pratica de branch:

- uma branch por mudanca;
- prefixo recomendado: `chore/`, `fix/`, `docs/` ou `codex/`;
- nao misturar firmware, visao e docs na mesma branch;
- criar tag apenas depois de teste completo do fluxo.

## Documentacao Detalhada

- [PROJECT_DETAILS.md](PROJECT_DETAILS.md)
- [BLUETOOTH_RFCOMM_GUIDE.md](BLUETOOTH_RFCOMM_GUIDE.md)
- [docs/config.md](docs/config.md)
- [docs/main.md](docs/main.md)
- [docs/story_engine.md](docs/story_engine.md)
- [docs/state_manager.md](docs/state_manager.md)
- [docs/vision.md](docs/vision.md)
- [docs/gesture_mapper.md](docs/gesture_mapper.md)
- [docs/media_controller.md](docs/media_controller.md)
- [docs/robot_comm.md](docs/robot_comm.md)
- [docs/cocomag.ino.md](docs/cocomag.ino.md)
- [docs/cocovision.ino.md](docs/cocovision.ino.md)
- [docs/cocovision_serial_reader.md](docs/cocovision_serial_reader.md)
- [docs/study_order.md](docs/study_order.md)
