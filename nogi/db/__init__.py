from datetime import datetime
import json
import os
import time

import sqlalchemy
from sqlalchemy import create_engine, types
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import MetaData
from sqlalchemy.sql.expression import delete, insert, update


class BaseModel:
    def __init__(self, engine, metadata, table, role='reader'):
        self.engine = engine
        self.metadata = metadata
        self.table = table
        self.role = role

    def execute(self, stmt: str):
        return self.engine.execute(stmt)

    def raw_insert(self, row: dict):
        assert self.role == 'writer'
        row['updated_at'] = int(time.time())
        return self.execute(insert(self.table, row))

    def raw_update(self, where: dict, row: dict):
        assert self.role == 'writer'
        row['updated_at'] = int(time.time())
        return self.execute(update(self.table).where(where).values(row))

    def raw_upsert(self, row: dict):
        assert self.role == 'writer'
        row['updated_at'] = int(time.time())
        return self.execute(Upsert(self.table, row))


def create_engine_and_metadata():
    settings = dict(
        max_overflow=-1,
        pool_size=8,
        pool_recycle=1024,
        pool_timeout=300,
        encoding='utf8')

    engine_url = 'mysql://{username}:{password}@{host}:{port}/{db_name}?binary_prefix=True&charset=utf8mb4'.format(
        username=os.environ.get('DB_USERNAME'),
        password=os.environ.get('DB_PASSWORD'),
        host=os.environ.get('DB_HOST', '127.0.0.1'),
        port=os.environ.get('DB_PORT', '3306'),
        db_name=os.environ.get('DB_NAME'))

    engine = create_engine(engine_url, **settings)
    metadata = MetaData(bind=engine)
    return engine, metadata


class Upsert(sqlalchemy.sql.expression.Insert):
    pass


@compiles(Upsert, "mysql")
def mysql_compile_upsert(insert_stmt, compiler, **kwargs):
    preparer = compiler.preparer
    if isinstance(insert_stmt.parameters, list):
        keys = insert_stmt.parameters[0].keys()
    else:
        keys = insert_stmt.parameters.keys()

    insert = compiler.visit_insert(insert_stmt, **kwargs)

    ondup = 'ON DUPLICATE KEY UPDATE'

    updates = ', '.join(
        '{} = VALUES({})'.format(preparer.format_column(c), preparer.format_column(c))
        for c in insert_stmt.table.columns
        if c.name in keys
    )
    upsert = ' '.join((insert, ondup, updates))
    return upsert


@compiles(Upsert, "sqlite")
def sqlite_compile_upsert(insert_stmt, compiler, **kwargs):
    insert = compiler.visit_insert(insert_stmt, **kwargs)
    return insert.replace("INSERT INTO", "INSERT OR REPLACE INTO", 1)


class StringfyJSON(types.TypeDecorator):

    @property
    def python_type(self):
        pass

    impl = types.TEXT

    def __init__(self):
        super().__init__()

    def process_literal_param(self, value, dialect):
        return super().process_literal_param(self, value, dialect)

    def process_bind_param(self, value, dialect):
        if value:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value:
            value = json.loads(value)
        return value


# TypeEngine.with_variant says "use StringyJSON instead when connecting to 'sqlite'"
MagicJSON = types.JSON().with_variant(StringfyJSON, 'sqlite')
