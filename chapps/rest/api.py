"""API-related objects for CHAPPS"""
### Note that the API is powered by FastAPI and as such, the main API object itself is designed to be
###   executed by uvicorn, probably a uvicorn worker coordinated by gunicorn (see FastAPI deployment docs)

from chapps.config import config
from chapps.adapter import PolicyConfigAdapter
from chapps.rest.models import User, Quota, Domain, UserResp, UsersResp, DomainResp, DomainsResp, QuotaResp, QuotasResp, IntResp, ConfigResp, DeleteResp, ErrorResp
from typing import Optional, List
from fastapi import FastAPI, Path, Query, Body
from pydantic import BaseModel
import time
import logging, chapps.logging

logger = logging.getLogger( __name__ )
logger.setLevel( logging.DEBUG )

api = FastAPI()
pca = PolicyConfigAdapter()
verstr = config.chapps.version

##### Users

@api.post("/user/", response_model=UserResp, status_code=201, responses={400: {"description": "Could not create user"}}, tags=['users'] )
async def create_user( user: User,
                       quota_id: int = Body( None , gt=0, title='Optionally supply a quota ID to link' ),
                       domain_ids: List[ int ] = Body( None, gt=0, title='Optionally supply a list of domain IDs to link') ):
    queries = [ f"INSERT INTO users( name ) VALUES ('{user.name}');",
                "SELECT LAST_INSERT_ID() INTO @newuid;",
                "SELECT id, name FROM users WHERE id=@newuid;" ]
    quota_link_query, domain_link_query, domain_link_data = None, None, None
    extra_keys = {}
    if quota_id:
        quota_resp = await get_quota( quota_id )
        if quota_resp.response is not None:
            quota_link_query= f"INSERT INTO quota_user (quota_id, user_id) VALUES ({quota_id}, @newuid);"
            quota_verify = Quota.joined_select( User, 'j.user_id = @newuid' )
        else:
            return ErrorResp.send( None, error='integrity', message=f'There is no quota with id = {quota_id}' )
    if domain_ids:
        domains_resp = await list_domains( "%", 0, 1000, domain_ids )
        if domains_resp.response is not None and len( domains_resp.response ) == len( domain_ids ):
            domain_link_query = f"INSERT INTO domain_user (domain_id, user_id) VALUES ( ? , @newuid );"
            domain_link_data = [ ( d_id ) for d_id in domain_ids ]
            domain_verify = Domain.joined_select( User, [ 'j.user_id = @newuid' ] )
        else:
            return ErrorResp.send( None, error='integrity', message=f'One or more of the specified domains does not exist' )
    new_user = None
    with pca.adapter_context() as cur:
        try:
            for q in queries:
                cur.execute( q )
            result = cur.fetchall()
            new_user = User.zip_records( result )[0] if result else None
        except mariadb.IntegrityError:
            return ErrorResp.send( None, error='integrity', message='A user with that name already exists.')
        except Exception as e:
            logger.exception("Attempting to create a user.")
        if new_user is None:
            return ErrorResp.send( None, error='internal', message='No user was created.' )
        if quota_link_query:
            try:
                cur.execute( quota_link_query )
            except mariadb.IntegrityError as e:
                return ErrorResp.send( None, error='integrity', message=str(e) )
            cur.execute( quota_verify )
            quotas = Quota.zip_records( cur.fetchall() )
            extra_keys[ 'quota' ] = quotas[0] if quotas else None
        if domain_link_query:
            try:
                cur.executemany( domain_link_query, domain_link_data )
            except mariadb.IntegrityError as e:
                return ErrorResp.send( None, error='integrity', message=str(e) )
    UserResp.send( new_user, **extra_keys )

@api.delete("/user/{user_id}", response_model=DeleteResp, tags=['users'])
async def delete_user(
        user_id: int = Path(..., gt=0,
                            title='The ID of the user to delete'
        ) ):
    select = f"SELECT id,user FROM users WHERE id={user_id};"
    delete = f"DELETE FROM users WHERE id={user_id};" # this is the prikey, no need to limit
    with pca.adapter_context() as cur:
        cur.execute( select )
        users = User.zip_records( cur.fetchall() )
        if users:
            user = users[0]
            response = f"Deleted user {user.name} ({user.id})"
            status = True
            cur.execute( delete )
        else:
            response = f"No user with id {user_id}"
            status = False
    return DeleteResp.send( response, status=status )

@api.get("/user/{user_id}", response_model=UserResp, tags=['users'])
async def get_user(user_id: int):
    query = User.select_query( where=[f'id={user_id}'] )
    with pca.adapter_context() as cur:
        cur.execute( query )
        results = User.zip_records( cur.fetchall() )
        if results:
            results = results[0]
            ### TODO: this routine also needs to populate the quota and domains fields
            return UserResp.send( results )
    return ErrorResp.send( None , error='nonexistent', message=f'There is no user with id {user_id}' )

@api.get("/users/", response_model=UsersResp, tags=['users'])
async def list_all_users(skip: int = 0, limit: int = 1000):
    return await list_users( '%', skip, limit )

@api.get("/users/{pattern}", response_model=UsersResp, tags=['users'])
async def list_users(pattern: str, skip: int = 0, limit: int = 1000):
    sanitized_pattern = pattern
    query = User.select_query( where=[f"name LIKE '%{sanitized_pattern}%'"], window=(skip,limit) )
    with pca.adapter_context() as cur:
        cur.execute( query )
        results = User.zip_records( cur.fetchall() )
    return UsersResp.send( results )

@api.get("/user-count/", tags=['users'])
async def count_all_users():
    return await count_users( '%' )

@api.get("/user-count/{pattern}", tags=['users'])
async def count_users( pattern: str ):
    cur = pca.conn.cursor()
    sanitized_pattern = pattern
    query = f"SELECT COUNT( * ) FROM users WHERE name LIKE '%{sanitized_pattern}%';"
    cur.execute( query )
    results = cur.fetchone()[0]
    cur.close()
    return IntResp.send( results )


##### Domains

@api.get("/domain/{domain_id}", response_model=DomainResp)
async def get_domain(domain_id: int = Path(...,gt=0)):
    query = Domain.select_query( where=[f'id={domain_id}'] )
    with pca.adapter_context() as cur:
        cur.execute( query )
        results = Domain.zip_records( cur.fetchall() )
        if results:
            results = results[0]
            return DomainResp.send( results )
    return ErrorResp.send( None , error='nonexistent', message=f'There is no user with id {user_id}' )


@api.get("/domains/", response_model=List[ Domain ])
async def list_all_domains(skip: int = 0, limit: int = 1000, ids: List[ int ] = None):
    return await list_domains( '%', skip, limit, ids )

@api.get("/domains/{pattern}", response_model=List[ Domain ])
async def list_domains(pattern: str, skip: int = 0, limit: int = 1000, ids: List[ int ] = None):
    sanitized_pattern = pattern
    where = [ f"name LIKE '%{sanitized_pattern}%'" ]
    if ids:
        where.append( f"id IN ({','.join(ids)})" )
    query = Domain.select_query( where=where, window=(skip,limit) )
    with pca.adapter_context() as cur:
        cur.execute( query )
        results = Domain.zip_records( cur.fetchall() )
    return DomainsResp.send( results )
