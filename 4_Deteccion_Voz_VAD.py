import collections
import whisper              
import sounddevice as sd    
import numpy as np          
import webrtcvad            # Detector de voz (Voice Activity Detection)
import scipy.io.wavfile as wav  
import tempfile, os, sys

# CONFIGURACIÓN
SAMPLE_RATE = 16000          # Frecuencia de muestreo (Hz)
CHANNELS = 1                 # Monocanal (un solo canal de audio)
FRAME_DURATION = 30          # Duración de cada frame en ms 
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)  # Muestras por frame
VAD_MODE = 2                 # Nivel de sensibilidad del VAD (0 = más sensible, 3 = más estricto)
MAX_SILENCE_FRAMES = int(0.8 * 1000 / FRAME_DURATION)  # Límite de silencio (para detener grabación)
MIN_AUDIO_FRAMES = int(0.5 * 1000 / FRAME_DURATION)    # Duración mínima aceptada del audio

vad = webrtcvad.Vad(VAD_MODE)  # Inicializa el detector de voz con la sensibilidad elegida


# DETECCIÓN DE VOZ EN UN FRAME
def is_speech(frame_bytes, frame_array):
    # Determina si el frame contiene voz (según el VAD)
    is_voiced = vad.is_speech(frame_bytes, SAMPLE_RATE)

    # Calcula energía RMS del frame para filtrar ruido débil
    rms = np.sqrt(np.mean(np.square(frame_array.astype(np.float32))))
    return is_voiced and rms > 500, rms  # Umbral de RMS ajustable según ruido ambiental


# GRABACIÓN AUTOMÁTICA BASADA EN VOZ
def record_voice():
    print("Esperando voz...")
    recording = []           # Almacena los bloques de audio grabados
    silence_counter = 0      # Cuenta los frames de silencio consecutivos
    speech_counter = 0       # Cuenta frames con voz
    speech_threshold = 5     # Frames de voz necesarios para iniciar grabación
    started = False
    stop_recording = False

    # Callback que procesa cada bloque de audio entrante
    def callback(indata, _, __, status):
        nonlocal recording, silence_counter, started, speech_counter, stop_recording

        if status:
            print(f"{status}", file=sys.stderr)  # Muestra advertencias (buffer overflows, etc.)

        audio = indata[:, 0]                     # Usa el canal 0 (monocanal)
        audio_int16 = (audio * 32767).astype(np.int16)  # Convierte float32 → int16
        frame_bytes = audio_int16.tobytes()      # Convierte a bytes para VAD

        speech, rms = is_speech(frame_bytes, audio_int16)  # Evalúa si hay voz

        if speech:
            print("Voz detectada | RMS:", int(rms))
            speech_counter += 1
            silence_counter = 0  # Reinicia el conteo de silencios
            if not started and speech_counter >= speech_threshold:
                print("Voz detectada. Grabando...")
                started = True
            if started:
                recording.append(audio_int16.copy())  # Guarda el bloque
        else:
            print("Silencio | RMS:", int(rms))
            if started:
                silence_counter += 1
                # Detiene grabación si hay silencio prolongado
                if silence_counter > MAX_SILENCE_FRAMES:
                    print("Fin de grabación por silencio prolongado")
                    stop_recording = True

    # Inicia la captura de audio con el callback
    with sd.InputStream(channels=CHANNELS, samplerate=SAMPLE_RATE,
                        blocksize=FRAME_SIZE, dtype='float32',
                        callback=callback):
        while not stop_recording:
            sd.sleep(100)  # Espera 100 ms entre iteraciones

    print("Finalizando y guardando audio")

    # Si el audio grabado es muy corto, se descarta
    if len(recording) < MIN_AUDIO_FRAMES:
        print("Audio demasiado corto")
        return None

    audio_data = np.concatenate(recording)  # Une todos los bloques grabados

    print("Directorio actual:", os.getcwd())

    output_filename = "grabacion_voz.wav"
    wav.write(output_filename, SAMPLE_RATE, audio_data)  # Guarda el archivo WAV
    print(f"Audio guardado como: {output_filename} ({len(audio_data)} muestras)")

    # Verifica si el archivo se guardó correctamente
    if os.path.exists(output_filename):
        print("Archivo WAV guardado correctamente.")
    else:
        print("No se pudo guardar el archivo WAV.")
            
    return output_filename


# TRANSCRIPCIÓN CON WHISPER
def transcribir_audio(ruta_audio, modelo='tiny', idioma='es'):
    print(f"Transcribiendo con Whisper... Ruta: {ruta_audio}")
    if not os.path.exists(ruta_audio):
        print("El archivo no existe")
        return "(Archivo de audio no encontrado)"
    model = whisper.load_model(modelo)  # Carga el modelo (tiny, base, small, etc.)
    result = model.transcribe(ruta_audio, language=None)  # Transcribe el archivo
    return result['text']


# HILO PRINCIPAL
if __name__ == "__main__":
    while True:
        archivo_grabado = record_voice()  # Espera y graba cuando detecta voz
        if archivo_grabado:
            try:
                texto = transcribir_audio(archivo_grabado)
                print(f"\nTranscripción:\n{texto}\n")
            except Exception as e:
                print(f"Error al transcribir el audio: {e}")
            finally:
                print("Transcripción finalizada")
        else:
            print("Esperando nueva voz...")
            
        # Pregunta al usuario si desea volver a grabar
        while True:
            respuesta = input("¿Quieres volver a grabar? (Pulsa 'Y' para sí, cualquier otra tecla para salir): ").strip().lower()
            if respuesta == 'y':
                break  # Repite el proceso de grabación
            else:
                print("Saliendo...")
                sys.exit(0)
