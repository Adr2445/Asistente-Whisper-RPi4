import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os
import sqlite3
import webrtcvad

# --- CONFIGURACIÓN ---
SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)
SEGMENTO_DURACION = 10.0  # segundos
DB_PATH = "audios_grabados.db"
VAD_MODE = 1  # 0 = menos estricto, 3 = más estricto


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
                avg_rms_voz REAL
            )
        """)
        conn.commit()


def save_audio(filename, max_rms, avg_rms, avg_rms_voz, db_path=DB_PATH):
    """Guarda el audio y sus métricas básicas."""
    with open(filename, "rb") as f:
        audio_blob = f.read()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO grabaciones (filename, audio, max_rms, avg_rms, avg_rms_voz)
            VALUES (?, ?, ?, ?, ?)
        """, (os.path.basename(filename), audio_blob, max_rms, avg_rms, avg_rms_voz))
        conn.commit()
    print(f"Audio '{filename}' guardado en la base de datos.")


# === GRABACIÓN ===
def grabar_audio():
    print("Grabando audio de 10 segundos... (Ctrl+C para cancelar)")

    total_frames = int(SAMPLE_RATE * SEGMENTO_DURACION)
    num_chunks = total_frames // FRAME_SIZE

    recording = []
    rms_values = []
    max_rms = 0.0

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
            for _ in range(num_chunks):
                frame, _ = stream.read(FRAME_SIZE)
                frame = frame[:, 0]
                rms_frame = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
                rms_values.append(rms_frame)
                max_rms = max(max_rms, rms_frame)
                print(f"RMS actual: {rms_frame:.4f}", end="\r")
                recording.append(frame)
        print("\nGrabación completada.")
    except KeyboardInterrupt:
        print("\nGrabación interrumpida por el usuario.")
        return None, None, None, None

    audio_data = np.concatenate(recording)
    avg_rms = float(np.mean(rms_values)) if rms_values else 0.0

    # Archivo temporal
    temp_filename = os.path.join(os.getcwd(), "audio_temp.wav")
    if os.path.exists(temp_filename):
        os.remove(temp_filename)
    wav.write(temp_filename, SAMPLE_RATE, audio_data)

    # Calcular RMS solo en voz
    avg_rms_voz = rms_solo_voz(temp_filename, VAD_MODE)

    # --- Redondear y generar nombre final ---
    rms_int = int(round(avg_rms_voz))  # Solo unidades
    final_filename = os.path.join(os.getcwd(), f"audio_volumen_{rms_int}RMS.wav")

    os.rename(temp_filename, final_filename)

    print(f"\nAudio guardado como: {final_filename}")
    print(f"RMS promedio total: {avg_rms:.4f}")
    print(f"RMS máximo: {max_rms:.4f}")
    print(f"RMS promedio (solo voz): {avg_rms_voz:.4f}")
    print(f"RMS redondeado: {rms_int}")

    return final_filename, max_rms, avg_rms, avg_rms_voz


# === MAIN ===
if __name__ == "__main__":
    init_db()

    while True:
        archivo, max_rms, avg_rms, avg_rms_voz = grabar_audio()
        if archivo:
            save_audio(archivo, max_rms, avg_rms, avg_rms_voz)

        print("\n¿Deseas grabar otro audio? (Y para continuar, otra tecla para salir)")
        if input("> ").strip().lower() != "y":
            print("Saliendo del programa.")
            break
