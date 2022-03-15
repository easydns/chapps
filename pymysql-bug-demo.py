"""A small script to demonstrate the bug in PyMySQL adaptation"""
import sqlalchemy as sa
from chapps.rest.models import User

db_creds = dict(
    username='chapps_test',
    password='screwy%pass${word}',
    database='chapps_test'
)
sample_select = User.Meta.orm_model.select_by_id(1)
# create two identical URLs, except for MySQL driver
pymysql_url = sa.engine.URL.create('mysql+pymysql', **db_creds)
default_url = sa.engine.URL.create('mysql', **db_creds)
# create parallel engines
pymysql_engine = sa.create_engine(pymysql_url)
default_engine = sa.create_engine(default_url)
# create connections, if possible
msg = [
    "The purpose of this script is to demonstrate that SQLAlchemy",
    "does not properly escape or encode the password field when",
    "passing it through to PyMySQL, resulting in an authentication",
    "failure which does not occur with other backends.  This has been",
    "demonstrated in some other places as well:",
    "https://stackoverflow.com/questions/51849583/pymysql-fails-to-authenticate-specific-user-mysqldb-succeeds",
    "Most notable about the above is the note that PyMySQL does not",
    "consider the escaping issue to be a bug, and requires that the",
    "input be protected somehow; in the example, by encoding it to bytes."
]
for m in msg:
    print(m)
print()
print("Trying PyMySQL:")
try:
    pymysql_conn = pymysql_engine.connect()
except Exception as e:
    print("PyMySQL unable to connect:")
    print(e)
else:
    print("PyMySQL connects fine.  Attempting to select user w/ id 1:")
    res = pymysql_conn.execute(sample_select)
    row = next(res)
    print(f"Got: {row!r}")
    pymysql_conn.close()
print()
print("Trying the default MySQL adapter:")
try:
    default_conn = default_engine.connect()
except Exception as e:
    print("Default MySQL adapter unable to connect:")
    print(e)
else:
    print("Default MySQL adapter connects fine.  Attempting to select user w/ id 1:")
    res = default_conn.execute(sample_select)
    row = next(res)
    print(f"Got: {row!r}")
    default_conn.close()
