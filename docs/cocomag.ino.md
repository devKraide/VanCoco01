# cocomag.ino

## Visao geral

`cocomag.ino` e o firmware do robô `CocoMag`.

Ele roda em um ESP32 e executa tres responsabilidades principais:

- receber comandos textuais vindos do computador
- acionar motores DC por meio de um driver L298N
- acionar um servo `SG90` para a rotina de `ACTION`

O firmware foi escrito para manter o protocolo de aplicacao simples:
- entrada por linhas de texto
- rotinas bloqueantes e previsiveis
- resposta textual ao final de cada rotina

Tambem existe suporte opcional a `BluetoothSerial`, condicionado aos macros do core ESP32 em tempo de compilacao.

## Papel no sistema

O papel deste firmware e ser o executor físico do `CocoMag` dentro da narrativa.

Ele nao decide quando agir. Essa decisao vem da aplicacao Python. O firmware apenas:

- recebe `COCOMAG:PRESENT`
- recebe `COCOMAG:ACTION`
- executa a rotina correspondente
- responde `COCOMAG_DONE`

Em outras palavras, ele implementa a camada de atuacao do robô.

## Integracao com outros modulos

### `robot_comm.py`

Esse e o principal par deste firmware no lado Python.

`robot_comm.py` envia:
- `COCOMAG:PRESENT`
- `COCOMAG:ACTION`

e espera de volta:
- `COCOMAG_DONE`

O protocolo textual usado aqui precisa permanecer consistente com o parsing feito no Python.

### `story_engine.py`

Nao conversa diretamente com o firmware, mas depende do significado semantico das respostas:
- quando `COCOMAG_DONE` chega, a narrativa pode avancar

### `main.py`

Tambem nao fala diretamente com o microcontrolador em baixo nivel, mas dispara comandos para o `RobotComm`, que por sua vez chegam ate este firmware.

## Fluxo principal

O fluxo principal do firmware e:

1. inicializar serial
2. inicializar opcionalmente `BluetoothSerial`
3. configurar pinos do driver de motor
4. configurar o servo
5. no `loop()`, ler streams de entrada
6. montar linhas completas por buffer
7. converter cada linha em comando
8. executar a rotina fisica correspondente
9. emitir `COCOMAG_DONE`

Este firmware nao possui scheduler, filas ou multitarefa propria. O modelo de execucao e intencionalmente simples: uma rotina por vez, de forma bloqueante.

## Estrutura do codigo, parte por parte

### Includes

```cpp
#include <Arduino.h>
#include <BluetoothSerial.h>
#include <ESP32Servo.h>
```

#### `Arduino.h`

Expõe a API basica da plataforma:
- `pinMode`
- `digitalWrite`
- `analogWrite`
- `delay`
- `Stream`
- `String`

#### `BluetoothSerial.h`

Fornece a interface de Bluetooth Classic SPP do ESP32.

O firmware nao assume que ela sempre estara disponivel em todos os cores/boards. Por isso o uso e protegido por macros de compilacao.

#### `ESP32Servo.h`

Fornece o controle do servo no ESP32.

Ela e usada para:
- configurar frequencia PWM do servo
- anexar o pino
- escrever os angulos da rotina `ACTION`

### Macros de disponibilidade Bluetooth

```cpp
#if defined(CONFIG_BT_ENABLED) && defined(CONFIG_BLUEDROID_ENABLED)
#define COCOMAG_BT_AVAILABLE 1
#else
#define COCOMAG_BT_AVAILABLE 0
#endif
```

Esse bloco detecta em compilacao se o core ESP32 expõe suporte a Bluetooth Classic.

Consequencia pratica:
- se o suporte existir, `BluetoothSerial` e ativado
- se nao existir, o firmware continua compilando e operando via USB serial

Isso evita quebrar o build em ambientes nos quais o core foi compilado sem Bluedroid.

### Constantes de hardware

