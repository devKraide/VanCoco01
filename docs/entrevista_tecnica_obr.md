# Preparacao Para Entrevista Tecnica OBR - VanCoco

Este documento e um material de apoio para explicar o VanCoco em uma entrevista
tecnica da OBR. A ideia nao e decorar palavra por palavra, mas entender o
raciocinio por tras do projeto e conseguir explicar com seguranca como cada
parte funciona.

## 1. Introducao Do Projeto

O VanCoco e um sistema de apresentacao interativa que integra visao
computacional, videos, robos fisicos e uma narrativa controlada por software.
O objetivo nao foi construir apenas um robo que executa uma tarefa isolada, mas
um sistema completo em que a acao dos atores, a reproducao de midia e os robos
ficam sincronizados.

Em termos simples, o notebook roda uma aplicacao Python que observa a camera,
reconhece gestos especificos, toca videos em tela cheia e envia comandos para
dois robos: CocoMag e CocoVision. Cada robo executa a sua parte fisica e devolve
um sinal de fim, como `COCOMAG_DONE` ou `COCOVISION_DONE`, para que a narrativa
continue.

A proposta artistica do projeto e transformar a apresentacao em uma cena
interativa. Os gestos nao sao botoes escondidos: eles fazem parte da linguagem
da apresentacao. A mao aberta, o indicador, o sinal de vitoria, o polegar, os
punhos e a oracao sao usados como gatilhos visuais para mudar de etapa. Ao mesmo
tempo, os robos nao ficam soltos; eles entram no momento certo do roteiro.

Uma frase boa para abrir a explicacao para os juizes:

> O VanCoco e uma apresentacao robotica sincronizada. O computador e o
> orquestrador: ele interpreta gestos pela camera, controla os videos e chama os
> robos no momento certo. Os robos executam a parte fisica e respondem para a
> state machine continuar com seguranca.

## 2. Arquitetura Geral Do Sistema

### Visao geral

A arquitetura foi separada em camadas para evitar que tudo ficasse misturado em
um unico arquivo. A aplicacao principal fica no notebook Ubuntu e os robos rodam
firmwares proprios em ESP32.

Componentes principais:

- Notebook com Ubuntu 24.04 LTS.
- Aplicacao Python.
- OpenCV para camera, processamento de imagem e ArUco.
- MediaPipe Hands e Pose para landmarks.
- VLC/libVLC para tocar videos com audio.
- PySide6 para janela fullscreen e overlay.
- ESP32 no CocoMag e no CocoVision.
- Comunicacao Bluetooth Classic exposta como portas RFCOMM.
- Arduino Nano como fallback central por USB.
- State machine para controlar a ordem da apresentacao.

### Como os modulos Python se dividem

`main.py` e o orquestrador. Ele inicializa tudo, roda o loop principal e decide
qual handler executar conforme o estado atual.

`story_engine.py` guarda a logica narrativa: qual gesto e aceito agora, qual
video vem depois, qual robo deve receber comando e qual resposta libera a
proxima etapa.

`state_manager.py` guarda o estado operacional da aplicacao: se esta aquecendo,
esperando gesto, tocando video, aguardando robo, esperando cor ou esperando
retorno.

`vision.py` transforma camera em sinais de alto nivel: gestos, marker ArUco e
motivos de rejeicao.

`gesture_mapper.py` estabiliza o gesto para evitar disparos acidentais. Ele so
aceita depois de frames consecutivos e usa latch para nao repetir o mesmo gesto
enquanto a mao continua parada.

`media_controller.py` cuida da janela, tela preta, overlay e VLC. Ele usa um
player persistente para nao recriar o VLC a cada video.

`robot_comm.py` abre as portas seriais/RFCOMM, envia comandos, le respostas em
threads e transforma texto vindo dos robos em eventos internos.

### Por que usar state machine

A decisao principal do projeto foi nao deixar cada parte decidir sozinha. O
video nao toca simplesmente porque apareceu uma mao; o gesto precisa estar
correto para o estado atual. O robo nao avanca a historia sozinho; ele responde
`DONE`, e o Python decide se esse `DONE` ainda faz sentido naquele momento.

