"""
parser/txt.py
Lee archivos .txt detectando el encoding automáticamente,
luego tokeniza el texto en palabras con metadatos para el motor RSVP.
"""
import re
import chardet


# ── 1. LECTURA CON DETECCIÓN DE ENCODING ─────────────────────────────────────

def read_txt(path: str) -> str:
    """
    Lee un archivo .txt detectando su encoding con chardet.
    Devuelve el contenido como str limpio.
    """
    with open(path, "rb") as f:
        raw = f.read()

    detected = chardet.detect(raw)
    encoding = detected.get("encoding") or "utf-8"
    confidence = detected.get("confidence", 0)

    # Si la confianza es baja o el encoding detectado no es fiable,
    # intentamos con utf-8 y latin-1 como fallbacks.
    try:
        text = raw.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")

    return text


# ── 2. LIMPIEZA DE TEXTO ──────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Normaliza el texto eliminando artefactos comunes de archivos TXT:
    - Guiones de separación de línea (palabra- / siguiente línea)
    - Saltos de línea simples dentro de un párrafo (los une)
    - Múltiples líneas en blanco → un solo separador de párrafo
    - Espacios múltiples
    """
    # Unir palabras cortadas con guión al final de línea
    text = re.sub(r"-\n(\S)", r"\1", text)

    # Salto de línea simple dentro de párrafo → espacio
    # (dos o más saltos = separador de párrafo, se respeta)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # Colapsar múltiples líneas en blanco a doble salto
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Colapsar espacios múltiples
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


# ── 3. CÁLCULO DE ORP ────────────────────────────────────────────────────────

def orp_index(word: str) -> int:
    """
    Devuelve el índice (0-based) de la letra ancla ORP de una palabra.
    Coincide exactamente con la lógica de orpIndex() en el JS del frontend,
    de modo que ambos lados calculan siempre el mismo resultado.
    """
    n = len(word)
    if n <= 3:  return 0
    if n <= 5:  return 1
    if n <= 8:  return 2
    if n <= 11: return 3
    if n <= 14: return 4
    return int(n * 0.28)


# ── 4. TOKENIZACIÓN ───────────────────────────────────────────────────────────

END_PUNCT_RE = re.compile(r"[.!?…;:,\-–—]$")

def tokenize(text: str) -> list[dict]:
    """
    Divide el texto en una lista de tokens con metadatos.

    Cada token es un dict:
    {
        "text":       str   — la palabra tal cual aparece en el texto,
        "para":       int   — índice del párrafo (0-based),
        "orp":        int   — posición de la letra ancla,
        "end_punct":  bool  — termina en puntuación,
        "is_long":    bool  — más de 8 caracteres,
        "is_very_long": bool — más de 13 caracteres,
    }

    Nota: el frontend recibe este array y lo usa directamente;
    no necesita recalcular nada.
    """
    # Separar párrafos por líneas en blanco
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]

    tokens = []
    for para_idx, para in enumerate(paragraphs):
        words = para.split()
        for word in words:
            if not word:
                continue
            tokens.append({
                "text":        word,
                "para":        para_idx,
                "orp":         orp_index(word),
                "end_punct":   bool(END_PUNCT_RE.search(word)),
                "is_long":     len(word) > 8,
                "is_very_long": len(word) > 13,
            })

    return tokens


# ── 5. FUNCIÓN PRINCIPAL: parse_txt ──────────────────────────────────────────

def parse_txt(path: str) -> dict:
    """
    Pipeline completo: lee → limpia → tokeniza un archivo .txt.

    Devuelve:
    {
        "title":      str           — nombre del archivo sin extensión,
        "word_count": int,
        "para_count": int,
        "tokens":     list[dict],   — lista de tokens para el frontend,
    }
    """
    import os

    raw_text   = read_txt(path)
    clean      = clean_text(raw_text)
    tokens     = tokenize(clean)

    para_count = (tokens[-1]["para"] + 1) if tokens else 0
    title      = os.path.splitext(os.path.basename(path))[0]

    return {
        "title":      title,
        "word_count": len(tokens),
        "para_count": para_count,
        "tokens":     tokens,
    }