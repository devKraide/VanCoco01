# Windows Setup

## 1. Instalar pre-requisitos

### Instalar `winget` (se necessario)

```powershell
winget --version
```

### Instalar Git

```powershell
winget install --id Git.Git -e
```

### Instalar Python 3.11

```powershell
winget install --id Python.Python.3.11 -e
```

## 2. Clonar o repositorio

```powershell
git clone <URL_DO_REPOSITORIO>
cd vanCoco
```

## 3. Ir para a branch Windows

```powershell
git checkout windows-port
```

## 4. Criar a venv

```powershell
py -3.11 -m venv .venv
```

## 5. Ativar a venv

### PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### CMD

```cmd
.venv\Scripts\activate.bat
```

## 6. Instalar dependencias

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

## 7. Rodar o projeto

```powershell
python main.py
```

## 8. Rodar com portas COM explicitas

```powershell
$env:COCOMAG_PORT="COM3"
$env:COCOVISION_PORT="COM4"
python main.py
```

## 9. Testar comandos isolados com `rfcomm_serial_probe.py`

### CocoMag

```powershell
python rfcomm_serial_probe.py --port COM3 --command COCOMAG:PRESENT
python rfcomm_serial_probe.py --port COM3 --command COCOMAG:ACTION
```

### CocoVision

```powershell
python rfcomm_serial_probe.py --port COM4 --command COCOVISION:PRESENT
python rfcomm_serial_probe.py --port COM4 --command COCOVISION:ACTION --listen-seconds 8
python rfcomm_serial_probe.py --port COM4 --command COCOVISION:RETURN
```

## 10. Comandos uteis

```powershell
python --version
py -3.11 --version
git branch
git status
where python
mode
```
