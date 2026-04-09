# robot_comm.py

## Visao geral

`robot_comm.py` concentra a comunicacao entre a aplicacao Python e os robos `CocoMag` e `CocoVision`.

Ele encapsula:
- abertura das conexoes
- envio de comandos textuais
- leitura assincrona das respostas
- traducao dessas respostas para eventos internos
- fallback simples para modo mock quando o robo nao esta disponivel

O arquivo foi estruturado para tratar USB serial e RFCOMM no Linux do mesmo jeito: ambos entram como portas serial controladas por `pyserial`.

## Papel no sistema

O papel deste modulo e isolar o transporte dos robos do restante do sistema.

Em vez de espalhar detalhes de:
- porta serial
- timeout
- thread de leitura
- parsing de `DONE`
- parsing de `COLOR_*`

por varios arquivos, tudo isso fica aqui.

Para o restante do projeto, a interface relevante e pequena:
- `send_command(robot, command)`
- `poll_events()`
- `close()`

Isso permite que `main.py` e `story_engine.py` trabalhem com eventos de alto nivel, sem depender de detalhes de serial ou RFCOMM.

## Integracao com outros modulos

### `config.py`

Fornece:
- baudrates
- modo de comunicacao de cada robo
- porta configurada de cada robo

Exemplos:
- `COCOMAG_COMM_MODE`
- `COCOMAG_PORT`
- `COCOVISION_COMM_MODE`
- `COCOVISION_PORT`

### `main.py`

E o principal consumidor deste modulo.

Usa `RobotComm` para:
- enviar comandos aos robos
- consultar eventos recebidos
- fechar conexoes no encerramento do app

### `story_engine.py`

Nao fala diretamente com a serial, mas depende da semantica dos eventos produzidos aqui.

Exemplos de eventos que a engine espera:
- `COCOMAG_DONE`
- `COCOVISION_DONE`
- `COLOR_RED`
- `COLOR_GREEN`
- `COLOR_BLUE`

### Firmware dos robos

O protocolo textual depende diretamente dos firmwares:
- `firmware/cocomag/cocomag.ino`
- `firmware/cocovision/cocovision.ino`

Este arquivo assume que os firmwares enviam linhas como:
- `COCOMAG_DONE`
- `COCOVISION_DONE`
- `COLOR_RED`

e aceitam linhas como:
- `COCOMAG:PRESENT`
- `COCOMAG:ACTION`
- `COCOVISION:PRESENT`
- `COCOVISION:ACTION`
- `COCOVISION:RETURN`

## Fluxo principal

O fluxo principal do modulo e:

1. ao instanciar `RobotComm`, tentar conectar `COCOMAG` e `COCOVISION`
2. abrir a porta correspondente de cada robo
3. iniciar uma thread de leitura para cada conexao aberta
4. quando o app pede um comando:
   - enviar `ROBO:COMANDO`
   - ou cair em fallback mock se nao houver conexao
5. quando uma linha chega do robo:
   - normalizar a mensagem
   - converter para `RobotEvent`
   - colocar na fila interna
6. `main.py` chama `poll_events()` para consumir esses eventos sem bloquear

## Principais estruturas e funcoes

### `RobotEvent`

Dataclass imutavel que representa um evento vindo de um robo.

Campos:
- `robot`
- `status`

Tambem expoe a propriedade `code`, que monta `ROBO_STATUS`.

### `RobotComm.__init__()`

Inicializa:
- fila de eventos
- timers de fallback mock
- locks
- conjunto de portas reservadas
- dicionario de conexoes por robo
- threads de leitura
- flag de bloqueio de eventos de cor

Ao final do construtor, tenta conectar:
- `COCOMAG`
- `COCOVISION`

### `send_command()`

Interface publica para envio de comandos.

Comportamento:
- tenta enviar o comando real
- se falhar, agenda um `DONE` mock por timer

Isso permite manter o fluxo narrativo testavel mesmo sem hardware conectado.

### `poll_events()`

Retorna todos os eventos pendentes da fila interna sem bloquear.

Esse metodo e o ponto de consumo usado pelo loop principal.

### `set_color_events_enabled()`

Liga ou desliga a aceitacao de eventos `COLOR_*`.

Isso e usado para impedir disparos de varias cores enquanto um video de cor esta em andamento.

### `clear_color_events()`

Limpa da fila apenas eventos de cor do `CocoVision`, preservando eventos de outros tipos.

