import sqlite3
import os
import numpy as np
import re
import difflib
import requests

# --- CONFIGURACIÓN ---
DB_INPUT = "audios_grabados.db"
DB_OUTPUT = "audios_transcritos.db"
REFERENCIA = "el volumen de mi voz cambia en cada grabación"

# Configuración del servidor remoto
TRANSCRIBE_SERVER = os.environ.get("TRANSCRIBE_SERVER", "http://192.168.1.12:8000")
API_TOKEN = "clave123"
TRANSCRIBE_ENDPOINT = f"{TRANSCRIBE_SERVER.rstrip('/')}/transcribe"


# === NORMALIZACIÓN ===
def normalize_for_wer(text):
    if text is None:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_for_cer(text):
    return normalize_for_wer(text).replace(" ", "")


# === FUNCIONES DE ERROR DETALLADAS ===
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
    """Crea la tabla de transcripciones si no existe."""
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
            cer_details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()


def seleccionar_audios():
    """Permite al usuario elegir hasta 10 audios."""
    with sqlite3.connect(DB_INPUT) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename FROM grabaciones")
        registros = cursor.fetchall()

        if not registros:
            print("No hay audios en la base de datos.")
            return []

        print("\n=== AUDIOS DISPONIBLES ===")
        print(f"{'ID':<5} {'Archivo':<40}")
        print("-" * 50)
        for id_, fn in registros:
            print(f"{id_:<5} {fn:<40}")

        seleccion = input("\nIntroduce los IDs de los audios (máx. 10, separados por comas): ").strip()
        ids = [int(x) for x in seleccion.split(",") if x.strip().isdigit()]
        ids = ids[:10]

        if not ids:
            print("No se seleccionaron audios.")
            return []

        ph = ",".join("?" * len(ids))
        cursor.execute(f"SELECT id, filename, audio FROM grabaciones WHERE id IN ({ph})", ids)
        audios = cursor.fetchall()

        print(f"\nSe han seleccionado {len(audios)} audios para transcribir.\n")
        return audios


# === ENVÍO AL SERVIDOR ===
def enviar_a_servidor(filename, audio_blob, language="es"):
    headers = {"X-API-KEY": API_TOKEN}
    files = {"file": (filename, audio_blob, "audio/wav")}
    params = {"language": language}
    try:
        resp = requests.post(TRANSCRIBE_ENDPOINT, headers=headers, files=files, params=params, timeout=180)
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: {e}")
        return None

    if resp.status_code != 200:
        print(f"Error del servidor: {resp.status_code} - {resp.text}")
        return None

    data = resp.json()
    return data.get("transcription", "")


# === PROCESO PRINCIPAL ===
def transcribir_lote(audios):
    wers, cers = [], []

    for idx, (audio_id, filename, audio_blob) in enumerate(audios, 1):
        print(f"\n[{idx}/{len(audios)}] Enviando '{filename}' al servidor...")

        texto = enviar_a_servidor(filename, audio_blob)
        if texto is None:
            continue

        ref = REFERENCIA

        wer_info = word_error_details(normalize_for_wer(ref), normalize_for_wer(texto))
        cer_info = char_error_details(normalize_for_cer(ref), normalize_for_cer(texto))

        wers.append(wer_info["wer"])
        cers.append(cer_info["cer"])

        print(f"{filename}")
        print(f" → Transcripción: {texto.strip()}")
        print(f" → WER: {wer_info['wer']:.2%} | CER: {cer_info['cer']:.2%}")

        with sqlite3.connect(DB_OUTPUT) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO transcripciones (filename, transcription, wer, cer, wer_details, cer_details)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                filename,
                texto,
                wer_info["wer"],
                cer_info["cer"],
                str(wer_info),
                str(cer_info)
            ))
            conn.commit()

    # --- Mostrar estadísticas globales solo en consola ---
    if wers:
        wer_mean, cer_mean = np.mean(wers), np.mean(cers)
        wer_std, cer_std = np.std(wers), np.std(cers)
        wer_max, wer_min = np.max(wers), np.min(wers)
        cer_max, cer_min = np.max(cers), np.min(cers)

        print("\n=== RESULTADOS GLOBALES ===")
        print(f"WER medio: {wer_mean:.2%} (±{wer_std:.2%})")
        print(f"CER medio: {cer_mean:.2%} (±{cer_std:.2%})")
        print(f"WER máx: {wer_max:.2%} | WER mín: {wer_min:.2%}")
        print(f"CER máx: {cer_max:.2%} | CER mín: {cer_min:.2%}")


# === MAIN ===
if __name__ == "__main__":
    init_db_transcripciones()
    print("=== TRANSCRIPCIÓN REMOTA (DETALLADA, SIN TIEMPOS) ===")

    audios = seleccionar_audios()
    if not audios:
        print("No hay audios seleccionados o disponibles.")
    else:
        transcribir_lote(audios)
        print("\nProceso completado. Resultados guardados en 'audios_transcritos.db'.")



