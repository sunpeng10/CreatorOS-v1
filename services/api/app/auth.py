import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .db import get_db
from .models import AuditLog, Membership, Organization, Session, User, serialize

router = APIRouter(prefix='/api/auth', tags=['认证'])
hasher = PasswordHash.recommended()
COOKIE = 'creatoros_session'


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(default='创作者', min_length=1, max_length=100)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('请输入有效邮箱')
        return value


def optional_user(request: Request, db: DBSession):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    record = db.scalar(select(Session).where(Session.token_hash == hashlib.sha256(token.encode()).hexdigest()))
    if not record:
        return None
    expires = record.expires_at.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return None
    return db.get(User, record.user_id)


def current_user(request: Request, db: DBSession = Depends(get_db)):
    user = optional_user(request, db)
    if user is None:
        raise HTTPException(401, '请先登录')
    return user


def require_admin(user: User = Depends(current_user)):
    if user.role != 'OWNER_ADMIN':
        raise HTTPException(403, '仅老板管理员可执行此操作')
    return user


def owned(db, model, identifier, user):
    record = db.get(model, identifier)
    if record is None or record.organization_id != user.organization_id:
        raise HTTPException(404, '记录不存在或无权访问')
    return record


def issue_session(db, user, response, request=None):
    if request:
        prior = request.cookies.get(COOKIE)
        if prior:
            old = db.scalar(select(Session).where(Session.token_hash == hashlib.sha256(prior.encode()).hexdigest()))
            if old:
                db.delete(old)
    token = secrets.token_urlsafe(48)
    db.add(Session(organization_id=user.organization_id, user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(days=7)))
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action='AUTH_SESSION_CREATED', target_id=user.id))
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', samesite='lax', max_age=604800, path='/')


def create_user(db, email, password, name, role='CLIENT_USER'):
    org = Organization(name=f'{name}的工作区')
    db.add(org)
    db.flush()
    user = User(email=email.strip().lower(), password_hash=hasher.hash(password), name=name, organization_id=org.id, role=role)
    db.add(user)
    db.flush()
    db.add(Membership(organization_id=org.id, user_id=user.id, role=role))
    db.commit()
    return user


@router.post('/register')
def register(body: Credentials, response: Response, request: Request, db: DBSession = Depends(get_db)):
    try:
        user = create_user(db, body.email, body.password, body.name)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '该邮箱已注册')
    issue_session(db, user, response, request)
    return serialize(user)


@router.post('/login')
def login(body: Credentials, response: Response, request: Request, db: DBSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    valid = False
    if user:
        try:
            valid = hasher.verify(body.password, user.password_hash)
        except Exception:
            valid = False
    if not valid:
        raise HTTPException(401, '邮箱或密码错误')
    issue_session(db, user, response, request)
    return serialize(user)


@router.get('/me')
def me(user: User = Depends(current_user)):
    return serialize(user)


@router.post('/logout')
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    token = request.cookies.get(COOKIE, '')
    record = db.scalar(select(Session).where(Session.token_hash == hashlib.sha256(token.encode()).hexdigest()))
    if record:
        db.delete(record)
        db.commit()
    response.delete_cookie(COOKIE, path='/')
    return {'ok': True}
