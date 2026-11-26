import io
import logging
import time
from typing import Optional
import os
import requests

import pysrt
from deep_translator import GoogleTranslator

GROQ_API_URL = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")

logger = logging.getLogger("srt_translator")


class TranslationError(Exception):
    pass


def _decode_srt_file(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return data.decode("latin-1")


def _normalize_language_code(code: Optional[str]) -> str:
    if not code:
        return ""
    return code.strip().lower()


def load_subtitles_from_bytes(data: bytes) -> pysrt.SubRipFile:
    text = _decode_srt_file(data)
    return pysrt.from_string(text)


def apply_latino_adjustments(text: str) -> str:
    if not text:
        return text
    replacements = {
        "ordenador": "computadora",
        "móvil": "celular",
        "vídeo": "video",
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text


def _translate_text(translator: GoogleTranslator, text: str, max_retries: int = 3, pause: int = 5, delay: float = 0.35) -> str:
    if not text.strip():
        return text

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            res = translator.translate(text)
            if delay > 0:
                time.sleep(delay)
            return res
        except Exception as error:
            last_error = error
            logger.warning("Error de traducción (intento %d/%d): %s", attempt, max_retries, error)
            if attempt == max_retries:
                break
            time.sleep(pause * attempt)

    raise TranslationError(f"No se pudo traducir el texto después de {max_retries} intentos: {last_error}")


def translate_subtitles(subs: pysrt.SubRipFile, source: str, target: str, max_retries: int = 3) -> pysrt.SubRipFile:
    source_lang = _normalize_language_code(source) or "auto"
    target_lang = _normalize_language_code(target)
    if not target_lang:
        raise TranslationError("El idioma de destino es obligatorio.")

    translator = GoogleTranslator(source=source_lang, target=target_lang)

    total = len(subs)
    logger.info("Traduciendo %d subtítulos de %s a %s", total, source_lang, target_lang)

    for index, sub in enumerate(subs, start=1):
        translated_text = _translate_text(translator, sub.text, max_retries=max_retries)
        sub.text = apply_latino_adjustments(translated_text)

        if index % 20 == 0 or index == total:
            logger.info("Progreso: %d/%d subtítulos traducidos", index, total)

    return subs


def serialize_subtitles(subs: pysrt.SubRipFile, encoding: str = "utf-8") -> bytes:
    buffer = io.StringIO()
    subs.write_into(buffer)
    return buffer.getvalue().encode(encoding)


def apply_time_offset(subs: pysrt.SubRipFile, seconds: int) -> pysrt.SubRipFile:
    if not seconds:
        return subs

    offset = pysrt.SubRipTime(seconds=seconds)
    for sub in subs:
        sub.start += offset
        sub.end += offset
    return subs


def translate_subtitles_with_progress(
    subs: pysrt.SubRipFile,
    source: Optional[str],
    target: str,
    start_index: int = 0,
    max_retries: int = 3,
    progress_save_fn=None,
    progress_interval: int = 20,
    postprocess_fn=None,
    postprocess_selector=None,
) -> pysrt.SubRipFile:
    """Traduce subtítulos a partir de `start_index` y llama a `progress_save_fn(last_index, subs)`
    después de cada subtítulo traducido. `start_index` es 0-based.
    """
    source_lang = _normalize_language_code(source) or "auto"
    target_lang = _normalize_language_code(target)
    if not target_lang:
        raise TranslationError("El idioma de destino es obligatorio.")

    translator = GoogleTranslator(source=source_lang, target=target_lang)

    total = len(subs)
    logger.info("Reanudando/traduciendo %d subtítulos de %s a %s desde %d", total, source_lang, target_lang, start_index)

    for idx in range(start_index, total):
        sub = subs[idx]
        translated_text = _translate_text(translator, sub.text, max_retries=max_retries)
        sub.text = apply_latino_adjustments(translated_text)

        # Post-process with LLM if requested and selector indicates
        if postprocess_fn and postprocess_selector:
            try:
                if postprocess_selector(sub.text):
                    new_text = postprocess_fn(sub.text)
                    if isinstance(new_text, str) and new_text.strip():
                        sub.text = new_text
            except Exception:
                logger.exception("Error during postprocess_fn")
        last_index = idx + 1
        if progress_save_fn:
            try:
                progress_save_fn(last_index, subs)
            except Exception:
                logger.exception("Error guardando progreso")

        if last_index % progress_interval == 0 or last_index == total:
            logger.info("Progreso: %d/%d subtítulos traducidos", last_index, total)

    return subs


def is_potentially_problematic(text: str, min_chars: int = 80, min_sentences: int = 2) -> bool:
    if not text or not text.strip():
        return False
    if len(text) >= min_chars:
        return True
    # Count sentence-like splits
    sentences = max(1, text.count('.') + text.count('!') + text.count('?'))
    if sentences >= min_sentences:
        return True
    return False


def postprocess_text_with_groq(text: str, target_lang: str) -> str:
    """Send text to a Groq endpoint defined by env vars and return the processed text.

    Expects environment variables: GROQ_API_URL and GROQ_API_KEY.
    The function will send JSON {"input": prompt} and try to extract a sensible text
    result from the JSON response or the raw text body.
    """
    api_url = GROQ_API_URL
    api_key = GROQ_API_KEY
    if not api_url or not api_key:
        raise RuntimeError("GROQ_API_URL and GROQ_API_KEY must be set to use post-processing")

    prompt = [
        {"role": "system", "content": "You are a professional translator. Improve and humanize the translated text so it sounds natural and idiomatic in the target language. Preserve meaning, punctuation, and casing. Return only the final translated text with no explanations."},
        {"role": "user", "content": f"Please improve and humanize this translation into {target_lang}:\n\n{text}"},
    ]

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": prompt,
        "max_tokens": 300,
        "temperature": 0.7,
    }

    # Try a few times with backoff
    last_err = None
    for attempt in range(1, 4):
        try:
            resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
            if resp.status_code != 200:
                last_err = RuntimeError(f"GROQ API returned {resp.status_code}: {resp.text}")
                logger.warning("Groq API non-200 status: %s", resp.status_code)
                logger.debug("Groq API response body: %s", resp.text)
                time.sleep(1 * attempt)
                continue

            # Parse JSON in OpenAI-style response
            try:
                j = resp.json()
                logger.debug("Groq API JSON response: %s", j)
                if isinstance(j, dict):
                    choices = j.get("choices")
                    if isinstance(choices, list) and len(choices) > 0:
                        first = choices[0]
                        if isinstance(first, dict):
                            message = first.get("message")
                            if isinstance(message, dict):
                                content = message.get("content")
                                if isinstance(content, str):
                                    return content.strip()
                            # Some Groq responses may place text directly under "text"
                            if "text" in first and isinstance(first["text"], str):
                                return first["text"].strip()
                            # Some responses include delta structure
                            if first.get("delta") and isinstance(first["delta"], dict):
                                delta_content = first["delta"].get("content")
                                if isinstance(delta_content, str):
                                    return delta_content.strip()
                    # Fallback common keys
                    for key in ("output", "text", "result", "message", "response"):
                        if key in j and isinstance(j[key], (str, list)):
                            val = j[key]
                            if isinstance(val, list):
                                return "\n".join(map(str, val))
                            return str(val)
            except ValueError:
                logger.warning("Groq API returned non-JSON body")

            # Fallback to raw text
            text_resp = resp.text.strip()
            if text_resp:
                return text_resp
            last_err = RuntimeError("Groq API returned empty response")
        except Exception as e:
            last_err = e
            logger.exception("Exception while calling Groq API on attempt %s", attempt)
            time.sleep(1 * attempt)

    raise last_err


def translate_srt_file(data: bytes, source: Optional[str], target: str) -> bytes:
    subs = load_subtitles_from_bytes(data)
    translated_subs = translate_subtitles(subs, source or "auto", target)
    return serialize_subtitles(translated_subs)
