import sounddevice as sd
import numpy as np
import sys

# Configuración
SAMPLE_RATE = 16000
CHANNELS = 1 # un solo canal (audio mono)
FRAME_DURATION = 30  # frames de 30ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000) # número de muestras por frame (480 muestras)

def calcular_rms(frame_array):
    """Calcula el valor RMS de un frame de audio"""
    rms = np.sqrt(np.mean(np.square(frame_array.astype(np.float32)))) # cálculo de la energía de la señal
    return rms

def mostrar_rms():
    print("Midiendo RMS en tiempo real... (Ctrl+C para detener)\n")

    def callback(indata, frames, time, status): # función que se ejecuta cada vez que "sounddevice" recibe un nuevo frame
        if status:
            print(f"{status}", file=sys.stderr) # informa sonre posibles errores
        audio = indata[:, 0] # toma el canal 0 por ser audio mono
        audio_int16 = (audio * 32767).astype(np.int16) # convierte las muestras float32 a int16
        rms = calcular_rms(audio_int16)
        print(f"RMS: {int(rms):5d}", end='\r') # muestra el valor RMS

    with sd.InputStream(channels=CHANNELS,
                        samplerate=SAMPLE_RATE,
                        blocksize=FRAME_SIZE,
                        dtype='float32',
                        callback=callback): # abre el micrófono e invoca a callback al recibir un frame
        try:
            while True:
                sd.sleep(100)
        except KeyboardInterrupt:
            print("\nMedición detenida")

if __name__ == "__main__":
    mostrar_rms()
