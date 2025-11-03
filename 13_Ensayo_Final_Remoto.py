import sqlite3
import os
import numpy as np
import re
import difflib
import time
import unicodedata
import requests

# --- CONFIGURACIÓN ---
DB_INPUT = "audios_grabados_frases.db"
DB_OUTPUT = "audios_transcritos_frases.db"

# Servidor remoto
TRANSCRIBE_SERVER = os.environ.get("TRANSCRIBE_SERVER", "http://192.168.1.12:8000")
API_TOKEN = "clave123"
TRANSCRIBE_ENDPOINT = f"{TRANSCRIBE_SERVER.rstrip('/')}/transcribe"

# === LISTA DE 140 FRASES DE REFERENCIA ===
REFERENCIAS = [
    # --- Tipo 1 ---
    "Hola, ¿cómo estás hoy?",
    "¿Podrías decirme qué tiempo hace en mi ciudad?",
    "Recuérdame llamar a mi madre a las ocho.",
    "Oye, pon un temporizador de cinco minutos.",
    "¿Puedes encender la música suave para estudiar?",
    "Quisiera saber cuántas calorías tiene una manzana.",
    "Envíale un mensaje a Carlos y dile que ya llegué.",
    "¿Qué significa la palabra resiliencia?",
    "Apaga las luces del salón, por favor.",
    "Anota en mi lista de tareas: comprar detergente.",
    "¿Cuál es la capital de Argentina?",
    "Llévame a la dirección del trabajo más rápido.",
    "¿Puedes traducir “thank you” al español?",
    "¿A qué hora sale el próximo tren a Valencia?",
    "Dime una curiosidad sobre el espacio.",
    "¿Cuánto tarda el horno en precalentarse a ciento ochenta grados?",
    "Cuéntame un chiste corto.",
    "¿Cuál es el significado de la palabra “entropía”?",
    "Inicia una alarma para mañana a las siete de la mañana.",
    "¿Qué día de la semana cae el quince de noviembre?",
    # --- Tipo 2 ---
    "La lluvia suave moja la hierba verde.",
    "Siete serpientes silenciosas se deslizan sobre la arena.",
    "El gato gris gruñe junto al granero.",
    "Pocas plumas pintan paisajes preciosos.",
    "La niña ríe y corre por la colina.",
    "Javier viaja a Guadalajara en julio.",
    "El viento sopla fuerte sobre los sauces.",
    "Quisiera quince quesos pequeños para probar.",
    "Ramón raspa rocas redondas en el río.",
    "Varios barcos blancos bordean la bahía.",
    "El zorro salta sobre la cerca azul.",
    "Hoy llueve poco, pero el cielo suena hondo.",
    "Los lirios lilas lucen lindos en la loma.",
    "Un pez pequeño nada rápido hacia la orilla.",
    "Crispín cruje croquetas crujientes con crema.",
    "Cada casa tiene un cuadro colgado cerca de la cama.",
    "Un búho ulula en la noche oscura.",
    "Las ovejas balan bajo la brisa del bosque.",
    "Pedro pisa piedras pulidas para practicar equilibrio.",
    "Quince koalas comen hojas cuando cae el sol.",
    # --- Tipo 3 ---
    "María viajó a Berlín el mes pasado.",
    "Andrés trabaja en Microsoft desde hace tres años.",
    "Paula visitó el Museo del Prado en Madrid.",
    "Luis y Ana viven en Buenos Aires.",
    "Google lanzó una nueva actualización para Android.",
    "Carlos estudia ingeniería en la Universidad de Sevilla.",
    "Sofía compró un café en Starbucks antes del trabajo.",
    "Apple presentó el nuevo iPhone en California.",
    "Marta conoció a Julia en una conferencia en Lisboa.",
    "Pedro viaja mañana a Nueva York por negocios.",
    "El tren de Renfe salió con diez minutos de retraso.",
    "Pablo Picasso nació en Málaga.",
    "Claudia trabaja en IBM como analista de datos.",
    "Miguel corrió el maratón de Boston este año.",
    "Laura estudia en la Universidad Nacional de Córdoba.",
    "El edificio de Google en Zúrich tiene vistas al lago.",
    "Sara reservó un vuelo a Tokio con Japan Airlines.",
    "Juan vio una película de Marvel en el cine.",
    "Claudia participó en un seminario en la Universidad de Oxford.",
    "En el aeropuerto de París compró un libro de Hemingway.",
    # --- Tipo 4 ---
    "Hoy es quince de octubre de dos mil veinticinco.",
    "Mañana será el dieciséis de marzo de dos mil veintiséis.",
    "La cita médica es el tres de mayo a las nueve y media.",
    "Mi vuelo sale el veinte de julio a las siete cuarenta y cinco.",
    "El examen está programado para el diez de diciembre.",
    "Cumplo treinta y un años el cinco de enero.",
    "El pedido número cuatro cinco siete ocho nueve fue entregado.",
    "La factura cuesta ciento veintitrés euros con cincuenta.",
    "El curso dura seis semanas.",
    "El tren número doscientos treinta y siete parte en veinte minutos.",
    "La próxima reunión es el veintisiete de noviembre.",
    "En dos mil veintitrés viajé cinco veces al extranjero.",
    "La película empieza a las ocho y termina a las diez.",
    "Faltan tres días para el evento.",
    "Mi dirección es calle doce número veinticuatro.",
    "La contraseña tiene ocho caracteres y tres números.",
    "El restaurante abre de doce a veintitrés horas.",
    "El concurso empieza el uno de abril.",
    "Tengo una reserva para el dieciocho de agosto a las nueve.",
    "Hoy es el día número doscientos ochenta y ocho del año.",
    # --- Tipo 5 ---
    "Este software es muy user-friendly.",
    "El datasheet indica el consumo máximo del circuito.",
    "Necesito reiniciar la workstation antes de compilar.",
    "Estoy haciendo un backup de todos los archivos.",
    "El router necesita un reset completo.",
    "El driver de la impresora está desactualizado.",
    "Este diseño tiene un estilo vintage.",
    "El teclado tiene layout en inglés.",
    "Prefiero usar un smartphone con buena cámara.",
    "Esa laptop tiene pantalla de catorce pulgadas.",
    "El proyecto usa un framework open source.",
    "Necesito actualizar el firmware del microcontrolador.",
    "Compré un mouse inalámbrico muy ergonómico.",
    "El sistema operativo tiene un bug en la interfaz.",
    "La startup presentó un nuevo producto en Silicon Valley.",
    "El diseñador hizo un logo minimalista con tipografía bold.",
    "Trabajo en modo home office tres días por semana.",
    "El archivo PDF tiene un watermark de seguridad.",
    "El correo fue marcado como spam por error.",
    "Este servidor cloud usa autenticación con token.",
    # --- Tipo 6 ---
    "Dos más dos son cuatro.",
    "Cinco por seis son treinta.",
    "Ocho dividido entre dos es cuatro.",
    "El veinte por ciento de cien es veinte.",
    "Cien menos setenta y cinco da veinticinco.",
    "Si sumas diez y quince obtienes veinticinco.",
    "Tres al cuadrado es nueve.",
    "Cuarenta dividido en cinco es ocho.",
    "La raíz cuadrada de dieciséis es cuatro.",
    "El doble de doce es veinticuatro.",
    "El promedio de tres, seis y nueve es seis.",
    "Multiplica treinta y cinco por dos.",
    "Si tengo cincuenta y gasto veinte, me quedan treinta.",
    "Diez por diez son cien.",
    "El área de un cuadrado de lado cuatro es dieciséis.",
    "Doce más doce menos seis es dieciocho.",
    "Cincuenta dividido por cinco da diez.",
    "El triple de siete es veintiuno.",
    "La mitad de cuarenta es veinte.",
    "Suma doscientos más trescientos y resta cien.",
    # --- Tipo 7 ---
    "Tres tristes tigres tragan trigo en un trigal.",
    "El cielo está enladrillado, ¿quién lo desenladrillará?",
    "Pablito clavó un clavito en la calva de un calvito.",
    "El perro de San Roque no tiene rabo.",
    "Pepe Pecas pica papas con un pico.",
    "Parra tenía una perra y Guerra tenía una parra.",
    "Si Pancha plancha con cuatro planchas, ¿con cuántas planchas plancha Pancha?",
    "Pedro Pérez pintor pinta preciosos paisajes para poder partir.",
    "Erre con erre cigarro, erre con erre barril.",
    "Cómo quieres que te quiera si el que quiero que me quiera no me quiere como quiero que me quiera.",
    "El hipopótamo hipo tiene hipo.",
    "Me han dicho que has dicho un dicho, ese dicho que me han dicho que has dicho.",
    "La bruja piruja prepara pociones para pobres príncipes.",
    "R con R guitarra, R con R carril.",
    "Saca la cáscara con la cuchara clara.",
    "Siete santos sanan siete sarpullidos.",
    "El relojero arregla relojes rotos.",
    "Carla carga el carro con cañas y canicas.",
    "Cuando cuentes cuentos cuenta cuántos cuentos cuentas.",
    "Rosa roza ramas raras rápidamente."
]

