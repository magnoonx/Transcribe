import logging
import uvicorn
import os
import hashlib
import json
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_400_BAD_REQUEST

from translator import (
    TranslationError,
    translate_srt_file,
    load_subtitles_from_bytes,
    serialize_subtitles,
    translate_subtitles_with_progress,
    postprocess_text_with_groq,
    is_potentially_problematic,
    apply_time_offset,
)

logger = logging.getLogger("srt_translator")

app = FastAPI(
    title="SRT Translator API",
    description="API para traducir archivos SRT usando Google Translator a través de deep-translator.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Directorio de cache configurable (variable de entorno SRT_CACHE_DIR)
CACHE_DIR = os.environ.get("SRT_CACHE_DIR", "srt_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Montar archivos estáticos para la interfaz web
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def web_ui():
    return FileResponse(os.path.join("static", "index.html"))


@app.get("/progress/{cache_id}")
def get_progress(cache_id: str):
    progress_path = os.path.join(CACHE_DIR, f"{cache_id}_progress.json")
    if not os.path.exists(progress_path):
        return JSONResponse(status_code=404, content={"detail": "No progress found"})
    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        last = int(data.get("last_index", 0))
        total = int(data.get("total", 0))
        done = (total > 0 and last >= total)
        return {"last_index": last, "total": total, "done": done}
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "Error reading progress"})


@app.get("/download/{cache_id}")
def download_result(cache_id: str):
    output_path = os.path.join(CACHE_DIR, f"{cache_id}.srt")
    if not os.path.exists(output_path):
        return JSONResponse(status_code=404, content={"detail": "Result not ready"})
    filename = os.path.basename(output_path)
    return FileResponse(output_path, media_type="text/plain; charset=utf-8", filename=filename)


@app.post(
    "/translate",
    response_class=StreamingResponse,
    summary="Traducir archivo SRT",
    description="Recibe un archivo SRT y devuelve el mismo archivo con el texto traducido al idioma destino.",
    tags=["Traducción"],
)
async def translate_srt(
    file: UploadFile = File(...),
    source: str = Form("auto"),
    target: str = Form(...),
    use_llm: str = Form("false"),
    time_offset_seconds: str = Form("0"),
):
    logger.info("Solicitud recibida para traducir archivo %s de %s a %s", file.filename, source, target)

    if file.content_type not in {"application/x-subrip", "text/plain", "application/octet-stream"}:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="El archivo debe ser un SRT válido.")

    try:
        payload = await file.read()

        # Determine whether to use LLM postprocessing
        use_llm_flag = str(use_llm).lower() in ("1", "true", "yes", "on")
        try:
            offset_seconds = int(str(time_offset_seconds).strip() or "0")
        except ValueError as exc:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="El desplazamiento de tiempos debe ser un número entero.") from exc

        sha = hashlib.sha256(payload).hexdigest()[:16]
        safe_name = os.path.splitext(os.path.basename(file.filename))[0].replace("/", "_").replace("\\", "_")
        safe_source = source.replace("/", "_").replace(" ", "_")
        safe_target = target.replace("/", "_").replace(" ", "_")

        llm_tag = "llm" if use_llm_flag else "nollm"
        cache_base = f"{sha}_{safe_name}_{safe_source}_{safe_target}_{llm_tag}"
        progress_path = os.path.join(CACHE_DIR, f"{cache_base}_progress.json")
        output_path = os.path.join(CACHE_DIR, f"{cache_base}.srt")
        input_path = os.path.join(CACHE_DIR, f"{cache_base}.srt.orig")

        # Guardar entrada en disco
        with open(input_path, "wb") as in_f:
            in_f.write(payload)

        # Inicializar progreso
        try:
            subs = load_subtitles_from_bytes(payload)
            total = len(subs)
        except Exception:
            total = 0

        initial = {"last_index": 0, "source": source, "target": target, "total": total}
        try:
            with open(progress_path, "w", encoding="utf-8") as f:
                json.dump(initial, f)
        except Exception:
            logger.exception("No se pudo escribir el progreso inicial")

        # Tarea de background
        def background_process():
            try:
                # Simple lockfile para evitar ejecución paralela del mismo cache_id
                lock_path = os.path.join(CACHE_DIR, f"{cache_base}.lock")
                # Intentar crear el lock de forma atómica
                try:
                    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                except FileExistsError:
                    logger.info("Otro worker ya está procesando %s, saliendo", cache_base)
                    return
                except Exception:
                    logger.exception("No se pudo crear lock, continuando de todos modos")

                with open(input_path, "rb") as f:
                    data = f.read()
                subs_obj = load_subtitles_from_bytes(data)

                # Si existe salida parcial y coincide en longitud, cargarla
                try:
                    import pysrt
                    if os.path.exists(output_path):
                        subs_partial = pysrt.open(output_path, encoding="utf-8")
                        if len(subs_partial) == len(subs_obj):
                            subs_obj = subs_partial
                except Exception:
                    logger.debug("No se cargó salida parcial")

                def progress_save_fn(last_index: int, subs_inner):
                    try:
                        with open(progress_path, "w", encoding="utf-8") as f:
                            json.dump({"last_index": int(last_index), "source": source, "target": target, "total": len(subs_obj)}, f)
                    except Exception:
                        logger.exception("Error guardando progreso")
                    try:
                        with open(output_path, "wb") as out_f:
                            out_f.write(serialize_subtitles(subs_inner))
                    except Exception:
                        logger.exception("No se pudo guardar parcial")

                # Decide postprocess_fn and selector based on flag
                pp_fn = None
                pp_selector = None
                if use_llm_flag:
                    pp_fn = lambda t: postprocess_text_with_groq(t, target)
                    pp_selector = is_potentially_problematic

                translated = translate_subtitles_with_progress(
                    subs_obj,
                    source,
                    target,
                    start_index=0,
                    progress_save_fn=progress_save_fn,
                    postprocess_fn=pp_fn,
                    postprocess_selector=pp_selector,
                )

                adjusted_translated = apply_time_offset(translated, offset_seconds)
                with open(output_path, "wb") as out_f:
                    out_f.write(serialize_subtitles(adjusted_translated))

                try:
                    with open(progress_path, "w", encoding="utf-8") as f:
                        json.dump({"last_index": len(translated), "source": source, "target": target, "total": len(translated)}, f)
                except Exception:
                    logger.exception("Error marcando progreso final")
                # Remover lock al finalizar
                try:
                    if os.path.exists(lock_path):
                        os.remove(lock_path)
                except Exception:
                    logger.exception("No se pudo remover el lockfile")
            except Exception:
                logger.exception("Error en background_process")

        try:
            import threading
            t = threading.Thread(target=background_process, daemon=True)
            t.start()
        except Exception:
            background_process()

    except Exception as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=f"Error al procesar el archivo: {exc}")

    return JSONResponse(status_code=202, content={"cache_id": cache_base})


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
