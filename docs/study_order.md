# Ordem recomendada de estudo do projeto

## Se eu fosse começar do zero para dominar este projeto, eu estudaria nesta ordem

### 1. `README.md`

Comecaria pelo `README.md` para entender:
- o objetivo geral do sistema
- o fluxo narrativo completo
- os robos envolvidos
- os videos esperados
- como o projeto roda no Linux e no macOS
- como USB e RFCOMM entram na operacao

Sem isso, o resto do codigo fica sem contexto.

### 2. `docs/config.md`

Depois eu iria para `docs/config.md`.

Motivo:
- `config.py` define o vocabulário do projeto
- estados, gestos, videos, comandos dos robos e flags vivem ali

Se voce entender `config.py`, o resto dos arquivos fica muito mais legivel.

### 3. `docs/story_engine.md`

Em seguida eu estudaria `docs/story_engine.md`.

Motivo:
- esse arquivo explica a narrativa real do sistema
- mostra em que ordem os gestos, robos e videos se conectam
- deixa claro o que o projeto "faz"

Esse e o melhor ponto para entender a historia codificada no sistema.

### 4. `docs/state_manager.md`

Depois eu iria para `docs/state_manager.md`.

Motivo:
- ele mostra os estados operacionais do app
- ajuda a separar "logica narrativa" de "estado de execucao"

Aqui a arquitetura comeca a ficar clara.

### 5. `docs/main.md`

Com a narrativa e os estados entendidos, eu estudaria `docs/main.md`.

Motivo:
- `main.py` e o orquestrador
- ele conecta visao, engine, player e robos
- aqui da para entender o ciclo real de execucao do app

Esse e o ponto em que tudo se encaixa.

### 6. `docs/vision.md`

Depois eu iria para `docs/vision.md`.

Motivo:
- aqui vivem os inputs visuais reais
- gestos, ArUco e `PRAYER_HANDS` saem daqui

So faz sentido estudar isso depois de entender quem consome esses sinais.

### 7. `docs/gesture_mapper.md`

Na sequencia, eu estudaria `docs/gesture_mapper.md`.

Motivo:
- ele explica a estabilizacao temporal dos gestos
- mostra por que detectar um gesto nao e o mesmo que aceita-lo no fluxo

Esse arquivo e pequeno, mas muito importante para confiabilidade.

### 8. `docs/media_controller.md`

Depois eu iria para `docs/media_controller.md`.

Motivo:
- ele explica a camada de apresentacao visual
- integra Qt, VLC, fullscreen, teclado e mock video

Esse modulo e importante para execucao, mas nao e o melhor ponto de entrada conceitual.

### 9. `docs/robot_comm.md`

Depois eu estudaria `docs/robot_comm.md`.

Motivo:
- aqui entra o mundo fisico dos robos
- explica USB, RFCOMM, eventos `DONE` e eventos de cor

Eu deixaria esse modulo para depois porque ele faz mais sentido quando o fluxo narrativo ja estiver claro.

### 10. Firmwares dos robos

Por fim, eu estudaria os firmwares:

- `docs/cocomag.ino.md`
- `docs/cocovision.ino.md`

Motivo:
- eles explicam a parte embarcada e mecanica
- mostram o que cada robô faz fisicamente
- detalham o protocolo do ponto de vista do ESP32

Eu deixaria os firmwares por ultimo porque eles sao muito mais faceis de entender quando voce ja conhece:
- o fluxo da historia
- os estados do app
- os comandos enviados pelo Python

### 11. Ferramenta auxiliar de bancada

Por ultimo, como apoio operacional, eu leria:

- `docs/cocovision_serial_reader.md`

Motivo:
- ele nao e central para a arquitetura
- e mais uma ferramenta de debug do que parte do fluxo principal

## Resumo curto da ordem

1. `README.md`
2. `docs/config.md`
3. `docs/story_engine.md`
4. `docs/state_manager.md`
5. `docs/main.md`
6. `docs/vision.md`
7. `docs/gesture_mapper.md`
8. `docs/media_controller.md`
9. `docs/robot_comm.md`
10. `docs/cocomag.ino.md`
11. `docs/cocovision.ino.md`
12. `docs/cocovision_serial_reader.md`

## Racional dessa ordem

A logica dessa trilha e:

1. entender primeiro o sistema por fora
2. depois entender a narrativa e os estados
3. depois entender a orquestracao do app
4. depois entender entradas e saídas
5. por ultimo entender hardware e ferramentas auxiliares

Se eu tivesse que resumir em uma frase:

> primeiro eu entenderia o que o sistema faz, depois como ele decide, depois como ele executa, e por fim como ele conversa com o hardware.
