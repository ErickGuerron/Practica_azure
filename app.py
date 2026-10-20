from flask import Flask, jsonify, request
import os, certifi, pytds, requests, hmac

#===============================
# conexion con la base de datos
#===============================

app = Flask(__name__)

def getConnection():
    return pytds.connect(
        server=os.environ.get("DB_SERVER"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=1433,
        cafile=certifi.where(),
        validate_host=True,
        row_strategy=pytds.namedtuple_row_strategy,
        enc_login_only=False
    )

def enviar_correo(proceso, detalle):
    url = 'https://api.brevo.com/v3/smtp/email'

    headers = {
        'api-key': os.environ.get('BREVO_API_KEY'),
        'Content-Type': 'application/json'
    }

    data = {
        'sender': {
            'email': os.environ.get('EMAIL_REMITENTE')
        },
        'to': [{
            'email': os.environ.get('EMAIL_DESTINO')
        }],
        'subject': f'[{proceso}]',
        'textContent': detalle
    }

    response = requests.post(
        url,
        headers=headers,
        json=data,
        timeout=15
    )

    response.raise_for_status()

@app.route('/test-db',methods=['GET'])
def test_db():
    try:
        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute("SELECT DB_NAME()")
        database = cursor.fetchone()[0]
        conn.close()
        return jsonify(
            {
                "message":"Conexion exitosa",
                "base_datos":database
            }
        ),200
    except Exception as e:
        return jsonify(
            {
                "message":"Error",
                "error":str(e)
            }
        ), 500

@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        with getConnection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, names, price, stock
                    FROM PRODUCTS_VW
                """)

                products = []

                for row in cursor.fetchall():
                    products.append({
                        "id": row[0],
                        "names": row[1],
                        "price": row[2],
                        "stock": row[3]
                    })

        return jsonify(products), 200

    except Exception:
        app.logger.exception("Error al consultar productos")

        return jsonify({
            "message": "Error interno al consultar productos"
        }), 500

@app.route('/api/products/<int:id>', methods=['GET'])
def get_product(id):
    try:
        with getConnection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, names, price, stock
                    FROM PRODUCTS_VW
                    WHERE id = ?
                """, (id,))

                row = cursor.fetchone()

        if row is None:
            return jsonify({
                "message": "Producto no encontrado"
            }), 404

        product = {
            "id": row[0],
            "names": row[1],
            "price": row[2],
            "stock": row[3]
        }

        return jsonify(product), 200

    except Exception:
        app.logger.exception(
            "Error al consultar el producto %s", id
        )

        return jsonify({
            "message": "Error interno al consultar el producto"
        }), 500

@app.route('/api/products', methods=['POST'])
def create_product():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "No existen datos validos"}), 400

        names = data.get('names')
        price = data.get('price')
        stock = data.get('stock')

        if not names or price is None or stock is None:
            return jsonify({"message": "Faltan datos requeridos"}), 400
        
        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute("""
            EXEC products_insert_sp ?, ?, ?
        """, (names , price, stock))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Producto creado exitosamente"}), 201
    except Exception as e:
        return jsonify(
            {
                "message": "Error",
                "error": str(e)
            }
        ), 500

@app.route('/api/procesar', methods=['POST'])
def procesar():
    api_key = request.headers.get('X-API-Key', '')
    expected_key = os.getenv('PROCESS_API_KEY', '')

    app.logger.info(
        "PROCESS_API_KEY configurada: %s",
        bool(expected_key)
    )

    app.logger.info(
        "Cabecera X-API-Key recibida: %s",
        bool(api_key)
    )

    app.logger.info(
        "Longitud clave configurada: %d",
        len(expected_key)
    )

    app.logger.info(
        "Longitud clave recibida: %d",
        len(api_key)
    )

    if not expected_key:
        return jsonify({
            'error': 'PROCESS_API_KEY no configurada'
        }), 500

    if not api_key:
        return jsonify({
            'error': 'No se envio X-API-Key'
        }), 401

    if not hmac.compare_digest(api_key, expected_key):
        return jsonify({
            'error': 'API Key no valida'
        }), 401

    return jsonify({
        'message': 'Autenticacion exitosa'
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)