Isso e importante em apresentacao ao vivo, porque a camera pode ver algo fora de
hora, o Bluetooth pode atrasar, e o robo pode mandar uma mensagem que ja nao
vale mais para aquele estado. A state machine funciona como um filtro de
coerencia.

## 3. Visao Computacional

### Como a camera vira gesto

A camera e aberta pelo OpenCV. No Ubuntu, o sistema tenta usar backend V4L2,
configura resolucao de 640x360, buffer pequeno e FPS alvo de 30. O buffer pequeno
foi importante para reduzir latencia, porque em apresentacao ao vivo e melhor
processar um frame recente do que um frame antigo.

Depois da captura, o frame e redimensionado por `VISION_PROCESSING_SCALE` e
convertido de BGR para RGB para o MediaPipe. O sistema so roda o que precisa:

- se o estado espera gesto de mao, roda Hands;
- se espera `PRAYER_HANDS`, roda Pose;
- se espera marker/lupa, roda ArUco;
- se nao precisa de camera naquele estado, nao processa visao.

Essa escolha reduz custo no loop principal e deixa o sistema mais previsivel.

### Landmarks e heuristicas

O MediaPipe entrega landmarks da mao. O projeto nao usa uma rede treinada nossa
para classificar gestos; ele usa heuristicas geometricas em cima dos landmarks.

Para cada mao, o codigo calcula um `FingerState`, com informacoes como:

- se os landmarks principais estao dentro do frame;
- se o polegar esta aberto;
- se o polegar esta para cima;
- se indicador, medio, anelar e mindinho estao abertos;
- alcance relativo de cada dedo;
- distancia entre dedos;
- quantidade de dedos dobrados.

As distancias sao normalizadas pelo tamanho da palma. Isso ajuda porque a mao
pode estar mais perto ou mais longe da camera.

### ROI e qualidade da mao

O sistema usa ROI para evitar aceitar gestos fora da area esperada. Ele tambem
rejeita mao parcial ou muito pequena. Alguns motivos de rejeicao aparecem nos
logs e no overlay, por exemplo:

- `no_hand`: nenhuma mao detectada;
- `outside_roi`: mao fora da area;
- `low_quality_hand`: mao cortada ou landmarks ruins;
- `palm_too_small`: mao muito distante;
- `no_candidate_matched_expected`: a mao apareceu, mas nao bateu com o gesto
  esperado.

Isso ajuda muito na entrevista, porque mostra que o projeto nao trata a visao
como uma caixa preta. Ele tenta explicar por que rejeitou.

### Debounce e latch

Depois que `vision.py` detecta um gesto bruto, `gesture_mapper.py` aplica
estabilizacao. O gesto precisa aparecer por `GESTURE_STABLE_FRAMES` frames e o
mesmo gesto nao e aceito de novo enquanto estiver latched.

Tambem existe tolerancia para poucos frames sem deteccao:
`GESTURE_MISSING_FRAME_TOLERANCE`. Isso evita que uma falha de um frame zere
imediatamente o gesto quando a camera oscila.

Explicacao simples para juiz:

> O MediaPipe pode oscilar por iluminacao, movimento ou oclusao. Entao nos
> separamos deteccao de aceitacao. Detectar em um frame nao basta; o gesto precisa
> ficar estavel e estar correto para o estado atual.

### Overlay e calibracao

Durante estados que esperam gesto, o overlay mostra a camera, o gesto esperado,
o gesto bruto, o motivo de rejeicao e status dos robos. Isso foi criado porque
em ensaio era dificil saber se o problema era a mao, a camera, o estado errado
ou o robo.

O `VISION_CALIBRATION_VIEW` tambem desenha ROI, landmarks, pose e estatisticas
de rejeicao. Esse recurso nao e parte artistica da apresentacao; e ferramenta
operacional para calibrar e diagnosticar.

### Gestos

#### HAND_OPEN

Usado para iniciar o primeiro video. A heuristica olha se varios dedos estao
estendidos e se ha abertura suficiente. Ela tambem tenta evitar confundir mao
aberta com polegar ou punho.