# === FUNCIONES AUXILIARES ===

# Diccionario simple de palabras numéricas a valores
NUMEROS = {
    "cero": 0, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "dieciséis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiuno": 21, "veintidos": 22, "veintidós": 22, "veintitres": 23, "veintitrés": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintiséis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29, "treinta": 30, "treinta y uno": 31, "treinta y cinco": 35, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
    "cien": 100, "ciento": 100, "ciento ochenta": 180, "doscientos": 200, "trescientos": 300,
    "cuatrocientos": 400, "quinientos": 500, "seiscientos": 600,
    "setecientos": 700, "ochocientos": 800, "novecientos": 900,
    "mil": 1000
}

# --- AUXILIARES ---
NUM_TIPOS = 7
FRASES_POR_TIPO = 20

def get_referencia(tipo, frase):
    """Devuelve la referencia según tipo y frase."""
    try:
        tipo_i = int(tipo)
        frase_i = int(frase)
    except Exception:
        return ""
    idx_global = (tipo_i - 1) * FRASES_POR_TIPO + (frase_i - 1)
    if 0 <= idx_global < len(REFERENCIAS):
        return REFERENCIAS[idx_global]
    return ""

def quitar_tildes(text):
    if text is None:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def texto_a_numero(text):
    tokens = re.findall(r"\d+|\w+", text, flags=re.UNICODE)
    salida = []
    for t in tokens:
        t_low = quitar_tildes(t.lower())
        if t_low in NUMEROS:
            salida.append(str(NUMEROS[t_low]))
        else:
            salida.append(t_low)
    return " ".join(salida)

