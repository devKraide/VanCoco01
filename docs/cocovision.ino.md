# cocovision.ino

## Visao geral

`cocovision.ino` e o firmware do robô `CocoVision`.

Ele roda em um ESP32 e combina tres blocos funcionais no mesmo firmware:

- transporte de comandos por USB serial e opcionalmente por Bluetooth Classic
- controle de locomocao via L298N e dois motores DC
- aquisicao e classificacao de cor via sensor `TCS34725`

O papel do firmware e executar a parte física do `CocoVision` no roteiro:
- apresentar-se
- avancar para a fase de leitura de cor
- retornar para tras quando solicitado
- emitir eventos textuais que o Python consegue interpretar

Apesar de ser compacto, o arquivo ja possui uma separacao razoavel entre:
- transporte
- protocolo textual
- rotinas de movimento
- logica do sensor de cor

## Papel no sistema

Este firmware e o executor embarcado do `CocoVision`.

Ele nao toma decisoes narrativas autonomas. A aplicacao Python continua sendo o orquestrador. O firmware faz quatro coisas centrais:

1. recebe comandos como texto:
   - `COCOVISION:PRESENT`
   - `COCOVISION:ACTION`
   - `COCOVISION:RETURN`
2. executa rotinas de movimento predefinidas
3. habilita/desabilita a fase de leitura continua de cor
4. envia eventos textuais de saida:
   - `COCOVISION_DONE`
   - `COCOVISION_COLOR=COLOR_*`
   - `COLOR_*`

Em termos de arquitetura do sistema, ele e a ponta de atuacao e sensoriamento do `CocoVision`.

## Integracao com outros modulos

### `robot_comm.py`

Este e o modulo Python mais diretamente acoplado ao firmware.

`robot_comm.py` envia:
- `COCOVISION:PRESENT`
- `COCOVISION:ACTION`
- `COCOVISION:RETURN`

e parseia as respostas:
- `COCOVISION_DONE`
- `COLOR_RED`
- `COLOR_GREEN`
- `COLOR_BLUE`

Existe tambem uma compatibilidade importante:
- o firmware envia `COCOVISION_COLOR=COLOR_*`
- e em seguida envia tambem `COLOR_*`

O lado Python sabe normalizar esse formato.

### `story_engine.py`

Nao fala diretamente com o ESP32, mas depende da semantica dos eventos produzidos aqui.

Exemplos:
- `COCOVISION_DONE` libera o avancar do fluxo
- `COLOR_*` dispara os videos de cor

### `main.py`

Age como orquestrador operacional: envia comandos ao `RobotComm`, que por sua vez chegam a este firmware, e reage aos eventos que o firmware produz.

## Fluxo principal

O fluxo global do firmware e:

1. inicializar serial
2. inicializar opcionalmente Bluetooth Classic
3. inicializar barramento I2C do sensor
4. inicializar pinos do L298N
5. validar a presenca do `TCS34725`
6. no `loop()`:
   - ler comandos de transporte
   - se uma rotina de movimento estiver ativa, nao entrar na leitura de cor
   - se o sensor nao estiver ativo, apenas esperar
   - se o sensor estiver ativo, capturar RGBC
   - classificar a cor dominante
   - publicar a cor com debounce

O firmware alterna entre dois modos principais:
- modo de comando/movimento
- modo de sensoriamento continuo

## Estrutura do codigo, parte por parte

### Includes

```cpp
#include <Arduino.h>
#include <BluetoothSerial.h>
#include <Wire.h>
#include <Adafruit_TCS34725.h>
```

#### `Arduino.h`

Fornece a base da API embarcada:
- `pinMode`
- `digitalWrite`
- `analogWrite`
- `delay`
- `millis`
- `Stream`
- `String`

#### `BluetoothSerial.h`

Fornece Bluetooth Classic SPP para ESP32.

O uso e opcional e protegido por macros de compilacao.

#### `Wire.h`

Implementa o barramento I2C utilizado para comunicar com o `TCS34725`.

#### `Adafruit_TCS34725.h`

Biblioteca do sensor de cor.

Fornece:
- inicializacao do sensor
- leitura de canais `red`, `green`, `blue`, `clear`

### Macros de disponibilidade Bluetooth

