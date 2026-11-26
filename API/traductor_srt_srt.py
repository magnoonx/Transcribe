import json
import os
import re
import time
import pysrt
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from deep_translator import GoogleTranslator

# Configuración de optimización de peticiones
BATCH_SIZE = 25              # Subtítulos agrupados por lote
MAX_BATCH_CHARS = 2500       # Máximo de caracteres por petición (límite de Google es 5000)
BATCH_DELIMITER = "\n[[#]]\n"
BATCH_REGEX = re.compile(r'\s*\[\s*\[\s*#\s*\]\s*\]\s*')


def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Selecciona el archivo SRT de entrada",
        filetypes=[("Archivos SRT", "*.srt"), ("Todos los archivos", "*.*")]
    )
    return file_path


def elegir_idiomas():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    usar_auto = messagebox.askyesno(
        "Idioma de entrada",
        "¿Deseas detectar automáticamente el idioma del archivo de entrada?"
    )

    if usar_auto:
        source = "auto"
    else:
        source = simpledialog.askstring(
            "Idioma de entrada",
            "Ingresa el código de idioma de entrada (por ejemplo: en, es, fr):",
            initialvalue="en"
        )
        if source:
            source = source.strip().lower()

    if not source:
        return None, None

    target = simpledialog.askstring(
        "Idioma de salida",
        "Ingresa el código de idioma de salida (por ejemplo: es, en, fr):",
        initialvalue="es"
    )
    if not target:
        return None, None

    return source, target.strip().lower()


