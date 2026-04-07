# cocovision_serial_reader.py

## Visao geral

`cocovision_serial_reader.py` e uma ferramenta auxiliar de linha de comando para inspecionar isoladamente a saida serial do `CocoVision`.

Ele nao participa do fluxo principal da aplicacao teatral. Em vez disso, serve como utilitario de diagnostico e bring-up de hardware.

O script:
- abre uma porta serial
- escuta mensagens do ESP32 do `CocoVision`
- valida um pequeno conjunto de mensagens esperadas
- imprime timestamp e classificacao no terminal

## Papel no sistema

O papel deste arquivo e facilitar debug do robô fora do contexto completo do app.

Ele e util para responder perguntas como:
- o `CocoVision` esta realmente enviando `COLOR_RED`, `COLOR_GREEN` e `COLOR_BLUE`?
- o sensor foi encontrado pelo firmware?
- a porta serial correta foi aberta?
- ha ruido inesperado na saida serial?

Em termos de arquitetura, ele e um utilitario operacional, nao um modulo central da aplicacao.

## Integracao com outros modulos

### Firmware `cocovision.ino`

Esse e o principal par deste script.

O script espera mensagens emitidas pelo firmware, especialmente:
- `COLOR_RED`
- `COLOR_GREEN`
- `COLOR_BLUE`
- `TCS34725_NOT_FOUND`

### `robot_comm.py`

Existe sobreposicao funcional parcial com o parser do `robot_comm.py`, mas com objetivos diferentes:

- `robot_comm.py` integra a serial ao app completo
- `cocovision_serial_reader.py` e um leitor isolado de diagnostico

Ele nao compartilha classe ou funcao com `robot_comm.py`; apenas observa o mesmo tipo de protocolo textual.

### Sistema operacional / pyserial

O script depende diretamente de:
- `pyserial`
- descoberta de portas por `serial.tools.list_ports`

## Fluxo principal

O fluxo de execucao do script e:

1. parsear argumentos de linha de comando
2. resolver a porta serial a ser usada
3. abrir a conexao serial
4. entrar em loop infinito de leitura
5. decodificar cada linha recebida
6. classificar a mensagem como valida ou desconhecida
7. imprimir com timestamp
8. encerrar com codigo apropriado em caso de erro ou `Ctrl+C`

Esse fluxo e deliberadamente simples, porque o objetivo do script e observabilidade e nao integracao narrativa.

## Estruturas e constantes principais

### `VALID_MESSAGES`

```python
VALID_MESSAGES = {"COLOR_RED", "COLOR_GREEN", "COLOR_BLUE", "TCS34725_NOT_FOUND"}
```

Conjunto de mensagens que o script reconhece explicitamente como esperadas.

Interpretacao:
- mensagens nesse conjunto sao mostradas como eventos validos
- qualquer outra linha e tratada como `UNKNOWN`

Isso ajuda a separar rapidamente:
- sinais uteis do firmware
- logs extras
- ruído inesperado

### `DEFAULT_BAUDRATE`

```python
DEFAULT_BAUDRATE = 115200
```

Baudrate padrao usado para abrir a serial.

Ele esta alinhado com o firmware atual do `CocoVision`.

## Principais funcoes explicadas

### `resolve_port(preferred_port: str | None) -> str | None`

Essa funcao resolve qual porta serial deve ser aberta.

Fluxo:

1. se o usuario passou `--port`, retorna essa porta diretamente
2. senao, varre as portas conhecidas por `list_ports.comports()`
3. escolhe a primeira que pareca USB/UART por heuristica de descricao/fabricante
4. se nao encontrar nada, retorna `None`

Heuristica atual:
- `"usb"` na descricao
- `"uart"` na descricao
- `"wch"` no fabricante
- `"silicon labs"` no fabricante

Essa heuristica e suficiente para debug rapido, mas nao deve ser tratada como descoberta infalivel em ambientes com varios dispositivos seriais conectados.

### `main() -> int`

Funcao principal do script.

#### Etapa 1: parser CLI