```cpp
constexpr int ENA = 5;
constexpr int IN1 = 18;
constexpr int IN2 = 19;
constexpr int ENB = 25;
constexpr int IN3 = 26;
constexpr int IN4 = 27;
constexpr int SERVO_PIN = 13;
```

Essas constantes definem o mapeamento eletrico atual:

- `ENA`, `ENB`: pinos PWM de habilitacao do L298N
- `IN1`, `IN2`: direcao do motor A
- `IN3`, `IN4`: direcao do motor B
- `SERVO_PIN`: sinal do servo `SG90`

O firmware assume que esse cabeamento e a fonte de verdade. Se o hardware mudar, a primeira manutencao normalmente e aqui.

### Constantes de movimento e servo

```cpp
constexpr int MOTOR_SPEED = 180;
constexpr unsigned long FORWARD_MS = 900;
constexpr unsigned long TURN_MS = 700;
constexpr unsigned long BACKWARD_MS = 800;
constexpr unsigned long STOP_MS = 250;
constexpr int SERVO_REST_ANGLE = 0;
constexpr int SERVO_ACTION_ANGLE = 90;
constexpr unsigned long SERVO_HOLD_MS = 700;
```

Essas constantes definem o comportamento fisico atual.

Importante:
- o movimento e controlado por tempo, nao por encoder
- nao existe feedback de posicao real
- a precisao depende de bateria, atrito, piso e carga do robô

Detalhes:
- `MOTOR_SPEED = 180` define o PWM aplicado nos dois motores
- `FORWARD_MS`, `TURN_MS`, `BACKWARD_MS` definem a duracao das etapas da apresentacao
- `STOP_MS` insere pausas mecanicas entre etapas
- `SERVO_REST_ANGLE` e a posicao neutra do servo
- `SERVO_ACTION_ANGLE` e o angulo de acao
- `SERVO_HOLD_MS` e o tempo em que o servo permanece no angulo de acao

### Estado global

```cpp
String serialBuffer;
String bluetoothBuffer;
bool isPresenting = false;
Servo actionServo;
#if COCOMAG_BT_AVAILABLE
BluetoothSerial SerialBT;
#endif
```

#### `serialBuffer`

Buffer incremental para montagem de comandos recebidos por USB serial.

#### `bluetoothBuffer`

Buffer incremental para montagem de comandos recebidos por Bluetooth Classic.

#### `isPresenting`

Flag de exclusao mutua simples.

Enquanto uma rotina esta em andamento:
- novos comandos sao ignorados
- isso evita reentrada de movimento durante uma acao bloqueante

#### `actionServo`

Instancia do servo usada exclusivamente pela rotina `ACTION`.

#### `SerialBT`

Instancia de Bluetooth Classic, criada apenas se o build suportar.

## Prototipos de funcao

Os prototipos no inicio deixam explicito o conjunto de primitivas do firmware:

- primitivas de baixo nivel de motor:
  - `setMotorA`
  - `setMotorB`
  - `moveForward`
  - `moveBackward`
  - `turnRight`
  - `stopMotors`
- rotinas de alto nivel:
  - `runPresentation`
  - `runAction`
- transporte/protocolo:
  - `handleCommand`
  - `readCommandStream`
  - `emitLine`

Essa separacao ja e um bom ponto de manutencao: atuacao fisica separada de transporte e parsing.

## `setup()`

### Inicializacao da serial

```cpp
Serial.begin(115200);
```

Abre o canal USB serial com baudrate fixo de `115200`.

### Inicializacao opcional do Bluetooth

```cpp
#if COCOMAG_BT_AVAILABLE
  SerialBT.begin("COCOMAG");
#else
  Serial.println("COCOMAG_BT_UNAVAILABLE");
#endif
```

Se Bluetooth Classic estiver disponivel:
- o dispositivo SPP passa a anunciar o nome `COCOMAG`

Se nao estiver:
- o firmware explicita isso na serial

Esse log e importante para diagnostico em campo.

### Configuracao dos pinos do driver

```cpp
pinMode(ENA, OUTPUT);
pinMode(IN1, OUTPUT);
...
```

