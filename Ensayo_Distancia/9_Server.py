# server.py
# REQUISITOS: pip install fastapi uvicorn[standard] python-multipart whisper
# Si usas GPU y la versión compatible de whisper, instala las dependencias CUDA apropiadas.

from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse
import time
import os
import tempfile
import whisper
from typing import Optional

API_TOKEN = "clave123"
MODEL_NAME = os.environ.get("TRANSCRIBE_MODEL", "large")  # modelo con el que se transcribe

app = FastAPI(title="Whisper Transcription Server")

# Cargamos el modelo una vez en el arranque (puede tardar varios segundos/minutos).
print(f"Cargando modelo Whisper '{MODEL_NAME}' ...")
t0 = time.time()
model = whisper.load_model(MODEL_NAME)
t1 = time.time()
print(f"Modelo cargado en {t1 - t0:.2f}s")


def check_api_token(token: Optional[str]):
    if token is None or token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), x_api_key: Optional[str] = Header(None), language: Optional[str] = "es"):
    """
    Recibe un archivo de audio (wav) y devuelve la transcripción JSON.
    Requiere cabecera X-API-KEY con el token (simple auth).
    """
    check_api_token(x_api_key)

    # Guardar el archivo temporalmente
    suffix = os.path.splitext(file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        contents = await file.read()
        tmp.write(contents)

    # Comprueba que el archivo existe y no esté vacío
    if os.path.getsize(tmp_path) == 0:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail="Archivo vacío")

    # Realizar la transcripción y medir tiempos
    start_trans = time.time()
    try:
        # Usamos language si se especifica (p. ej. "es")
        result = model.transcribe(tmp_path, language=language)
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Error en transcripción: {str(e)}")
    end_trans = time.time()

    # Limpiar archivo temporal
    os.remove(tmp_path)

    text = result.get("text", "")
    response = {
        "transcription": text,
        "model": MODEL_NAME,
        "transcription_time_s": end_trans - start_trans,
        "model_load_time_s": t1 - t0,
        # Añade campos adicionales si quieres (segments, confidence, etc.)
    }
    return JSONResponse(response)
