import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import auth, content
from .db import SessionLocal


@asynccontextmanager
async def lifespan(app):
    if os.getenv('CREATOROS_TESTING') != '1':
        from .workflow import recover_interrupted_tasks
        recover_interrupted_tasks()
    yield


app = FastAPI(title='CreatorOS · 爆款实验室 API', version='0.1.0', lifespan=lifespan, description='本地内容研究平台。AI 仅在明确确认后调用，订单支付仅为 DEMO 模拟。')
allowed_origins = {os.getenv('WEB_ORIGIN', 'http://127.0.0.1:3000'), os.getenv('API_URL', 'http://127.0.0.1:8000'), 'http://localhost:3000', 'http://127.0.0.1:3000'}
app.add_middleware(CORSMiddleware, allow_origins=list(allowed_origins), allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Content-Type'])
attempts = defaultdict(deque)


@app.middleware('http')
async def security(request: Request, call_next):
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        origin = request.headers.get('origin')
        if origin and origin not in allowed_origins:
            return JSONResponse({'error': {'code': 'ORIGIN_DENIED', 'message': '请求来源不被允许'}}, status_code=403)
    if request.method == 'POST' and request.url.path in {'/api/auth/login', '/api/auth/register', '/api/leads'}:
        key = ((request.client.host if request.client else 'unknown'), request.url.path)
        now = time.monotonic()
        history = attempts[key]
        while history and now - history[0] > 60:
            history.popleft()
        if len(history) >= 30:
            return JSONResponse({'error': {'code': 'RATE_LIMIT', 'message': '操作频繁，请一分钟后重试'}}, status_code=429)
        history.append(now)
    length = request.headers.get('content-length')
    if length and length.isdigit() and int(length) > (int(os.getenv('MAX_UPLOAD_MB', '100')) + 2) * 1024 * 1024:
        return JSONResponse({'error': {'code': 'TOO_LARGE', 'message': '上传超过大小限制'}}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    detail = exc.detail
    code = detail.get('code', f'HTTP_{exc.status_code}') if isinstance(detail, dict) else f'HTTP_{exc.status_code}'
    message = detail.get('message', '请求未通过校验') if isinstance(detail, dict) else str(detail)
    return JSONResponse({'error': {'code': code, 'message': message}, 'detail': detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Never return the original input, which may include passwords or private media.
    issues = [{'field': '.'.join(map(str, e['loc'])), 'message': e['msg']} for e in exc.errors()]
    return JSONResponse({'error': {'code': 'VALIDATION_ERROR', 'message': '请检查输入字段'}, 'issues': issues}, status_code=422)


@app.get('/api/health', tags=['系统'])
def health():
    with SessionLocal() as db:
        db.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'connected', 'service': 'CreatorOS', 'version': '0.1.0'}


app.include_router(auth.router)
app.include_router(content.router)
# Imported after foundational dependencies to keep domain modules independent.
from .analysis import router as analysis_router
from .business import router as business_router
app.include_router(analysis_router)
app.include_router(business_router, prefix='/api')
