from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Union

import requests
import datetime

if TYPE_CHECKING:
    from sqlalchemy.engine.url import URL

# -----------------------------------------------------------------------------


# Imported from: shillelagh.backends.apsw.dialects.gsheets
def extract_query(url: URL) -> Dict[str, Union[str, Sequence[str]]]:
    """
    Extract the query from the SQLAlchemy URL.
    """
    if url.query:
        return dict(url.query)

    # there's a bug in how SQLAlchemy <1.4 handles URLs without hosts,
    # putting the query string as the host; handle that case here
    if url.host and url.host.startswith("?"):
        return dict(urllib.parse.parse_qsl(url.host[1:]))  # pragma: no cover

    return {}


def get_last_query(entry: Union[str, Sequence[str]]) -> str:
    if not isinstance(entry, str):
        entry = entry[-1]
    return entry


# -----------------------------------------------------------------------------


def run_query(
    graphql_api: str,
    *,
    query: str,
    bearer_token: Optional[str] = None,
    headers: Optional[Dict[str, Any]] = None,
    cookies: Optional[Dict[str, Any]] = None,
    timeout: int = 300,  # 设置超时时间
) -> Dict[str, Any]:
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"


    # 打印请求的详细内容
    print(f"""
----- Request Details -----
URL     : {graphql_api}
Headers : {headers}
Cookies : {cookies}
Query   : {query}
""")

    try:
        # 发起 POST 请求，并设置超时
        resp = requests.post(
            graphql_api, json={"query": query}, headers=headers, cookies=cookies, timeout=timeout
        )
        # 检查是否有 HTTP 错误
        resp.raise_for_status()

    except requests.Timeout:
        print(f"Request timed out: {timeout}s")
        raise
    except requests.RequestException as ex:
        print(f"An error occurred: {ex}")
        raise

    resp_data = resp.json()

    # 检查 GraphQL 响应中是否有 errors
    if "errors" in resp_data:
        print(f"GraphQL Errors: {resp_data['errors']}")
        raise ValueError(resp_data["errors"])

    return resp_data["data"]


def convert_timestamp_to_datetime(timestamp):
    """
    将秒级或毫秒级时间戳转换为人类可读的日期时间格式。
    
    :param timestamp: 秒级或毫秒级时间戳
    :return: 可读的日期时间字符串
    """
    # 判断时间戳是秒级还是毫秒级
    if len(str(timestamp)) == 13:  # 如果是13位，则为毫秒级
        # 将毫秒级时间戳转换为秒级时间戳
        timestamp = timestamp / 1000
    
    # 转换为 datetime 对象
    dt_obj = datetime.datetime.fromtimestamp(timestamp)
    return dt_obj
    # 格式化为字符串
    # return dt_obj.strftime('%Y-%m-%d %H:%M:%S')