# tools/get_last_contact.py
import pyodbc, os, struct, logging
from azure.identity import AzureCliCredential
from dotenv import load_dotenv
load_dotenv()

def get_last_contact(fan_id: str) -> dict:
    """
    Returns how many days since orchestrator last acted on this fan.
    Only counts AGENT_ACTION rows — not fan-initiated events.
    If no AGENT_ACTION rows exist → returns 999 (safe to contact).
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
            SELECT TOP 1
                event_timestamp,
                DATEDIFF(DAY, event_timestamp, GETDATE()) AS days_since_last_contact
            FROM gold_fact_engagement
            WHERE fan_id = ?
            AND row_type = 'AGENT_ACTION'
            ORDER BY event_timestamp DESC
        """, (fan_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "days_since_last_contact": int(row.days_since_last_contact),
                "last_contact_date": str(row.event_timestamp)
            }

        # No AGENT_ACTION rows exist yet — never contacted
        return {
            "days_since_last_contact": 999,
            "last_contact_date": None
        }

    except Exception as e:
        logging.error(f"get_last_contact error: {e}")
        return {"error": str(e)}
