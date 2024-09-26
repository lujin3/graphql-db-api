from superset.db_engine_specs.sqlite import SqliteEngineSpec
from typing import Any
import json
import logging
from flask import request

logger = logging.getLogger()

class GraphQLEngineSpec(SqliteEngineSpec):
    """Engine for GraphQL API tables"""

    engine = "graphql"
    engine_name = "GraphQL"
    allows_joins = True
    allows_subqueries = True

    default_driver = "apsw"
    sqlalchemy_uri_placeholder = "graphql://"

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
    
       