```cpp
#if defined(CONFIG_BT_ENABLED) && defined(CONFIG_BLUEDROID_ENABLED)
#define COCOVISION_BT_AVAILABLE 1
#else
#define COCOVISION_BT_AVAILABLE 0
#endif
```

Esses macros tornam o firmware resiliente a ambientes em que o core ESP32 nao expõe Bluetooth Classic.

Consequencia:
- se Bluetooth estiver disponivel, `SerialBT` e ativado
- se nao estiver, o firmware continua funcional por USB serial

Isso evita dependencia obrigatoria do transporte Bluetooth para o build compilar.

## Constantes de comunicacao, sensor e hardware

### Serial e debounce

```cpp
constexpr unsigned long SERIAL_BAUDRATE = 115200;
constexpr unsigned long DETECTION_DEBOUNCE_MS = 1200;
```

- `SERIAL_BAUDRATE` fixa o baudrate da USB serial
- `DETECTION_DEBOUNCE_MS` limita repeticao da mesma cor em janela curta

### Thresholds de classificacao de cor

```cpp
constexpr float MIN_CLEAR_VALUE = 120.0f;
constexpr float DOMINANCE_RATIO = 1.18f;
```

#### `MIN_CLEAR_VALUE`

Threshold minimo do canal `clear`.

Se a iluminacao refletida for muito baixa:
- o firmware considera a leitura insuficiente
- nenhuma cor e emitida

Isso reduz falso positivo em cenas muito escuras ou quando o sensor nao esta apontado para o objeto certo.

#### `DOMINANCE_RATIO`

Fator de dominancia entre canais.

Para uma cor ser aceita, seu canal precisa vencer os outros por pelo menos esse fator multiplicativo.

Exemplo:
- vermelho so e aceito se `redRatio > greenRatio * DOMINANCE_RATIO`
- e tambem `redRatio > blueRatio * DOMINANCE_RATIO`

Esse criterio e mais robusto que simplesmente escolher o maior canal bruto.

### I2C

```cpp
constexpr int I2C_SDA_PIN = 21;
constexpr int I2C_SCL_PIN = 22;
```

Define explicitamente os pinos do barramento I2C:
- `SDA = GPIO 21`
- `SCL = GPIO 22`

Isso evita depender dos defaults da placa e aumenta previsibilidade na montagem.

### Pinos do driver de motor

```cpp
constexpr int ENA = 5;
constexpr int IN1 = 18;
constexpr int IN2 = 19;
constexpr int ENB = 25;
constexpr int IN3 = 26;
constexpr int IN4 = 27;
```

Mesmo padrao logico do `CocoMag`:
- `ENA`, `ENB`: habilitacao/PWM
- `IN1`, `IN2`: direcao do motor A
- `IN3`, `IN4`: direcao do motor B

### Parametros de movimento

```cpp
constexpr int MOTOR_SPEED = 180;
constexpr unsigned long FORWARD_MS = 900;
constexpr unsigned long TURN_MS = 700;
constexpr unsigned long BACKWARD_MS = 800;
constexpr unsigned long STOP_MS = 250;
```

Esses valores definem o comportamento fisico atual do robô.

Importante:
- o sistema usa controle por tempo
- nao ha encoder
- nao ha odometria
- nao ha realimentacao de posicao

O movimento depende de:
- tensao da bateria
- atrito do piso
- massa transportada
- estado mecanico

## Instancia do sensor

```cpp
Adafruit_TCS34725 tcs =
    Adafruit_TCS34725(TCS34725_INTEGRATIONTIME_50MS, TCS34725_GAIN_4X);
```

O sensor e configurado com:
- tempo de integracao `50 ms`
- ganho `4x`

Essa configuracao e um compromisso entre:
- sensibilidade
- velocidade de resposta
- nivel de ruido

## Estado global do firmware

```cpp
String lastColor = "";
String serialBuffer = "";
String bluetoothBuffer = "";
unsigned long lastSentAt = 0;
bool isPresenting = false;
bool sensorActive = false;
```

### `lastColor`

Memoria da ultima cor emitida.

Usada pelo debounce para evitar repeticao rapida da mesma classificacao.

### `serialBuffer`

Buffer incremental para montagem de comandos vindos da USB serial.

### `bluetoothBuffer`

