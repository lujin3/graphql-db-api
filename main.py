from sqlalchemy import create_engine
from sqlalchemy import text
from urllib.parse import urlencode, urlunparse, ParseResult

# We use GraphQL SWAPI (The Star Wars API) c/o Netlify:

adapter_kwargs = {
    "headers": {
        "X-Ifp-Tenant-Id": "ffeb581c-6f23-43d2-b507-e224e04bc82d",
        "token": "eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJjb3VudHJ5IjoiIiwiY3JlYXRpb25UaW1lIjoxNjkzOTA0Njc0LCJleHAiOjE3MjY2NDI4MjksImZpcnN0TmFtZSI6IiIsImlhdCI6MTcyNjYzOTIyOSwiaWQiOiIzYmRiMmJmNS00YmNiLTExZWUtOTRiYy0wMGQ4NjEyM2U4OWUiLCJpc3MiOiJ3aXNlLXBhYXMiLCJsYXN0TW9kaWZpZWRUaW1lIjowLCJsYXN0TmFtZSI6IiIsInJlZnJlc2hUb2tlbiI6IjRlZjMxZDZlLTc1ODMtMTFlZi1iMzRkLTAwZDg2MTIzZTg5ZSIsInN0YXR1cyI6IkFjdGl2ZSIsInVzZXJuYW1lIjoiaW90ZWRnZUBpb3RlZGdlLnNlbnNlIn0.sRl8btPgzqB6EpvKfGniwdhBWFYQHfuA7n-0qdoYeOhyCOFRTi9aRC5ZWNh1O3tQ4Lg0pgnmmt3mXjzXBveqTQ",
    },
    "cookies": {},
}


engine = create_engine(
    "graphql://127.0.0.1:8082/query?is_https=0", adapter_kwargs=adapter_kwargs
)

# 构建查询字符串
query_string = urlencode(
    {
        "iarg_startTS": 1725850811000,
        "iarg_endTS": 1725957547000,
        "iarg_limit": 0,
    }
)
print(query_string)

table = f"factory?{query_string}"
query = """SELECT ts AS ts,
       sum(value) AS "SUM(value)"
FROM main.firefighting
WHERE ts >= 1627962437000
GROUP BY ts
ORDER BY "SUM(value)" DESC
LIMIT 2
OFFSET 0"""

print(query)
# query = "select id, name from 'dataSetList?query_args=%s'"
# query = "select name, homeworld__name from 'allPeople?include=homeworld'"

with engine.connect() as connection:
    for row in connection.execute(text(query)):
        print(row)