Todos os pinos do L298N sao configurados como saida.

### Estado inicial seguro dos motores

```cpp
stopMotors();
```

Garante que o robô nao parte em movimento ao ligar.

### Inicializacao do servo

```cpp
actionServo.setPeriodHertz(50);
actionServo.attach(SERVO_PIN, 500, 2400);
actionServo.write(SERVO_REST_ANGLE);
```

Detalhes tecnicos:
- `50 Hz` e a frequencia classica de controle de servo hobby
- `500..2400 us` define a janela de pulso usada para mapear angulos
- o servo e explicitamente levado para a posicao de repouso no boot

## `loop()`

```cpp
readCommandStream(Serial, serialBuffer);
#if COCOMAG_BT_AVAILABLE
  readCommandStream(SerialBT, bluetoothBuffer);
#endif
```

O loop principal so faz a leitura das duas entradas possiveis:
- USB serial
- Bluetooth Classic

Nao existe polling de sensores ou logica autonoma. O `CocoMag` e completamente reativo a comandos externos.

## Parsing de comandos

### `readCommandStream(Stream& stream, String& buffer)`

Essa funcao implementa um leitor de linhas sobre qualquer `Stream`.

Isso e um ponto tecnico importante do firmware:
- tanto `Serial` quanto `BluetoothSerial` implementam a interface `Stream`
- por isso a mesma funcao atende os dois transportes

Fluxo interno:

1. enquanto houver bytes disponiveis
2. ler um caractere
3. se for `\n` ou `\r`
   - tratar o buffer como uma linha completa
   - chamar `handleCommand`
   - limpar o buffer
4. senao, anexar o caractere ao buffer

Esse desenho evita duplicar a logica de recepcao entre USB e Bluetooth.

## Decodificacao do protocolo

### `handleCommand(const String& command)`

Essa funcao e a fronteira entre transporte e semantica.

#### Normalizacao

```cpp
String normalized = command;
normalized.trim();
```

Remove espacos e terminadores residuais.

#### Rejeicao de entrada vazia

```cpp
if (normalized.isEmpty()) {
  return;
}
```

Protege contra linhas vazias ou ruído simples.

#### Exclusao mutua

```cpp
if (isPresenting) {
  return;
}
```

Enquanto uma rotina bloqueante estiver rodando, novos comandos sao descartados.

Isso simplifica muito o firmware, ao custo de nao haver fila de comandos.

#### Comando `COCOMAG:PRESENT`

```cpp
if (normalized == "COCOMAG:PRESENT") {
  isPresenting = true;
  runPresentation();
  isPresenting = false;
  return;
}
```

Executa a apresentacao do robô.

#### Comando `COCOMAG:ACTION`

```cpp
if (normalized == "COCOMAG:ACTION") {
  isPresenting = true;
  runAction();
  isPresenting = false;
}
```

Executa a acao individual com servo.

## Rotinas de alto nivel

### `runPresentation()`

Sequencia atual:

1. frente por `FORWARD_MS`
2. pausa por `STOP_MS`
3. giro a direita por `TURN_MS`
4. pausa por `STOP_MS`
5. re por `BACKWARD_MS`
6. pausa por `STOP_MS`
7. emitir `COCOMAG_DONE`

Observacoes tecnicas:
- a funcao e completamente bloqueante
- o uso de `delay()` torna o comportamento previsivel, mas impede multitarefa
- essa escolha e adequada aqui porque o protocolo exige simplicidade e previsibilidade

### `runAction()`

Sequencia atual:

1. frente por `FORWARD_MS`
2. pausa por `STOP_MS`
3. servo vai para `SERVO_ACTION_ANGLE`
4. espera `SERVO_HOLD_MS`
5. servo retorna para `SERVO_REST_ANGLE`
6. pausa por `STOP_MS`
7. emitir `COCOMAG_DONE`

Observacoes:
- o movimento mecanico do servo e aberto, sem confirmacao de posicao
- o tempo de espera assume que o servo consegue chegar ao angulo configurado dentro da janela