Buffer incremental para montagem de comandos vindos do Bluetooth Classic.

### `lastSentAt`

Marca temporal do ultimo envio de cor aceito.

Usada em conjunto com `lastColor`.

### `isPresenting`

Flag de exclusao mutua entre:
- rotina de movimento
- loop de leitura de cor

Enquanto ela estiver `true`, o firmware nao entra na fase de sensoriamento continuo.

### `sensorActive`

Flag que controla explicitamente se o sensor deve ou nao participar do `loop()`.

Esse detalhe e central para a arquitetura do robô:
- `ACTION` liga a fase de leitura
- `RETURN` desliga a fase de leitura

### `SerialBT`

Criado somente quando `COCOVISION_BT_AVAILABLE` e verdadeiro.

## Prototipos

O conjunto de prototipos mostra bem a divisao do firmware:

- classificacao de cor:
  - `detectDominantColor`
  - `publishColorIfNeeded`
- transporte/protocolo:
  - `handleCommand`
  - `readCommandStream`
  - `emitLine`
- rotinas narrativas:
  - `runPresentation`
  - `runAction`
  - `runReturn`
- primitivas de locomocao:
  - `moveForward`
  - `moveBackward`
  - `turnRight`
  - `stopMotors`
  - `setMotorA`
  - `setMotorB`

Essa divisao deve ser preservada porque ela ja reduz acoplamento entre camadas.

## `setup()`

### Inicializacao da serial

```cpp
Serial.begin(SERIAL_BAUDRATE);
```

Abre a USB serial no baudrate definido.

### Inicializacao opcional do Bluetooth

```cpp
#if COCOVISION_BT_AVAILABLE
  SerialBT.begin("COCOVISION");
#else
  Serial.println("COCOVISION_BT_UNAVAILABLE");
#endif
```

Se o build suportar Bluetooth Classic:
- o dispositivo SPP anuncia o nome `COCOVISION`

Se nao suportar:
- o firmware deixa isso explicito no monitor serial

### Inicializacao do I2C

```cpp
Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
```

Esse detalhe e importante porque fixa os pinos reais usados pelo barramento.

### Inicializacao do driver de motor

```cpp
pinMode(ENA, OUTPUT);
...
stopMotors();
```

O firmware garante estado inicial seguro antes de qualquer comando de movimento.

### Validacao do sensor de cor

```cpp
if (!tcs.begin()) {
  Serial.println("TCS34725_NOT_FOUND");
  while (true) {
    delay(1000);
  }
}
```

Se o sensor nao responder:
- o firmware entra em falha terminal
- permanece preso em loop infinito

Essa decisao e intencionalmente conservadora:
- sem sensor, o robô nao consegue cumprir sua funcao narrativa principal
- falhar cedo ajuda no diagnostico

## `loop()`

O `loop()` possui duas fases distintas.

### 1. Fase de transporte

```cpp
readCommandStream(Serial, serialBuffer);
#if COCOVISION_BT_AVAILABLE
  readCommandStream(SerialBT, bluetoothBuffer);
#endif
```

Lê continuamente comandos vindos dos dois canais.

### 2. Fase de arbitragem entre movimento e sensor

```cpp
if (isPresenting) {
  return;
}

if (!sensorActive) {
  delay(80);
  return;
}
```

Interpretacao:
- se uma rotina de movimento esta rodando, nao ler sensor
- se o sensor nao esta habilitado, ficar em idle leve

Isso evita conflitos entre locomocao e fase de leitura.

### 3. Fase de leitura de cor

```cpp
tcs.getRawData(&red, &green, &blue, &clear);
String colorName = detectDominantColor(red, green, blue, clear);
publishColorIfNeeded(colorName);
delay(80);
```

O loop de cor roda em polling com periodo aproximado de `80 ms`, mais o tempo interno do sensor e do processamento.

Esse modelo e simples, previsivel e suficiente para a frequencia narrativa desejada.

## Parsing e transporte

### `readCommandStream(Stream& stream, String& buffer)`

Essa funcao abstrai a recepcao por qualquer fonte que implemente `Stream`.

Isso e relevante porque:
- `Serial` implementa `Stream`
- `BluetoothSerial` implementa `Stream`

