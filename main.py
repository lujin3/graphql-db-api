from sqlalchemy import create_engine
from sqlalchemy import text
from urllib.parse import urlencode

adapter_kwargs = {
    "headers": {
        "X-Ifp-Tenant-Id": "ffeb581c-6f23-43d2-b507-e224e04bc82d",
        "token": "xxxx",
    },
    "cookies": {
        "TSTenant": "ffeb581c-6f23-43d2-b507-e224e04bc82d",
        "EIToken": "xxxx"
    },
}

engine = create_engine(
    "graphql://127.0.0.1:8082/query?is_https=0", adapter_kwargs=adapter_kwargs
)

# Building the query string
query_string = urlencode(
    {
        "iarg_startTS": 1725850811000,
        "iarg_endTS": 1725957547000,
        "iarg_limit": 0,
    }
)

table = f"firefighting?{query_string}"
query = f"""SELECT ts AS ts,
       sum(value) AS "SUM(value)"
FROM '{table}'
WHERE ts >= '2024-09-01 00:00:00' AND ts < '2024-10-01 00:00:00'
GROUP BY ts
ORDER BY "SUM(value)" DESC
LIMIT 2
OFFSET 0"""


with engine.connect() as connection:
    for row in connection.execute(text(query)):
        print(row)
