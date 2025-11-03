import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os
import sqlite3
import webrtcvad
import time
from collections import deque

# --- CONFIGURACIÓN ---
SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)
SEGMENTO_DURACION = 10.0  # segundos por bloque
ENERGY_THRESHOLD = 500  # umbral RMS para detectar voz
PRE_BUFFER_DUR = 0.5  # segundos antes de la detección de voz
DB_PATH = "audios_grabados_frases.db"
VAD_MODE = 1  # 0 = menos estricto, 3 = más estricto

vad = webrtcvad.Vad(VAD_MODE)

# === FUNCIONES AUXILIARES ===
def rms_solo_voz(filename, vad_mode=1):
    """Calcula el RMS promedio solo en frames con voz."""
    rate, audio = wav.read(filename)
    if len(audio.shape) > 1:
        audio = audio[:, 0]
    vad = webrtcvad.Vad(vad_mode)
    frame_len = int(rate * 30 / 1000)
    num_frames = len(audio) // frame_len

    rms_voz = []
    for i in range(num_frames):
        frame = audio[i * frame_len:(i + 1) * frame_len]
        frame_bytes = frame.tobytes()
        try:
            if vad.is_speech(frame_bytes, rate):
                rms_voz.append(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        except Exception:
            continue

    if rms_voz:
        return float(np.mean(rms_voz))
    else:
        return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

def hay_voz(audio_chunk):
    """Determina si hay voz en un chunk de audio."""
    if len(audio_chunk) < FRAME_SIZE:
        return False
    num_frames = len(audio_chunk) // FRAME_SIZE
    for i in range(num_frames):
        frame = audio_chunk[i * FRAME_SIZE:(i + 1) * FRAME_SIZE]
        frame_bytes = frame.tobytes()
        try:
            vad_result = vad.is_speech(frame_bytes, SAMPLE_RATE)
        except Exception:
            vad_result = False
        rms = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
        if vad_result and rms > ENERGY_THRESHOLD:
            return True
    return False


# === BASE DE DATOS ===
def init_db(db_path=DB_PATH):
    """Crea la base de datos si no existe."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grabaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                audio BLOB,
                max_rms REAL,
                avg_rms REAL,
                avg_rms_voz REAL,
                tipo INTEGER,
                frase INTEGER,
                version INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_audio(filename, max_rms, avg_rms, avg_rms_voz, tipo, frase, version, db_path=DB_PATH):
    """Guarda el audio y sus métricas básicas en la base de datos."""
    with open(filename, "rb") as f:
        audio_blob = f.read()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO grabaciones (filename, audio, max_rms, avg_rms, avg_rms_voz, tipo, frase, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (os.path.basename(filename), audio_blob, max_rms, avg_rms, avg_rms_voz, tipo, frase, version))
        conn.commit()
    print(f"✅ Audio '{filename}' guardado en la base de datos.")


# === GRABACIÓN AUTOMÁTICA ===
def grabar_por_voz(tipo, frase, version):
    print("\n🎤 Esperando voz... (Ctrl+C para salir)")
    pre_buffer = deque(maxlen=int(PRE_BUFFER_DUR * SAMPLE_RATE))
    recording = []
    en_grabacion = False
    max_rms = 0.0
    rms_values = []

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
            while True:
                frame, _ = stream.read(FRAME_SIZE)
                frame = frame[:, 0]
                rms_frame = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
                rms_values.append(rms_frame)
                max_rms = max(max_rms, rms_frame)

                # Si no estamos grabando, esperamos voz
                if not en_grabacion:
                    pre_buffer.extend(frame)
                    if hay_voz(frame):
                        print("🔊 Voz detectada, iniciando grabación...")
                        en_grabacion = True
                        recording.append(np.array(pre_buffer))
                        pre_buffer.clear()
                        inicio_bloque = time.time()
                else:
                    recording.append(frame)
                    tiempo_actual = time.time()
                    if tiempo_actual - inicio_bloque >= SEGMENTO_DURACION:
                        # Se cumple el bloque de 10s → verificamos si hay voz
                        verif_frames = []
                        for _ in range(int(0.5 * 1000 / FRAME_DURATION)):
                            frame_verif, _ = stream.read(FRAME_SIZE)
                            frame_verif = frame_verif[:, 0]
                            verif_frames.append(frame_verif)
                        verif_audio = np.concatenate(verif_frames)
                        recording.append(verif_audio)
                        if not hay_voz(verif_audio):
                            print("🤫 Silencio detectado. Fin de grabación.")
                            break
                        else:
                            print("📢 Se sigue detectando voz, continuando grabación...")
                            inicio_bloque = tiempo_actual
    except KeyboardInterrupt:
        print("\nInterrumpido por usuario.")
        return None, None, None, None

    if not recording:
        print("No se grabó ningún audio.")
        return None, None, None, None

    audio_data = np.concatenate(recording)
    avg_rms = float(np.mean(rms_values)) if rms_values else 0.0

    # --- Calcular RMS solo en voz ---
    temp_filename = os.path.join(os.getcwd(), "audio_temp.wav")
    wav.write(temp_filename, SAMPLE_RATE, audio_data)
    avg_rms_voz = rms_solo_voz(temp_filename, VAD_MODE)

    # --- Nombre final ---
    final_filename = os.path.join(os.getcwd(), f"audio_tipo{tipo}_frase{frase}_version{version}.wav")
    if os.path.exists(final_filename):
        os.remove(final_filename)
    os.rename(temp_filename, final_filename)

    print(f"\n📁 Audio guardado como: {final_filename}")
    print(f"📊 RMS promedio total: {avg_rms:.4f}")
    print(f"📊 RMS máximo: {max_rms:.4f}")
    print(f"📊 RMS promedio (solo voz): {avg_rms_voz:.4f}")

    return final_filename, max_rms, avg_rms, avg_rms_voz


# === MAIN ===
if __name__ == "__main__":
    init_db()
    print("=== Sistema de Grabación Automática ===")

    while True:
        try:
            tipo = int(input("\nIngrese el número de tipo (X): "))
            frase = int(input("Ingrese el número de frase (Y): "))
            version = int(input("Ingrese el número de versión (Z): "))

            archivo, max_rms, avg_rms, avg_rms_voz = grabar_por_voz(tipo, frase, version)
            if archivo:
                save_audio(archivo, max_rms, avg_rms, avg_rms_voz, tipo, frase, version)

            print("\n¿Deseas grabar otro audio? (Y para continuar, otra tecla para salir)")
            if input("> ").strip().lower() != "y":
                print("👋 Saliendo del programa.")
                break

        except ValueError:
            print("⚠️ Ingresa números válidos para tipo, frase y versión.")

