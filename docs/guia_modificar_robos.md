# Guia Rapido Para Modificar CocoMag E CocoVision

Este guia e para ajustes pequenos de movimento nos firmwares dos robos. Use com
cuidado: mude uma coisa por vez, grave no ESP32 e teste o comando isolado antes
de rodar a apresentacao inteira.

Arquivos:

- CocoMag: `firmware/cocomag/cocomag.ino`
- CocoVision: `firmware/cocovision/cocovision.ino`

## Regra De Ouro

Antes de mexer:

1. confirme qual robo esta alterando;
2. mude uma constante ou um trecho pequeno;
3. grave no ESP32;
4. teste com `rfcomm_serial_probe.py`;
5. so depois rode `python3 main.py`.

Se mudar movimento, nao mude visao, Python e firmware ao mesmo tempo.

## Mudar Quanto O Robo Anda

O tempo de movimento esta em milissegundos. Quanto maior o valor, mais tempo o
robo anda.

### CocoMag

No `cocomag.ino`, procure:

```cpp
constexpr unsigned long PRESENT_FORWARD_MS = 2000;
constexpr unsigned long PRESENT_BACKWARD_MS = 1500;
constexpr unsigned long ACTION_FORWARD_MS = 3000;
constexpr unsigned long ACTION_POST_TURN_FORWARD_MS = 2000;
constexpr unsigned long ACTION_BACKWARD_MS = 2000;
```

Exemplos:

- quer andar mais para frente no `PRESENT`: aumente `PRESENT_FORWARD_MS`;
- quer voltar menos no `PRESENT`: diminua `PRESENT_BACKWARD_MS`;
- quer que a `ACTION` avance menos no comeco: diminua `ACTION_FORWARD_MS`;
- quer que volte mais no fim da `ACTION`: aumente `ACTION_BACKWARD_MS`.

### CocoVision

No `cocovision.ino`, procure:

```cpp
constexpr unsigned long PRESENT_FORWARD_MS = 2000;
constexpr unsigned long PRESENT_BACKWARD_MS = 1500;
constexpr unsigned long ACTION_FORWARD_MS = 1500;
constexpr unsigned long RETURN_BACKWARD_MS = 1500;
```

Exemplos:

- `ACTION_FORWARD_MS`: quanto o CocoVision anda antes de ler cor;
- `RETURN_BACKWARD_MS`: quanto ele volta depois do video da cor;
- se mudar `ACTION_FORWARD_MS`, normalmente confira se `RETURN_BACKWARD_MS`
  ainda deixa o robo voltar para a posicao esperada.

## Mudar Velocidade

Velocidade principal:

```cpp
constexpr int MOVE_SPEED = 220;
constexpr int TURN_SPEED = 180;
```

- `MOVE_SPEED`: velocidade para andar para frente/tras;
- `TURN_SPEED`: velocidade de giro.

Evite colocar direto em `255` sem testar. Mais velocidade pode dar mais tranco,
mais erro de giro e mais escorregamento.

## Mudar O Que E Frente E Tras

Se o robo anda ao contrario, primeiro confira fios do motor. Se a mecanica ja
esta montada e voce quer corrigir por firmware, use:

```cpp
constexpr bool MOTOR_A_INVERTED = false;
constexpr bool MOTOR_B_INVERTED = true;
```

Essas flags existem nos dois firmwares.

- Se apenas um lado esta invertido, altere so o motor daquele lado.
- Se os dois lados estao invertidos, inverta os dois.
- Depois teste `PRESENT`, porque ele usa frente, giro e re.

Nao altere `setMotorA()` e `setMotorB()` direto para ajustes simples. Use as
flags `MOTOR_A_INVERTED` e `MOTOR_B_INVERTED`.

## Mudar O Giro

### CocoMag

```cpp
constexpr float PRESENT_TARGET_DEGREES = 360.0f;
constexpr float ACTION_TURN_DEGREES = 90.0f;
constexpr float ACTION_TURN_BACK_DEGREES = -90.0f;
```

- `PRESENT_TARGET_DEGREES`: giro da apresentacao;
- `ACTION_TURN_DEGREES`: giro principal da action;
- `ACTION_TURN_BACK_DEGREES`: giro de volta.

Valor positivo gira para um lado. Valor negativo gira para o outro.

