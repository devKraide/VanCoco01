# Guia de Bluetooth RFCOMM

Este guia explica como operar `CocoMag` e `CocoVision` via Bluetooth Classic no Linux usando dispositivos RFCOMM como:

- `/dev/rfcomm0`
- `/dev/rfcomm1`

O projeto trata esses devices como portas serial normais via `pyserial`.

## Visao geral

No Linux, o fluxo operacional recomendado e:

1. parear cada ESP32
2. descobrir o MAC de cada robô
3. bindar cada robô em um `/dev/rfcommX`
4. apontar o projeto para essas portas
5. rodar o app normalmente

## Descobrir o MAC Bluetooth dos robos

Voce pode descobrir o MAC:

- pelo monitor serial do ESP32
- ou pelo `bluetoothctl`

Exemplo com `bluetoothctl`:

```bash
bluetoothctl
power on
scan on
```

Quando aparecer algo assim:

```text
Device A8:42:E3:91:36:1A COCOMAG
Device B4:E6:2D:12:34:56 COCOVISION
```

anote os MACs.

Depois:

```text
scan off
pair A8:42:E3:91:36:1A
trust A8:42:E3:91:36:1A
connect A8:42:E3:91:36:1A

pair B4:E6:2D:12:34:56
trust B4:E6:2D:12:34:56
connect B4:E6:2D:12:34:56

quit
```

## Criar os devices RFCOMM

### Exemplo padrao

Se quiser usar:

- `CocoMag -> /dev/rfcomm0`
- `CocoVision -> /dev/rfcomm1`

rode:

```bash
sudo rfcomm bind /dev/rfcomm0 A8:42:E3:91:36:1A 1
sudo rfcomm bind /dev/rfcomm1 B4:E6:2D:12:34:56 1
```

## Como trocar quem vira `rfcomm0` e `rfcomm1`

Voce pode escolher qualquer mapeamento.

Exemplo invertido:

- `CocoVision -> /dev/rfcomm0`
- `CocoMag -> /dev/rfcomm1`

```bash
sudo rfcomm bind /dev/rfcomm0 B4:E6:2D:12:34:56 1
sudo rfcomm bind /dev/rfcomm1 A8:42:E3:91:36:1A 1
```

O numero `0` ou `1` nao tem significado fixo. O que importa e manter consistencia entre:

- o bind feito no Linux
- e as variaveis/portas usadas ao rodar o projeto

## Liberar um device RFCOMM

Se quiser trocar o bind ou refazer a conexao:

```bash
sudo rfcomm release /dev/rfcomm0
sudo rfcomm release /dev/rfcomm1
```

Depois, refaca o `bind`.

## Validar se os devices existem

```bash
ls -l /dev/rfcomm0 /dev/rfcomm1
```

Se um deles nao existir, o bind nao foi criado corretamente.

## Rodar o projeto com Bluetooth RFCOMM

Com:

- `CocoMag -> /dev/rfcomm0`
- `CocoVision -> /dev/rfcomm1`

rode:

```bash
export COCOMAG_PORT=/dev/rfcomm0
export COCOVISION_PORT=/dev/rfcomm1
source .venv/bin/activate && python main.py
```

## Rodar com mapeamento invertido

Se voce decidiu:

- `CocoVision -> /dev/rfcomm0`
- `CocoMag -> /dev/rfcomm1`

rode:

```bash
export COCOMAG_PORT=/dev/rfcomm1
export COCOVISION_PORT=/dev/rfcomm0
source .venv/bin/activate && python main.py
```

## Logs esperados

Quando tudo estiver certo, o app deve mostrar algo parecido com:

```text
[RobotComm] COCOMAG conectado via rfcomm em /dev/rfcomm0
[RobotComm] COCOVISION conectado via rfcomm em /dev/rfcomm1
```

E, quando um comando for enviado:

```text
[RobotComm] Enviando para COCOMAG: COCOMAG:PRESENT
```

## Teste isolado com `rfcomm_serial_probe.py`

O script `rfcomm_serial_probe.py` serve para testar transporte e firmware sem depender do resto do projeto.

Ele:

- abre uma porta serial ou RFCOMM
- envia um comando textual com newline
- escuta a resposta por alguns segundos

## Uso basico do probe

### Testar `CocoMag`

```bash
source .venv/bin/activate
python rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:PRESENT
```

### Testar `CocoMag ACTION`

```bash
python rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:ACTION
```

### Testar `CocoVision PRESENT`

```bash
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:PRESENT
```

