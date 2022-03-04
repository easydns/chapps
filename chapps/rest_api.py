"""API-related objects for CHAPPS"""
### Note that the API is powered by FastAPI and as such, the main API object itself is designed to be
###   executed by uvicorn, probably a uvicorn worker coordinated by gunicorn (see FastAPI deployment docs)

from chapps.config import config
from chapps.adapter import PolicyConfigAdapter
from typing import Optional, List
from fastapi import FastAPI, Path, Query, Body
from pydantic import BaseModel
import time

class CHAPPSModel( BaseModel ):
    id: int
    name: str

    @classmethod
    def zip_records( model, records: List[ List ] ):
        keys = list( model.schema()['properties'].keys() )
        return [ model( **dict( zip( keys, record ) ) ) for record in records ]

    @classmethod
    def select_query( model, *, where = [], limit = (0,1000), order = 'id' ):
        """Build a select suitable for wrapping in a model"""
        keys = list( model.schema()['properties'].keys() )
        query = f"SELECT {','.join( keys )} FROM {model.__name__.lower()}s"
        if where:
            query += f" WHERE {' AND '.join( where )}"
        query += f" ORDER BY {order} LIMIT {','.join( [ str(l) for l in limit] )};"
        return query

class User( CHAPPSModel ):
    """A model to represent users"""

class Quota( BaseModel ):
    """A model to represent quotas"""
    quota: int

class Domain( BaseModel ):
    """A model to represent domains"""

class CHAPPSResponse( BaseModel ):
    version: str
    timestamp: float
    response: object

    @classmethod
    def send( model, response, **kwargs ):
        """Utility function for encapsulating responses in a standard body"""
        return model( version=verstr, timestamp=time.time(), response=response, **kwargs )

class UserResp( CHAPPSResponse ):
    response: User
    domains: Optional[ List[ Domain ] ] = None
    quota: Optional[ Quota ] = None

class UsersResp( CHAPPSResponse ):
    response: List[ User ]

class DomainResp( CHAPPSResponse ):
    response: Domain
    users: Optional[ List[ Domain ] ] = None

class DomainsResp( CHAPPSResponse ):
    response: List[ Domain ]

class QuotaResp( CHAPPSResponse ):
    response: Quota

class QuotasResp( CHAPPSResponse ):
    response: List[ Quota ]

api = FastAPI()
pca = PolicyConfigAdapter()
verstr = config.chapps.version

@api.post("/users/", response_model=UserResp)
async def create_user( user: User, quota_id: int = Body( 0 ), domain_ids: List[ int ] = [] ):
    queries = [ f"INSERT INTO users( name ) VALUES ('{user.name}');",
                "SELECT id, name FROM users WHERE id=LAST_INSERT_ID();" ]
    with pca.adapter_context() as cur:
        for q in queries:
            cur.execute( q )
        result = cur.fetchone()
    return UserResp.send( User.zip_records( [ result ] )[0] )

@api.get("/users/", response_model=UsersResp)
async def list_all_users(skip: int = 0, limit: int = 1000):
    return await list_users( '%', skip, limit )

# @api.get("/users/{user_id}", response_model=UserResp)
# async def get_user(user_id: int):
#     keys = list( User.schema()['properties'].keys() )

@api.get("/users/{pattern}", response_model=UsersResp)
async def list_users(pattern: str, skip: int = 0, limit: int = 1000):
    sanitized_pattern = pattern
    query = User.select_query( where=[f"name LIKE '%{sanitized_pattern}%'"], limit=(skip,limit) )
    keys = list( User.schema()['properties'].keys() )
    with pca.adapter_context() as cur:
        cur.execute( query )
        results = User.zip_records( cur.fetchall() )
    cur.close()
    return UsersResp.send( results )

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

@api.get("/domains/", response_model=List[ Domain ])
async def list_all_domains(skip: int = 0, limit: int = 1000):
    return await list_domains( '%', skip, limit )

@api.get("/domains/{pattern}", response_model=List[ Domain ])
async def list_domains(pattern: str, skip: int = 0, limit: int = 1000):
    sanitized_pattern = pattern
    query = Domain.select_query( where=[ f"name LIKE '%{sanitized_pattern}%" ] )
    with pca.adapter_context() as cur:
        cur.execute( query )
        results = Domain.zip_records( cur.fetchall() )
    return DomainsResp.send( results )