Essa limpeza e importante para evitar que cores antigas avancem o fluxo indevidamente.

### `close()`

Encerra:
- threads de leitura
- conexoes abertas

Deve ser chamado no shutdown do app.

### `_connect_robot()`

Faz a abertura efetiva da conexao de um robo.

Passos:
- validar `pyserial`
- descobrir modo e porta
- abrir a `serial.Serial`
- resetar buffers apenas no modo serial USB
- registrar a porta como reservada
- iniciar a thread de leitura

Hoje o modo `serial` e `rfcomm` convergem para o mesmo tratamento: ambos sao portas serial.

### `_send_robot_command()`

Envia uma linha textual no formato:

```text
ROBOT:COMMAND
```

Se a conexao nao existir, tenta reconectar antes.

Se ocorrer erro de escrita:
- loga o erro
- desconecta o robo
- retorna `False`

Na implementacao atual, o envio tambem registra um log curto com a linha enviada, o que ajuda a diagnosticar transporte USB ou RFCOMM.

### `_serial_read_loop()`

Thread dedicada para leitura de uma conexao.

Responsabilidades:
- fazer `readline()`
- decodificar bytes
- normalizar mensagens especiais
- transformar texto em `RobotEvent`
- logar respostas nao mapeadas

Regra especial importante:
- `COCOVISION_COLOR=COLOR_RED` e reduzido para `COLOR_RED`

Isso existe por compatibilidade com o firmware do `CocoVision`.

### `_disconnect_robot()`

Fecha a conexao de um robo e libera a porta do conjunto de portas reservadas.

### `_resolve_robot_port()`

Decide qual porta usar.

Ordem atual:
1. variavel de ambiente `ROBOT_PORT`
2. valor fixo em `config.py`
3. descoberta automatica apenas para modo serial USB

Para `rfcomm`, se nao houver porta explicita configurada, retorna `None`.

### `_get_comm_mode()` e `_get_baudrate()`

Helpers pequenos para resolver os parametros por robo.

## Pontos criticos e de manutencao

### 1. O protocolo textual e contrato com o firmware

Se os firmwares mudarem mensagens como:
- `COCOMAG_DONE`
- `COCOVISION_DONE`
- `COLOR_RED`

este modulo precisa ser atualizado em conjunto.

### 2. `rfcomm` depende de porta explicita

No modo `rfcomm`, o arquivo nao tenta descobrir `/dev/rfcomm0` automaticamente.

E preciso que a porta venha de:
- `config.py`
- ou variavel de ambiente

Isso e intencional, porque o bind do RFCOMM no Linux e operacional e deve ser controlado externamente.

### 3. O fallback mock pode mascarar falhas se nao for observado

Se um robo nao conectar, o app nao trava. Ele agenda um `DONE` falso.

Isso e util para desenvolvimento, mas em producao exige atencao aos logs para garantir que a conexao real aconteceu.

### 4. Eventos de cor sao um caso especial

O `CocoVision` envia fluxo continuo de `COLOR_*`.

Por isso este modulo tem duas protecoes:
- `set_color_events_enabled()`
- `clear_color_events()`

Qualquer mudanca nessa parte precisa ser validada com o fluxo narrativo de cores.

### 5. Multithreading simples, mas sensivel

O modelo atual usa:
- uma fila thread-safe
- uma thread por conexao
- locks para escrita e timers

E simples e suficiente, mas alteracoes devem preservar:
- ausencia de bloqueio no loop principal
- leitura continua
- shutdown limpo

### 6. A descoberta automatica e heuristica

No modo serial sem porta explicita, a descoberta por `list_ports` usa descricoes e fabricantes.

Isso ajuda no plug-and-play, mas nao deve ser considerado infalivel em producao.

Para ambiente controlado, o ideal e definir as portas explicitamente.

## Resumo de manutencao

`robot_comm.py` deve continuar como camada unica de transporte e parsing dos robos.

Ao evoluir este arquivo, preservar a separacao:
- `main.py` coordena
- `story_engine.py` interpreta eventos
- `robot_comm.py` apenas conecta, envia, le e traduz linhas em eventos

Se um novo robo ou novo tipo de evento entrar no sistema, a extensao natural acontece aqui:
- abrir nova conexao
- mapear novo texto para `RobotEvent`
- manter o restante do app desacoplado do transporte.
