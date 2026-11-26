# Subtranslator (Android)

Proyecto Android minimal que implementa el flujo de traducción de SRT similar a la versión Python.

Requisitos:
- Android Studio (última versión recomendada)
- SDK Platforms: Android 34
- Gradle 8.x compatible (el wrapper en el proyecto usa Gradle 8.4.1)

Qué incluye:
- Lógica para seleccionar un archivo SRT desde el dispositivo
- Selección de idioma de entrada (incluye `auto` para detección automática)
- Selección de idioma de salida
- Traducción vía API pública de LibreTranslate (https://libretranslate.de)
- Guardado del SRT traducido en `getExternalFilesDir(null)` y archivo de progreso JSON para reanudar

Cómo abrir:
1. Abre Android Studio
2. Selecciona "Open" y elige la carpeta `Subtranslator` en la raíz del repositorio
3. Deja que Android Studio sincronice Gradle (puede descargar dependencias)
4. Ejecuta la app en un emulador o dispositivo físico con acceso a Internet

Notas:
- La app usa la instancia pública de LibreTranslate. Para uso intensivo o producción, configura un servidor propio o cambia `API_BASE` en `TranslationManager.kt` a la URL de tu servicio.
- Los archivos resultantes se escriben en el almacenamiento de la app: `Android/data/<package>/files/` o `getExternalFilesDir(null)`.
- Si quieres que el archivo se guarde en `Downloads`, puedo añadir esa opción y manejo de permisos.

Siguientes pasos sugeridos:
- Añadir íconos y mejoras de UI
- Manejo de errores más exhaustivo y reintentos visibles
- Soporte para traducir usando un backend Python local (si prefieres reutilizar la lógica existente)
