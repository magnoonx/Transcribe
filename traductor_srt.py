import os
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
    tipos = [("Archivos de video", "*.mp4 *.mkv *.avi *.mov"), ("Todos", "*.*")]
    ruta_video = filedialog.askopenfilename(title="Selecciona video en INGLÉS para traducir", filetypes=tipos)
    root.destroy()
    return ruta_video

def generar_traduccion(video_path, model_size="small"):
    if not video_path: return

    # MODIFICACIÓN: Apuntamos a la ruta común de la caché de Hugging Face del usuario actual
    # Nota: Apuntamos a la carpeta 'hub', la librería buscará 'models--Systran--faster-whisper-small' adentro.
    ruta_cache_comun = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")

    print(f"\n--- Iniciando TRADUCCIÓN al Español ---")
    print(f"Cargando modelo desde: {ruta_cache_comun}")
    
    # Cargamos el modelo usando la ruta de descarga específica
    model = WhisperModel(
        model_size, 
        device="cpu", 
        compute_type="int8", 
        download_root=ruta_cache_comun
    )

    # El resto del proceso se mantiene igual
    segments, info = model.transcribe(
    video_path, 
    language="es",
    beam_size=10, 
    vad_filter=True,
    # El prompt es la clave para el "sabor" del idioma
    initial_prompt="Habla un español de Latinoamérica, usando 'ustedes' en lugar de 'vosotros'. El tono es natural y fluido.",
    # Parámetros de precisión técnica
    best_of=5,
    repetition_penalty=1.2,           # Evita que el modelo se "ulucle" en una palabra
    no_repeat_ngram_size=3,           # Mejora la fluidez al evitar repeticiones innecesarias
    condition_on_previous_text=True,  # Crucial para mantener el contexto del diálogo
    compression_ratio_threshold=2.4,  # Ayuda a evitar fallos en partes con ruido
    log_prob_threshold=-1.0           # Filtra alucinaciones si la calidad de audio baja
    )

    print(f"Idioma original detectado: {info.language}")
    print(f"Traduciendo audio a español...")

    output_srt = os.path.splitext(video_path)[0] + "_ESPAÑOL.srt"
    
    with open(output_srt, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            f.write(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n\n")
            print(f"[{start}] {segment.text.strip()}")

    print(f"\n¡TRADUCCIÓN LISTA! Guardado como: {os.path.basename(output_srt)}")

if __name__ == "__main__":
    ruta = seleccionar_archivo()
    if ruta:
        generar_traduccion(ruta, model_size="medium")