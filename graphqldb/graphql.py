from superset.db_engine_specs.sqlite import SqliteEngineSpec
from superset.constants import TimeGrain
from typing import Any
import json
import logging
from flask import request
from sqlalchemy.engine.reflection import Inspector
from superset.superset_typing import ResultSetColumnType

logger = logging.getLogger()

class GraphQLEngineSpec(SqliteEngineSpec):
    """Engine for GraphQL API tables"""

    engine = "graphql"
    engine_name = "GraphQL"
    allows_joins = True
    allows_subqueries = True

    default_driver = "apsw"
    sqlalchemy_uri_placeholder = "graphql://"

    # TODO(cancan101): figure out what other spec items make sense here
    # See: https://preset.io/blog/building-database-connector/


    _time_grain_expressions = {
        None: "{col}",
        TimeGrain.SECOND: "{col}",
        TimeGrain.MINUTE: "{col}",
        TimeGrain.HOUR: "{col}",
        TimeGrain.DAY: "{col}",
        TimeGrain.WEEK: "{col}",
        TimeGrain.MONTH: "{col}",
        TimeGrain.QUARTER: "{col}",
        TimeGrain.YEAR: "{col}",
        TimeGrain.WEEK_ENDING_SATURDAY: "{col}",
        TimeGrain.WEEK_STARTING_SUNDAY: "{col}",
    }

    @staticmethod
    def get_extra_params(database) -> dict[str, Any]:
        """
        Some databases require adding elements to connection parameters,
        like passing certificates to `extra`. This can be done here.

        :param database: database instance from which to extract extras
        :raises CertificateException: If certificate is not valid/unparseable
        """
        extra: dict[str, Any] = {}
        if database.extra:
            try:
                extra = json.loads(database.extra)
            except json.JSONDecodeError as ex:
                logger.error(ex, exc_info=True)
                raise ex

        cookies = {
                "TSTenant": request.cookies.get('TSTenant'),
                "EIToken": request.cookies.get('EIToken')
            }
        # params["adapter_kwargs"] = {'cookies': cookies}
        adapter_kwargs = {"cookies": cookies}
        engine_params = {"adapter_kwargs": adapter_kwargs}
        extra["engine_params"]= engine_params
        return extra
    
    @classmethod
    def fetch_data(cls, cursor: Any, limit: int | None = None) -> list[tuple[Any, ...]]:
        data = super().fetch_data(cursor, limit)


        return data
    
    @classmethod
    def get_columns(
        cls,
        inspector: Inspector,
        table_name: str,
        schema: str | None,
        options: dict[str, Any] | None = None,
    ) -> list[ResultSetColumnType]:
        """
        将 ts 列转换为 datetime 类型
        """
        base_cols = super().get_columns(inspector, table_name, schema, options)
        for col in base_cols:
            if col["column_name"] == "ts":
                col["type"] = "TIMESTAMP"
        return base_cols
