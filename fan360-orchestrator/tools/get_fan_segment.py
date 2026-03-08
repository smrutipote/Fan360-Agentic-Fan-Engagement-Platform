# tools/get_fan_segment.py
import pyodbc, os, struct, logging
from azure.identity import AzureCliCredential
from dotenv import load_dotenv
load_dotenv()

def get_fan_segment(fan_id: str) -> dict:
    """
    Reads gold_fan_segments.
    Returns the fan's segment label e.g. 'VIP Diehard', 'Casual Viewer'
    """
    credential = AzureCliCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("UTF-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={os.getenv('FABRIC_SQL_SERVER')},1433;"
        f"Database={os.getenv('FABRIC_SQL_DATABASE')};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    try:
        conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 1 *
            FROM gold_fan_segments
            WHERE fan_id = ?
        """, (fan_id,))

        row = cursor.fetchone()
        cols = [desc[0] for desc in cursor.description]
        conn.close()

        if row:
            result = dict(zip(cols, row))
            print(f"  DEBUG gold_fan_segments row: {result}")
            return result

        return {"fan_segment": "Unknown", "fan_id": fan_id}

    except Exception as e:
        logging.error(f"get_fan_segment error: {e}")
        return {"error": str(e)}