## Saida de mensagens

### `emitLine(const char* message)`

Essa funcao centraliza toda a emissao textual do firmware.

Comportamento:
- sempre envia pela USB serial
- se houver cliente Bluetooth conectado, tambem envia por Bluetooth

Esse e o principal ponto que torna o firmware pronto para multiplos transportes sem duplicar a logica de negocio.

## Primitivas de movimento

### `moveForward()`

Aciona ambos os motores no sentido positivo com `MOTOR_SPEED`.

### `moveBackward()`

Aciona ambos os motores no sentido inverso com `MOTOR_SPEED`.

### `turnRight()`

Aciona um motor para frente e o outro para tras, produzindo giro no eixo.

### `stopMotors()`

Implementa parada dura:
- PWM zerado em `ENA` e `ENB`
- todas as linhas de direcao em `LOW`

Essa combinacao ajuda a reduzir movimento residual entre etapas.

### `setMotorA()` e `setMotorB()`

Essas sao as primitivas reais de acionamento do L298N.

Cada uma:
- escolhe o sentido pelas linhas `INx`
- aplica velocidade pela linha `ENx`

Esse nivel de abstracao torna facil mudar as rotinas de alto nivel sem repetir logica de H-bridge.

## Pontos criticos e de manutencao

### 1. O firmware usa controle por tempo, nao por posicao

Essa e a principal limitacao tecnica atual.

Consequencias:
- a distancia percorrida varia conforme bateria, piso e carga
- o angulo de giro nao e absoluto
- a repetibilidade fisica e boa para apresentacao, mas nao metrologica

### 2. `delay()` bloqueia tudo

Durante `runPresentation()` e `runAction()`:
- nenhum novo comando e processado
- nao existe paralelismo

Isso e uma escolha consciente de simplicidade. Se um dia houver necessidade de resposta concorrente, a arquitetura precisara mudar.

### 3. `String` em microcontrolador

O uso de `String` simplifica muito o parsing, mas em firmware de longa duracao pode aumentar risco de fragmentacao de heap.

Neste projeto, como o protocolo e simples e a taxa de mensagens e baixa, o custo e aceitavel.

### 4. Dependencia do core ESP32 para Bluetooth Classic

O firmware so ativa `BluetoothSerial` quando:
- `CONFIG_BT_ENABLED`
- `CONFIG_BLUEDROID_ENABLED`

estao disponiveis no build.

Se nao estiverem:
- o firmware continua funcional por USB
- imprime `COCOMAG_BT_UNAVAILABLE`

### 5. O protocolo textual e um contrato externo

Se mudar:
- nome do dispositivo Bluetooth
- strings `COCOMAG:PRESENT`
- `COCOMAG:ACTION`
- `COCOMAG_DONE`

sera necessario atualizar o lado Python junto.

### 6. O servo e inicializado no boot e levado ao repouso

Isso e importante para previsibilidade mecanica.

Se o hardware do servo mudar:
- revisar pulso minimo e maximo do `attach`
- revisar angulos de repouso e acao

### 7. O codigo ja esta bem separado por camadas

Hoje a divisao esta clara:
- transporte: `readCommandStream`, `emitLine`
- protocolo: `handleCommand`
- alto nivel: `runPresentation`, `runAction`
- baixo nivel: `move*`, `setMotor*`, `stopMotors`

Essa separacao deve ser preservada.

## Resumo de manutencao

O firmware do `CocoMag` ja esta estruturado de forma incremental e profissional para o tamanho do problema.

Ele ja esta praticamente pronto para:
- USB serial
- Bluetooth Classic quando o core suportar

Ao evoluir esse arquivo, a manutencao mais segura e:

1. manter o protocolo textual estavel
2. preservar a separacao entre transporte, protocolo e movimento
3. alterar constantes de tempo e pinos antes de alterar estrutura
4. so introduzir maquina de estados nao bloqueante se houver necessidade real

Para o contexto atual de apresentacao teatral, a implementacao e simples, robusta e coerente com o restante do sistema.
