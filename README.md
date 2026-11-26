# Transcribe

Pequeño conjunto de scripts para transcribir y generar subtítulos (SRT), traducir SRT y mostrar subtítulos en un overlay transparente (Electron).

## Requisitos
- Windows
- Python 3.10+ (recomendado)
- Node.js + npm (solo si usarás el overlay Electron)

## Instalación (Windows)
1. Crear y activar entorno virtual:

```powershell
python -m venv .envTranscribe
.\.envTranscribe\Scripts\Activate.ps1
```

2. Instalar dependencias Python:

```powershell
pip install -r requirements.txt
```

3. Para el overlay (opcional):

```powershell
# Si no tienes package.json en el repo
npm init -y
npm install electron --save-dev
npx electron .
```

## Archivos principales
- `generar_srt.py`: Interfaz simple para seleccionar un video y generar un archivo `.srt` usando `faster-whisper`.
- `transcribe.py`: Escucha audio en tiempo real (usa `sounddevice`) y muestra transcripciones por consola.
- `traductor_srt.py`: Genera subtítulos traducidos (usa `faster-whisper` con prompt en español).
- `traductor_srt_srt.py`: Traduce archivos `.srt` existentes usando `deep-translator` y `pysrt`.
- `overlay.js` y `index.html`: Overlay transparente hecho con Electron que lanza `transcribe.py` y muestra texto en pantalla.

## Notas y recomendaciones
- Ajusta las rutas hardcodeadas en los scripts si tu entorno difiere (por ejemplo, la ruta al ejecutable Python en `overlay.js` o la caché del Hub de Hugging Face en los scripts que usan `download_root`).
- `faster-whisper` puede requerir FFmpeg para procesar ciertos formatos de audio/video.
- Para `transcribe.py`, confirma el índice del dispositivo de entrada de audio en Windows o ajusta `device=None` para usar el predeterminado.

## Ejemplos de uso
- Generar SRT mediante GUI:

```powershell
python generar_srt.py
```

- Traducir un SRT ya existente:

```powershell
python traductor_srt_srt.py
```

- Ejecutar overlay (desde la carpeta del proyecto, con Node.js instalado):

```powershell
npx electron .
```

Si quieres, puedo:
- Añadir versiones concretas a `requirements.txt`.
- Crear un `package.json` mínimo para el overlay y comandos `npm`.
- Transformar `generar_srt.py` en una CLI que acepte rutas por argumento.