#### POINT

Usado para o segundo video. O sistema espera indicador estendido e outros dedos
dobrados. Uma dificuldade real encontrada foi que, quando a mao fica muito de
frente para a camera, os dedos dobrados podem parecer mais compridos nos
landmarks 2D. Por isso o `POINT` fica mais confiavel com um pequeno angulo da
mao. Essa e uma limitacao natural de landmarks projetados em imagem.

#### V_SIGN

Usado para liberar a acao do CocoMag. A regra exige indicador e medio abertos,
anelar e mindinho fechados, e evita confundir com polegar para cima.

#### THUMB_UP

Usado para disparar o video 5. A regra olha se o polegar esta para cima e se os
outros dedos nao estao abertos.

#### CLOSED_FIST

Usado para disparar o video 6. A regra exige dedos fechados e evita aceitar se o
indicador aparece aberto ou se o polegar parece `THUMB_UP`.

#### DOUBLE_CLOSED_FIST

Usado como alternativa ao marker na etapa do video 8. O sistema exige duas maos,
ambas como punho fechado, separadas entre si, dentro da area esperada e estaveis
por mais frames. Isso reduz falso positivo, porque duas maos e um gesto
simultaneo sao mais dificeis de acontecer por acaso.

#### PRAYER_HANDS

Usado para o final. Diferente dos outros, ele usa MediaPipe Pose, nao so Hands.
O sistema olha os pulsos e ombros: pulsos proximos, alinhados ao centro do
corpo, em uma faixa de altura do peito e nao acima do nariz. No estado final, o
`PRAYER_HANDS` ganha prioridade para evitar que seja roubado por um gesto de mao.

### Problemas reais encontrados na visao

Problemas que fazem sentido explicar:

- MediaPipe oscila em movimento rapido.
- Alguns gestos dependem do angulo da mao.
- `POINT` frontal pode ser rejeitado porque a projecao 2D dos dedos dobrados
  parece longa.
- Iluminacao e distancia mudam a qualidade dos landmarks.
- Mao cortada na borda do frame gera falso positivo se nao houver filtro.

Solucoes adotadas:

- ROI para limitar a area de aceitacao.
- Filtros de qualidade de mao.
- Debounce por frames.
- Latch para nao repetir gesto.
- Motivos de rejeicao e overlay para calibracao.
- Processamento por estado, evitando rodar detectores desnecessarios.

## 4. State Machine

### Ideia central

A state machine e o que impede o sistema de aceitar qualquer coisa a qualquer
momento. Cada etapa sabe exatamente qual entrada espera.

Estados operacionais principais:

- `WARMING_UP`: camera e MediaPipe aquecendo.
- `IDLE_BLACK_SCREEN`: esperando gesto inicial.
- `PLAYING_VIDEO`: video em reproducao.
- `WAITING_PRESENTATION`: aguardando apresentacao dos dois robos.
- `WAITING_COCOMAG_ACTION`: aguardando `V_SIGN`.
- `WAITING_COCOMAG_ACTION_COMPLETION`: aguardando `COCOMAG_DONE`.
- `WAITING_VIDEO5_TRIGGER`: aguardando `THUMB_UP`.
- `WAITING_COCOVISION_ACTION_COMPLETION`: aguardando `COCOVISION_DONE`.
- `WAITING_COLOR`: aguardando `COLOR_BLUE`.
- `WAITING_VIDEO6_TRIGGER`: aguardando `CLOSED_FIST`.
- `WAITING_COCOVISION_RETURN_COMPLETION`: aguardando retorno do CocoVision.
- `WAITING_VIDEO8_TRIGGER`: aguardando ArUco/lupa ou `DOUBLE_CLOSED_FIST`.
- `WAITING_VIDEO9_TRIGGER`: aguardando `PRAYER_HANDS`.

### Fluxo real da apresentacao

