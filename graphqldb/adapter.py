from __future__ import annotations

from collections import defaultdict
from typing import (
    Any,
    Collection,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    Union,
    cast,
)
from urllib.parse import parse_qs, urlparse

from shillelagh.adapters.base import Adapter
from shillelagh.fields import (
    Boolean,
    Field,
    Filter,
    Float,
    Integer,
    ISODate,
    ISODateTime,
    ISOTime,
    String,
    DateTime,
)

from shillelagh.fields import Field, RowID

from shillelagh.typing import RequestedOrder, Row

from .lib import get_last_query, run_query, convert_timestamp_to_datetime

# -----------------------------------------------------------------------------


class MaybeNamed(TypedDict):
    name: Optional[str]


class TypeInfo(MaybeNamed):
    ofType: Optional[Union[TypeInfo, MaybeNamed]]
    # technically an enum:
    kind: str


class FieldInfo(TypedDict):
    name: str
    type: TypeInfo


class TypeInfoWithFields(TypeInfo):
    fields: Optional[List[FieldInfo]]


QueryArg = Union[str, int]

# -----------------------------------------------------------------------------


def parse_gql_type(type_info: TypeInfo) -> Field:
    # TODO(cancan101): do we want to handle Nones here?
    name: Optional[str] = type_info["name"]
    if name == "String":
        return String()
    elif name == "ID":
        # TODO(cancan101): figure out if we want to map this to UUID, int, etc
        # This should probably be an API-level setting
        return String()
    elif name == "Int":
        return Integer()
    elif name == "Float":
        return Float()
    elif name == "Boolean":
        return Boolean()
    # These are extended scalars:
    elif name == "DateTime":
        # https://www.graphql-scalars.dev/docs/scalars/date-time
        return ISODateTime()
    elif name == "Date":
        # https://www.graphql-scalars.dev/docs/scalars/date
        return ISODate()
    elif name == "Time":
        # https://www.graphql-scalars.dev/docs/scalars/time
        return ISOTime()
    elif name == "Timestamp":
        return DateTime()
    else:
        # TODO(cancan101): how do we want to handle other scalars?
        raise ValueError(f"Unknown type: {name}")


def get_type_entries(
    field_obj: FieldInfo,
    *,
    data_types: Dict[str, TypeInfoWithFields],
    include: Collection[str],
    path: Optional[List[str]] = None,
) -> Dict[str, Field]:
    path = path or []

    field_name = field_obj["name"]
    new_path = path + [field_name]

    field_obj_type = field_obj["type"]

    kind = field_obj_type["kind"]
    if kind == "SCALAR":
        field_field = parse_gql_type(field_obj_type)
        return {"__".join(new_path): field_field}
    elif kind == "NON_NULL":
        of_type = field_obj_type["ofType"]

        if of_type is None:
            raise ValueError("of_type is None")

        of_type_name = of_type["name"]
        if of_type_name is None:
            raise ValueError("of_type_name is None")

        return get_type_entries(
            FieldInfo(
                name=field_name,
                type=data_types[of_type_name],
            ),
            data_types=data_types,
            include=include,
            path=path,
        )
    # TODO(cancan101): other types to handle:
    # LIST, ENUM, UNION, INTERFACE, OBJECT (implicitly handled)
    else:
        # Check to see if this is a requested include
        if field_name in include:
            ret = {}
            name = field_obj_type["name"]
            if name is None:
                raise ValueError(f"Unable to get type of: {field_name}")

            fields = data_types[name]["fields"]
            if fields is None:
                raise ValueError(f"Unable to get fields for: {name}")

            for field in fields:
                ret.update(
                    get_type_entries(
                        field, data_types=data_types, include=include, path=new_path
                    )
                )
            return ret

        return {}


# -----------------------------------------------------------------------------


# clean these up:
def find_by_name(name: str, *, types: List[FieldInfo]) -> Optional[FieldInfo]:
    name_match = [x for x in types if x["name"] == name]
    if len(name_match) == 0:
        return None
    return name_match[0]


def find_type_by_name(name: str, *, types: List[FieldInfo]) -> Optional[TypeInfo]:
    entry = find_by_name(name, types=types)
    if entry is None:
        return None
    return entry["type"]


