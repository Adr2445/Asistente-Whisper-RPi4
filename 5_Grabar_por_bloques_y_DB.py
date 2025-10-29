import sounddevice as sd        
import numpy as np              
import webrtcvad                
import whisper                  
import scipy.io.wavfile as wav  
import os, time, sqlite3
from datetime import datetime
from collections import deque   # Estructura FIFO usada como buffer circular

# --- CONFIGURACIÓN ---
SAMPLE_RATE = 16000             # Frecuencia de muestreo (Hz) (necesaria para pasar de señal analógica a digital)
CHANNELS = 1                    # Monocanal (un solo canal de audio)
FRAME_DURATION = 30             # Duración de cada frame en ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)  # Muestras por frame
VAD_MODE = 1                    # Sensibilidad del detector de voz (0=sensible, 3=estricto)
MODEL = "base"                  # Modelo Whisper a usar
SEGMENTO_DURACION = 10.0        # Duración máxima de cada bloque grabado (segundos)
PRE_BUFFER_DUR = 0.5            # Audio previo antes de detectar voz (segundos)
ENERGY_THRESHOLD = 500         # Umbral RMS mínimo para considerar voz
DB_PATH = "audios_distancia.db" # Ruta de la base de datos SQLite

vad = webrtcvad.Vad(VAD_MODE)   # Inicializa el detector de voz

# === BASE DE DATOS ===
def init_db(db_path=DB_PATH): # Crea una base de datos para almacenar los audios grabados y las transcripciones
    """Crea la tabla si no existe."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                audio BLOB,
                transcription TEXT,
                max_rms REAL,
                reference_text TEXT,
                grabacion_duracion REAL,
                transcripcion_duracion REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_to_db(filename, transcription=None, max_rms=None, reference_text=None,
               grabacion_duracion=None, transcripcion_duracion=None, db_path=DB_PATH):
    """Guarda el audio y su información en la base de datos."""
    with open(filename, "rb") as f:
        audio_blob = f.read()  # Carga el archivo en binario
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audios (filename, audio, transcription, max_rms, reference_text, 
                                grabacion_duracion, transcripcion_duracion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (os.path.basename(filename), audio_blob, transcription, max_rms,
              reference_text, grabacion_duracion, transcripcion_duracion))
        conn.commit()
    print(f"Audio '{os.path.basename(filename)}' guardado en la base de datos "
          f"(RMS máx: {max_rms:.2f}, Grabación: {grabacion_duracion:.2f}s, "
          f"Transcripción: {transcripcion_duracion:.2f}s).")

# === DETECCIÓN DE VOZ ===
def hay_voz(audio_chunk):
    """Evalúa si el fragmento contiene voz (VAD + RMS)."""
    if len(audio_chunk) < FRAME_SIZE:
        return False
    num_frames = len(audio_chunk) // FRAME_SIZE
    for i in range(num_frames):
        frame = audio_chunk[i * FRAME_SIZE:(i + 1) * FRAME_SIZE]
        frame_bytes = frame.tobytes()
        try:
            vad_result = vad.is_speech(frame_bytes, SAMPLE_RATE)  # Detección binaria
        except Exception:
            vad_result = False
        rms = np.sqrt(np.mean(frame.astype(np.float32) ** 2))     # Energía RMS del frame
        if vad_result and rms > ENERGY_THRESHOLD:                 # Se considera voz si cumple ambos
            return True
    return False

# === GRABACIÓN ===
def grabar_por_bloques():
    """Graba audio en bloques hasta detectar silencio prolongado."""
    print("Esperando voz... (Ctrl+C para salir)")

    pre_buffer = deque(maxlen=int(PRE_BUFFER_DUR * SAMPLE_RATE))  # Guarda audio previo
    recording = []              # Lista donde se acumulan frames
    en_grabacion = False
    max_rms = 0.0
    inicio_bloque = None
    tiempo_inicio = time.time()  # Inicio de la sesión completa

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
            while True:
                frame, _ = stream.read(FRAME_SIZE)     # Lee un bloque de audio
                frame = frame[:, 0]                    # Canal único
                rms_frame = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
                max_rms = max(max_rms, rms_frame)      # Guarda el RMS máximo detectado

                if not en_grabacion:
                    pre_buffer.extend(frame)           # Guarda los últimos frames previos
                    if hay_voz(frame):                 # Si hay voz → inicia grabación
                        print("Voz detectada, iniciando grabación...")
                        en_grabacion = True
                        inicio_bloque = time.time()
                        recording.append(np.array(pre_buffer))
                        pre_buffer.clear()
                else:
                    recording.append(frame)
                    tiempo_actual = time.time()
                    # Cada 10 s verifica si sigue habiendo voz
                    if tiempo_actual - inicio_bloque >= SEGMENTO_DURACION:
                        inicio_bloque = tiempo_actual
                        verif_frames = []
                        for _ in range(int(0.5 * 1000 / FRAME_DURATION)):  # 0.5 s de verificación
                            frame_verif, _ = stream.read(FRAME_SIZE)
                            frame_verif = frame_verif[:, 0]
                            verif_frames.append(frame_verif)
                        verif_audio = np.concatenate(verif_frames)
                        recording.append(verif_audio)
                        if not hay_voz(verif_audio):
                            print("Silencio detectado. Fin de grabación.")
                            break
                        else:
                            print("Continuando grabación...")

    except KeyboardInterrupt:
        print("\nInterrumpido por usuario.")
        return None, None, None

    if not recording:
        print("No se grabó ningún audio.")
        return None, None, None

    # --- Guardar el audio grabado ---
    audio_data = np.concatenate(recording)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")   # Nombre único con fecha/hora para cada audio (así no se sobreescriben)
    filename = os.path.join(os.getcwd(), f"audio_{timestamp}.wav")
    wav.write(filename, SAMPLE_RATE, audio_data)            # Guarda el archivo WAV
    tiempo_fin = time.time()
    duracion = tiempo_fin - tiempo_inicio                   # Duración total
    print(f"Audio guardado: {filename} (Duración: {duracion:.2f} s)")
    return filename, max_rms, duracion

# === TRANSCRIPCIÓN ===
def transcribir_audio(ruta_audio, modelo=MODEL):
    """Transcribe el audio y mide el tiempo que tarda."""
    print(f"Transcribiendo con Whisper... Ruta: {ruta_audio}")
    if not os.path.exists(ruta_audio):
        print("El archivo no existe.")
        return "(Archivo de audio no encontrado)", 0.0

    model = whisper.load_model(modelo)                # Carga el modelo especificado
    inicio = time.time()
    result = model.transcribe(ruta_audio, language="es")  # Transcripción en español
    fin = time.time()
    duracion_transcripcion = fin - inicio

    texto = result.get("text", "")                    # Obtiene el texto reconocido
    print(f"\nTranscripción: {texto}")
    print(f"Tiempo de transcripción: {duracion_transcripcion:.2f} s")

    return texto, duracion_transcripcion

# === MAIN ===
if __name__ == "__main__":
    init_db()  # Crea la base de datos si no existe

    archivo, max_rms, duracion_grabacion = grabar_por_bloques()
    if archivo:
        texto, duracion_transcripcion = transcribir_audio(archivo) # Llama a la función que transcribe y muestra todo por terminal
        # Guarda todo en la base de datos
        save_to_db(
            archivo,
            transcription=texto,
            max_rms=max_rms,
            grabacion_duracion=duracion_grabacion,
            transcripcion_duracion=duracion_transcripcion
        )