### Testar `CocoVision ACTION`

```bash
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:ACTION --listen-seconds 8
```

### Testar `CocoVision RETURN`

```bash
python rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:RETURN
```

## Parametros uteis do probe

### `--port`

Porta a abrir:

- `/dev/rfcomm0`
- `/dev/rfcomm1`
- `/dev/ttyUSB0`
- etc.

### `--command`

Linha textual enviada ao robô.

### `--baudrate`

Baudrate da porta.

Padrao:

```text
115200
```

### `--listen-seconds`

Tempo de escuta apos enviar o comando.

Util para comandos que demoram mais para responder.

### `--startup-delay`

Espera curta entre abrir a porta e enviar o comando.

Pode ajudar em links RFCOMM mais lentos.

Exemplo:

```bash
python rfcomm_serial_probe.py \
  --port /dev/rfcomm0 \
  --command COCOMAG:PRESENT \
  --startup-delay 1.0 \
  --listen-seconds 6
```

## Todos os comandos possiveis hoje

### CocoMag

#### `COCOMAG:PRESENT`

Acao atual:

- anda para frente `900 ms`
- para `250 ms`
- gira a direita `700 ms`
- para `250 ms`
- anda para tras `800 ms`
- para `250 ms`
- envia `COCOMAG_DONE`

#### `COCOMAG:ACTION`

Acao atual:

- anda para frente `900 ms`
- para `250 ms`
- gira servo `SG90` no `D13` para `90 graus`
- espera `700 ms`
- volta servo para `0 grau`
- para `250 ms`
- envia `COCOMAG_DONE`

### CocoVision

#### `COCOVISION:PRESENT`

Acao atual:

- anda para frente `900 ms`
- para `250 ms`
- gira a direita `700 ms`
- para `250 ms`
- anda para tras `800 ms`
- para `250 ms`
- envia `COCOVISION_DONE`

#### `COCOVISION:ACTION`

Acao atual:

- anda para frente `900 ms`
- para `250 ms`
- ativa leitura continua do sensor de cor
- limpa debounce interno
- envia `COCOVISION_DONE`

Depois disso, o firmware pode emitir:

- `COLOR_RED`
- `COLOR_GREEN`
- `COLOR_BLUE`

e tambem o formato:

- `COCOVISION_COLOR=COLOR_RED`
- `COCOVISION_COLOR=COLOR_GREEN`
- `COCOVISION_COLOR=COLOR_BLUE`

#### `COCOVISION:RETURN`

Acao atual:

- desativa leitura de cor
- anda para tras `900 ms`
- para `250 ms`
- envia `COCOVISION_DONE`

## Fluxo rapido de manutencao

Se voce alterar tempos ou movimentos dos robos no firmware, o fluxo recomendado de teste e:

1. recompilar e subir o firmware
2. fazer o bind RFCOMM
3. testar o comando isolado com `rfcomm_serial_probe.py`
4. so depois rodar o projeto completo

Isso ajuda a separar:

- problema no firmware
- problema no transporte Bluetooth
- problema na integracao do app

## Diagnostico rapido

### Se o probe nao abre a porta

Provavel problema em:

- `rfcomm bind`
- permissao no Linux
- device nao criado

### Se o probe abre, envia, mas nao recebe nada

Provavel problema em:

- link Bluetooth/RFCOMM
- firmware Bluetooth do robô
- comando diferente do esperado pelo firmware

### Se o probe recebe `DONE`

O transporte esta ok.

Nesse caso, se o app principal ainda falhar, o problema tende a estar:

- na configuracao do projeto
- ou na integracao do fluxo principal

## Comandos uteis de sistema

Listar devices Bluetooth pareados:

```bash
bluetoothctl devices
```

Listar binds RFCOMM:

```bash
rfcomm
```

Liberar binds:

```bash
sudo rfcomm release /dev/rfcomm0
sudo rfcomm release /dev/rfcomm1
```

Refazer binds:

```bash
sudo rfcomm bind /dev/rfcomm0 XX:XX:XX:XX:XX:XX 1
sudo rfcomm bind /dev/rfcomm1 YY:YY:YY:YY:YY:YY 1
```

## Resumo curto

Fluxo operacional recomendado:

1. parear ESP32
2. descobrir MAC
3. bindar `/dev/rfcomm0` e `/dev/rfcomm1`
4. testar com `rfcomm_serial_probe.py`
5. exportar `COCOMAG_PORT` e `COCOVISION_PORT`
6. rodar `python main.py`
