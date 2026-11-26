package com.example.subtranslator

import android.content.Context
import android.net.Uri
import android.content.ContentValues
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.FileOutputStream
import java.io.OutputStream
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.lang.Exception
import java.util.concurrent.TimeUnit

data class SrtEntry(var index: Int, var timing: String, var text: String)

class TranslationManager(private val context: Context) {

    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    private val API_BASE = "https://libretranslate.de"

    suspend fun translateSrt(
        uri: Uri,
        source: String,
        target: String,
        progressCallback: (Int, Int) -> Unit,
        saveToDownloads: Boolean = false
    ): String = withContext(Dispatchers.IO) {
        val inputText = readTextFromUri(uri)
        val entries = parseSrt(inputText)
        val outputDir = context.getExternalFilesDir(null) ?: context.filesDir
        val baseName = queryFileNameFromUri(uri).replaceAfterLast('.', queryFileNameFromUri(uri)).let { name ->
            // remove extension
            if (name.contains('.')) name.substring(0, name.lastIndexOf('.')) else name
        }
        val safeSource = source.replace("/", "_").replace(" ", "_")
        val safeTarget = target.replace("/", "_").replace(" ", "_")
        val outputFile = File(outputDir, "${baseName}_${safeTarget}.srt")
        val progressFile = File(outputDir, "${baseName}_${safeSource}_${safeTarget}_progress.json")

        var lastIndex = loadProgress(progressFile, source, target)

        if (lastIndex > 0) {
            // If there is a partial output file, try to load translated parts into entries
            try {
                val existing = readTextFromFile(outputFile)
                val existingEntries = parseSrt(existing)
                if (existingEntries.size == entries.size) {
                    for (i in existingEntries.indices) entries[i].text = existingEntries[i].text
                }
            } catch (_: Exception) {
            }
        }

        val total = entries.size

        for (i in lastIndex until total) {
            val original = entries[i].text
            val translated = try {
                translateTextWithRetries(original, source, target)
            } catch (e: Exception) {
                // stop on fatal error
                throw e
            }
            entries[i].text = translated
            saveSrt(entries, outputFile)
            saveProgress(progressFile, i + 1, source, target)
            progressCallback(i + 1, total)
        }

        if (progressFile.exists()) progressFile.delete()

        // Optionally copy to Downloads
        return@withContext try {
            if (saveToDownloads) {
                val displayName = outputFile.name
                val saved = saveFileToDownloads(outputFile, displayName)
                saved
            } else {
                outputFile.absolutePath
            }
        } catch (e: Exception) {
            // Fallback to returning the app file path
            outputFile.absolutePath
        }
    }

    private fun readTextFromFile(file: File): String {
        return file.readText(Charsets.UTF_8)
    }

    private fun readTextFromUri(uri: Uri): String {
        context.contentResolver.openInputStream(uri).use { stream ->
            val reader = BufferedReader(InputStreamReader(stream, Charsets.UTF_8))
            val sb = StringBuilder()
            var line: String?
            while (true) {
                line = reader.readLine() ?: break
                sb.append(line).append('\n')
            }
            return sb.toString()
        }
    }

    private fun parseSrt(text: String): MutableList<SrtEntry> {
        val blocks = text.split(Regex("\\r?\\n\\r?\\n"))
        val list = mutableListOf<SrtEntry>()
        for (block in blocks) {
            val lines = block.trim().split(Regex("\\r?\\n"))
            if (lines.size >= 2) {
                val idx = lines[0].toIntOrNull() ?: (list.size + 1)
                val timing = lines[1]
                val txt = if (lines.size > 2) lines.subList(2, lines.size).joinToString("\n") else ""
                list.add(SrtEntry(idx, timing, txt))
            }
        }
        return list
    }

    private fun saveSrt(entries: List<SrtEntry>, file: File) {
        val sb = StringBuilder()
        for ((i, e) in entries.withIndex()) {
            sb.append(e.index).append('\n')
            sb.append(e.timing).append('\n')
            sb.append(e.text.trim()).append('\n')
            if (i < entries.size - 1) sb.append('\n')
        }
        file.writeText(sb.toString(), Charsets.UTF_8)
    }

