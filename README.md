Proyecto de análisis del funcionamiento de los diferentes modelos Whisper implementados en una Raspberry Pi 4 para estudiar su viabilidad como transcriptores para un asistente virtual.

Los primeros 2 programas son pruebas simples de grabación y de transcripción con Whisper a partir de las cuales se llevó a cabo el desarrollo de los programas más avanzados que fueron usados en los experimentos finales.

El programa 3 fue utilizado para visualizar el valor RMS (energía de la señal) detectado por el micrófono y compararlo con los decibelios medidos por un decibelímetro digital.

El cuarto programa consiste en un código que implementa un sistema de grabación basado en la detección de voz del usuario mediante VAD (Voice Activity Detection), de modo que comienza la grabación al detectar voz y la detiene cuando pasan unos segundos sin detectarla.

El programa 5 utiliza otro método de grabación (debido a problemas de calidad de audio con el método del programa 4) y utiliza VAD pero sólo para determinar cuándo comenzar a grabar. Una vez detectada la voz del usuario, graba bloques de 10 segundos de duración, al final de los cuales vuelve a utilizar VAD para comprobar si el usuario sigue realizando la consulta al asistente. En caso afirmativo, graba otros 10 segundos. En caso negativo, finaliza la grabación.
Además, también incorpora el uso de una base de datos en la que almacena los audios grabados y los textos transcritos junto con datos como el valor máximo de RMS o la duración del proceso de transcripción para facilitar los experimentos con el código.

El código 6 fue el empleado en para la grabación de audios en una prueba de volumen, de manera que se midiera la precisión de la transcripción resultante en base al volumen al que se dictara la frase al micrófono. Por ello, y para poder probar todos los rangos de energía RMS, se eliminó el umbral de voz y se implementó un sistema de grabación de audio de duración fija de 10 segundos, además de una monitorización del valor RMS por pantalla (como el programa 3) y una medida de valores RMS promedio y máximo de la señal.

El programa 7 fue el encargado de implementar los modelos Whisper Tiny, Base y Small en la Raspberry Pi 4 para llevar a cabo la prueba de distancia. En este código, se transcriben los audios grabados con el programa anterior de forma que se puedan ejecutar todos los audios grabados a cierto volumen en una sola ejecución y así se obtengan métricas de precisión como el error WER y CER y los valores promedios y desviacion típica entre los audios de un conjunto.

El programa 8 tiene la misma función que el 7, pero envía los audios a un servidor externo para que sea él el encargado de transcribir los audios grabados.

El programa 9 es el código que se ejecuta en el servidor remoto (pc personal) y es el mismo para todas las pruebas. Transcribe los audios que recibe y saca métricas de tiempo de transcripción.

El programa 10 es similar al 7, pero en lugar de la prueba de volumen, se encarga de transcribir los audios de la prueba de distancia, de forma que el valor RMS pasa a ser otro valor de salida a evaluar.

El programa 11 se asemeja al 8, pero de nuevo, especializado para la prueba de distancia. Debe ser ejecutado a la vez que el 9, ya que también usa servidor remoto.

Los programas 12 y 13 son los empleados en la prueba final de transcripción. Toman los audios grabados y almacenados en la base de datos "audios_grabados_frases" y los transcriben, con la diferencia de implementar cálculos de tiempo promedio de transcripción y de diferenciar entre audios de distinto tipo por su nomenclatura.

También se incluyen las bases de datos generadas a lo largo de las pruebas, con comprobaciones de las transcripciones resultantes.