Fluxo:
1. ler bytes disponiveis
2. acumular no buffer
3. ao encontrar `\n` ou `\r`, interpretar como fim de linha
4. enviar a linha para `handleCommand`

Essa e a principal razao pela qual o firmware ja estava praticamente pronto para Bluetooth sem reescrita.

### `emitLine(const char* message)`

Centraliza a saida textual.

Comportamento:
- sempre imprime na USB serial
- se houver cliente Bluetooth conectado, tambem imprime por Bluetooth

Essa funcao desacopla protocolo e transporte. As funcoes de alto nivel nao precisam saber por qual meio a mensagem vai sair.

## Protocolo de comandos

### `handleCommand(const String& command)`

Esse metodo e a fronteira entre texto recebido e acao do robô.

#### Normalizacao

```cpp
String normalized = command;
normalized.trim();
```

Remove espacos e terminadores residuais.

#### Rejeicao de linha invalida ou reentrada

```cpp
if (normalized.isEmpty() || isPresenting) {
  return;
}
```

Isso protege contra:
- entrada vazia
- comandos recebidos durante uma rotina bloqueante

#### `COCOVISION:PRESENT`

Executa a apresentacao inicial e responde `COCOVISION_DONE`.

#### `COCOVISION:ACTION`

Executa o avanco inicial, liga a fase de leitura de cor e responde `COCOVISION_DONE`.

#### `COCOVISION:RETURN`

Desliga a fase de leitura, move o robô para tras e responde `COCOVISION_DONE`.

## Classificacao de cor

### `detectDominantColor(uint16_t red, uint16_t green, uint16_t blue, uint16_t clear)`

Essa funcao transforma a leitura RGBC bruta em uma classificacao discreta.

### Etapa 1: validar iluminacao minima

```cpp
if (clear < MIN_CLEAR_VALUE) {
  return "";
}
```

Se a reflexao total for insuficiente, o resultado e descartado.

### Etapa 2: normalizar por `clear`

```cpp
float redRatio = static_cast<float>(red) / clear;
...
```

Essa normalizacao reduz dependencia de intensidade absoluta de luz.

Sem essa etapa, o sistema ficaria mais sensivel a variacao de distancia e iluminacao.

### Etapa 3: testar dominancia relativa

Cada cor so e aceita se superar as outras por `DOMINANCE_RATIO`.

Exemplo para vermelho:

```cpp
if (redRatio > greenRatio * DOMINANCE_RATIO && redRatio > blueRatio * DOMINANCE_RATIO)
```

Isso torna a classificacao mais conservadora e reduz ambiguidades.

### Retorno

Retorna:
- `"COLOR_RED"`
- `"COLOR_GREEN"`
- `"COLOR_BLUE"`
- ou string vazia quando nao ha confianca suficiente

## Publicacao de cor

### `publishColorIfNeeded(const String& colorName)`

Essa funcao aplica debounce e emite a mensagem.

#### Rejeicao de entrada vazia

Se `colorName` vier vazia, nao publica nada.

#### Debounce por cor + tempo

```cpp
bool isDebounced = colorName == lastColor && (now - lastSentAt) < DETECTION_DEBOUNCE_MS;
```

Isso significa:
- a mesma cor nao sera repetida continuamente dentro da janela
- outra cor diferente pode ser enviada imediatamente

#### Saida em dois formatos

```cpp
emitLine(("COCOVISION_COLOR=" + colorName).c_str());
emitLine(colorName.c_str());
```

O firmware emite a mesma informacao em dois formatos:

1. `COCOVISION_COLOR=COLOR_RED`
2. `COLOR_RED`

Interpretacao tecnica:
- o primeiro formato e mais autoexplicativo para debug
- o segundo e o formato mais simples para o parser narrativo

O lado Python atualmente suporta ambos.

#### Atualizacao do debounce

Ao publicar, o firmware memoriza:
- `lastColor`
- `lastSentAt`

## Rotinas de alto nivel

### `runPresentation()`

Sequencia:
1. frente por `FORWARD_MS`
2. pausa por `STOP_MS`
3. giro a direita por `TURN_MS`
4. pausa por `STOP_MS`
5. re por `BACKWARD_MS`
6. pausa por `STOP_MS`
7. emitir `COCOVISION_DONE`

Essa e a rotina cenica da apresentacao inicial do robô.

### `runAction()`

