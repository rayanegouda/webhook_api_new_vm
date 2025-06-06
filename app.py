from flask import Flask, request, jsonify
import boto3
import json
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

def get_secret_value(secret_id: str, key: str = None, region_name: str = "eu-west-1"):
    client = boto3.client("secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_id)
    secret = json.loads(response["SecretString"])
    return secret if key is None else secret.get(key)

def get_db_credentials(secret_id="guacamole-db-config", region="eu-west-1"):
    config = get_secret_value(secret_id, region_name=region)
    real_secret_id = config["active_secret"]
    db_creds = get_secret_value(real_secret_id, region_name=region)
    return {
        "host": db_creds["host"],
        "port": db_creds.get("port", 3306),
        "user": db_creds["username"],
        "password": db_creds["password"],
        "dbname": db_creds.get("dbname", "guacamole_db")
    }

def create_db_engine():
    creds = get_db_credentials()
    db_url = f"mysql+pymysql://{creds['user']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['dbname']}"
    return create_engine(db_url, pool_pre_ping=True)

@app.route('/create-connection', methods=['POST'])
def create_connection():
    data = request.json
    ip = data.get("ip")
    private_key = data.get("private_key")

    if not ip or not private_key:
        return jsonify({"error": "Missing IP or private_key"}), 400

    engine = create_db_engine()
    conn_name = f"SSH - {ip}"
    try:
        with engine.begin() as conn:
            # Insertion de la connexion
            conn.execute(text("""
                INSERT INTO guacamole_connection (connection_name, protocol, parent_id)
                VALUES (:name, 'ssh', NULL)
            """), {"name": conn_name})

            # Récupération du dernier ID
            result = conn.execute(text("SELECT LAST_INSERT_ID() AS id"))
            connection_id = result.fetchone()["id"]

            # Insertion des paramètres
            parameters = [
                ("hostname", ip),
                ("port", "22"),
                ("username", "ubuntu"),
                ("private-key", private_key)
            ]

            for name, value in parameters:
                conn.execute(text("""
                    INSERT INTO guacamole_connection_parameter
                    (connection_id, parameter_name, parameter_value)
                    VALUES (:cid, :pname, :pvalue)
                """), {"cid": connection_id, "pname": name, "pvalue": value})

        return jsonify({
            "connection_id": connection_id,
            "connection_name": conn_name
        }), 201

    except SQLAlchemyError as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