1. `HAND_OPEN` toca `video1.mp4`.
2. `POINT` toca `video2.mp4`.
3. Depois do video 2, o Python envia `COCOMAG:PRESENT` e `COCOVISION:PRESENT`.
4. Quando os dois respondem `DONE`, toca `video3.mp4`.
5. `V_SIGN` envia `COCOMAG:ACTION`.
6. `COCOMAG_DONE` toca `video4.mp4`.
7. `THUMB_UP` toca `video5.mp4`.
8. `CLOSED_FIST` toca `video6.mp4`.
9. Depois do video 6, o Python envia `COCOVISION:ACTION`.
10. `COCOVISION_DONE` libera a leitura de cor.
11. `COLOR_BLUE` toca `video7.mp4`.
12. Depois do video 7, o Python envia `COCOVISION:RETURN`.
13. `COCOVISION_DONE` libera a etapa do video 8.
14. ArUco/lupa ou `DOUBLE_CLOSED_FIST` toca `video8.mp4`.
15. `PRAYER_HANDS` toca `video9a.mp4` ou `video9b.mp4`, conforme `FINAL_OUTCOME`.

### Como evita erros

O sistema evita erro de tres formas:

- so constroi `VisionRequest` para o que o estado atual precisa;
- so aceita gesto se `StoryEngine` disser que e o gesto esperado;
- so consome evento de robo se aquele evento faz sentido naquele estado.

Exemplo: se o CocoVision mandar `COLOR_BLUE` antes da fase de cor, o Python nao
usa essa cor para avancar a narrativa. E quando entra na fase de cor, o sistema
limpa eventos antigos para nao consumir uma leitura atrasada.

## 5. Sistema De Fallback

### Por que o fallback foi criado

Apresentacao ao vivo tem risco: Bluetooth pode atrasar, a camera pode nao pegar
um gesto, um sensor pode falhar ou um robo pode nao responder no tempo esperado.
O fallback foi criado para manter a apresentacao recuperavel sem quebrar a
ordem da state machine.

O ponto mais importante: o fallback nao e um atalho solto. Ele entra pela mesma
logica de estado. Se o sistema esta esperando um gesto, o fallback injeta aquele
gesto esperado. Se esta esperando um robo, injeta o `DONE` daquele robo. Se esta
esperando cor, injeta `COLOR_BLUE`. Se esta esperando o video 8, injeta o marker.

### Fallback central

O fallback central e um Arduino Nano com sensor ultrassonico. Ele fica ligado
por USB e manda apenas uma linha para o Python:

```text
CENTRAL_FALLBACK_TRIGGER
```

O Python recebe essa linha por `robot_comm.py`, coloca em uma fila e o `main.py`
decide o que esse pulso significa no estado atual.

### Ultrassonico local nos robos

CocoMag e CocoVision tambem possuem leitura ultrassonica local. No firmware, o
ultrassonico chama `handleTrigger("ULTRA", RequestedCommand::ANY)` quando detecta
presenca abaixo do limite e respeita um latch de liberacao. Ou seja, ele nao
fica disparando em loop enquanto a mao/objeto continua perto.

Isso cria redundancia: o computador tem o fallback central, e os robos tambem
tem uma forma local de disparar a proxima acao permitida pela state machine
embarcada.

### Segurança operacional

O fallback foi pensado para robustez, nao para esconder erro. Ele ajuda a
continuar a apresentacao se uma parte falhar, mas os logs mostram quando ele foi
usado, por exemplo `CENTRAL_FALLBACK_ACCEPTED`. Assim a equipe consegue saber
depois se a etapa passou pelo caminho principal ou pelo caminho de recuperacao.

## 6. Robos

### CocoMag

#### Hardware e transporte

CocoMag usa ESP32, Bluetooth Classic, dois motores DC com driver L298N, servo,
sensor ultrassonico e MPU6050. A comunicacao com o notebook e feita por
Bluetooth/RFCOMM, que no Ubuntu aparece como `/dev/rfcomm0`.

O firmware aceita comandos textuais:

- `COCOMAG:PRESENT`
- `COCOMAG:ACTION`
- `COCOMAG:RESET`

E responde eventos como:

- `COCOMAG_DONE`
- `COCOMAG_RESET_DONE`
- logs de MPU e rotacao.

