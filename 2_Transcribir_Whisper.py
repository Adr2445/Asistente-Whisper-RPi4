

import sounddevice as sd
from scipy.io.wavfile import write
import whisper

# Parámetros de grabación
DURACION = 10        # segundos
FS = 44100           # frecuencia de muestreo (44.1 kHz estándar)
FICHERO = "grabacion.wav" # nombre archivo de audio

print("Grabando...")

# Grabar audio
audio = sd.rec(int(DURACION * FS), samplerate=FS, channels=1, dtype='int16')
sd.wait()  # Esperar a que finalice la grabación

print("Grabación finalizada, guardando archivo...")

# Guardar en WAV
write(FICHERO, FS, audio)

print(f"Archivo guardado como {FICHERO}")

# Transcripción con Whisper
print("Cargando modelo Whisper")
modelo = whisper.load_model("tiny") 

print("Transcribiendo audio")
resultado = modelo.transcribe(FICHERO, language="es") # se configura transcripción en español

print("\nTranscripción:")
print(resultado["text"])
