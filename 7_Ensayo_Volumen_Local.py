import whisper
import sqlite3
import os
import numpy as np
import re
import difflib

# --- CONFIGURACIÓN ---
DB_INPUT = "audios_grabados.db"
DB_OUTPUT = "audios_transcritos.db"
MODEL = "small"
REFERENCIA = "el volumen de mi voz cambia en cada grabación"


# === FUNCIONES AUXILIARES ===
def normalize_for_wer(text):
    if text is None:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_for_cer(text):
    if text is None:
        return ""
    text = normalize_for_wer(text)
    return text.replace(" ", "")


def word_error_details(reference, hypothesis):
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    seq = difflib.SequenceMatcher(None, ref_words, hyp_words)
    S = D = I = M = 0
    for tag, i1, i2, j1, j2 in seq.get_opcodes():
        if tag == 'replace':
            S += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            D += i2 - i1
        elif tag == 'insert':
            I += j2 - j1
        elif tag == 'equal':
            M += (i2 - i1)
    N = len(ref_words)
    wer = (S + D + I) / N if N > 0 else 0.0
    return {"wer": wer, "S": S, "D": D, "I": I, "M": M, "N": N}


def char_error_details(reference, hypothesis):
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    seq = difflib.SequenceMatcher(None, ref_chars, hyp_chars)
    S = D = I = M = 0
    for tag, i1, i2, j1, j2 in seq.get_opcodes():
        if tag == 'replace':
            S += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            D += i2 - i1
        elif tag == 'insert':
            I += j2 - j1
        elif tag == 'equal':
            M += (i2 - i1)
    N = len(ref_chars)
    cer = (S + D + I) / N if N > 0 else 0.0
    return {"cer": cer, "S": S, "D": D, "I": I, "M": M, "N": N}


# === BASE DE DATOS ===
def init_db_transcripciones(db_path=DB_OUTPUT):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcripciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                transcription TEXT,
                wer REAL,
                cer REAL,
                wer_details TEXT,
                cer_details TEXT
            )
        """)
        conn.commit()


def listar_audios_disponibles():
    with sqlite3.connect(DB_INPUT) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, max_rms, avg_rms, avg_rms_voz FROM grabaciones")
        registros = cursor.fetchall()

    if not registros:
        print("No hay audios registrados.")
        return []

    print("\n=== AUDIOS DISPONIBLES ===")
    print(f"{'ID':<5} {'Archivo':<40} {'Max RMS':<10} {'Avg RMS':<10} {'RMS Voz':<10}")
    print("-" * 94)

    def safe_float(x):
        """Convierte cualquier tipo (bytes, str, float, None) a float."""
        if isinstance(x, float):
            return x
        elif isinstance(x, (int, np.integer)):
            return float(x)
        elif isinstance(x, (bytes, bytearray)):
            try:
                return float(x.decode(errors="ignore"))
            except Exception:
                try:
                    return float(np.frombuffer(x, dtype=np.float32)[0])
                except Exception:
                    return np.nan
        elif isinstance(x, str):
            try:
                return float(x.strip())
            except ValueError:
                return np.nan
        else:
            return np.nan

    for id_, fn, max_r, avg_r, voz_r in registros:
        max_r = safe_float(max_r)
        avg_r = safe_float(avg_r)
        voz_r = safe_float(voz_r)
        print(f"{id_:<5} {fn:<40} {max_r:<10.4f} {avg_r:<10.4f} {voz_r:<10.4f}")

    return registros


def obtener_audios_por_id(ids):
    with sqlite3.connect(DB_INPUT) as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in ids)
        query = f"SELECT id, filename, audio FROM grabaciones WHERE id IN ({placeholders})"
        cursor.execute(query, ids)
        return cursor.fetchall()


def transcribir_y_guardar(audios):
    model = whisper.load_model(MODEL)
    print(f"\nModelo '{MODEL}' cargado correctamente.")

    wers = []
    cers = []

    for idx, (audio_id, filename, audio_blob) in enumerate(audios, 1):
        temp_path = f"temp_{filename}"
        with open(temp_path, "wb") as f:
            f.write(audio_blob)

        print(f"\n[{idx}/{len(audios)}] Transcribiendo: {filename}")
        result = model.transcribe(temp_path, language="es")
        texto = result.get("text", "").strip()

        ref_wer = normalize_for_wer(REFERENCIA)
        hyp_wer = normalize_for_wer(texto)
        ref_cer = normalize_for_cer(REFERENCIA)
        hyp_cer = normalize_for_cer(texto)

        wer_info = word_error_details(ref_wer, hyp_wer)
        cer_info = char_error_details(ref_cer, hyp_cer)

        os.remove(temp_path)

        with sqlite3.connect(DB_OUTPUT) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transcripciones (filename, transcription, wer, cer, wer_details, cer_details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (filename, texto, wer_info["wer"], cer_info["cer"], str(wer_info), str(cer_info)))
            conn.commit()

        wers.append(wer_info["wer"])
        cers.append(cer_info["cer"])

        print(f"{filename}:")
        print(f"   → Transcripción: {texto}")
        print(f"   → WER: {wer_info['wer']:.2%} | CER: {cer_info['cer']:.2%}")

    # === RESUMEN FINAL ===
    if wers and cers:
        wer_mean, cer_mean = np.mean(wers), np.mean(cers)
        wer_std, cer_std = np.std(wers), np.std(cers)
        print("\n=== RESUMEN FINAL ===")
        print(f"WER medio: {wer_mean:.2%} (±{wer_std:.2%})")
        print(f"CER medio: {cer_mean:.2%} (±{cer_std:.2%})")
        print(f"WER máx: {np.max(wers):.2%} | WER mín: {np.min(wers):.2%}")
        print(f"CER máx: {np.max(cers):.2%} | CER mín: {np.min(cers):.2%}")


if __name__ == "__main__":
    init_db_transcripciones()

    print("=== TRANSCRIPCIÓN MANUAL DE AUDIOS ===")
    audios_disponibles = listar_audios_disponibles()

    if not audios_disponibles:
        print("No hay audios para transcribir. Graba algunos primero con 'grabar_audios.py'.")
    else:
        seleccion = input("\nIntroduce los IDs de los audios que quieres transcribir (ej: 1,3,5): ").strip()
        if not seleccion:
            print("No se introdujeron IDs. Saliendo...")
        else:
            try:
                ids = [int(x) for x in seleccion.split(",") if x.strip().isdigit()]
                audios = obtener_audios_por_id(ids)

                if not audios:
                    print("No se encontraron audios con esos IDs.")
                else:
                    transcribir_y_guardar(audios)
                    print("\nTranscripciones completadas y guardadas en 'audios_transcritos.db'.")
            except Exception as e:
                print(f"Error procesando la selección: {e}")
