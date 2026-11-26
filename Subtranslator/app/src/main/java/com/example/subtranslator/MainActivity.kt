package com.example.subtranslator

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import android.Manifest
import android.os.Build
import androidx.appcompat.app.AppCompatActivity
import androidx.core.net.toFile
import androidx.lifecycle.lifecycleScope
import com.example.subtranslator.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var selectedUri: Uri? = null
    private val requestWritePermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        // The actual flow will handle the result inline when requested
    }

    private val pickSrtFile = registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { processSrtFile(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.buttonSelectInput.setOnClickListener {
            pickSrtFile.launch("application/x-subrip")
        }

        binding.buttonTranslate.setOnClickListener {
            val sourceLang = binding.inputSourceLanguage.text.toString().trim().ifEmpty { "auto" }
            val targetLang = binding.inputTargetLanguage.text.toString().trim().ifEmpty { "es" }
            if (sourceLang.isEmpty() || targetLang.isEmpty()) {
                binding.textStatus.text = "Ingresa ambos idiomas."
                return@setOnClickListener
            }
            val uri = selectedUri
            if (uri == null) {
                binding.textStatus.text = "Selecciona primero un archivo SRT."
                return@setOnClickListener
            }

            binding.buttonTranslate.isEnabled = false
            binding.buttonSelectInput.isEnabled = false
            binding.textStatus.text = "Iniciando traducción..."

            lifecycleScope.launchWhenStarted {
                try {
                    val manager = TranslationManager(this@MainActivity)
                    val saveToDownloads = binding.switchSaveDownloads.isChecked
                    if (saveToDownloads && Build.VERSION.SDK_INT < 29) {
                        // request legacy write permission
                        val granted = requestWritePermission.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                        // Note: the launcher returns asynchronously; we proceed and rely on user granting permission
                    }

                    manager.translateSrt(uri, sourceLang, targetLang, { done, total ->
                        runOnUiThread {
                            binding.textStatus.text = "Progreso: $done / $total"
                        }
                    }, saveToDownloads).also { outputPath ->
                        runOnUiThread {
                            binding.textStatus.text = "Traducción completa:\n$outputPath"
                        }
                    }
                } catch (e: Exception) {
                    runOnUiThread {
                        binding.textStatus.text = "Error: ${e.message}"
                    }
                } finally {
                    runOnUiThread {
                        binding.buttonTranslate.isEnabled = true
                        binding.buttonSelectInput.isEnabled = true
                    }
                }
            }
        }
    }

    private fun processSrtFile(uri: Uri) {
        selectedUri = uri
        binding.textStatus.text = "Procesando archivo..."
        lifecycleScope.launch {
            val fileName = queryFileName(uri)
            binding.textStatus.text = "Archivo seleccionado: $fileName"
        }
    }

    private suspend fun queryFileName(uri: Uri): String = withContext(Dispatchers.IO) {
        return@withContext try {
            contentResolver.query(uri, null, null, null, null)?.use { cursor ->
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
}