Sequencia:
1. frente por `FORWARD_MS`
2. pausa por `STOP_MS`
3. ativar o sensor (`sensorActive = true`)
4. limpar o estado do debounce de cor
5. emitir `COCOVISION_DONE`

O ponto mais importante aqui e conceitual:
- `ACTION` nao faz a leitura completa
- `ACTION` apenas posiciona o robô e habilita a fase de leitura continua

### `runReturn()`

Sequencia:
1. desligar o sensor (`sensorActive = false`)
2. mover para tras por `FORWARD_MS`
3. pausa por `STOP_MS`
4. emitir `COCOVISION_DONE`

Observacao importante:
- o retorno usa `FORWARD_MS`
- isso garante que o tempo de volta seja exatamente o mesmo do avancar da rotina `ACTION`

Esse detalhe foi escolhido explicitamente para manter simetria temporal na apresentacao.

## Primitivas de movimento

### `moveForward()`

Aciona os dois motores no sentido de avancar.

### `moveBackward()`

Aciona os dois motores no sentido contrario.

### `turnRight()`

Aciona um motor para frente e o outro para tras, gerando rotacao no eixo.

### `stopMotors()`

Executa parada forte:
- PWM zerado
- linhas de direcao em `LOW`

### `setMotorA()` e `setMotorB()`

Sao as primitivas de mais baixo nivel do atuador.

Cada funcao:
- define sentido pelas linhas de direcao
- define velocidade pela linha de enable em PWM

## Pontos criticos e de manutencao

### 1. O firmware e hibrido: atuador + sensor

Diferente do `CocoMag`, este firmware combina:
- locomocao
- protocolo
- sensor de cor

Isso aumenta a importancia de preservar a separacao interna atual.

### 2. O modelo e bloqueante

As rotinas `runPresentation()`, `runAction()` e `runReturn()` usam `delay()`.

Consequencias:
- durante essas rotinas, nao ha processamento concorrente real
- a leitura de comandos e pausada enquanto a rotina esta dentro da propria execucao

Para o uso atual isso e aceitavel e previsivel.

### 3. A leitura de cor so acontece quando `sensorActive == true`

Esse flag e o gate principal do comportamento do robô.

Se essa logica for alterada sem cuidado, a fase de cor pode:
- nunca começar
- nunca terminar
- enviar cores em momentos errados da narrativa

### 4. O debounce de cor e local ao firmware

O sistema hoje possui duas camadas de protecao:
- debounce local no firmware
- controle de aceitacao/limpeza de eventos no Python

As duas camadas se complementam.

### 5. O parser do Python conhece a string `COCOVISION_COLOR=...`

Se esse formato for mudado aqui, `robot_comm.py` precisa acompanhar.

### 6. O fail-fast do sensor e deliberado

Se `tcs.begin()` falhar, o firmware trava em loop.

Isso e tecnicamente simples e operacionalmente util, porque evita um falso positivo de “robô pronto” sem sensor funcional.

### 7. Bluetooth e opcional de verdade

O firmware foi preparado para Bluetooth Classic, mas nao depende dele para funcionar.

Se o build do core nao suportar:
- a serial USB continua operacional
- o log `COCOVISION_BT_UNAVAILABLE` aparece

### 8. O controle de movimento continua sendo temporal

Tal como no `CocoMag`, nao ha feedback de distancia real.

Todos os movimentos dependem de:
- tempo
- PWM
- condicao mecanica real do robô

## Resumo de manutencao

`cocovision.ino` ja esta em um estado tecnicamente bom para o escopo do projeto.

Ele esta praticamente pronto para:
- USB serial
- Bluetooth Classic quando o core ESP32 suportar

Os pontos que mais merecem cuidado em manutencao futura sao:

1. manter o protocolo textual sincronizado com o Python
2. preservar a separacao entre transporte, movimento e sensor
3. calibrar thresholds de cor sem quebrar o fluxo narrativo
4. validar qualquer mudanca de temporizacao em `ACTION` e `RETURN`
5. manter a simetria temporal entre avancar e retornar quando isso for parte da encenacao

Para o contexto atual, o firmware esta simples, coeso e suficientemente robusto para apresentacao, desde que os thresholds de cor e os tempos de movimento estejam calibrados no hardware real.