def get_edges_type_name(fields: List[FieldInfo]) -> Optional[str]:
    entry_type = find_type_by_name("edges", types=fields)
    if entry_type is None:
        return None
    edges_info = entry_type["ofType"]
    if edges_info is None:
        return None
    return edges_info["name"]


def get_node_type_name(fields: List[FieldInfo]) -> Optional[str]:
    node_info = find_type_by_name("node", types=fields)
    if node_info is None:
        return None
    return node_info["name"]


# -----------------------------------------------------------------------------


def extract_flattened_value(node: Dict[str, Any], field_name: str) -> Any:
    ret: Any = node
    for path in field_name.split("__"):
        if ret is None:
            return ret
        elif not isinstance(ret, dict):
            raise TypeError(f"{field_name} is not dict path")
        ret = ret.get(path)
    return ret


def get_gql_fields(column_names: Sequence[str]) -> str:
    # TODO(cancan101): actually nest this
    def get_field_str(fields: List[str], root: Optional[str] = None) -> str:
        ret = " ".join(fields)
        if root is not None:
            ret = f"{root} {{{ret}}}"
        return ret

    mappings: Dict[Optional[str], List[str]] = defaultdict(list)
    for field in [x.split("__", 1) for x in column_names]:
        if len(field) == 1:
            mappings[None].append(field[-1])
        else:
            mappings[field[0]].append(field[-1])

    fields_str = " ".join(
        get_field_str(fields, root=root) for root, fields in mappings.items()
    )
    return fields_str


def _parse_query_arg(k: str, v: List[str]) -> Tuple[str, str]:
    if len(v) > 1:
        raise ValueError(f"{k} was specified {len(v)} times")

    return (k, v[0])


def _parse_query_args(query: Dict[str, List[str]]) -> Dict[str, QueryArg]:
    str_args = dict(
        _parse_query_arg(k[4:], v) for k, v in query.items() if k.startswith("arg_")
    )
    int_args = dict(
        (k, int(v))
        for k, v in (
            _parse_query_arg(k[5:], v)
            for k, v in query.items()
            if k.startswith("iarg_")
        )
    )
    overlap = set(str_args.keys()) & set(int_args.keys())
    if overlap:
        raise ValueError(f"{overlap} was specified in multiple arg sets")

    return dict(str_args, **int_args)


def _format_arg(arg: QueryArg) -> str:
    if isinstance(arg, str):
        return f'"{arg}"'
    return str(arg)


def _get_variable_argument_str(args: Dict[str, QueryArg]) -> str:
    return " ".join(f"{k}: {_format_arg(v)}" for k, v in args.items())


# -----------------------------------------------------------------------------


