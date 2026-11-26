import os
import tkinter as tk
from tkinter import filedialog, ttk
from faster_whisper import WhisperModel
import shutil
import subprocess
import tempfile
from deep_translator import GoogleTranslator

def format_timestamp(seconds: float):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def seleccionar_archivo_e_idiomas():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    tipos = [
        ("Archivos de video", "*.mp4 *.ts *.wmv *.mkv *.avi *.mov *.flv"),
        ("Todos los archivos", "*.*")
    ]
    ruta_video = filedialog.askopenfilename(title="Selecciona el video para subtitular", filetypes=tipos)
    if not ruta_video:
        root.destroy()
        return None, None, None

    # Ventana modal para configurar idiomas
    dialog = tk.Toplevel(root)
    dialog.title("Configuración de Subtítulos")
    dialog.geometry("450x370")
    dialog.resizable(False, False)
    dialog.attributes('-topmost', True)
    
    # Centrar la ventana en pantalla
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'{width}x{height}+{x}+{y}')

    src_var = tk.StringVar(value="en")
    tgt_var = tk.StringVar(value="es")

    # Grupo 1: Idioma del audio del video (Origen)
    frame_src = tk.LabelFrame(dialog, text=" 1. Idioma del Audio del Video (Origen) ", font=("Segoe UI", 10, "bold"), padx=15, pady=8)
    frame_src.pack(fill="x", padx=20, pady=10)

    rb_src_en = tk.Radiobutton(frame_src, text="🇬🇧  Inglés", variable=src_var, value="en", font=("Segoe UI", 9))
    rb_src_en.pack(side="left", padx=10)

    rb_src_es = tk.Radiobutton(frame_src, text="🇪🇸  Español", variable=src_var, value="es", font=("Segoe UI", 9))
    rb_src_es.pack(side="left", padx=10)

    rb_src_auto = tk.Radiobutton(frame_src, text="🌐  Autodetectar", variable=src_var, value="auto", font=("Segoe UI", 9))
    rb_src_auto.pack(side="left", padx=10)

    # Grupo 2: Idioma deseado de subtítulos (Destino)
    frame_tgt = tk.LabelFrame(dialog, text=" 2. Idioma Deseado del Subtítulo (Destino) ", font=("Segoe UI", 10, "bold"), padx=15, pady=8)
    frame_tgt.pack(fill="x", padx=20, pady=10)

    rb_tgt_es = tk.Radiobutton(frame_tgt, text="🇪🇸  Español (Traducción Natural)", variable=tgt_var, value="es", font=("Segoe UI", 9), anchor="w")
    rb_tgt_es.pack(fill="x", pady=2)

    rb_tgt_en = tk.Radiobutton(frame_tgt, text="🇬🇧  Inglés (Original / Traducido)", variable=tgt_var, value="en", font=("Segoe UI", 9), anchor="w")
    rb_tgt_en.pack(fill="x", pady=2)

    rb_tgt_both = tk.Radiobutton(frame_tgt, text="🌐  Ambos (Original + Traducido)", variable=tgt_var, value="both", font=("Segoe UI", 9), anchor="w")
    rb_tgt_both.pack(fill="x", pady=2)

    def on_confirm():
        dialog.destroy()
        root.destroy()

    btn_confirm = tk.Button(dialog, text="Iniciar Subtitulado", command=on_confirm, bg="#0078D4", fg="white", font=("Segoe UI", 10, "bold"), padx=25, pady=6, relief="flat", cursor="hand2")
    btn_confirm.pack(pady=15)

    dialog.protocol("WM_DELETE_WINDOW", on_confirm)
    dialog.grab_set()
    root.mainloop()

    return ruta_video, src_var.get(), tgt_var.get()

_translator_cache = {}

def traducir_texto(texto: str, origen: str, destino: str) -> str:
    if not texto or not texto.strip() or origen == destino:
        return texto
    try:
        key = (origen, destino)
        if key not in _translator_cache:
            _translator_cache[key] = GoogleTranslator(source=origen if origen != "auto" else "auto", target=destino)
        traducido = _translator_cache[key].translate(texto)
        return traducido if traducido else texto
    except Exception as e:
        print(f" [Aviso: error al traducir segmento: {e}]")
        return texto

