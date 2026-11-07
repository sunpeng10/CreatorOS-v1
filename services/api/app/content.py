import mimetypes
import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import current_user, owned
from .customer_links import customer_for, is_demo_record
from .db import DATA_DIR, get_db
from .media import parse_media, video_frames
from .models import Approval, AuditLog, ContentAnalysis, ContentAsset, ContentItem, CreatorAccount, Experiment, Order, User, serialize

router = APIRouter(prefix='/api', tags=['素材与工作台'])
UPLOAD_DIR = DATA_DIR / 'uploads'


class ContentBody(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(default='', max_length=200000)
    kind: str = Field(default='text', pattern='^(text|image|album|video)$')
    account_id: str | None = None
    platform: str = Field(default='未指定', max_length=80)
    category: str = Field(default='未分类', max_length=100)
    author: str = Field(default='', max_length=200)
    published_at: str | None = None
    statistics: dict = Field(default_factory=dict)


class DeletionRequest(BaseModel):
    reason: str = Field(default='', max_length=3000)


def checked_title(db, title, organization_id):
    title = title.strip()
    if not title or len(title) > 300:
        raise HTTPException(422, '请填写 1–300 字的作品标题')
    if db.scalar(select(ContentItem.id).where(ContentItem.organization_id == organization_id, func.trim(ContentItem.title) == title).limit(1)):
        raise HTTPException(409, '作品标题已存在，请更换标题后保存。')
    return title


def add_content(db, item):
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        if 'CONTENT_TITLE_EXISTS' in str(error.orig):
            raise HTTPException(409, '作品标题已存在，请更换标题后保存。') from error
        raise


@router.get('/contents')
def contents(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(ContentItem).where(ContentItem.organization_id == user.organization_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {'items': [serialize(x) for x in db.scalars(query.order_by(ContentItem.created_at.desc()).offset((page-1)*page_size).limit(page_size))], 'total': total}


@router.post('/contents')
def create_content(body: ContentBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.account_id:
        owned(db, CreatorAccount, body.account_id, user)
    item = ContentItem(organization_id=user.organization_id, title=checked_title(db, body.title, user.organization_id), text=body.text, kind=body.kind, account_id=body.account_id, data=body.model_dump(exclude={'title', 'text', 'kind', 'account_id'}))
    add_content(db, item)
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action='CONTENT_CREATED', target_id=item.id))
    db.commit()
    return serialize(item)


@router.get('/contents/{identifier}')
def get_content(identifier: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db, ContentItem, identifier, user)
    result = serialize(item)
    result['assets'] = [serialize(x) for x in db.scalars(select(ContentAsset).where(ContentAsset.content_id == item.id, ContentAsset.organization_id == user.organization_id).order_by(ContentAsset.created_at))]
    return result


@router.post('/assets/upload')
def upload(files: list[UploadFile] = File(...), title: str = Form(...), text: str = Form(''), platform: str = Form('未指定'), category: str = Form('未分类'), account_id: str | None = Form(None), author: str = Form(''), published_at: str = Form(''), statistics: str = Form('{}'), user: User = Depends(current_user), db: Session = Depends(get_db)):
    import json
    if not title.strip() or len(title) > 300 or len(text) > 200000 or not 1 <= len(files) <= 12:
        raise HTTPException(422, '请填写标题，文本不超过 20 万字符，一次上传 1–12 个文件')
    if account_id:
        owned(db, CreatorAccount, account_id, user)
    title = checked_title(db, title, user.organization_id)
    try:
        stats = json.loads(statistics)
        if not isinstance(stats, dict):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, '统计数据必须为 JSON 对象')
    limit = int(os.getenv('MAX_UPLOAD_MB', '100')) * 1024 * 1024
    folder = UPLOAD_DIR / user.organization_id
    folder.mkdir(parents=True, exist_ok=True)
    created_paths = []
    total = 0
    item = ContentItem(organization_id=user.organization_id, title=title.strip(), text=text, kind='text', account_id=account_id or None, data={'platform': platform, 'category': category, 'author': author, 'published_at': published_at, 'statistics': stats, 'analysis_status': '本地基础分析'})
    add_content(db, item)
    metadata_list = []
    try:
        for position, file in enumerate(files):
            original = (file.filename or 'file').replace('\\', '/').split('/')[-1][:250]
            suffix = Path(original).suffix.lower()
            if suffix not in {'.mp4', '.mov', '.jpg', '.jpeg', '.png', '.webp', '.txt', '.md', '.srt', '.vtt'}:
                raise HTTPException(422, '文件扩展名不受支持')
            destination = folder / (str(uuid4()) + suffix)
            created_paths.append(destination)
            size = 0
            with destination.open('wb') as output:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    total += len(chunk)
                    if total > limit:
                        raise HTTPException(413, f'本次上传总大小不得超过 {limit // 1024 // 1024} MB')
                    output.write(chunk)
            if not size:
                raise HTTPException(422, '不能上传空文件')
            info = parse_media(destination, suffix, int(os.getenv('MAX_VIDEO_SECONDS', '600')))
            metadata_list.append(info)
            mime = {'.md': 'text/markdown', '.srt': 'text/plain', '.vtt': 'text/vtt', '.mov': 'video/quicktime'}.get(suffix) or mimetypes.guess_type(original)[0] or 'application/octet-stream'
            asset = ContentAsset(organization_id=user.organization_id, content_id=item.id, path=str(destination.resolve()), original_name=original, mime=mime, size=size, data={'position': position, 'metadata': info, 'role': 'original'})
            db.add(asset)
            db.flush()
            if info['kind'] in {'text', 'subtitle'}:
                item.text += ('\n\n' if item.text else '') + info['text']
            elif info['kind'] == 'image' and item.kind != 'video':
                item.kind = 'album' if len([x for x in metadata_list if x['kind'] == 'image']) > 1 else 'image'
            elif info['kind'] == 'video':
                item.kind = 'video'
                scenes, frames, warning = video_frames(destination, info)
                keyframes = []
                for frame in frames:
                    thumb_path = Path(frame['path'])
                    created_paths.append(thumb_path)
                    thumbnail = ContentAsset(organization_id=user.organization_id, content_id=item.id, path=str(thumb_path), original_name=f'关键帧 {frame["timecode"]}s.jpg', mime='image/jpeg', size=thumb_path.stat().st_size, data={'role': 'keyframe', 'timecode': frame['timecode']})
                    db.add(thumbnail)
                    db.flush()
                    keyframes.append({'asset_id': thumbnail.id, 'timecode': frame['timecode']})
                asset.data = {**asset.data, 'scenes': scenes, 'keyframes': keyframes, 'warning': warning}
                item.data = {**item.data, 'metadata': info, 'scenes': scenes, 'keyframes': keyframes}
        item.data = {**item.data, 'media': metadata_list, 'characters': len(item.text), 'transcription': '用户提供字幕/文稿' if item.text else '未转录'}
        db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action='ASSETS_UPLOADED', target_id=item.id, data={'file_count': len(files), 'bytes': total}))
        db.commit()
        return get_content(item.id, user, db)
    except Exception:
        db.rollback()
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise


