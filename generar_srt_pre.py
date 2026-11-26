import os
import subprocess
import tkinter as tk
from tkinter import filedialog
from faster_whisper import WhisperModel

def format_timestamp(seconds: float):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    tipos = [
        ("Archivos de video", "*.mp4 *.ts *.wmv *.mkv *.avi *.mov *.flv"),
        ("Todos los archivos", "*.*")
    ]
    ruta_video = filedialog.askopenfilename(title="Selecciona el video para subtitular", filetypes=tipos)
    root.destroy()
    return ruta_video

def preprocesar_audio_ffmpeg(video_path):
    """
    Extrae y normaliza el audio usando FFmpeg. 
    Usa el filtro loudnorm para resaltar sonidos bajos (susurros).
    """
    temp_audio = "temp_normalized_audio.wav"
    print(f"--- Optimizando audio para detectar susurros ---")
    
    # loudnorm intenta normalizar el volumen basándose en estándares de sonoridad.
    # -ar 16000 es la frecuencia nativa que usa Whisper.
    comando = [
        'ffmpeg', '-i', video_path,
        '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', 
        '-ar', '16000', '-ac', '1',
        '-y', temp_audio
    ]
    
    try:
        # Ejecuta el comando ocultando la salida técnica de ffmpeg
        subprocess.run(comando, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return temp_audio
    except Exception as e:
        print(f"Error al procesar audio con FFmpeg: {e}")
        return video_path # Si falla, intenta usar el original

def generar_subtitulos(video_path, model_size="medium"):
    if not video_path:
        print("Operación cancelada.")
        return

    # 1. Pre-procesamiento de audio
    audio_procesado = preprocesar_audio_ffmpeg(video_path)

    # 2. Configuración de Rutas (Caché local del usuario actual)
    ruta_cache_comun = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    
    print(f"\n--- Iniciando Transcripción Sensible ---")
    print(f"Cargando modelo '{model_size}'...")
    
    model = WhisperModel(
        model_size, 
        device="cpu", 
        compute_type="int8", 
        download_root=ruta_cache_comun
    )

    # 3. Transcripción con sensibilidad ultra-alta
    print(f"Procesando: {os.path.basename(video_path)}")
    
    segments, info = model.transcribe(
        audio_procesado, 
        beam_size=5, 
        vad_filter=True,
        vad_parameters=dict(
            threshold=0.005,              # Umbral bajísimo para captar lo casi inaudible
            min_silence_duration_ms=200,  # No ignora pausas cortas entre susurros
            speech_pad_ms=500
        ),
        best_of=5,
        repetition_penalty=1.2,
        no_repeat_ngram_size=3,
        condition_on_previous_text=True,  # Ayuda al modelo a "adivinar" palabras por contexto
        log_prob_threshold=None,          # No descarta segmentos por "poca confianza"
        no_speech_threshold=0.2           # Obliga a intentar transcribir casi todo
    )

    print(f"Idioma detectado: {info.language} (Precisión: {info.language_probability:.2f})")

    # 4. Escritura del archivo SRT
    output_srt = os.path.splitext(video_path)[0] + ".srt"
    print("Transcribiendo... (Presiona Ctrl+C para cancelar)")
    
    try:
        with open(output_srt, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start = format_timestamp(segment.start)
                end = format_timestamp(segment.end)
                text = segment.text.strip()
                
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
                print(f"[{start}] {text}")

        print(f"\n¡ÉXITO! Proceso terminado.")
        print(f"Archivo guardado en: {output_srt}")
        
    except Exception as e:
        print(f"\nOcurrió un error durante la escritura: {e}")
    finally:
        # Limpieza del archivo temporal
        if os.path.exists(audio_procesado) and audio_procesado == "temp_normalized_audio.wav":
            os.remove(audio_procesado)

if __name__ == "__main__":
    ruta = seleccionar_archivo()
    if ruta:
        generar_subtitulos(ruta, model_size="medium")