def abrir_srt_seguro(ruta):
    """Abre un archivo SRT probando las codificaciones más habituales."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            return pysrt.open(ruta, encoding=enc)
        except (UnicodeDecodeError, Exception):
            continue
    return pysrt.open(ruta)


def cargar_progreso(progress_path, source, target):
    if not os.path.exists(progress_path):
        return 0
    try:
        with open(progress_path, "r", encoding="utf-8") as archivo:
            data = json.load(archivo)
            if data.get("source") != source or data.get("target") != target:
                return 0
            return int(data.get("last_index", 0))
    except Exception:
        return 0


def guardar_progreso(progress_path, last_index, source, target):
    data = {"last_index": int(last_index), "source": source, "target": target}
    with open(progress_path, "w", encoding="utf-8") as archivo:
        json.dump(data, archivo)


def limpiar_progreso(progress_path):
    try:
        if os.path.exists(progress_path):
            os.remove(progress_path)
    except Exception:
        pass


def traducir_con_reintentos(translator, texto, pause=10):
    """Traduce un texto con reintentos exponenciales y cuenta regresiva visual si Google aplica Rate Limit (429)."""
    while True:
        try:
            return translator.translate(texto)
        except KeyboardInterrupt:
            raise
        except Exception as error:
            err_str = str(error)
            es_429 = "429" in err_str or "too many requests" in err_str.lower()
            if es_429:
                print(f"\n[Aviso] Límite de peticiones de Google (429 Too Many Requests).")
                print(f"Esperando enfriamiento de {pause}s para restablecer conexión...")
            else:
                print(f"\n[Error de traducción]: {error}")
                print(f"Reintentando en {pause}s...")

            for s in range(pause, 0, -1):
                print(f"\r  -> Esperando {s}s para reintentar (Presiona Ctrl+C para pausar y guardar)... ", end="", flush=True)
                time.sleep(1)
            print("\r" + " " * 85 + "\r", end="", flush=True)

            pause = min(pause * 2, 60)


def traducir_individual(translator, texto, delay=0.3):
    """Traduce un subtítulo individual con delay de cortesía."""
    if not texto or not texto.strip():
        return texto
    res = traducir_con_reintentos(translator, texto)
    if delay > 0:
        time.sleep(delay)
    return res


def traducir_lote(translator, lista_textos, delay=0.4):
    """
    Traduce una lista de subtítulos agrupados en una sola petición HTTP.
    Si Google Translate modifica los delimitadores, realiza fallback
    traduciendo individualmente para evitar cualquier desfase en los subtítulos.
    """
    if not lista_textos:
        return []

    if len(lista_textos) == 1:
        return [traducir_individual(translator, lista_textos[0], delay=delay)]

    textos_preparados = [t.replace("[[#]]", "[#]") for t in lista_textos]
    bloque = BATCH_DELIMITER.join(textos_preparados)

    try:
        traduccion = traducir_con_reintentos(translator, bloque)
        if delay > 0:
            time.sleep(delay)

        partes = BATCH_REGEX.split(traduccion)
        if len(partes) == len(lista_textos):
            return [p.strip() for p in partes]

        print(f"\n[Aviso] Lote de {len(lista_textos)} subtítulos devolvió {len(partes)} fragmentos. Aplicando fallback individual...")
    except Exception as e:
        print(f"\n[Aviso en lote]: {e}. Aplicando fallback individual...")

    # Fallback seguro subtítulo por subtítulo
    resultados = []
    for txt in lista_textos:
        resultados.append(traducir_individual(translator, txt, delay=delay))
    return resultados


def aplicar_ajustes_latino(texto):
    if not texto:
        return texto
    reemplazos = [
        (r'\bordenador\b', 'computadora'),
        (r'\bOrdenador\b', 'Computadora'),
        (r'\bordenadores\b', 'computadoras'),
        (r'\bOrdenadores\b', 'Computadoras'),
        (r'\bmóvil\b', 'celular'),
        (r'\bMóvil\b', 'Celular'),
        (r'\bmóviles\b', 'celulares'),
        (r'\bMóviles\b', 'Celulares'),
        (r'\bvídeo\b', 'video'),
        (r'\bVídeo\b', 'Video'),
        (r'\bvídeos\b', 'videos'),
        (r'\bVídeos\b', 'Videos'),
    ]
    for patron, reemplazo in reemplazos:
        texto = re.sub(patron, reemplazo, texto)
    return texto


def traducir_srt():
    input_path = seleccionar_archivo()
    if not input_path:
        print("No se seleccionó ningún archivo.")
        return

    source, target = elegir_idiomas()
    if not source or not target:
        print("No se seleccionaron los idiomas correctamente.")
        return

    base_name = os.path.splitext(input_path)[0]
    output_path = f"{base_name}_{target}.srt"
    safe_source = source.replace("/", "_").replace(" ", "_")
    safe_target = target.replace("/", "_").replace(" ", "_")
    progress_path = f"{base_name}_{safe_source}_{safe_target}_progress.json"

    try:
        subs = abrir_srt_seguro(input_path)
        translator = GoogleTranslator(source=source, target=target)

        last_index = cargar_progreso(progress_path, source, target)
        if last_index > 0:
            print(f"Reanudando desde el subtítulo {last_index + 1} de {len(subs)}...")
            if os.path.exists(output_path):
                try:
                    subs_traducidos = abrir_srt_seguro(output_path)
                    if len(subs_traducidos) == len(subs):
                        subs = subs_traducidos
                    else:
                        print("El archivo de salida existente no coincide con el archivo original. Se reanudará usando el archivo original.")
                except Exception:
                    print("No se pudo leer el archivo de salida existente. Se reanudará usando el archivo original.")
        else:
            if source == "auto":
                print(f"Detectando automáticamente el idioma del archivo y traduciendo a {target}...")
            else:
                print(f"Traduciendo desde {source} a {target}...")

        total_subs = len(subs)
        print(f"Total de subtítulos: {total_subs}")
        print(f"Optimizando con traducción por lotes (hasta {BATCH_SIZE} subtítulos por llamada)...")

        idx = last_index
        while idx < total_subs:
            # Armar lote respetando tamaño y longitud máxima de caracteres
            batch_indices = []
            batch_texts = []
            batch_chars = 0

            while idx < total_subs and len(batch_indices) < BATCH_SIZE:
                sub_text = subs[idx].text.strip()
                if not sub_text:
                    # Subtítulo vacío, avanzamos sin gastar llamada
                    idx += 1
                    continue

                if batch_chars + len(sub_text) > MAX_BATCH_CHARS and batch_indices:
                    break

                batch_indices.append(idx)
                batch_texts.append(sub_text)
                batch_chars += len(sub_text)
                idx += 1

            if not batch_indices:
                break

            # Traducir el lote en una sola petición
            traducciones = traducir_lote(translator, batch_texts, delay=0.4)

            # Asignar resultados
            for sub_i, trad in zip(batch_indices, traducciones):
                subs[sub_i].text = aplicar_ajustes_latino(trad)

            # Guardado periódico por lote (evita escribir en disco por cada subtítulo)
            ultimo_procesado = batch_indices[-1] + 1
            subs.save(output_path, encoding="utf-8")
            guardar_progreso(progress_path, ultimo_procesado, source, target)

            porcentaje = (ultimo_procesado / total_subs) * 100
            print(f"Progreso: {ultimo_procesado}/{total_subs} subtítulos ({porcentaje:.1f}%)")

        subs.save(output_path, encoding="utf-8")
        limpiar_progreso(progress_path)

        messagebox.showinfo("Éxito", f"Archivo traducido y guardado como:\n{output_path}")
        print(f"\n¡Traducción finalizada con éxito! Guardado en: {output_path}")

    except KeyboardInterrupt:
        messagebox.showwarning("Interrumpido", "La traducción fue pausada por el usuario. El progreso se guardó y se reanudará la próxima vez.")
        print("\nTraducción interrumpida por el usuario. Progreso guardado con éxito.")
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error: {e}")
        print(f"\nOcurrió un error: {e}")


if __name__ == "__main__":
    traducir_srt()