def normalize_for_wer(text):
    if text is None:
        return ""
    text = text.lower()
    text = quitar_tildes(text)
    text = text.replace("-", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = texto_a_numero(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def normalize_for_cer(text):
    return normalize_for_wer(text).replace(" ", "")

# --- MÉTRICAS ---
def word_error_rate(ref, hyp):
    ref_words, hyp_words = ref.split(), hyp.split()
    seq = difflib.SequenceMatcher(None, ref_words, hyp_words)
    S = D = I = 0
    for tag, i1, i2, j1, j2 in seq.get_opcodes():
        if tag == "replace":
            S += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            D += i2 - i1
        elif tag == "insert":
            I += j2 - j1
    N = len(ref_words)
    return (S + D + I) / N if N > 0 else 0.0

def char_error_rate(ref, hyp):
    ref_chars, hyp_chars = list(ref), list(hyp)
    seq = difflib.SequenceMatcher(None, ref_chars, hyp_chars)
    S = D = I = 0
    for tag, i1, i2, j1, j2 in seq.get_opcodes():
        if tag == "replace":
            S += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            D += i2 - i1
        elif tag == "insert":
            I += j2 - j1
    N = len(ref_chars)
    return (S + D + I) / N if N > 0 else 0.0

# --- COMUNICACIÓN CON SERVIDOR ---
def enviar_a_servidor(filename, audio_blob, language="es"):
    headers = {"X-API-KEY": API_TOKEN}
    files = {"file": (filename, audio_blob, "audio/wav")}
    data = {"language": language}
    try:
        resp = requests.post(TRANSCRIBE_ENDPOINT, headers=headers, files=files, data=data, timeout=300)
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        return None, None

    if resp.status_code != 200:
        print(f"⚠️ Error del servidor {resp.status_code}: {resp.text}")
        return None, None

    try:
        data = resp.json()
        texto = data.get("transcription", "")
        tiempo_remoto = data.get("transcription_time_s", None)
        return texto, tiempo_remoto
    except Exception as e:
        print(f"⚠️ Error al parsear respuesta: {e}")
        return None, None

# --- BASE DE DATOS ---
def init_db():
    with sqlite3.connect(DB_OUTPUT) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcripciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                tipo INTEGER,
                frase INTEGER,
                transcription TEXT,
                referencia TEXT,
                wer REAL,
                cer REAL,
                tiempo_seg REAL
            )
        """)
        conn.commit()

def obtener_audios():
    with sqlite3.connect(DB_INPUT) as conn:
        c = conn.cursor()
        c.execute("SELECT filename, audio, tipo, frase, version FROM grabaciones ORDER BY tipo, frase, version")
        return c.fetchall()

# --- PROCESO PRINCIPAL ---
def transcribir_todo():
    audios = obtener_audios()
    if not audios:
        print("⚠️ No se encontraron audios en la base de datos.")
        return

    init_db()

    wers_por_tipo = {}
    cers_por_tipo = {}
    tiempos_por_tipo = {}

    total = len(audios)
    print(f"\nEnviando {total} audios al servidor {TRANSCRIBE_SERVER} ...\n")

    for idx, (filename, audio_blob, tipo, frase, version) in enumerate(audios, 1):
        print(f"\n=== [{idx}/{total}] Tipo {tipo}, Frase {frase}, Versión {version} ===")

        t0 = time.time()
        texto, tiempo_remoto = enviar_a_servidor(filename, audio_blob)
        t1 = time.time()
        duracion_total = t1 - t0  # tiempo total incluyendo red

        if texto is None:
            print("❌ Fallo al transcribir. Saltando...")
            continue

        ref = get_referencia(tipo, frase)
        wer = word_error_rate(normalize_for_wer(ref), normalize_for_wer(texto))
        cer = char_error_rate(normalize_for_cer(ref), normalize_for_cer(texto))

        tipo_int = int(tipo) if str(tipo).isdigit() else -1

        wers_por_tipo.setdefault(tipo_int, []).append(wer)
        cers_por_tipo.setdefault(tipo_int, []).append(cer)
        tiempos_por_tipo.setdefault(tipo_int, []).append(duracion_total)

        with sqlite3.connect(DB_OUTPUT) as conn:
            conn.execute("""
                INSERT INTO transcripciones (filename, tipo, frase, transcription, referencia, wer, cer, tiempo_seg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (filename, tipo, frase, texto, ref, wer, cer, duracion_total))
            conn.commit()

        print(f"Ref: {ref}")
        print(f"Hyp: {texto.strip()}")
        print(f"WER: {wer:.2%} | CER: {cer:.2%}")
        if tiempo_remoto is not None:
            print(f"⚙️  Tiempo servidor: {tiempo_remoto:.2f}s | ⏱️ Total (incl. red): {duracion_total:.2f}s")
        else:
            print(f"⏱️  Tiempo total: {duracion_total:.2f}s")

    # --- Resultados globales ---
    print("\n\n===== RESULTADOS GLOBALES POR TIPO =====")
    for tipo in sorted(k for k in wers_por_tipo.keys() if k != -1):
        wers = np.array(wers_por_tipo[tipo])
        cers = np.array(cers_por_tipo[tipo])
        tiempos = np.array(tiempos_por_tipo[tipo])
        print(f"\nTipo {tipo}:")
        print(f"   → WER medio: {np.mean(wers):.2%} (±{np.std(wers):.2%}) | min: {np.min(wers):.2%} | max: {np.max(wers):.2%}")
        print(f"   → CER medio: {np.mean(cers):.2%} (±{np.std(cers):.2%}) | min: {np.min(cers):.2%} | max: {np.max(cers):.2%}")
        print(f"   → Tiempo medio: {np.mean(tiempos):.2f}s (±{np.std(tiempos):.2f}s)")

    print("\n✅ Transcripción remota completada y guardada en la base de datos.")

# --- MAIN ---
if __name__ == "__main__":
    transcribir_todo()