#### Controle de movimento

Os motores usam PWM. O firmware tem rampa de aceleracao (`rampDrive`) e parada
suave (`softStopDrive`) para reduzir tranco mecanico. Um dos motores pode ser
invertido por constante, porque na montagem fisica os lados podem ficar
espelhados.

Para giros, o CocoMag usa MPU6050. Antes de girar, ele calibra o bias do eixo Z,
integra velocidade angular ao longo do tempo e para quando atinge o angulo alvo
ou quando estoura timeout. O giro da apresentacao e de 360 graus; na acao ele
usa giros de 90 e -90 graus.

#### Servo

O servo do CocoMag fica no pino configurado e tem duas posicoes principais:
`SERVO_BACK_ANGLE` e `SERVO_FRONT_ANGLE`. Na rotina `ACTION`, ele vai para a
frente por um tempo e depois o robo executa o retorno. O reset coloca o servo de
volta para a posicao traseira quando o robo esta parado.

#### State machine local

O firmware do CocoMag tambem tem uma state machine local:

- `READY_FOR_PRESENT`
- `READY_FOR_ACTION`
- `COMPLETED`

Isso impede, por exemplo, que `ACTION` rode antes de `PRESENT`. O Python controla
a narrativa geral, mas o firmware tambem se protege contra comandos fora de
ordem.

#### Reset

O reset para motores, limpa latch do ultrassonico e volta para
`READY_FOR_PRESENT`. Se o reset chega durante uma rotina, o firmware marca
`resetRequested`, aborta com seguranca e responde reset quando possivel.

### CocoVision

#### Hardware e transporte

CocoVision tambem usa ESP32, Bluetooth Classic, motores DC com L298N, MPU6050 e
ultrassonico. Alem disso, tem sensor de cor TCS34725. No Ubuntu, normalmente
fica em `/dev/rfcomm1`.

Comandos aceitos:

- `COCOVISION:PRESENT`
- `COCOVISION:ACTION`
- `COCOVISION:RETURN`
- `COCOVISION:COLOR_CONFIRMED`
- `COCOVISION:RESET`

Respostas principais:

- `COCOVISION_DONE`
- `COLOR_BLUE`
- `COCOVISION_COLOR_CONFIRMED_DONE`
- `COCOVISION_RESET_DONE`

#### Movimento e MPU

Assim como o CocoMag, o CocoVision usa MPU6050 para giro da rotina de
apresentacao. O firmware calibra bias, integra o eixo Z e usa timeout para nao
ficar preso tentando girar para sempre.

Na rotina `ACTION`, o CocoVision avanca por um tempo e depois ativa a leitura de
cor. Na rotina `RETURN`, ele anda para tras e responde `COCOVISION_DONE`.

#### Sensor de cor

O TCS34725 mede valores de vermelho, verde, azul e clear. O firmware calcula
razoes por clear e usa um fator de dominancia. No fluxo atual, so `COLOR_BLUE`
e publicado para o Python. Isso evita que qualquer leitura de cor vire evento
narrativo.

Depois que a cor e enviada, o firmware desativa o sensor para aquela etapa e
vai para `READY_FOR_RETURN`.

#### State machine local

Estados locais do CocoVision:

- `READY_FOR_PRESENT`
- `READY_FOR_ACTION`
- `WAITING_FOR_COLOR`
- `READY_FOR_RETURN`
- `COMPLETED`

Isso faz o firmware rejeitar comando fora de ordem. Por exemplo, `RETURN` so faz
sentido depois da cor.

#### Sincronizacao com Python

O Python nao fica tentando adivinhar quanto tempo a rotina do robo demorou. Ele
espera o `DONE`. Essa foi uma decisao importante: usar evento real em vez de
tempo fixo no notebook. Se o robo atrasar um pouco, a narrativa espera.

## 7. Overlay Operacional

O overlay foi criado porque, em ensaio, quando algo falhava, nao era claro se o
problema estava na camera, no estado da narrativa, no Bluetooth ou no robo.

Ele mostra:

