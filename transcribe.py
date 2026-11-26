import os
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import sys

# 1. Configurar la ruta relativa al directorio del script
script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, ".modelos/small")

print(f"--- Iniciando transcriptor ---")
print(f"Buscando modelo en: {model_path}")

# 2. Cargar el modelo (usando CPU por estabilidad)
try:
    # Si descargaste el modelo 'small', asegúrate de que los archivos estén 
    # directamente dentro de la carpeta .modelos
    model = WhisperModel(model_path, device="cpu", compute_type="int8")
    print("Modelo cargado exitosamente.")
except Exception as e:
    print(f"ERROR al cargar el modelo: {e}")
    sys.exit(1)

# 3. Función de procesamiento
def process_audio(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    
    # Convertir audio a float32 (formato que requiere Whisper)
    audio_data = indata.flatten().astype(np.float32)
    
    # Solo transcribir si hay volumen suficiente (evita procesar silencio)
    if np.max(np.abs(audio_data)) > 0.0051:
        segments, info = model.transcribe(audio_data, beam_size=8, language="en")
        for segment in segments:
            print(f"[{segment.start:.1f}s] {segment.text}", flush=True)

# 4. Configurar el flujo de entrada
# 'device=None' usará tu dispositivo predeterminado del sistema. 
# Asegúrate de que el "Virtual Cable" sea el dispositivo de entrada por defecto en Windows.
try:
    with sd.InputStream(device=1, 
                        channels=1, 
                        callback=process_audio, 
                        samplerate=16000, 
                        blocksize=160000): # Procesa bloques de 3 segundos
        print("\n>>> ESCUCHANDO AUDIO (VLC -> Virtual Cable) <<<")
        print("Presiona Ctrl+C para detener.")
        while True:
            sd.sleep(1000)
except KeyboardInterrupt:
    print("\nDeteniendo transcriptor...")
except Exception as e:
    print(f"Error en el stream de audio: {e}")