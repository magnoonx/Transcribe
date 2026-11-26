const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;

function createWindow() {
    // Configuración de la ventana transparente
    mainWindow = new BrowserWindow({
        width: 1000,
        height: 200,
        x: 460, // Ajustado para centrar aproximadamente en pantallas estándar
        y: 750, // Posicionado en la parte inferior
        transparent: true,    // Hace el fondo invisible
        frame: false,         // Quita los bordes de la ventana
        alwaysOnTop: true,    // Se mantiene sobre VLC
        resizable: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    // Carga el diseño HTML
    mainWindow.loadFile('index.html');

    // Permite hacer clic a través de la ventana (para no bloquear VLC)
    mainWindow.setIgnoreMouseEvents(true, { forward: true });

    // --- CONFIGURACIÓN DE RUTAS ---
    // Usamos path.resolve para obtener la ruta absoluta real en Windows
    const pythonPath = path.resolve(__dirname, '.envTranscribe/Scripts/python.exe');
    const scriptPath = path.resolve(__dirname, 'transcribe.py');

    console.log('--- Iniciando Procesos ---');
    console.log('Ruta Python:', pythonPath);
    console.log('Ruta Script:', scriptPath);

    // Validación de seguridad
    if (!fs.existsSync(pythonPath)) {
        console.error("¡ERROR!: No se encontró el ejecutable en .venv/Scripts/python.exe");
        return;
    }

    // --- LANZAMIENTO DEL SCRIPT DE PYTHON ---
    const py = spawn(pythonPath, [scriptPath], {
        shell: false,
        windowsHide: true // Oculta la ventana de comandos negra de Python
    });

    // Captura la salida de texto de Whisper
    py.stdout.on('data', (data) => {
        const text = data.toString().trim();
        if (text) {
            console.log('Traducción recibida:', text);
            // Envía el texto al archivo index.html
            mainWindow.webContents.send('new-text', text);
        }
    });

    // Captura errores de Python
    py.stderr.on('data', (data) => {
        console.error(`Error de Python: ${data}`);
    });

    py.on('close', (code) => {
        console.log(`Proceso de Python finalizado con código: ${code}`);
    });
}

// Iniciar Electron
app.whenReady().then(createWindow);

// Cerrar todo al salir
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});