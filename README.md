# VanCoco

VanCoco e um sistema interativo para apresentacao OBR. O Python controla a
narrativa, detecta gestos pela camera, toca videos e conversa com os robos por
Bluetooth/serial.

Componentes principais:

- Python
- OpenCV/MediaPipe
- VLC/libVLC e PySide6
- Bluetooth/Serial
- ESP32 CocoMag e CocoVision
- Arduino Nano como fallback central por USB

Sistema alvo oficial: Ubuntu 24.04 LTS.

## Requisitos

- Ubuntu 24.04 LTS
- Python 3
- Git
- VLC/libVLC
- Camera ou webcam
- Bluetooth funcionando no PC
- ESP32 CocoMag e CocoVision pareados
- Arduino Nano conectado via USB para fallback central

## Dependencias Ubuntu

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip vlc libvlc-bin libxcb-cursor0 bluez v4l-utils
sudo usermod -aG dialout $USER
```

Depois de adicionar o usuario ao grupo `dialout`, faca logout/login antes de
usar portas seriais sem `sudo`.

## Baixar o projeto

```bash
git clone <URL_DO_REPOSITORIO>
cd vanCoco
```

## Criar ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

## Midia esperada

Os videos devem ficar em `midia/`:

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

## Conectar robos por Bluetooth

Os ESP32 precisam estar pareados no Ubuntu antes de criar as portas RFCOMM.

### Parear uma vez

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

### Criar portas RFCOMM

Use este roteiro sempre que ligar o PC/robos e for rodar a apresentacao.

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

Se `rfcomm release` disser que a porta nao existe, pode ignorar.

Configure as portas para o Python:

```bash
export COCOMAG_PORT=/dev/rfcomm0
export COCOVISION_PORT=/dev/rfcomm1
```

Se algum robo estiver ligado por USB serial, use a porta correspondente, por
exemplo `/dev/ttyUSB0` ou `/dev/ttyACM0`.

## Conectar Arduino Nano central

Conecte o Arduino Nano por USB e identifique a porta:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
dmesg | tail -n 30
```

Configure a porta do fallback central:

```bash
export CENTRAL_FALLBACK_PORT=/dev/ttyUSB0
```

O Nano envia a linha `CENTRAL_FALLBACK_TRIGGER`. O Python interpreta esse sinal
na state machine e injeta o evento esperado naquele momento da narrativa.

## Configuracao

As configuracoes principais ficam em `config.py`.

Ajuste ali quando necessario:

- camera (`CAMERA_INDEX` e parametros de captura)
- portas dos robos (`COCOMAG_PORT`, `COCOVISION_PORT`)
- porta do fallback central (`CENTRAL_FALLBACK_PORT`)
- caminhos dos videos em `midia/`
- logs, debug e modo de apresentacao

As variaveis de ambiente `COCOMAG_PORT`, `COCOVISION_PORT` e
`CENTRAL_FALLBACK_PORT` podem ser usadas para sobrescrever as portas sem editar
o arquivo.

## Como rodar

```bash
source .venv/bin/activate
export COCOMAG_PORT=/dev/rfcomm0
export COCOVISION_PORT=/dev/rfcomm1
export CENTRAL_FALLBACK_PORT=/dev/ttyUSB0
python main.py
```

Logs esperados quando Bluetooth e serial estiverem funcionando:

```text
[RobotComm] COCOMAG conectado via rfcomm em /dev/rfcomm0
[RobotComm] COCOVISION conectado via rfcomm em /dev/rfcomm1
```

## Fluxo esperado

1. A camera detecta gestos com OpenCV/MediaPipe.
2. O Python controla a state machine da narrativa.
3. A state machine toca videos e envia comandos aos robos.
4. CocoMag e CocoVision respondem com eventos reais.
5. Fallbacks entram apenas quando necessario.

Nenhum video deve tocar fora da state machine.

## Fallbacks

- Fallback central USB: o Arduino Nano envia `CENTRAL_FALLBACK_TRIGGER`; o
  Python decide qual evento esperado deve ser injetado.
- Ultrassonico local dos robos: executa a proxima acao permitida pela state
  machine local de cada robo.
- O fallback nao decide a narrativa. A state machine decide tudo.

## Testar comandos isolados

Com as portas RFCOMM criadas:

```bash
source .venv/bin/activate
python rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:PRESENT
python rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:ACTION
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:PRESENT
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:ACTION --listen-seconds 8
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:RETURN
```

## Troubleshooting

### Camera nao abre

```bash
v4l2-ctl --list-devices
```

Confirme a webcam e ajuste `CAMERA_INDEX` em `config.py`.

### VLC/libVLC nao encontrado

```bash
sudo apt install -y vlc libvlc-bin
source .venv/bin/activate
python -c "import vlc; print(vlc.__version__)"
```

### Bluetooth nao conecta

```bash
bluetoothctl devices Paired
bluetoothctl info <MAC_DO_ESP32>
sudo rfcomm release /dev/rfcomm0
sudo rfcomm bind /dev/rfcomm0 <MAC_DO_ESP32> 1
ls -l /dev/rfcomm0
```

Confirme que o ESP32 esta ligado, pareado, confiavel (`trust`) e usando o MAC
correto.

### Porta serial sem permissao

```bash
groups
sudo usermod -aG dialout $USER
```

Faca logout/login e tente novamente.

### Robo nao responde

- Confira bateria/alimentacao do robo.
- Confira se a porta `COCOMAG_PORT` ou `COCOVISION_PORT` aponta para o robo certo.
- Teste com `rfcomm_serial_probe.py`.
- Reinicie o bind RFCOMM se a conexao ficou presa.

### Arduino Nano nao aparece

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
dmesg | tail -n 30
```

Use cabo USB com dados, confira a porta em `CENTRAL_FALLBACK_PORT` e valide se o
Nano esta enviando `CENTRAL_FALLBACK_TRIGGER`.

## Documentacao detalhada

- [PROJECT_DETAILS.md](PROJECT_DETAILS.md)
- [BLUETOOTH_RFCOMM_GUIDE.md](BLUETOOTH_RFCOMM_GUIDE.md)
- [docs/config.md](docs/config.md)
- [docs/main.md](docs/main.md)
- [docs/robot_comm.md](docs/robot_comm.md)
- [docs/state_manager.md](docs/state_manager.md)
- [docs/story_engine.md](docs/story_engine.md)
- [docs/vision.md](docs/vision.md)
- [docs/cocomag.ino.md](docs/cocomag.ino.md)
- [docs/cocovision.ino.md](docs/cocovision.ino.md)
