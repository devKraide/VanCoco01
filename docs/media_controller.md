# media_controller.py

## Visao geral

`media_controller.py` e a camada de apresentacao visual do projeto.

Ele concentra:
- criacao e configuracao da janela fullscreen
- integracao entre Qt (`PySide6`) e VLC
- controle de tela preta
- reproducao de videos reais
- simulacao de video por tempo (`mock video`)
- captura de teclado da janela principal
- sinalizacao de fim de video para o loop principal

O arquivo nao implementa narrativa, nao interpreta gestos e nao fala com os robos. O papel dele e exclusivamente operacional e visual.

## Papel no sistema

Este modulo e o responsavel por materializar visualmente o fluxo narrativo.

Ele fornece ao restante da aplicacao uma interface simples para:
- mostrar a tela preta
- tocar um video
- parar um video
- simular um video quando o arquivo nao existe
- consumir teclas pressionadas
- saber quando um video terminou
- encerrar a janela e o `QApplication`

Em termos arquiteturais:
- `main.py` decide o que deve ser mostrado
- `media_controller.py` executa essa exibicao

## Integracao com outros modulos

### `config.py`

Consome:
- `WINDOW_NAME`

Esse valor e usado como titulo da janela principal.

### `main.py`

E o principal consumidor do modulo.

`main.py` usa:
- `show_black_screen()`
- `start_video()`
- `start_mock_video()`
- `stop_video()`
- `update_ui()`
- `consume_key()`
- `consume_video_finished()`
- `should_close()`
- `close()`

Em outras palavras, `main.py` usa este arquivo como backend visual e de player.

### `state_manager.py`

Nao conversa diretamente com este modulo, mas o estado operacional do app precisa permanecer coerente com o que o `MediaController` esta exibindo.

### VLC e Qt

Este modulo integra diretamente:
- `python-vlc`
- `PySide6`

Essa integracao e o principal motivo de o arquivo existir como modulo proprio.

## Fluxo principal

O fluxo de uso do `MediaController` no app e:

1. criar o `QApplication`
2. criar a janela fullscreen
3. entrar no loop principal do app
4. a cada ciclo:
   - processar eventos Qt
   - verificar fim de mock video
   - devolver teclas consumidas
5. quando um video precisa tocar:
   - parar qualquer playback anterior
   - criar `MediaPlayer`
   - bindar o player ao widget nativo
   - iniciar o playback
6. quando o video termina:
   - o evento do VLC seta `_video_finished = True`
   - `main.py` consome esse sinal no ciclo seguinte

## Estruturas principais

### Preparacao de ambiente Qt

No topo do arquivo existe uma preparacao explicita do ambiente Qt:

```python
PYSIDE6_PATHS = list(getattr(PySide6, "__path__", []))
...
os.environ.setdefault("QT_PLUGIN_PATH", str(QT_PLUGINS_DIR))
os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(QT_PLATFORMS_DIR))
if platform.system() == "Darwin":
    os.environ.setdefault("QT_QPA_PLATFORM", "cocoa")
```

Essa parte e importante porque reduz problemas de descoberta de plugins Qt em distribuicoes e ambientes locais.

Tecnicamente, ela faz:
- localizar o diretório do PySide6 instalado
- derivar os diretórios de plugins Qt
- registrar essas rotas em variaveis de ambiente
- no macOS, forcar a plataforma `cocoa`

Essa preparacao acontece antes do import de classes Qt.

### `PresentationWindow`

Janela Qt principal da apresentacao.

Essa classe encapsula o widget visual que o VLC usa como superficie de video e tambem captura teclado.

#### `__init__()`

Cria:
- a propria janela
- um `QWidget` filho chamado `_video_surface`

Esse `_video_surface` e o widget nativo ao qual o VLC sera acoplado.

#### `video_surface`

Property simples que expoe o widget onde o VLC vai desenhar.

#### `keyPressEvent()`

Captura teclado diretamente da janela.

Comportamento:
- `Esc` registra a tecla `27`
- qualquer outro caractere textual e convertido para `ord(text)`

Isso produz uma interface de teclado simples e desacoplada para o `MediaController`.

#### `closeEvent()`

Quando a janela e fechada:
- notifica o controller com `request_close()`
- depois segue com o fluxo normal do Qt

#### `resizeEvent()`

Mantem o `_video_surface` sempre ocupando a geometria inteira da janela.

Esse detalhe e importante porque o VLC desenha nesse widget nativo.

#### `_configure_window()`

Configura:
- titulo da janela
- cursor oculto
- preenchimento automatico
- paleta preta
- widget de video com `WA_NativeWindow`
- widget de video inicialmente escondido

O uso de `WA_NativeWindow` e tecnicamente importante porque o VLC precisa de uma janela/superficie nativa do sistema para renderizar.

### `MediaController`

Classe principal do modulo.

Estado interno:
- `self._app`
- `self._pressed_key`
- `self._is_running`
- `self._video_finished`
- `self._mock_video_deadline`
- `self._vlc_instance`
- `self._media_player`
- `self._window`

## Principais funcoes explicadas

### `__init__()`

Inicializa todo o stack visual:

1. cria ou reaproveita o `QApplication`
2. registra o path de plugins Qt
3. inicializa flags internas
4. cria a instancia base do VLC
5. cria a janela principal
6. coloca a janela em fullscreen

Esse metodo e o bootstrap visual do sistema.

### `show_black_screen()`