def generar_subtitulos(video_path, source_lang="en", target_lang="es", model_size="turbo"):
    if not video_path:
        print("Operación cancelada.")
        return

    def normalize_audio(input_path: str) -> str:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ffmpeg = os.path.join(script_dir, "ffmpeg.exe")
        local_bin_ffmpeg = os.path.join(script_dir, "bin", "ffmpeg.exe")
        
        if os.path.isfile(local_ffmpeg):
            ffmpeg_exe = local_ffmpeg
        elif os.path.isfile(local_bin_ffmpeg):
            ffmpeg_exe = local_bin_ffmpeg
        else:
            ffmpeg_exe = shutil.which("ffmpeg")

        if not ffmpeg_exe:
            print("ffmpeg no encontrado — se usará el archivo original.")
            return input_path

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)

        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            input_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-af",
            "highpass=f=75, lowpass=f=8000, dynaudnorm=f=150:g=15:m=40.0:b=1, loudnorm=I=-14:TP=-1.0:LRA=11",
            tmp_path,
        ]

        try:
            print("Aplicando normalización dinámica (dynaudnorm + filtro vocal) para capturar susurros...")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return tmp_path
        except Exception as e:
            print(f"La normalización avanzada falló ({e}). Se usará el archivo original.")
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return input_path

    # 1. Configuración de Rutas Portables
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_cache_comun = os.path.join(script_dir, "modelos")
    os.makedirs(ruta_cache_comun, exist_ok=True)
    
    print(f"\n--- Iniciando Proceso Robusto de Alta Sensibilidad (Modo Portable) ---")
    print(f"Cargando modelo '{model_size}' desde carpeta local de modelos ({ruta_cache_comun})...")
    
    model = WhisperModel(
        model_size, 
        device="cpu", 
        compute_type="int8", 
        download_root=ruta_cache_comun
    )

    # 2. Transcripción con Whisper
    print(f"Procesando: {os.path.basename(video_path)}")
    normalized_audio = normalize_audio(video_path)

    whisper_lang = source_lang if source_lang != "auto" else None

    segments, info = model.transcribe(
        normalized_audio,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            threshold=0.0001,
            min_silence_duration_ms=200,
            speech_pad_ms=500,
            min_speech_duration_ms=100
        ),
        initial_prompt="Whispered speech, low background music, faint dialogue, conversation.",
        best_of=5,
        repetition_penalty=1.2,
        no_repeat_ngram_size=3,
        condition_on_previous_text=False,
        language=whisper_lang,
        task="transcribe",
        compression_ratio_threshold=2.4,
        log_prob_threshold=-4.5,
        no_speech_threshold=0.85
    )

    idioma_detectado = info.language if info.language else (source_lang if source_lang != "auto" else "en")
    print(f"Idioma detectado/configurado en el audio: {idioma_detectado} (Precisión: {info.language_probability:.2f})")
    print("Transcribiendo y traduciendo con máxima sensibilidad... (Presiona Ctrl+C para cancelar)")

    # 3. Filtrado y preparación de contenido
    avg_logprob_threshold = -4.0
    no_speech_prob_threshold = 0.85

    base_path = os.path.splitext(video_path)[0]
    subtitulos_original = []
    subtitulos_traducidos = []

    # Determinar idioma destino primario y secundario
    lang_traducido = "es" if idioma_detectado == "en" else "en"

    written = 0
    for seg in segments:
        start = format_timestamp(seg.start)
        end = format_timestamp(seg.end)
        text_orig = seg.text.strip()

        avg_lp = getattr(seg, "avg_logprob", None)
        no_speech = getattr(seg, "no_speech_prob", None)

        if avg_lp is not None and avg_lp < avg_logprob_threshold:
            print(f"[SKIP {start}] baja confianza avg_logprob={avg_lp:.2f}")
            continue

        if no_speech is not None and no_speech > no_speech_prob_threshold:
            print(f"[SKIP {start}] probable no-speech (no_speech_prob={no_speech:.2f})")
            continue

        written += 1

        # Guardar original
        subtitulos_original.append((written, start, end, text_orig))

        # Traducir si es necesario
        if target_lang in [lang_traducido, "both"] or (target_lang != idioma_detectado and target_lang != "both"):
            target_translation = target_lang if target_lang != "both" else lang_traducido
            text_trad = traducir_texto(text_orig, idioma_detectado, target_translation)
            subtitulos_traducidos.append((written, start, end, text_trad))
            print(f"[{start}] ORIGEN ({idioma_detectado}): {text_orig}  -->  DESTINO ({target_translation}): {text_trad}")
        else:
            print(f"[{start}] {text_orig}")

    # Limpiar archivo temporal si se creó
    if normalized_audio != video_path and os.path.exists(normalized_audio):
        try:
            os.remove(normalized_audio)
        except Exception:
            pass

    # 4. Escritura de archivos SRT
    archivos_creados = []

    # Determinar sufijos y guardar según la selección
    if target_lang == "both":
        # Guardar archivo original
        out_orig = f"{base_path}_{idioma_detectado.upper()}.srt"
        with open(out_orig, "w", encoding="utf-8") as f:
            for item in subtitulos_original:
                f.write(f"{item[0]}\n{item[1]} --> {item[2]}\n{item[3]}\n\n")
        archivos_creados.append(out_orig)

        # Guardar archivo traducido
        out_trad = f"{base_path}_{lang_traducido.upper()}.srt"
        with open(out_trad, "w", encoding="utf-8") as f:
            for item in subtitulos_traducidos:
                f.write(f"{item[0]}\n{item[1]} --> {item[2]}\n{item[3]}\n\n")
        archivos_creados.append(out_trad)
    else:
        # Si el usuario eligió un solo idioma
        if target_lang == idioma_detectado:
            out_file = f"{base_path}_{target_lang.upper()}.srt"
            with open(out_file, "w", encoding="utf-8") as f:
                for item in subtitulos_original:
                    f.write(f"{item[0]}\n{item[1]} --> {item[2]}\n{item[3]}\n\n")
            archivos_creados.append(out_file)
        else:
            out_file = f"{base_path}_{target_lang.upper()}.srt"
            with open(out_file, "w", encoding="utf-8") as f:
                for item in subtitulos_traducidos:
                    f.write(f"{item[0]}\n{item[1]} --> {item[2]}\n{item[3]}\n\n")
            archivos_creados.append(out_file)

    print(f"\n¡ÉXITO! Video completo procesado.")
    for arc in archivos_creados:
        print(f"Archivo guardado en: {arc}")

if __name__ == "__main__":
    ruta, src_lang, tgt_lang = seleccionar_archivo_e_idiomas()
    if ruta and src_lang and tgt_lang:
        generar_subtitulos(ruta, source_lang=src_lang, target_lang=tgt_lang, model_size="turbo")