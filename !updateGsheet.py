import os
from datetime import datetime
import pandas as pd
import pymysql

# --- BASE DIRECTORY & EXPORT LOCATION SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')


def fetch_db_data(start_dt, end_dt):
    """Executes JOIN query against Azure MySQL using GitHub Secrets."""
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    database = os.getenv("DB_NAME")
    port = int(os.getenv("DB_PORT", 3306))

    missing_secrets = [
        name
        for name, val in [
            ("DB_HOST", host),
            ("DB_USER", user),
            ("DB_PASS", password),
            ("DB_NAME", database),
        ]
        if not val
    ]

    if missing_secrets:
        raise ValueError(f"Missing required secrets: {', '.join(missing_secrets)}")

    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        ssl={'ssl': {}},
    )

    try:
        sql = """
            SELECT 
                wr.wr_busno,
                wr.captain_id,
                u.username,
                u.fullname,
                wr.depot_id,
                d.depot_name,
                MAX(wr.route_id) AS max_route_id,
                r.route_no
            FROM ds_wages_route wr
            LEFT JOIN depot d 
                ON CAST(d.depot_id AS CHAR) = CAST(wr.depot_id AS CHAR)
            LEFT JOIN user u 
                ON u.username = CAST(wr.captain_id AS CHAR)
            LEFT JOIN route r 
                ON CAST(r.route_id AS CHAR) = CAST(wr.route_id AS CHAR)
            WHERE wr.wr_created >= %s
              AND wr.wr_created <  %s
            GROUP BY 
                wr.wr_busno,
                wr.captain_id,
                u.username,
                u.fullname,
                wr.depot_id,
                d.depot_name,
                r.route_no;
        """
        df = pd.read_sql(sql, connection, params=[start_dt, end_dt])
        return df
    finally:
        connection.close()


def main():
    # Set default date range or read from environment variables
    start_date = os.getenv("START_DATE", "2026-07-28")
    end_date = os.getenv("END_DATE", "2026-08-01")

    start_dt = f"{start_date} 00:00:00"
    end_dt = f"{end_date} 00:00:00"

    print(f"Fetching data from {start_dt} to {end_dt}...")

    df = fetch_db_data(start_dt, end_dt)

    if df.empty:
        print("No records found for the selected date range.")
        return

    # Ensure export directory exists
    os.makedirs(EXPORT_DIR, exist_ok=True)

    # Save output Excel file
    filename = (
        f"EDPRS_Wages_Route_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    file_path = os.path.join(EXPORT_DIR, filename)

    df.to_excel(file_path, index=False, engine='openpyxl')
    print(
        f"Success! Exported {len(df)} rows to Excel at: {file_path}"
    )


if __name__ == "__main__":
    main()
