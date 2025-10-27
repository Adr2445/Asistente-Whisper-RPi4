import sounddevice as sd
from scipy.io.wavfile import write

# Parámetros de grabación
DURACION = 10        # duración del audio a grabar en segundos
FS = 44100           # frecuencia de muestreo, necesaria para la función "sd.rec"
FICHERO = "grabacion_prueba.wav" # nombre con el que se guardará el audio

print("Grabando...")

# Grabar audio
audio = sd.rec(int(DURACION * FS), samplerate=FS, channels=1, dtype='int16')
sd.wait()  # Esperar a que finalice la grabación

print("Grabación finalizada, guardando archivo...")

# Guardar en WAV
write(FICHERO, FS, audio)

print(f"Archivo guardado como {FICHERO}")
