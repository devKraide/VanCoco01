# Apresentacao Rapida

Use este roteiro quando o VSCode ja estiver aberto no projeto.

## 1. Atualizar projeto

```bash
git pull
```

## 2. Ativar venv

```bash
source .venv/bin/activate
```

## 3. Recriar conexoes dos robos

```bash
sudo rfcomm release /dev/rfcomm0
sudo rfcomm release /dev/rfcomm1

sudo rfcomm bind /dev/rfcomm0 08:A6:F7:BC:35:6E 1
sudo rfcomm bind /dev/rfcomm1 3C:E9:0E:8C:02:EE 1

export COCOMAG_PORT=/dev/rfcomm0
export COCOVISION_PORT=/dev/rfcomm1
export CENTRAL_FALLBACK_PORT=/dev/ttyUSB0
```

## 4. Rodar

```bash
python3 main.py
```

Para sair: `q` ou `Esc`.