- estado narrativo amigavel;
- estado interno do sistema;
- gesto esperado;
- gesto bruto detectado;
- motivo de rejeicao;
- ultimo evento;
- ultimo comando enviado;
- ultimo retorno recebido;
- status de conexao dos robos;
- quais robos ainda faltam responder.

Modos:

- `CAMERA_AND_LOGS`: usado quando o sistema espera gesto ou marker. Mostra
  preview da camera e logs.
- `LOGS_ONLY`: usado quando o sistema espera robo, cor ou retorno. Nao precisa
  mostrar preview porque a camera nao e a entrada principal.
- `HIDDEN`: usado durante video. A apresentacao fica limpa, sem debug na tela.

Do ponto de vista de competicao, o overlay mostra maturidade operacional: a
equipe nao depende de adivinhar o que aconteceu. Ela consegue observar o estado
do sistema.

## 8. Desenvolvimento Do Projeto

### Problemas reais encontrados

#### MediaPipe e gestos

O maior desafio da visao foi transformar landmarks em gestos confiaveis em
condicoes reais. A mao nem sempre esta no mesmo angulo, a iluminacao muda e os
landmarks podem oscilar. Alguns gestos parecidos, como `POINT`, `V_SIGN` e
`HAND_OPEN`, exigiram heuristicas mais cuidadosas.

O `POINT` frontal foi um caso importante: com a palma de frente, os dedos
dobrados podem parecer mais longos na imagem, entao o sistema pode rejeitar como
`open_hand_like` ou `other_fingers_not_folded`. A solucao operacional foi
orientar o gesto com um pouco de angulo e manter logs/overlay para calibracao.

#### Bluetooth/RFCOMM

Bluetooth no Ubuntu funciona, mas precisa de rotina: parear, confiar no
dispositivo, criar `/dev/rfcomm0` e `/dev/rfcomm1`, e exportar as portas. Por
isso foi criado um roteiro de apresentacao rapida, com `git pull`, venv,
`rfcomm bind` e `python3 main.py`.

Tambem criamos `rfcomm_serial_probe.py` para testar comandos isolados sem rodar
a apresentacao inteira.

#### VLC e video

O VLC foi escolhido porque lida bem com videos com audio. A integracao com Qt
exigiu um widget nativo e ajustes de plataforma. O player e persistente, mas
trocar midia ainda pode causar pequeno engasgo no inicio. Em vez de mexer sem
criterio antes da apresentacao, mantivemos logs e uma integracao estavel.

#### Sincronizacao

Um problema comum em projeto com video e robo e sincronizar por tempo fixo.
Aqui evitamos isso nos robos: o Python manda comando e espera `DONE`. Isso
melhora robustez, porque a acao fisica pode variar um pouco sem quebrar o
roteiro.

#### Firmware e mecanica

No firmware, os cuidados principais foram:

- reset para voltar a estado conhecido;
- rampas de motor para reduzir tranco;
- soft stop;
- calibracao do MPU antes de giros;
- timeout de rotacao;
- logs de progresso;
- ultrassonico com latch para nao repetir trigger.

### Processo iterativo

O projeto foi melhorado por ensaio e auditoria. Quando um gesto falhava, a
equipe nao apenas "baixava threshold"; primeiro olhava o motivo de rejeicao,
testava no overlay e avaliava falso positivo. Quando um robo nao respondia, era
testado isoladamente pela serial/RFCOMM. Quando havia risco de apresentacao, a
prioridade era manter o sistema recuperavel.

## 9. Robustez E Confiabilidade

### Medidas de robustez

- State machine central no Python.
- State machine local nos firmwares.
- Debounce e latch de gestos.
- ROI e filtros de qualidade da mao.
- Eventos `DONE` em vez de tempos fixos para robos.
- Reset inicial dos robos antes do idle.
- Fallback central por USB.
- Ultrassonico local nos robos.
- Logs de performance e eventos.
- Overlay operacional.
- Testes isolados com `rfcomm_serial_probe.py`.
- Branches separadas por mudanca.
- Tags estaveis como `obr-stable-v1` e `obr-stable-v1.1`.
- Branch de recuperacao quando necessario.

