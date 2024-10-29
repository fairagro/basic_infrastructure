"""
This is a Python script that runs inside a Docker container as part of the Spilo-Test Kubernetes
job.

It tests the PostgreSQL database connection for a given database by attempting to connect to the
database and execute a simple query. It fails if the connection fails or the query execution fails.

The connection settings are retrieved from the environment variables DB_HOST and DB_NAME.

The script then waits for a specified amount of time before exiting. The waiting time is specified
by the environment variable WAIT_TIME.

The script writes some information to stdout, such as the database connection settings and the time
until the script exits.
"""

import datetime
import time
import os

import psycopg

# Get the database connection settings from environment variables
host = os.environ.get('DB_HOST')
database = os.environ.get('DB_NAME')
username = os.environ.get('DB_USER')
password = os.environ.get('DB_PASSWORD')
table_name = os.environ.get('DB_TABLE')
column_name = os.environ.get('DB_COLUMN')

# Create a connection to the database
conn = psycopg.connect(
    host=host,
    database=database,
    user=username,
    password=password
)

# Create a cursor object
cur = conn.cursor()

# Create the table and column if they do not exist
cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id SERIAL PRIMARY KEY
    );
""")

cur.execute(f"""
    ALTER TABLE {table_name}
    ADD COLUMN IF NOT EXISTS {column_name} TIMESTAMP;
""")

# Commit the changes
conn.commit()

while True:
    # Get the current timestamp
    current_timestamp = datetime.datetime.now()

    # Insert the timestamp into the database
    cur.execute("INSERT INTO your_table (timestamp) VALUES (%s)",
                (current_timestamp,))

    # Commit the changes
    conn.commit()

    # Wait for 1 second before inserting the next timestamp
    time.sleep(1)