```python
parser = argparse.ArgumentParser(...)
parser.add_argument("--port", ...)
parser.add_argument("--baudrate", ...)
```

O usuario pode:
- escolher explicitamente a porta
- sobrescrever o baudrate padrao

#### Etapa 2: resolucao da porta

```python
port = resolve_port(args.port)
if port is None:
    print("[CocoVision] Nenhuma porta serial encontrada.")
    return 1
```

Se nenhuma porta for encontrada, o script termina com erro.

#### Etapa 3: abertura da serial

```python
with serial.Serial(port, args.baudrate, timeout=0.2) as connection:
```

Detalhes tecnicos:
- usa context manager para garantir fechamento limpo
- usa timeout curto (`0.2 s`) para manter o loop responsivo

#### Etapa 4: loop de leitura

```python
while True:
    raw_line = connection.readline()
```

O script faz polling simples de linhas completas.

Se nao vier dado:
- continua o loop

Se vier uma linha:
- decodifica em UTF-8 com tolerancia a erros
- remove espacos e terminadores
- ignora linhas vazias

#### Etapa 5: classificacao e log

```python
timestamp = time.strftime("%H:%M:%S")
if message in VALID_MESSAGES:
    print(f"[{timestamp}] {message}")
else:
    print(f"[{timestamp}] UNKNOWN: {message}")
```

Esse formato e util para:
- correlacionar resposta do sensor com acao fisica
- enxergar rapidamente mensagens nao previstas

#### Etapa 6: tratamento de excecoes

O script trata:
- `serial.SerialException`
- `KeyboardInterrupt`

Assim, ele termina com mensagens claras tanto em erro de serial quanto em encerramento manual.

## Comportamento operacional

Quando tudo esta correto, a saida tipica e algo como:

```text
[CocoVision] Escutando /dev/ttyUSB1 em 115200 baud.
[14:32:10] COLOR_RED
[14:32:12] COLOR_GREEN
```

Quando o firmware emite algo fora do conjunto esperado, o script mostra:

```text
[14:32:15] UNKNOWN: COCOVISION_DONE
```

Isso e importante: o script nao conhece todo o protocolo do `CocoVision`, apenas um subconjunto util para diagnostico do sensor.

## Pontos criticos e de manutencao

### 1. O conjunto `VALID_MESSAGES` e intencionalmente pequeno

Ele foca no caso de uso de debug de cor.

Por isso, outras mensagens validas do firmware podem aparecer como `UNKNOWN`.

Isso nao significa necessariamente erro no firmware; pode apenas significar que a whitelist do script e limitada.

### 2. A descoberta automatica de porta e heuristica

Se houver varios dispositivos seriais conectados, a porta escolhida automaticamente pode nao ser a do `CocoVision`.

Nesses casos, o uso correto e passar `--port` explicitamente.

### 3. O script nao envia comandos

Ele e somente leitor.

Logo, ele nao consegue:
- iniciar `ACTION`
- iniciar `PRESENT`
- iniciar `RETURN`

Para isso, o robô precisa ja estar configurado para emitir mensagens ou o comando deve ser enviado por outro meio.

### 4. O parser nao normaliza `COCOVISION_COLOR=...`

Hoje o script espera diretamente `COLOR_RED`, `COLOR_GREEN` e `COLOR_BLUE`.

Se o firmware emitir somente o formato prefixado, ele aparecera como `UNKNOWN`.

No estado atual do firmware isso nao e um problema, porque o firmware tambem emite a forma curta.

### 5. O script nao participa da narrativa

Qualquer tentativa de usar esse utilitario como parte do fluxo da apresentacao seria inadequada.

Ele existe para:
- teste de bancada
- verificacao de sensor
- confirmacao de serial

## Resumo de manutencao

`cocovision_serial_reader.py` deve continuar pequeno e utilitario.

Ao evoluir este arquivo:
- manter foco em observabilidade
- evitar acoplamento com a narrativa
- atualizar `VALID_MESSAGES` se o protocolo de debug do firmware mudar
- preservar a simplicidade da CLI

Ele funciona melhor como ferramenta enxuta de diagnostico rapido do `CocoVision`.