### Como explicar freeze de versao

Uma boa resposta:

> Antes da apresentacao, a gente evita mexer em heuristica ou firmware sem teste.
> Quando uma versao funciona no hardware, ela vira referencia. Mudancas entram em
> branch separada, e a gente so marca tag estavel depois de rodar o fluxo
> completo. Isso e importante porque uma alteracao pequena em visao ou Bluetooth
> pode melhorar um caso e quebrar outro.

### O que ainda nao e perfeito

E importante nao vender o projeto como infalivel. Pontos honestos:

- gestos dependem de iluminacao, distancia e angulo da mao;
- Bluetooth pode precisar recriar bind;
- VLC pode ter pequeno engasgo ao iniciar video;
- MPU por integracao tem drift, entao usamos calibracao, tolerancia e timeout;
- fallback existe porque apresentacao ao vivo precisa de plano B.

Essa honestidade costuma ser bem vista quando vem acompanhada de solucao.

## 10. Possiveis Perguntas Dos Juizes

### 1. Qual e a ideia principal do projeto?

Resposta sugerida:

> A ideia e uma apresentacao robotica interativa. O notebook interpreta gestos dos
> atores por visao computacional, toca videos e sincroniza dois robos fisicos.
> Nao e so uma sequencia de videos nem so um robo autonomo; e uma integracao entre
> narrativa, visao e robos embarcados.

### 2. Quem controla a narrativa?

> A narrativa e controlada pelo Python, principalmente por `story_engine.py` e
> `main.py`. Os robos executam comandos e respondem eventos, mas quem decide se
> o fluxo pode avancar e a state machine do notebook.

### 3. Por que usar uma state machine?

> Porque a apresentacao tem ordem. Um `COLOR_BLUE` so vale na fase de cor, um
> `COCOMAG_DONE` so vale quando estamos esperando o CocoMag, e um gesto so deve
> funcionar na etapa certa. A state machine evita que uma entrada fora de hora
> quebre o roteiro.

### 4. Como voces reconhecem gestos?

> Usamos MediaPipe para obter landmarks da mao e da pose. Depois aplicamos
> heuristicas geometricas: alcance dos dedos, dedos dobrados, distancias entre
> landmarks e posicao dentro da ROI. O gesto bruto ainda passa por debounce antes
> de ser aceito.

### 5. Por que nao usar teclado ou controle manual?

> O objetivo era integrar o gesto ao conceito da apresentacao. Ainda temos
> fallback para recuperacao, mas o caminho principal e autonomo: camera detecta,
> state machine valida, video ou robo avanca.

### 6. Como o sistema evita falso positivo de gesto?

> Primeiro, so processamos o gesto esperado para o estado atual. Depois, usamos
> ROI e qualidade da mao. Por fim, o `GestureMapper` exige estabilidade por
> frames e usa latch para nao repetir o mesmo gesto.

### 7. O que acontece se o robo nao responder?

> O sistema nao trava imediatamente em codigo, mas fica aguardando o evento real
> ou um fallback. Temos o fallback central por USB, que injeta o evento esperado
> daquele estado. O importante e que ele ainda passa pela state machine.

### 8. Como funciona o fallback central?

> E um Arduino Nano com sensor ultrassonico. Quando detecta presenca, manda
> `CENTRAL_FALLBACK_TRIGGER` pela serial USB. O Python recebe isso e interpreta de
> acordo com o estado atual: pode virar gesto esperado, `DONE` de robo, cor azul
> ou marker do video 8.

### 9. O fallback nao tira autonomia do projeto?

> O caminho principal continua autonomo. O fallback e uma camada de robustez para
> apresentacao ao vivo. Ele nao decide a narrativa sozinho; ele apenas simula a
> entrada que a state machine ja estava esperando. Isso e mais parecido com um
> modo de recuperacao do que com controle manual livre.

### 10. Como os robos se comunicam com o computador?

> Por Bluetooth Classic no ESP32. No Ubuntu, criamos portas RFCOMM, como
> `/dev/rfcomm0` para CocoMag e `/dev/rfcomm1` para CocoVision. O Python abre
> essas portas com `pyserial`, envia linhas de texto como `COCOMAG:ACTION` e le
> respostas como `COCOMAG_DONE`.

