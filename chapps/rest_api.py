"""API-related objects for CHAPPS"""
### Note that the API is powered by FastAPI and as such, the main API object itself is designed to be
###   executed by uvicorn, probably a uvicorn worker coordinated by gunicorn (see FastAPI deployment docs)

from chapps.config import config
from chapps.adapter import PolicyConfigAdapter
from typing import Optional, List
from fastapi import FastAPI, Path, Query, Body
from pydantic import BaseModel
import time

class User( BaseModel ):
    id: int
    name: str

class Quota( BaseModel ):
    id: int
    name: str
    quota: int

class Domain( BaseModel ):
    id: int
    name: str

class StdResp( BaseModel ):
    version: str
    timestamp: float
    response: object

class UserResp( StdResp ):
    response: User

class UsersResp( StdResp ):
    response: List[ User ]

api = FastAPI()
pca = PolicyConfigAdapter()
verstr = config.chapps.version

def json_response( response, **kwargs ):
    """Utility function for encapsulating responses in a standard body"""
    return dict( version=verstr, timestamp=time.time(), response=response, **kwargs )

@api.post("/users/", response_model=UserResp)
async def create_user( user: User, quota_id: int = Body( 0 ) ):
    results = dict(
        username=user.name,
        starting_quota=quota_id,
        allowed_domains=domain_ids
    )
    return results

@api.get("/users/", response_model=UsersResp)
async def list_all_users(skip: int = 0, limit: int = 1000):
    return await list_users( '%', Rskip, limit )

@api.get("/users/{pattern}", response_model=UsersResp)
async def list_users(pattern: str, skip: int = 0, limit: int = 1000):
    cur = pca.conn.cursor()
    sanitized_pattern = pattern
    query = f"SELECT id, name FROM users WHERE name LIKE '%{sanitized_pattern}%' ORDER BY id LIMIT {skip},{limit};"
    cur.execute( query )
    results = [  User( id=id, name=name ) for id, name in cur.fetchall() ]
    cur.close()
    return json_response( results )

@api.get("/user-count/")
async def count_all_users():
    return await count_users( '%' )

@api.get("/user-count/{pattern}")
async def count_users( pattern: str ):
    cur = pca.conn.cursor()
    sanitized_pattern = pattern
    query = f"SELECT COUNT( * ) FROM users WHERE name LIKE '{pattern}';"
    cur.execute( query )
    results = cur.fetchone()[0]
    cur.close()
    return json_response( results )

@api.get("/domains/")
async def get_all_domains(skip: int = 0, limit: int = 1000):
    return await get_domains( '%', skip, limit )

@api.get("/domains/{pattern}")
async def get_domains(pattern: str, skip: int = 0, limit: int = 1000):
    sanitized_pattern = pattern
    query = f"SELECT id, name FROM domains WHERE name LIKE '{sanitized_pattern}' ORDER BY id LIMIT {skip},{limit};"
    with pca.adapter_context() as cur:
        cur.execute( query )
        results = [ Domain( id=id, name=name ) for id, name in cur.fetchall() ]
    return json_response( results )
