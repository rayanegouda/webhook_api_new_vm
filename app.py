from flask import Flask, request, jsonify
import boto3
import os
import json
from botocore.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

aws_config = Config(
    max_pool_connections=100,
    retries={'max_attempts': 3}
)


def get_secret_value(secret_id: str):
    region_name = os.environ.get("AWS_REGION_NAME")
    if not region_name:
        raise RuntimeError("Missing AWS_REGION_NAME environment variable")

    client = boto3.client(
        "secretsmanager",
        config=aws_config,
        region_name=region_name,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    response = client.get_secret_value(SecretId=secret_id)
    return json.loads(response["SecretString"])


def get_db_credentials():
    secret_ids = {
        "host": "rds-db-credentials/cluster-3MGGV2VUZDWQSJFDD6TQ4744HQ/admin/1748251685700",
        "username": "rds!cluster-27e3f900-f4c4-44bc-a1e0-19cc44356684",
        "password": "rds!cluster-27e3f900-f4c4-44bc-a1e0-19cc44356684",
    }

    return {
        "host": get_secret_value(secret_ids["host"])["host"],
        "port": 3306,
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
    protocol = data.get("connection_protocol", "ssh")
    conn_name = data.get("connection_name")

    if not ip or not private_key or not conn_name:
        return jsonify({"error": "Missing ip, private_key or connection_name"}), 400

    try:
        engine = create_db_engine()

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO guacamole_connection (connection_name, protocol, parent_id)
                VALUES (:name, :protocol, NULL)
            """), {"name": conn_name, "protocol": protocol})

            result = conn.execute(text("SELECT LAST_INSERT_ID() AS id")).mappings()
            connection_id = result.fetchone()["id"]

            parameters = [
                ("hostname", ip),
                ("port", "22" if protocol == "ssh" else "3389"),
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
            "connection_protocol": protocol,
            "connection_name": conn_name
        }), 201

    except SQLAlchemyError as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