### 11. Por que protocolo textual?

> Porque e simples de debugar. A gente consegue abrir uma serial, ver exatamente
> `COCOVISION_DONE` ou `COLOR_BLUE`, testar com `rfcomm_serial_probe.py` e
> diagnosticar sem ferramenta especial.

### 12. Como o CocoMag controla movimento?

> Ele usa dois motores DC com driver L298N, PWM, rampas de aceleracao e parada
> suave. Para giros, usa MPU6050: calibra o bias do gyro Z, integra velocidade
> angular e para quando chega no angulo ou quando da timeout.

### 13. Para que serve o servo no CocoMag?

> O servo faz parte da rotina de acao. Ele tem uma posicao traseira de repouso e
> uma posicao frontal durante a acao. No reset, quando o robo esta parado, ele
> volta para a posicao segura.

### 14. Como o CocoVision detecta cor?

> Ele usa TCS34725. O firmware le vermelho, verde, azul e clear, calcula
> proporcoes e aplica uma regra de dominancia. No fluxo atual, so `COLOR_BLUE`
> e publicado para o Python.

### 15. O que e `PRAYER_HANDS` tecnicamente?

> E um gesto final baseado em pose, nao apenas mao. O sistema compara os pulsos e
> ombros: pulsos proximos, alinhados ao centro do corpo e na altura do peito. No
> estado final ele tem prioridade para nao ser confundido com gesto de mao.

### 16. Como voces depuram durante a apresentacao?

> Pelo overlay. Ele mostra estado atual, gesto esperado, motivo de rejeicao,
> ultimo comando enviado, ultimo retorno e status dos robos. Durante video o
> overlay fica oculto para nao atrapalhar a apresentacao.

### 17. Por que usar VLC?

> Porque precisavamos tocar videos com audio em tela cheia de forma confiavel. O
> VLC/libVLC ja resolve muitos formatos de midia. A integracao com PySide6 da uma
> janela controlada pelo nosso app.

### 18. O que foi mais dificil?

> A parte mais dificil foi integrar tudo em tempo real. Cada parte isolada
> funcionava, mas o desafio era sincronizar camera, video, Bluetooth, robos e
> fallback sem uma entrada fora de hora quebrar a narrativa.

### 19. Como voces testam?

> Testamos em camadas. Primeiro comandos isolados via `rfcomm_serial_probe.py`.
> Depois gestos pelo overlay, olhando motivos de rejeicao. Depois fluxo parcial
> por etapas e, por fim, o fluxo completo com videos e robos. Antes da
> apresentacao, evitamos alterar heuristicas sem retestar os gestos principais.

### 20. Se pudessem evoluir o projeto, o que fariam?

> Eu melhoraria a robustez da visao com coleta de exemplos reais dos nossos
> gestos e talvez um classificador treinado, mas manteria a state machine. Tambem
> documentaria ainda mais os testes de hardware e automatizaria o checklist de
> Bluetooth antes da apresentacao.

## 11. Conclusao

O VanCoco foi importante porque juntou varias areas de robotica em um projeto so:
software, visao computacional, comunicacao, firmware, sensores, atuadores,
midia e operacao em tempo real.

O principal aprendizado tecnico foi que um sistema de competicao nao pode ser
apenas "funciona uma vez". Ele precisa ser explicavel, recuperavel e observavel.
Por isso o projeto tem state machine, logs, overlay, fallbacks, resets,
protocolo textual e separacao entre modulos.

Uma boa conclusao para entrevista:

> O que eu mais aprendi no VanCoco foi pensar como sistema completo. Nao bastava
> reconhecer um gesto ou fazer um robo andar. A gente precisava garantir que cada
> parte conversasse com a outra, que os erros fossem visiveis, e que a
> apresentacao pudesse continuar mesmo se uma entrada falhasse. Para mim, essa e
> a parte mais robotica do projeto: integrar percepcao, decisao e acao no mundo
> real.