@router.get('/assets/{identifier}')
def asset(identifier: str, download: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = owned(db, ContentAsset, identifier, user)
    path = Path(record.path).resolve()
    if not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
        raise HTTPException(404, '素材文件不存在')
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', serialize(record)['original_name'])
    response = FileResponse(path, media_type=record.mime, filename=filename, content_disposition_type='attachment' if download else 'inline')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@router.get('/dashboard')
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    def rows(model):
        return list(db.scalars(select(model).where(model.organization_id == user.organization_id).order_by(model.created_at.desc())))
    analyses, accounts, works = rows(ContentAnalysis), rows(CreatorAccount), rows(ContentItem)
    orders = list(db.scalars(select(Order).where(or_(Order.organization_id == user.organization_id, Order.data['customer_organization_id'].as_string() == user.organization_id)).order_by(Order.created_at.desc())))
    orders = [order for order in orders if not is_demo_record(order) and customer_for(db, order) and (user.role == 'OWNER_ADMIN' and order.organization_id == user.organization_id or customer_for(db, order).id == user.id)]
    running_experiments = db.scalar(select(func.count()).select_from(Experiment).where(Experiment.organization_id == user.organization_id, Experiment.status.in_(['PLANNED', 'RUNNING'])))
    titles = {item.id: item.title for item in works}
    return {'counts': {'contents': len(works), 'analyses': len(analyses), 'orders': len(orders), 'accounts': len(accounts), 'experiments': running_experiments}, 'analyses': [{**serialize(x), 'content_title': titles.get(x.content_id)} for x in analyses[:6]], 'orders': [serialize(x) for x in orders[:5]], 'accounts': [serialize(x) for x in accounts], 'contents': [serialize(x) for x in works[:6]], 'source': '当前工作区真实录入数据；服务订单按注册客户关联展示'}


@router.get('/settings/export')
def export(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .db import Base
    result = {}
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if model.__name__ in {'Session', 'User'} or not hasattr(model, 'organization_id'):
            continue
        result[model.__tablename__] = [serialize(x) for x in db.scalars(select(model).where(model.organization_id == user.organization_id))]
    return {'workspace_id': user.organization_id, 'profile': serialize(user), 'records': result}


@router.post('/settings/deletion-request')
def request_deletion(body: DeletionRequest | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    admin = db.scalar(select(User).where(User.role == 'OWNER_ADMIN').order_by(User.created_at))
    if not admin:
        raise HTTPException(503, '尚未初始化管理员')
    prior = db.scalar(select(Approval).where(Approval.organization_id == admin.organization_id, Approval.kind == 'DELETE_USER_DATA', Approval.target_id == user.id, Approval.status == 'PENDING'))
    if prior:
        return {'id': prior.id, 'status': prior.status, 'message': '已有待审批的删除请求'}
    reason = body.reason.strip() if body else ''
    approval = Approval(organization_id=admin.organization_id, kind='DELETE_USER_DATA', target_id=user.id, reason=reason or '用户请求删除工作区数据，需管理员审查并离线执行', data={'requester_id': user.id, 'requester_org': user.organization_id, 'execution': 'MANUAL_ONLY'})
    db.add(approval)
    db.flush()
    db.add(AuditLog(organization_id=admin.organization_id, actor_id=user.id, action='deletion.requested', target_id=approval.id))
    db.commit()
    return {'id': approval.id, 'status': approval.status, 'message': '请求已提交，审批不会自动执行不可逆删除'}
