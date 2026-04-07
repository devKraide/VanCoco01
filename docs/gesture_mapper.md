# gesture_mapper.py

## Visao geral

`gesture_mapper.py` e a camada de estabilizacao entre a deteccao bruta de gestos e o restante do fluxo narrativo.

O arquivo recebe um gesto identificado pela visao e decide se ele ja esta estavel o suficiente para ser aceito pelo sistema. Quando aceita, devolve um objeto estruturado contendo:
- o gesto validado
- a acao de video associada, quando existir

Esse modulo nao detecta landmarks, nao decide narrativa e nao toca video. Ele filtra ruido temporal e transforma um gesto bruto em um evento utilizavel.

## Papel no sistema

O papel principal de `gesture_mapper.py` e evitar disparos acidentais.

Ele implementa:
- debounce temporal por frames consecutivos
- latch para impedir repeticao do mesmo gesto sem "soltar"
- mapeamento opcional de gesto para `VideoAction`
- log curto quando um gesto e finalmente aceito

Sem esse modulo, qualquer oscilacao momentanea da visao poderia disparar videos ou avancar etapas narrativas indevidamente.

## Integracao com outros modulos

### `vision.py`

`vision.py` e quem produz o gesto bruto (`GestureName` ou `None`).

`gesture_mapper.py` nao tenta detectar gestos sozinho; ele depende da classificacao ja pronta vinda da visao.

### `config.py`

Consome:
- `GESTURE_STABLE_FRAMES`
- `GestureName`
- `VIDEO_ACTIONS`
- `VideoAction`

Ou seja, o debounce e o mapa padrao gesto -> video sao definidos fora deste arquivo.

### `main.py`

`main.py` usa o mapper nos pontos em que transforma input em trigger narrativo, principalmente em:
- `_read_trigger_source()`

O resultado aceito pelo mapper e o que efetivamente entra no `StoryEngine`.

### `story_engine.py`

O `StoryEngine` recebe o gesto ja estabilizado, nao o gesto bruto da camera.

Isso reduz risco de ruido narrativo e mantem a engine focada na semantica do fluxo, nao em tratamento de estabilidade.

## Fluxo principal

O fluxo do arquivo e pequeno e direto:

1. recebe um gesto bruto em `map_gesture()`
2. se o gesto for `None`, zera o estado interno
3. se o gesto repetir o frame anterior, incrementa o contador de estabilidade
4. se o gesto mudar, reinicia o contador
5. se ainda nao atingiu `GESTURE_STABLE_FRAMES`, nao aceita
6. se o gesto ja foi aceito e ainda esta "latched", nao repete
7. quando aceita:
   - marca o gesto como latched
   - procura uma `VideoAction` no mapa
   - emite log curto
   - retorna `GestureResult`

## Principais estruturas e funcoes

### `GestureResult`

Dataclass imutavel com dois campos:
- `gesture`
- `action`

Ela permite separar claramente:
- o gesto reconhecido
- a acao direta associada, se existir

Isso e importante porque nem todo gesto do sistema dispara video diretamente.

### `GestureMapper.__init__()`

Inicializa:
- mapa de acoes
- ultimo gesto visto
- contador de frames estaveis
- latch do gesto atual
- ultima mensagem de debug

O parametro `action_map` permite override em testes ou cenarios especiais, mas por padrao usa `VIDEO_ACTIONS` do `config.py`.

### `map_gesture()`

E a funcao central do modulo.

Responsabilidades:
- resetar o estado quando nao ha gesto
- contar repeticao de um mesmo gesto por frames consecutivos
- bloquear aceitacao prematura
- impedir repeticao em loop do mesmo gesto
- devolver `GestureResult` apenas quando o gesto estiver pronto

Comportamento importante:
- se o gesto some (`None`), o latch e liberado
- se o gesto muda antes de estabilizar, a contagem recomeça
- um mesmo gesto nao e emitido continuamente enquanto a mao permanecer parada

### `_debug_emit()`

Imprime um log curto quando um gesto e aceito.

Formato atual:

```text
[GestureMapper] accepted=HAND_OPEN action=YES
```

Esse log ajuda a distinguir:
- gesto bruto detectado pela visao
- gesto realmente aceito pelo fluxo

## Pontos criticos e de manutencao

### 1. `GESTURE_STABLE_FRAMES` muda o comportamento global

Esse valor vem de `config.py` e afeta todos os gestos que passam por este mapper.

Se estiver muito alto:
- o sistema fica duro
- gestos bons podem nao entrar

Se estiver muito baixo:
- aumenta risco de falso positivo

### 2. O latch e intencional

`_latched_gesture` impede que um gesto continuo dispare varias vezes seguidas.

Esse comportamento e essencial para nao tocar o mesmo video varias vezes enquanto a pessoa mantem a mao parada.

Ao alterar essa regra, e preciso validar o fluxo inteiro.

### 3. Nem todo gesto tem `VideoAction`

O mapper pode aceitar um gesto e retornar `action=None`.

Isso e esperado em gestos cuja interpretacao depende do estado narrativo e do `StoryEngine`.

Portanto:
- `gesture aceito` nao significa sempre `video direto`

### 4. Este modulo nao resolve ambiguidade geometrica

Ele trabalha em cima do gesto ja classificado.

Se a visao estiver classificando mal:
- o problema esta em `vision.py`
- nao em `gesture_mapper.py`

O mapper cuida de estabilidade temporal, nao de geometria dos dedos.

### 5. Logs de debug devem continuar curtos

O log atual e util porque mostra apenas o essencial:
- gesto aceito
- se tem acao direta

Se esse metodo passar a imprimir demais, o terminal perde valor operacional.

## Resumo de manutencao

Este arquivo deve continuar pequeno e previsivel.

Ao mexer nele, manter a responsabilidade restrita a:
- debounce
- latch
- conversao de gesto aceito para `GestureResult`

Evitar colocar aqui:
- regra narrativa
- heuristica de landmarks
- logica de video
- protocolo de robo

O modulo funciona melhor como filtro temporal entre `vision.py` e `story_engine.py`.