Implementa o estado visual neutro do app.

Faz:
- esconder a superficie de video
- garantir fullscreen
- trazer a janela para frente
- ativar a janela

Esse metodo e usado repetidamente nos estados de espera.

### `start_video(video_path)`

Inicia a reproducao de um arquivo real.

Fluxo interno:

1. chama `stop_video()` para limpar playback anterior
2. valida se o arquivo existe
3. reseta flags de fim de video e mock
4. cria `Media` e `MediaPlayer` do VLC
5. associa a media ao player
6. mostra a superficie de video
7. binda o player ao widget Qt
8. anexa eventos de fim de video
9. chama `play()`

Esse metodo e o centro da integracao Qt + VLC.

### `start_mock_video(duration_seconds)`

Implementa um fallback quando o arquivo de video nao existe ou quando a narrativa quer simular playback curto.

Em vez de tocar midia real:
- limpa o player real
- grava um deadline futuro
- esconde a superficie de video

Depois, `update_ui()` marca `_video_finished = True` quando o tempo expira.

### `stop_video()`

Responsavel por encerrar playback atual, se houver.

Comportamento:
- se houver `MediaPlayer`, chama `stop()` e `release()`
- zera o player
- limpa deadline de mock
- volta para tela preta

Esse metodo centraliza cleanup do player e evita duplicacao.

### `close()`

Encerramento completo da camada de apresentacao.

Faz:
- `stop_video()`
- fecha a janela
- encerra o `QApplication`

### `update_ui()`

Metodo que precisa ser chamado ciclicamente pelo loop principal.

Responsabilidades:
- processar eventos Qt (`processEvents()`)
- verificar se um mock video ja venceu
- se venceu, marcar `_video_finished = True`

Sem esse metodo, a janela ficaria sem eventos e os mocks nunca terminariam.

### `consume_key()`

Retorna a ultima tecla registrada e limpa o buffer interno.

Esse modelo e de consumo simples: uma tecla por vez.

### `should_close()`

Retorna `True` quando a janela foi sinalizada para fechar.

Na implementacao atual, devolve o inverso de `_is_running`.

### `consume_video_finished()`

Retorna `True` apenas uma vez por evento de fim de video.

Mecanica:
- se `_video_finished` estiver falso, retorna `False`
- se estiver verdadeiro, consome e reseta a flag

Isso transforma o fim de video em um evento de polling amigavel ao loop principal.

### `register_key()`

Metodo chamado pela janela para gravar a ultima tecla pressionada.

### `request_close()`

Metodo chamado pela janela quando o usuario fecha a interface.

### `_bind_player_to_window()`

Esse e um dos pontos mais tecnicos do arquivo.

Objetivo:
- ligar o `MediaPlayer` do VLC ao widget Qt nativo correto

Fluxo:
- obter `winId()` do `video_surface`
- converter para inteiro
- escolher a chamada correta conforme o sistema operacional

No macOS:
- usa `set_nsobject`

No Linux:
- usa `set_xwindow`
- desabilita input de mouse e teclado capturados pelo proprio VLC

Se o sistema nao for suportado, levanta erro explicito.

Esse metodo e central para portabilidade entre Linux e macOS.

### `_attach_player_events()`

Anexa o callback de fim de video do VLC:
- `MediaPlayerEndReached`

### `_on_video_finished()`

Callback simples que marca:
- `_video_finished = True`

O tratamento real continua no loop principal do app.

## Pontos criticos e de manutencao

### 1. Integracao Qt + VLC e sensivel a plataforma

O metodo `_bind_player_to_window()` depende fortemente do sistema operacional.

Hoje ha suporte explicito para:
- macOS
- Linux

Qualquer expansao para outro sistema exige ajuste aqui.

### 2. O widget de video precisa continuar sendo nativo

`WA_NativeWindow` no `video_surface` nao e detalhe cosmetico; ele e requisito tecnico para o VLC renderizar corretamente.

### 3. `update_ui()` e obrigatorio no loop principal

Se o `main.py` parar de chamar esse metodo com frequencia:
- o Qt para de processar eventos
- a janela congela
- o teclado para de responder
- o mock video nao termina

### 4. O modelo de teclado e propositalmente simples

So existe uma tecla armazenada por vez em `_pressed_key`.

Para o projeto atual isso basta, mas nao e um sistema de fila de input.

### 5. `stop_video()` sempre volta para tela preta

Esse comportamento e importante para consistencia visual do app.

Quem modificar esse metodo precisa entender que ele nao apenas para o player; ele tambem restaura o estado visual base.

### 6. O fallback de mock video depende de `time.monotonic()`

Isso e correto do ponto de vista tecnico, porque evita problemas com ajuste de relogio do sistema.

### 7. O arquivo centraliza bootstrap visual

As configuracoes de plugin Qt e integracao VLC estao no topo do modulo.

Elas devem continuar juntas, porque fazem parte do bootstrap da camada visual.

## Resumo de manutencao

`media_controller.py` deve continuar sendo a camada operacional de apresentacao.

Ao evoluir esse modulo:
- manter desacoplado de narrativa
- preservar a interface simples usada por `main.py`
- validar qualquer mudanca em Linux e macOS
- testar com cuidado:
  - fullscreen
  - fim de video
  - mock video
  - captura de teclado
  - binding VLC/Qt

Este arquivo funciona melhor quando permanece focado em uma responsabilidade: controlar a janela e o playback de forma previsivel para o restante do sistema.
