# VanCoco

Guia rapido de execucao no Linux.

Documentacao completa:
- [PROJECT_DETAILS.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/PROJECT_DETAILS.md)
- [BLUETOOTH_RFCOMM_GUIDE.md](/Users/nicolaskraide/Documents/EU/CreatorKraide/www/project%20spell/vanCoco/BLUETOOTH_RFCOMM_GUIDE.md)

## Pre-requisitos

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip vlc libxcb-cursor0
```
## Status do projeto

Atualmente, o projeto possui branches diferentes para cada ambiente de execução.

### Branches
- `main` → versão base / macOS (**inativa no momento**)
- `linux-tests` → versão atual mais estável para **Linux**
- `windows-port` → versão em adaptação para **Windows** (usar apenas quando estiver pronta)

### Qual branch usar?
- **Linux:** usar `linux-tests`
- **macOS:** `main` (somente se necessário)
- **Windows:** `windows-port` (quando disponível/estável)

### Como clonar e entrar na branch correta

#### Linux
```bash
git clone <URL_DO_REPOSITORIO>
cd VanCoco01
git checkout linux-tests
```
#### MacOS
```bash
git clone <URL_DO_REPOSITORIO>
cd VanCoco01
git checkout main
```

#### Windows (pré-requisitos)

- Instalar VLC:
  https://images.videolan.org/vlc/index.pt_BR.html

```bash
git clone <URL>
cd VanCoco01
git checkout windows-port

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Para instruções completas de setup no Windows, veja:
docs/windows-setup.md


## Instalar dependências (após estar na branch escolhida [linux/macOS]= usar comandos acima)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

## Midia esperada

Arquivos em `midia/`:

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

## Rodar por Bluetooth RFCOMM

```bash
sudo rfcomm bind /dev/rfcomm0 XX:XX:XX:XX:XX:XX 1 //ignorar isso 
sudo rfcomm bind /dev/rfcomm1 YY:YY:YY:YY:YY:YY 1 //ignorar isso
export COCOMAG_PORT=/dev/rfcomm0    // alterar isso conforme a ordem da conexão com o bluetooth -> se for primeiro = 0, senão = 1
export COCOVISION_PORT=/dev/rfcomm1
source .venv/bin/activate && python main.py
```

## Testar comandos isolados

```bash
source .venv/bin/activate
python rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:PRESENT
python rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:ACTION
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:PRESENT
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:ACTION --listen-seconds 8
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:RETURN
```

## Rodar por USB

```bash
export COCOMAG_PORT=/dev/ttyUSB0
export COCOVISION_PORT=/dev/ttyUSB1
source .venv/bin/activate && python main.py
```