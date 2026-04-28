"""
app.py — RSVP Reader: servidor Flask fase 2
Rutas:
  GET  /                → página principal (reader)
  POST /upload          → sube un archivo .txt, lo parsea, guarda caché JSON
  GET  /book/<book_id>  → devuelve tokens JSON de un libro ya cargado
"""
import os
import json
import uuid
import hashlib
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, abort, render_template_string
from flask_cors import CORS

from parser.txt import parse_txt

# ── Configuración ─────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).parent
UPLOAD_DIR  = BASE_DIR / "uploads"
CACHE_DIR   = BASE_DIR / "cache"
ALLOWED_EXT = {".txt"}

UPLOAD_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
CORS(app)  # permite llamadas desde el HTML abierto como archivo local
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


def file_hash(path: Path) -> str:
    """SHA-256 de los primeros 64 KB para identificar el archivo sin leerlo completo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(65536))
    return h.hexdigest()[:16]


def cache_path(book_id: str) -> Path:
    return CACHE_DIR / f"{book_id}.json"


# ── Rutas ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """
    Sirve el reader HTML.
    En fase 2 devolvemos un HTML mínimo que carga el reader.
    En fases posteriores esto será render_template('reader.html').
    """
    # Por ahora devolvemos un HTML que explica cómo usar la API.
    # Cuando integres el frontend completo, reemplaza esto con:
    #   return render_template("reader.html")
    return """
    <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
    <title>RSVP Reader API</title>
    <style>body{font-family:monospace;max-width:600px;margin:4rem auto;line-height:2}</style>
    </head><body>
    <h2>RSVP Reader — API activa</h2>
    <p><strong>POST /upload</strong> — sube un .txt, recibe book_id y metadatos</p>
    <p><strong>GET /book/&lt;book_id&gt;</strong> — devuelve los tokens JSON</p>
    <p>Abre <code>rsvp_reader.html</code> en tu navegador para el frontend.</p>
    </body></html>
    """


@app.route("/upload", methods=["POST"])
def upload():
    """
    Recibe un archivo .txt via multipart/form-data (campo: 'file').
    1. Valida extensión y tamaño (Flask lo limita vía MAX_CONTENT_LENGTH).
    2. Guarda en uploads/ con nombre seguro basado en UUID.
    3. Parsea con parse_txt().
    4. Guarda el resultado en cache/<book_id>.json.
    5. Devuelve metadatos + book_id para que el frontend solicite los tokens.

    Respuesta 200:
    {
        "book_id":    "abc123",
        "title":      "mi_libro",
        "word_count": 1234,
        "para_count": 8,
    }
    """
    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo (campo 'file')"}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"Solo se aceptan archivos: {', '.join(ALLOWED_EXT)}"}), 415

    # Nombre seguro: UUID + extensión original
    ext      = Path(file.filename).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / safe_name

    file.save(str(save_path))

    # Parsear
    try:
        result = parse_txt(str(save_path))
    except Exception as e:
        save_path.unlink(missing_ok=True)
        return jsonify({"error": f"Error al parsear el archivo: {e}"}), 500

    # Generar book_id estable basado en contenido
    book_id = file_hash(save_path)

    # Guardar caché JSON
    cp = cache_path(book_id)
    if not cp.exists():
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

    return jsonify({
        "book_id":    book_id,
        "title":      result["title"],
        "word_count": result["word_count"],
        "para_count": result["para_count"],
    }), 200


@app.route("/book/<book_id>")
def get_book(book_id: str):
    """
    Devuelve los tokens de un libro previamente subido.
    El frontend llama a este endpoint después de recibir el book_id del upload.

    Respuesta 200:
    {
        "title":      str,
        "word_count": int,
        "para_count": int,
        "tokens": [
            {"text": "La", "para": 0, "orp": 0, "end_punct": false, "is_long": false, ...},
            ...
        ]
    }
    """
    # Validar book_id (solo hex, 16 chars)
    if not book_id.isalnum() or len(book_id) > 32:
        abort(400)

    cp = cache_path(book_id)
    if not cp.exists():
        return jsonify({"error": "Libro no encontrado. Sube el archivo de nuevo."}), 404

    with open(cp, "r", encoding="utf-8") as f:
        data = json.load(f)

    return jsonify(data), 200


# ── Arranque ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)