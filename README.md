# VanCoco

Aplicacao interativa minima em Python para o fluxo:

`tela preta -> gesto -> video -> tela preta`

Escopo atual:
- camera ativa em background
- deteccao de gestos simples com MediaPipe Hands
- reproducao de video com audio embutido na janela principal
- retorno automatico para tela preta ao fim do video
- atalhos de teclado para teste

## Requisitos

Ambiente recomendado no Linux Mint:
- Linux Mint atual
- Python 3.11
- `python3.11-venv`
- VLC instalado no sistema

Dependencias Python usadas pelo projeto:
- `opencv-python`
- `mediapipe==0.10.9`
- `PySide6`
- `python-vlc`
- `numpy`

## Instalar no Linux Mint

### 1. Instalar dependencias de sistema

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip vlc libxcb-cursor0
```

Observacao:
- `vlc` e necessario para o backend de video/audio
- `libxcb-cursor0` costuma ser util para evitar problemas de plugins Qt em algumas instalacoes Linux

### 2. Clonar o projeto

```bash
git clone <URL_DO_REPOSITORIO>
cd vanCoco
```

### 3. Criar e ativar ambiente virtual

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 4. Instalar dependencias Python

```bash
python -m pip install --upgrade pip
python -m pip install opencv-python mediapipe==0.10.9 PySide6 python-vlc numpy
```

## Como rodar

Com o ambiente virtual ativado:

```bash
python main.py
```

## Controles

- `1` reproduz `midia/video1.mp4`
- `2` reproduz `midia/video2.mp4`
- `q` sai da aplicacao
- `Esc` sai da aplicacao

## Estrutura atual

- `main.py`: loop principal da aplicacao
- `vision.py`: camera e deteccao de gestos
- `gesture_mapper.py`: mapeamento gesto -> acao
- `media_controller.py`: janela principal fullscreen e player embutido
- `state_manager.py`: estados e bloqueios de reproducao
- `config.py`: configuracoes e mapeamentos

## Observacoes importantes

- O projeto usa OpenCV apenas para visao computacional.
- A camada de apresentacao usa `PySide6`.
- A reproducao de video usa `python-vlc` embutido na janela principal.
- Cada video toca apenas uma vez por execucao da aplicacao.
- Durante a reproducao, novos gestos ficam bloqueados.

## Solucao de problemas

### MediaPipe com erro de API

Se aparecer erro relacionado a `mediapipe.solutions`, reinstale a versao compativel:

```bash
python -m pip uninstall -y mediapipe
python -m pip install mediapipe==0.10.9
```

### VLC nao encontrado

Verifique se o VLC esta instalado:

```bash
vlc --version
```

Se nao estiver:

```bash
sudo apt install -y vlc
```

### Erro de plugin Qt no Linux

Se houver erro visual ou de inicializacao do Qt, tente:

```bash
sudo apt install -y libxcb-cursor0
```

## Publicacao no GitHub

Antes de subir:
- confirme que a pasta `midia/` esta com os arquivos esperados
- confirme que o `.venv/` nao esta versionado
- inclua este `README.md`

Sugestao de `.gitignore` minima:

```gitignore
.venv/
__pycache__/
*.pyc
```

## Manutencao do README

Este README foi escrito para refletir o estado atual do projeto no branch atual.
Quando mudarmos dependencias, backend de video ou fluxo de execucao, o ideal e atualizar este arquivo no mesmo commit da mudanca.
