from flask import Flask, request, jsonify
import boto3, os, time
import json
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

def get_secret_value(secret_id: str):
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_id)
    return json.loads(response["SecretString"])

def get_db_credentials(region="eu-west-1"):
    # Changer ici les IDs exacts de secrets pour chaque champ
    secret_ids = {
        "host": "rds-db-credentials/cluster-3MGGV2VUZDWQSJFDD6TQ4744HQ/admin/1748251685700",
        "port": "rds-db-port-secret-id",  # optionnel, ou hardcodé 3306
        "username": "rds!cluster-27e3f900-f4c4-44bc-a1e0-19cc44356684",
        "password": "rds!cluster-27e3f900-f4c4-44bc-a1e0-19cc44356684",
        "dbname": "rds-db-name-secret-id"
    }

    return {
        "host": get_secret_value(secret_ids["host"])["host"],
        "port": int(3306),
        "user": get_secret_value(secret_ids["username"])["username"],
        "password": get_secret_value(secret_ids["password"])["password"],
        "dbname": "guacamole_db"
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
	#region_name = os.environ.get("REGION_NAME")
	#aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
	#aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
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
