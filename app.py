from flask import Flask, jsonify, request
import os
import certifi
import pytds

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
        validate_host=true
    )

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
        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT id, names, price, stock FROM PRODUCTS_VW
        """)
        products =[]
        for row in cursor.fetchall():
            products.append({
                "id":row.id,
                "names":row.names,
                "price":row.price,
                "stock":row.stock
            })
        cursor.close()
        conn.close()
        return jsonify(products),200
    
    except Exception as e:
        return jsonify(
            {
                "message": "Error",
                "error": str(e)
            }
        ), 500

@app.route('/api/products/<int:id>', methods=['GET'])
def get_product(id):
    try:
        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute("""
           SELECT id, names, price, stock FROM PRODUCTS_VW WHERE id = ?"""
                       , id)
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            product = {
                "id": row.id,
                "names": row.names,
                "price": row.price,
                "stock": row.stock
            }
            return jsonify(product), 200

        return jsonify({"message": "Product not found"}), 404

    except Exception as e:
        return jsonify(
            {
                "message": "Error",
                "error": str(e)
            }
        ), 500

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
        

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)