### CocoVision

```cpp
constexpr float PRESENT_TARGET_DEGREES = 360.0f;
```

No fluxo atual, o CocoVision usa giro no `PRESENT`. A `ACTION` dele e andar,
parar e ativar leitura de cor.

## Mudar O PRESENT

Procure a funcao:

```cpp
bool runPresentation()
```

Ela e a rotina chamada quando o Python envia:

- `COCOMAG:PRESENT`
- `COCOVISION:PRESENT`

Estrutura comum:

1. anda para frente;
2. para suave;
3. gira usando MPU;
4. anda para tras;
5. para suave;
6. envia `*_DONE`.

Para ajuste simples, prefira mudar constantes de tempo e angulo. Evite mexer na
ordem da funcao perto da apresentacao.

## Mudar O ACTION

### CocoMag

Procure:

```cpp
bool runAction()
```

Fluxo atual:

1. anda para frente;
2. gira 90 graus;
3. anda mais um pouco;
4. gira de volta;
5. aciona servo;
6. anda para tras;
7. envia `COCOMAG_DONE`.

Servo:

```cpp
constexpr int SERVO_BACK_ANGLE = 0;
constexpr int SERVO_FRONT_ANGLE = 180;
constexpr unsigned long ACTION_SERVO_FRONT_HOLD_MS = 2000;
```

- `SERVO_BACK_ANGLE`: posicao recolhida;
- `SERVO_FRONT_ANGLE`: posicao de acao;
- `ACTION_SERVO_FRONT_HOLD_MS`: quanto tempo segura na posicao de acao.

### CocoVision

Procure:

```cpp
bool runAction()
```

Fluxo atual:

1. anda para frente;
2. para;
3. ativa leitura de cor;
4. envia `COCOVISION_DONE`.

Depois disso, o firmware fica esperando detectar `COLOR_BLUE`. Quando detecta,
envia `COLOR_BLUE` e passa para `READY_FOR_RETURN`.

## Mudar O RETURN Do CocoVision

Procure:

```cpp
bool runReturn()
```

Ele e chamado quando o Python envia:

```text
COCOVISION:RETURN
```

Fluxo atual:

1. desativa sensor de cor;
2. anda para tras por `RETURN_BACKWARD_MS`;
3. para;
4. envia `COCOVISION_DONE`.

## Mudar Cor Do CocoVision

A classificacao esta em:

```cpp
String detectDominantColor(...)
```

Mas o fluxo atual da apresentacao so publica:

```cpp
COLOR_BLUE
```

Isso acontece em:

```cpp
void publishColorIfNeeded(const String& colorName)
```

Se quiser mudar para outra cor no futuro, nao basta mudar o firmware. Tambem
precisa ajustar o Python, principalmente `COLOR_VIDEO_PATHS` em `config.py` e o
fluxo esperado da apresentacao.

## Como Testar Sem Rodar Tudo

Com as portas RFCOMM criadas:

```bash
source .venv/bin/activate
python3 rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:PRESENT
python3 rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:ACTION
python3 rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:PRESENT
python3 rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:ACTION --listen-seconds 8
python3 rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:RETURN
```

Depois de qualquer teste estranho, mande reset:

```bash
python3 rfcomm_serial_probe.py --port /dev/rfcomm0 --command COCOMAG:RESET
python3 rfcomm_serial_probe.py --port /dev/rfcomm1 --command COCOVISION:RESET
```

## O Que Nao Mexer Perto Da Apresentacao

Evite mexer sem tempo para teste:

- nomes dos comandos: `PRESENT`, `ACTION`, `RETURN`, `RESET`;
- mensagens `COCOMAG_DONE` e `COCOVISION_DONE`;
- state machine local;
- thresholds de cor;
- logica de reset;
- pinos de motor, I2C e Bluetooth;
- parametros de MPU se o giro ja esta calibrado.

## Checklist Depois De Mudar Movimento

1. O robo para quando termina?
2. O `DONE` chegou no terminal?
3. O reset funciona?
4. O robo nao ficou invertido?
5. O giro ainda aponta para o lado certo?
6. A apresentacao completa ainda sincroniza com o Python?

Se uma mudanca pequena piorou o comportamento, volte a constante anterior e
teste de novo. Em robos de palco, estabilidade vale mais do que movimento
perfeito.
