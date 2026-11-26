# SRT Translator API

Esta API convierte archivos `.srt` traduciendo su texto desde un idioma de origen a un idioma de destino.

## Endpoints

- `POST /translate`
  - `file`: archivo SRT (multipart/form-data)
  - `source`: código del idioma de origen (`auto` por defecto)
  - `target`: código del idioma de destino

## Ejemplo de uso con `curl`

```bash
curl -X POST "http://localhost:8000/translate" \
  -F "file=@input.srt" \
  -F "source=auto" \
  -F "target=es" \
  --output translated_input.srt
```

## Ejecución

1. Activar el entorno virtual:

```powershell
cd D:\MEGA_FOLDER\Proyectos_desarrollo\Python\Transcribe\API
.envTranscribe\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Ejecutar el servidor:

```powershell
uvicorn app:app --host 0.0.0.0 --port 8000
```