    private fun loadProgress(progressFile: File, source: String, target: String): Int {
        if (!progressFile.exists()) return 0
        return try {
            val jo = JSONObject(progressFile.readText(Charsets.UTF_8))
            val s = jo.optString("source", "")
            val t = jo.optString("target", "")
            if (s != source || t != target) return 0
            jo.optInt("last_index", 0)
        } catch (e: Exception) {
            0
        }
    }

    private fun saveProgress(progressFile: File, lastIndex: Int, source: String, target: String) {
        try {
            val jo = JSONObject()
            jo.put("last_index", lastIndex)
            jo.put("source", source)
            jo.put("target", target)
            progressFile.writeText(jo.toString(), Charsets.UTF_8)
        } catch (_: Exception) {
        }
    }

    private fun translateTextWithRetries(text: String, source: String, target: String): String {
        var pause = 2_000L
        var attempts = 0
        while (true) {
            try {
                val detectedSource = if (source == "auto") detectLanguage(text) else source
                return translateRequest(text, detectedSource ?: source, target)
            } catch (e: Exception) {
                attempts++
                if (attempts >= 6) throw e
                Thread.sleep(pause)
                pause = (pause * 2).coerceAtMost(60_000L)
            }
        }
    }

    private fun detectLanguage(text: String): String? {
        val url = "$API_BASE/detect"
        val media = "application/json; charset=utf-8".toMediaType()
        val bodyObj = JSONObject()
        bodyObj.put("q", text)
        val body = bodyObj.toString().toRequestBody(media)
        val req = Request.Builder().url(url).post(body).build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw Exception("Detect failed: ${resp.code}")
            val s = resp.body?.string() ?: return null
            val arr = JSONArray(s)
            if (arr.length() > 0) {
                val first = arr.getJSONObject(0)
                return first.optString("language", null)
            }
            return null
        }
    }

    private fun translateRequest(text: String, source: String, target: String): String {
        val url = "$API_BASE/translate"
        val media = "application/json; charset=utf-8".toMediaType()
        val bodyObj = JSONObject()
        bodyObj.put("q", text)
        bodyObj.put("source", source)
        bodyObj.put("target", target)
        bodyObj.put("format", "text")
        val body = bodyObj.toString().toRequestBody(media)
        val req = Request.Builder().url(url).post(body).build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw Exception("Translate failed: ${resp.code}")
            val s = resp.body?.string() ?: return ""
            val jo = JSONObject(s)
            return jo.optString("translatedText", "")
        }
    }

    private fun queryFileNameFromUri(uri: Uri): String {
        return try {
            context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val nameIndex = cursor.getColumnIndex("_display_name")
                if (nameIndex != -1 && cursor.moveToFirst()) {
                    cursor.getString(nameIndex)
                } else {
                    uri.lastPathSegment ?: "subtitulo.srt"
                }
            } ?: uri.lastPathSegment ?: "subtitulo.srt"
        } catch (e: Exception) {
            uri.lastPathSegment ?: "subtitulo.srt"
        }
    }

    private fun saveFileToDownloads(file: File, displayName: String): String {
        // API 29+ use MediaStore
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val resolver = context.contentResolver
            val contentValues = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, displayName)
                put(MediaStore.Downloads.MIME_TYPE, "text/plain")
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            }
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                ?: throw Exception("No se pudo crear URI en MediaStore")
            resolver.openOutputStream(uri).use { out ->
                if (out == null) throw Exception("No se pudo abrir stream de salida")
                file.inputStream().use { input ->
                    input.copyTo(out)
                }
            }
            return uri.toString()
        } else {
            // Legacy path for older devices
            val downloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
            if (!downloads.exists()) downloads.mkdirs()
            val dest = File(downloads, displayName)
            file.copyTo(dest, overwrite = true)
            return dest.absolutePath
        }
    }
}