class GraphQLAdapter(Adapter):
    safe = True
    is_connection: bool

    def __init__(
        self,
        table: str,
        include: Collection[str],
        query_args: Dict[str, QueryArg],
        is_connection: Optional[bool],
        graphql_api: str,
        bearer_token: Optional[str] = None,
        pagination_relay: Optional[bool] = None,
        list_queries: Optional[List[str]] = None,
        headers: Optional[Dict[str, Any]] = None,
        cookies: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()

        # The query field name
        self.table = table

        self.include = set(include)
        self.query_args = query_args

        if is_connection is not None:
            self.is_connection = is_connection
        else:
            self.is_connection = list_queries is None or table not in list_queries

        self.graphql_api = graphql_api
        self.bearer_token = bearer_token
        self.headers = headers
        self.cookies = cookies

        if pagination_relay is True and self.is_connection is False:
            raise ValueError("pagination_relay True and is_connection False")
        # For now, default this to True. In the future, we can perhaps guess
        self.pagination_relay = True if pagination_relay is None else pagination_relay

        query_type_and_types_query = """{
  __schema {
    queryType {
      fields {
        name
        args {
          name
        }
        type {
          name
          kind
          ofType {
            name
            kind
            ofType {
              kind
              name
              ofType {
                name
              }
            }
          }
        }
      }
    }
    types {
      name
      kind
      fields {
        name
        type {
          name
          kind
          ofType {
            name
          }
        }
      }
    }
  }
}"""

        query_type_and_types = self.run_query(query=query_type_and_types_query)
        query_type_and_types_schema = query_type_and_types["__schema"]
        queries_return_fields: List[FieldInfo] = query_type_and_types_schema["queryType"]["fields"]
        
        # find the matching query (a field on the query object)
        # TODO(cancan101): handle missing
        type_entry = find_type_by_name(self.table, types=queries_return_fields)
        if type_entry is None:
            raise ValueError(f"Unable to resolve type_entry for {self.table}")

        data_types_list: List[TypeInfoWithFields] = query_type_and_types_schema["types"]
        data_types: Dict[str, TypeInfoWithFields] = {
            t["name"]: t for t in data_types_list if t["name"] is not None
        }

        if type_entry["name"]:
            query_return_type_name = type_entry["name"]
        elif type_entry["ofType"]["name"]:
            query_return_type_name = type_entry["ofType"]["name"]
        else:
            raise ValueError(
                f"Unable to resolve query_return_type_name for {self.table}"
            )

        query_return_fields = data_types[query_return_type_name]["fields"]
        if query_return_fields is None:
            raise ValueError("No fields found on query")

        self.columns: Dict[str, Field] = {}
        for node_field in query_return_fields:
            self.columns.update(
                get_type_entries(
                    node_field, data_types=data_types, include=self.include
                )
            )

        self.args = next((f["args"] for f in queries_return_fields if f["name"] == self.table), [])
        valid_arg_names = {arg["name"] for arg in self.args}
        self.query_args = {k: v for k, v in self.query_args.items() if k in valid_arg_names}

    @staticmethod
    def supports(uri: str, fast: bool = True, **kwargs: Any) -> Optional[bool]:
        # TODO the slow path here could connect to the GQL Server
        return True

    @staticmethod
    def parse_uri(
        table: str,
    ) -> Tuple[str, List[str], Dict[str, QueryArg], Optional[bool]]:
        """
        This will pass in the first n args of __init__ for the Adapter
        """
        parsed = urlparse(table)
        query_string = parse_qs(parsed.query)

        include_entry = query_string.get("include")
        is_connection_raw_qs = query_string.get("is_connection")
        if is_connection_raw_qs is None:
            is_connection = None
        else:
            is_connection = get_last_query(is_connection_raw_qs) != "0"

        include: List[str] = []
        if include_entry:
            for i in include_entry:
                include.extend(i.split(","))

        query_args = _parse_query_args(query_string)

        return (parsed.path, include, query_args, is_connection)

    def get_columns(self) -> Dict[str, Field]:
        return self.columns

    def run_query(self, query: str) -> Dict[str, Any]:
        return run_query(
            self.graphql_api,
            query=query,
            bearer_token=self.bearer_token,
            headers=self.headers,
            cookies=self.cookies,
        )

    def get_data(
        self,
        bounds: Dict[str, Filter],
        order: List[Tuple[str, RequestedOrder]],
        **kwargs: Any,
    ) -> Iterator[Dict[str, Any]]:
        fields_str = get_gql_fields(list(self.columns.keys()))

        if self.query_args:
            variable_str = f"({_get_variable_argument_str(self.query_args)})"
        else:
            # Don't generate the () for empty list of query_args
            variable_str = ""

        query = f"""query {{
{self.table}{variable_str}{{
    {fields_str}
}}
}}"""
        query_data = self.run_query(query=query)
        nodes: List[Dict[str, Any]] = query_data[self.table]

        for node in nodes:
            yield {c: extract_flattened_value(node, c) for c in self.columns.keys()}


    def get_rows(
        self,
        bounds: Dict[str, Filter],
        order: List[Tuple[str, RequestedOrder]],
        **kwargs: Any,
    ) -> Iterator[Row]:
        """
        Yield rows as native Python types.
        """
        columns = self.get_columns()
        parsers = {column_name: field.parse for column_name, field in columns.items()}
        parsers["rowid"] = RowID().parse

        # 提前计算需要时间戳转换的列
        ts_rows = {column_name for column_name, field in columns.items() if field.type == "TIMESTAMP"}

        for row in self.get_data(bounds, order, **kwargs):

            yield {
                column_name: parsers[column_name](convert_timestamp_to_datetime(value) if column_name in ts_rows else value)
                for column_name, value in row.items()
                if column_name in parsers
            }
