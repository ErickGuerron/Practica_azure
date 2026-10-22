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

def enviar_correo(proceso, html_detalle):
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    remitente = os.environ.get("EMAIL_REMITENTE")
    destino = os.environ.get("EMAIL_DESTINO")

    if not all([api_key, remitente, destino]):
        raise ValueError(
            "Faltan variables de entorno para Brevo"
        )

    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    data = {
        "sender": {
            "email": remitente
        },
        "to": [
            {"email": destino}
        ],
        "subject": f"[{proceso}]",
        "htmlContent": html_detalle
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=15
        )

        if not response.ok:
            app.logger.error(
                "Error Brevo HTTP %s: %s",
                response.status_code,
                response.text[:1000]
            )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException:
        app.logger.exception(
            "Error de comunicación con Brevo"
        )
        raise

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
    expected_key = os.environ.get('PROCESS_API_KEY')

    if not expected_key:
        app.logger.error("PROCESS_API_KEY no configurada")
        return jsonify({
            'error': 'Configuración del servidor incompleta'
        }), 500

    api_key = request.headers.get('X-API-Key', '')

    if not hmac.compare_digest(api_key, expected_key):
        return jsonify({
            'error': 'API Key no valida'
        }), 401

    try:
        with getConnection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT names, price FROM dbo.PRODUCTS_VW")
                productos = cursor.fetchall()
                total = len(productos)

        html_content = f"""
        <p>Se procesaron <b>{total}</b> registros.</p>
        <p>A continuación la lista de productos:</p>
        <br>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif; width: 100%;">
            <thead>
                <tr style="background-color: #f2f2f2; text-align: left;">
                    <th>Nombre del Producto</th>
                    <th>Precio</th>
                </tr>
            </thead>
            <tbody>
        """

        for prod in productos:
            html_content += f"""
                <tr>
                    <td>{prod[0]}</td>
                    <td>{prod[1]}</td>
                </tr>
            """

        html_content += """
            </tbody>
        </table>
        """

        enviar_correo(
            'Consulta de productos',
            html_content
        )

        return jsonify({
            'procesamiento': 'finalizado',
            'total_productos': total,
            'notificacion': 'enviado'
        }), 200

    except Exception:
        app.logger.exception("Error al procesar productos")

        return jsonify({
            'error': 'Error interno al procesar productos'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)