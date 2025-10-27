Proyecto de análisis del funcionamiento de los diferentes modelos Whisper implementados en una Raspberry Pi 4 para estudiar su viabilidad como transcriptores para un asistente virtual.

Los primeros 2 programas son pruebas simples de grabación y de transcripción con Whisper a partir de las cuales se llevó a cabo el desarrollo de los programas más avanzados que fueron usados en los experimentos finales.

El programa 3 fue utilizado para visualizar el valor RMS (energía de la señal) detectado por el micrófono y compararlo con los decibelios medidos por un decibelímetro digital.

El cuarto programa consiste en un código que implementa un sistema de grabación basado en la detección de voz del usuario mediante VAD (Voice Activity Detection), de modo que comienza la grabación al detectar voz y la detiene cuando pasan unos segundos sin detectarla.

El programa 5 utiliza otro método de grabación (debido a problemas de calidad de audio con el método del programa 4) y utiliza VAD pero sólo para determinar cuándo comenzar a grabar. Una vez detectada la voz del usuario, graba bloques de 10 segundos de duración, al final de los cuales vuelve a utilizar VAD para comprobar si el usuario sigue realizando la consulta al asistente. En caso afirmativo, graba otros 10 segundos. En caso negativo, finaliza la grabación.
