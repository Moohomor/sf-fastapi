from passlib.hash import pbkdf2_sha256 as sha256
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4
from loguru import logger
import os
from functools import wraps
from globals import conn, sessions
from utils import Exception400

auth_router = APIRouter(prefix='/auth', tags=['Session management'])

def auth_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        sid = kwargs['r'].sid
        if sid not in sessions:
            async def route_substitution(*args, **kwargs):
                raise Exception400('Invalid session')
            return await route_substitution(*args, **kwargs)
        return await func(*args, **kwargs)
    return wrapper

class AuthRequest(BaseModel):
    login: str = Field(description="Login must not contain spaces", pattern=r'^[ ]*')
    password: str

class LoginResponse(BaseModel):
    sid: str

@auth_router.post('/reg')
async def reg(r: AuthRequest):
    """Asks login and password (both are strings).
    Returns {result:OK} on success and code 500 on error"""
    with conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO sf.users (name, password) VALUES (%s, %s)',
                        (r.login, sha256.hash(r.password + os.environ.get('SALT', ''))))
            conn.commit()
    return {'result': 'OK'}


@auth_router.post('/login')
async def login(r: AuthRequest) -> LoginResponse:
    """Asks login and password (both are strings).
    Returns {result:OK, 'sid': <session id>} on success and code 500 on error"""
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password, id FROM sf.users "
                        f"WHERE name=\'{r.login}\'")
            row = cur.fetchone()
            if row is None or not sha256.verify(r.password + os.environ.get('SALT', ''), row[0]):
                return JSONResponse({'result': 'Wrong login or password'}, 403)
    sid = str(uuid4())
    sessions[sid] = {'name': r.login, 'uid': row[1], 'started': datetime.now()}
    return LoginResponse(sid=sid)


class LogoutRequest(BaseModel):
    sid: str = Field(description="Session id returned by login or reg route")


@auth_router.post('/logout')
async def logout(r: LogoutRequest):
    """Removes session on success"""
    sessions.pop(r.sid, 0)
    return {'result': 'OK'}