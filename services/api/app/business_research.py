"""Local, explainable research: no scraping, synthetic metrics, or paid calls."""
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import median
from urllib.parse import urlsplit, urlunsplit
from xml.etree.ElementTree import ParseError

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import current_user, owned
from .db import get_db
from .models import (BenchmarkItem, ContentAnalysis, ContentItem, ContentVersion,
                     CreatorAccount, Experiment, MetricSnapshot, Recommendation,
                     User, serialize, stamp)
from .business_common import audit, extras, fail, listing, required, rows, save, update_data

router = APIRouter(tags=["research"])
METRICS = ("views", "likes", "comments", "shares", "favorites", "impressions", "followers")
ALIASES = {"标题": "title", "作品标题": "title", "播放量": "views", "阅读量": "views", "点赞": "likes", "点赞数": "likes", "评论": "comments", "转发": "shares", "收藏": "favorites", "曝光量": "impressions", "粉丝数": "followers", "观测日期": "observed_at", "日期": "observed_at", "分类": "category", "平台": "platform", "作者": "author", "链接": "url"}


def account_details(body):
    details = extras(body, ["category", "persona", "audience", "style", "description"])
    if "profile_url" in body or "url" in body:
        url = canonical_url(body.get("profile_url", body.get("url")))
        details.update(profile_url=url, url=url)
    return details


@router.get("/accounts")
def accounts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return listing(rows(db, CreatorAccount, user))


@router.post("/accounts")
def create_account(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    account = CreatorAccount(organization_id=user.organization_id, name=required(body, "name", 200), platform=required(body, "platform", 80), data=account_details(body))
    return save(db, account, user, "account.created")


@router.get("/accounts/{account_id}")
def get_account(account_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return serialize(owned(db, CreatorAccount, account_id, user))


@router.patch("/accounts/{account_id}")
def edit_account(account_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    account = owned(db, CreatorAccount, account_id, user)
    for key in ["name", "platform"]:
        if key in body:
            setattr(account, key, required(body, key, 200))
    update_data(account, account_details(body))
    return save(db, account, user, "account.updated")


def canonical_url(value):
    if not value:
        return ""
    if not isinstance(value, str) or len(value) > 2000:
        fail("来源链接格式无效")
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        fail("来源链接格式无效")
    if parts.scheme not in {"https", "http"} or not parts.netloc or parts.username or parts.password:
        fail("来源链接只支持不含凭证的 http/https URL；服务不会抓取该链接")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def normalized_benchmark(body, demo=False):
    demo = demo or str(body.get("is_demo", "")).lower() in {"true", "1", "yes"}
    values = {"title": required(body, "title", 500), "platform": str(body.get("platform") or "未指定")[:80], "url": canonical_url(body.get("url")), "author": str(body.get("author") or "")[:200], "category": str(body.get("category") or "未分类")[:100], "is_demo": bool(demo)}
    extra = extras(body, ["tags", "audience", "structure", "text", "source", "collected_at", "published_at", "notes"])
    metric_source = body.get("metrics") if isinstance(body.get("metrics"), dict) else body
    validated, errors = validate_metric_rows([{"title": values["title"], **{key: metric_source.get(key) for key in METRICS}}], {})
    if errors:
        fail(errors[0]["message"])
    extra["metrics"] = validated[0]["metrics"]
    extra["source"] = "DEMO 示例，不是真实热门作品" if demo else str(extra.get("source") or "用户手工提供，未经平台验证")
    extra["collected_at"] = str(extra.get("collected_at") or stamp())
    extra["favorite"] = False
    values["data"] = extra
    return values


def insert_benchmark(db, user, values):
    for existing in rows(db, BenchmarkItem, user):
        same = (values["url"] and canonical_url(existing.url) == values["url"]) or (not values["url"] and not existing.url and (existing.title, existing.platform, existing.author) == (values["title"], values["platform"], values["author"]))
        if same and existing.is_demo == values["is_demo"]:
            return existing, False
    item = BenchmarkItem(organization_id=user.organization_id, **values)
    db.add(item); db.flush()
    audit(db, user, "library.imported" if values["is_demo"] else "library.created", item.id)
    return item, True


@router.get("/library")
def library(q: str = "", platform: str = "", category: str = "", favorite: bool = False, include_demo: bool = True, offset: int = 0, limit: int = 100, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if offset < 0 or not 1 <= limit <= 500:
        fail("分页参数无效")
    items = rows(db, BenchmarkItem, user)
    items = [x for x in items if (not q or q.casefold() in json.dumps(serialize(x), ensure_ascii=False).casefold()) and (not platform or x.platform == platform) and (not category or x.category == category) and (include_demo or not x.is_demo) and (not favorite or (x.data or {}).get("favorite"))]
    return {"items": [serialize(x) for x in items[offset:offset + limit]], "total": len(items)}


@router.post("/library")
def add_library(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    item, created = insert_benchmark(db, user, normalized_benchmark(body))
    db.commit()
    return {**serialize(item), "duplicate": not created}


async def read_table(file):
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        fail("导入文件不能超过 5 MB", 413)
    name = (file.filename or "import.csv").replace("\\", "/").split("/")[-1]
    suffix = name.rsplit(".", 1)[-1].lower()
    try:
        if suffix == "csv":
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("gb18030")
            reader = csv.DictReader(io.StringIO(text))
            headers = reader.fieldnames or []
            table = list(reader)
        elif suffix == "xlsx":
            from openpyxl import load_workbook
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if sum(entry.file_size for entry in archive.infolist()) > 50 * 1024 * 1024:
                    fail("Excel 解压后体积超过限制", 413)
            book = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            sheet = book.active
            if sheet.max_row > 5001 or sheet.max_column > 100:
                book.close(); fail("导入最多支持 5000 行、100 列")
            iterator = sheet.iter_rows(values_only=True)
            headers = [str(x or "").strip() for x in next(iterator, [])]
            table = [dict(zip(headers, line)) for line in iterator]
            book.close()
        else:
            fail("仅支持 CSV 或 XLSX 文件")
    except (ValueError, UnicodeError, csv.Error, OSError, KeyError, zipfile.BadZipFile, ParseError):
        fail("无法解析导入文件，请检查编码与格式")
    if not headers or len(headers) > 100 or len(set(headers)) != len(headers):
        fail("表头不能为空或重复，且最多 100 列")
    if len(table) > 5000:
        fail("导入最多支持 5000 行")
    if not table:
        fail("文件只有表头或为空，请至少提供一行数据")
    return table, headers, name, hashlib.sha256(raw).hexdigest()


@router.post("/library/import")
async def import_library(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    table, _, name, digest = await read_table(file)
    values = []
    for index, row in enumerate(table, 2):
        mapped = {ALIASES.get(key, key): value for key, value in row.items()}
        mapped["source"] = f"用户授权导入：{name} 第 {index} 行"
        values.append(normalized_benchmark(mapped))
    imported, duplicates = 0, 0
    for value in values:
        value["data"]["file_sha256"] = digest
        _, created = insert_benchmark(db, user, value)
        imported += int(created); duplicates += int(not created)
    db.commit()
    return {"imported": imported, "duplicates": duplicates, "source": name}


@router.post("/library/demo")
def demo_library(db: Session = Depends(get_db), user: User = Depends(current_user)):
    demos = [
        ("DEMO · 用三分钟解释 Python 函数", "编程", "函数 入门 案例 对比", 100),
        ("DEMO · Python 自动化脚本入门", "编程", "自动化 教学 问题 方案", 200),
        ("DEMO · 用调试器理解 Python 错误", "编程", "调试 错误 教学", 300),
        ("DEMO · 如何评估 AI 工具的可靠性", "AI 工具", "AI 工具 验证 边界", None),
        ("DEMO · 科普内容如何标明证据来源", "知识科普", "证据 来源 事实 不确定性", None),
    ]
    imported = 0
    for title, category, text, views in demos:
        _, created = insert_benchmark(db, user, normalized_benchmark({"title": title, "platform": "DEMO", "author": "DEMO 教学账号", "category": category, "text": text, "views": views, "collected_at": "2026-11-01T00:00:00Z"}, demo=True))
        imported += int(created)
    db.commit()
    return {"imported": imported, "is_demo": True, "notice": "显式导入的虚构示例，不作为真实热门作品；推荐默认排除。"}


@router.get("/library/{item_id}")
def get_library(item_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return serialize(owned(db, BenchmarkItem, item_id, user))


@router.delete("/library/{item_id}")
def delete_library(item_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = owned(db, BenchmarkItem, item_id, user)
    for recommendation in db.scalars(select(Recommendation).where(Recommendation.organization_id == user.organization_id, Recommendation.benchmark_id == item.id)):
        db.delete(recommendation)
    audit(db, user, "library.deleted", item.id)
    db.delete(item); db.commit()
    return {"deleted": True}


@router.post("/library/{item_id}/favorite")
def favorite_library(item_id: str, body: dict = Body(default={}), db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = owned(db, BenchmarkItem, item_id, user)
    update_data(item, {"favorite": bool(body.get("favorite", not (item.data or {}).get("favorite", False)))})
    return save(db, item, user, "library.favorite")


def tokens(text):
    text = str(text).casefold()
    result = re.findall(r"[a-z0-9_]+", text)
    for segment in re.findall(r"[\u4e00-\u9fff]+", text):
        result.extend(segment)
        result.extend(segment[i:i + 2] for i in range(len(segment) - 1))
    return result


def rank_benchmarks(query, items, limit=5):
    documents = [tokens(" ".join(str(item.get(key) or "") for key in ["title", "category", "text", "tags", "audience", "structure"])) for item in items]
    frequencies = Counter(token for document in documents for token in set(document))
    def vector(document):
        counts = Counter(document)
        return {token: (1 + math.log(count)) * (1 + math.log((1 + len(items)) / (1 + frequencies[token]))) for token, count in counts.items()}
    query_vector = vector(tokens(query))
    query_norm = math.sqrt(sum(value ** 2 for value in query_vector.values()))
    authors = defaultdict(list)
    for item in sorted(items, key=lambda x: str(x.get("collected_at", "")), reverse=True):
        views = item.get("metrics", {}).get("views", item.get("views"))
        group = (item.get("platform"), item.get("author"))
        if item.get("author") and isinstance(views, (int, float)) and math.isfinite(views) and views >= 0 and len(authors[group]) < 30:
            authors[group].append(views)
    result = []
    for item, document in zip(items, documents):
        features = vector(document)
        norm = math.sqrt(sum(value ** 2 for value in features.values()))
        similarity = sum(value * features.get(token, 0) for token, value in query_vector.items()) / (query_norm * norm) if norm and query_norm else 0
        metrics = item.get("metrics") or {key: item.get(key) for key in METRICS}
        samples = authors[(item.get("platform"), item.get("author"))]
        baseline = median(samples) if len(samples) >= 3 else None
        views = metrics.get("views")
        relative = round(views / baseline, 4) if baseline and isinstance(views, (int, float)) else None
        common = sorted(set(query_vector) & set(features), key=lambda token: (-query_vector[token] * features[token], token))[:6]
        reasons = ["主题特征重合：" + "、".join(common)] if common else ["与当前查询未发现明显文本重合，请人工核对类别与受众"]
        if relative is not None:
            reasons.append(f"相对播放表现 {relative:.2f} 倍；同平台同作者可用最近样本 {len(samples)} 条，中位数 {baseline:g}；这不是因果或爆款保证")
        else:
            reasons.append("相对表现不可计算：至少需要同平台同作者 3 条有播放量的样本，且中位数大于 0")
        completeness = sum(metrics.get(key) is not None for key in METRICS) / len(METRICS)
        result.append({**item, "similarity": round(similarity, 4), "score": round(similarity, 4), "relative_performance": relative, "author_median_views": baseline, "author_sample_size": len(samples), "reasons": reasons, "data_completeness": round(completeness, 4), "borrow": "借鉴主题组织与解释结构，并核对证据", "avoid_copying": "保留自己的案例与表达；未经许可不要复制原作素材"})
    return sorted(result, key=lambda item: (-item["similarity"], str(item.get("id"))))[:limit]


@router.post("/recommendations/search")
def recommendations(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = str(body.get("query") or "").strip()
    content_id = body.get("content_id")
    if content_id:
        content = owned(db, ContentItem, content_id, user)
        query = query or f"{content.title} {content.text}"
    if not query or len(query) > 20000:
        fail("请输入主题或选择作品（最多 20000 字符）")
    limit = body.get("limit", 5)
    if not isinstance(limit, int) or not 3 <= limit <= 10:
        fail("推荐数量必须为 3 到 10")
    items = [serialize(item) for item in rows(db, BenchmarkItem, user) if body.get("include_demo") or not item.is_demo]
    ranked = rank_benchmarks(query, items, limit)
    for item in ranked:
        db.add(Recommendation(organization_id=user.organization_id, content_id=content_id, benchmark_id=item["id"], score=item["similarity"], data={"query": query, "reasons": item["reasons"], "relative_performance": item["relative_performance"], "algorithm": "local-tfidf-zh-v1"}))
    db.commit()
    return {"items": ranked, "total": len(ranked), "source": "local-tfidf-zh-v1", "limitations": ["基于当前授权入库文本的词与汉字二元特征相似度，不等同于深层语义理解；表现指标独立展示。", "不抓取外部页面；样本少于请求数量时仅返回现有样本。"]}


def parse_mapping(mapping):
    if not mapping:
        return {}
    try:
        value = json.loads(mapping)
    except (ValueError, TypeError):
        fail("mapping 必须为 JSON 对象")
    if not isinstance(value, dict) or any(not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()):
        fail("mapping 必须为字段名到列名的映射")
    return value


def validate_metric_rows(table, mapping):
    validated, errors = [], []
    canonical = set(METRICS) | {"title", "content_id", "observed_at", "category", "platform", "published_url", "is_demo"}
    for index, raw in enumerate(table, 2):
        row = {ALIASES.get(str(key).strip(), str(key).strip()): value for key, value in raw.items() if key is not None}
        for key, value in mapping.items():
            if key in canonical:
                row[key] = raw.get(value)
            elif value in canonical:
                row[value] = raw.get(key)
        title, content_id = str(row.get("title") or "").strip(), str(row.get("content_id") or "").strip()
        problems = []
        if not title and not content_id:
            problems.append("作品标题或 content_id 必填")
        metrics = {}
        for key in METRICS:
            value = row.get(key)
            if value is None or str(value).strip().lower() in {"", "null", "none", "n/a", "na", "-"}:
                metrics[key] = None
            else:
                try:
                    number = float(str(value).replace(",", ""))
                    if not math.isfinite(number) or number < 0 or number != int(number) or number > 10 ** 15:
                        raise ValueError()
                    metrics[key] = int(number)
                except (TypeError, ValueError, OverflowError):
                    metrics[key] = None
                    problems.append(f"{key} 必须为非负整数或空值")
        observed = row.get("observed_at")
        if isinstance(observed, (datetime, date)):
            observed = observed.isoformat()
        observed = str(observed or "").strip()
        if observed:
            try:
                datetime.fromisoformat(observed.replace("Z", "+00:00"))
            except ValueError:
                problems.append("observed_at 必须为 ISO 日期或时间，例如 2026-11-01")
        if problems:
            errors.append({"row": index, "message": "；".join(problems)})
        validated.append({"row": index, "title": title, "content_id": content_id or None, "observed_at": observed, "metrics": metrics, "category": str(row.get("category") or "未分类"), "platform": str(row.get("platform") or "未指定"), "published_url": str(row.get("published_url") or ""), "is_demo": str(row.get("is_demo", "")).lower() in {"true", "1", "yes"}})
    return validated, errors


async def metric_input(file, mapping, account_id, db, user):
    if account_id:
        owned(db, CreatorAccount, account_id, user)
    table, headers, name, digest = await read_table(file)
    mapping_dict = parse_mapping(mapping)
    parsed, errors = validate_metric_rows(table, mapping_dict)
    for row in parsed:
        if row["content_id"]:
            content = owned(db, ContentItem, row["content_id"], user)
            if account_id and content.account_id and content.account_id != account_id:
                fail("所选作品不属于当前导入账号")
    return parsed, errors, headers, name, digest


@router.post("/metrics/preview")
async def preview_metrics(file: UploadFile = File(...), mapping: str = Form(""), account_id: str = Form(""), db: Session = Depends(get_db), user: User = Depends(current_user)):
    parsed, errors, headers, name, digest = await metric_input(file, mapping, account_id, db, user)
    return {"items": parsed[:100], "total": len(parsed), "errors": errors, "valid": not errors, "columns": headers, "source": name, "file_sha256": digest, "mapping_help": "JSON 格式：{\"views\":\"播放量列名\"}；空指标保留 null"}


@router.post("/metrics/import")
async def import_metrics(file: UploadFile = File(...), mapping: str = Form(""), account_id: str = Form(""), db: Session = Depends(get_db), user: User = Depends(current_user)):
    parsed, errors, _, name, digest = await metric_input(file, mapping, account_id, db, user)
    if errors:
        fail({"message": "导入校验失败，未写入任何数据", "errors": errors})
    imported, duplicates, ids = 0, 0, []
    for row in parsed:
        identity = {key: row[key] for key in ["title", "content_id", "observed_at", "metrics", "is_demo"]}
        identity["account_id"] = account_id or None
        key = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        existing = db.scalar(select(MetricSnapshot).where(MetricSnapshot.organization_id == user.organization_id, MetricSnapshot.import_hash == key))
        if existing:
            duplicates += 1; continue
        if row["content_id"]:
            content = owned(db, ContentItem, row["content_id"], user)
        else:
            matches = db.scalars(select(ContentItem).where(ContentItem.organization_id == user.organization_id, ContentItem.title == row["title"], ContentItem.account_id == (account_id or None))).all()
            if len(matches) > 1:
                fail("同名作品不唯一，请用 content_id 指定要更新的作品")
            content = matches[0] if matches else ContentItem(organization_id=user.organization_id, account_id=account_id or None, title=row["title"], kind="metrics", text="", data={"category": row["category"], "platform": row["platform"], "is_demo": row["is_demo"]})
            db.add(content); db.flush()
        snapshot = MetricSnapshot(organization_id=user.organization_id, content_id=content.id, account_id=account_id or content.account_id or None, observed_at=row["observed_at"] or stamp(), source=name, import_hash=key, data={"metrics": row["metrics"], "file_sha256": digest, "source_row": row["row"], "original_filename": name, "observed_at_inferred": not bool(row["observed_at"]), "published_url": row["published_url"], "category": row["category"], "source_kind": "demo_fixture" if row["is_demo"] else "user_import", "is_demo": row["is_demo"]})
        db.add(snapshot); db.flush(); ids.append(snapshot.id); imported += 1
    audit(db, user, "metrics.imported", digest, {"imported": imported, "duplicates": duplicates, "filename": name})
    db.commit()
    return {"imported": imported, "duplicates": duplicates, "snapshot_ids": ids, "source": name, "errors": []}


def snapshot_view(snapshot, content, denominator):
    metrics = {key: (snapshot.data or {}).get("metrics", {}).get(key) for key in METRICS}
    numerator_values = [metrics[key] for key in ["likes", "comments", "shares", "favorites"]]
    denominator_value = metrics.get(denominator)
    rate = sum(numerator_values) / denominator_value if denominator_value and all(value is not None for value in numerator_values) else None
    return {"id": snapshot.id, "snapshot_id": snapshot.id, "content_id": snapshot.content_id, "account_id": snapshot.account_id, "title": content.title if content else "未知作品", "category": (snapshot.data or {}).get("category") or ((content.data or {}).get("category") if content else None) or "未分类", "observed_at": snapshot.observed_at, "source": snapshot.source, "is_demo": bool((snapshot.data or {}).get("is_demo")), **metrics, "engagement_rate": round(rate, 6) if rate is not None else None, "metrics": metrics}


@router.get("/analytics/overview")
def analytics(denominator: str = "views", account_id: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    if denominator not in {"views", "impressions", "followers"}:
        fail("互动率分母仅支持 views、impressions、followers")
    if account_id:
        owned(db, CreatorAccount, account_id, user)
    contents = {item.id: item for item in rows(db, ContentItem, user)}
    snapshots = [item for item in rows(db, MetricSnapshot, user) if not account_id or item.account_id == account_id]
    all_items = [snapshot_view(item, contents.get(item.content_id), denominator) for item in sorted(snapshots, key=lambda x: (x.observed_at, x.created_at, x.id))]
    latest = {}
    for item in all_items:
        latest[item["content_id"]] = item
    items = list(latest.values())
    categories = defaultdict(list)
    for item in items:
        categories[item["category"]].append(item)
    comparisons = []
    for category, group in sorted(categories.items()):
        values = [item["views"] for item in group if item["views"] is not None]
        comparisons.append({"category": category, "count": len(group), "views_sample_size": len(values), "median_views": median(values) if values else None, "total_views": sum(values) if values else None})
    return {"items": items, "total": len(items), "trends": all_items, "rankings": sorted(items, key=lambda x: (x["views"] is None, -(x["views"] or 0), x["content_id"])), "category_comparison": comparisons, "denominator": denominator, "engagement_formula": f"(likes + comments + shares + favorites) / {denominator}；任一必要项缺失或分母为 0 时结果为 null", "source": "用户导入的指标快照；排行使用每个作品最新快照", "date_range": {"from": all_items[0]["observed_at"] if all_items else None, "to": all_items[-1]["observed_at"] if all_items else None}, "limitations": ["快照可能是累计值，趋势不可直接解释为新增量。", "缺失指标不补零，样本不一致的类别不可直接推断优劣。", "缺少对照和一致观测窗口时，增长不能证明某条建议的因果效果。"]}


def experiment_data(body, db, user, existing=None):
    data = {**(existing or {}), **extras(body, ["hypothesis", "planned_changes", "planned_publish_at", "observation_window", "target_metric", "published_url", "notes", "outcome_content_id", "baseline_snapshot_id", "outcome_snapshot_id"])}
    if data.get("target_metric") and data["target_metric"] not in METRICS:
        fail("目标指标必须为支持的统计字段")
    if data.get("outcome_content_id"):
        owned(db, ContentItem, data["outcome_content_id"], user)
    for key in ["baseline_snapshot_id", "outcome_snapshot_id"]:
        if data.get(key):
            owned(db, MetricSnapshot, data[key], user)
    baseline = owned(db, MetricSnapshot, data["baseline_snapshot_id"], user) if data.get("baseline_snapshot_id") else None
    outcome = owned(db, MetricSnapshot, data["outcome_snapshot_id"], user) if data.get("outcome_snapshot_id") else None
    if outcome and data.get("outcome_content_id") and outcome.content_id != data["outcome_content_id"]:
        fail("结果快照不属于关联的后续作品")
    metric = data.get("target_metric", "views")
    before = (baseline.data or {}).get("metrics", {}).get(metric) if baseline else None
    after = (outcome.data or {}).get("metrics", {}).get(metric) if outcome else None
    data["result"] = {"metric": metric, "baseline": before, "outcome": after, "absolute_change": after - before if before is not None and after is not None else None, "relative_change": round((after - before) / before, 6) if before and after is not None else None, "evidence_status": "observed_difference" if before is not None and after is not None else "insufficient_data", "uncertainty": "单次前后对比不能证明因果；需核对流量来源、发布时间、内容差异和一致观测窗口。"}
    return data


@router.get("/experiments")
def experiments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return listing(rows(db, Experiment, user))


@router.post("/experiments")
def create_experiment(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    content_id, analysis_id = body.get("content_id"), body.get("analysis_id")
    content = owned(db, ContentItem, content_id, user) if content_id else None
    if analysis_id:
        analysis = owned(db, ContentAnalysis, analysis_id, user)
        if content_id and analysis.content_id != content_id:
            fail("分析与作品不匹配")
        content_id = analysis.content_id
        content = owned(db, ContentItem, content_id, user)
    data = experiment_data(body, db, user)
    if content:
        versions = list(db.scalars(select(ContentVersion).where(ContentVersion.organization_id == user.organization_id, ContentVersion.content_id == content.id).order_by(ContentVersion.version.desc())))
        data["content_snapshot"] = {"title": content.title, "text": content.text, "version": serialize(versions[0]) if versions else None, "captured_at": stamp()}
    experiment = Experiment(organization_id=user.organization_id, title=required(body, "title", 500), content_id=content_id, analysis_id=analysis_id, status="PLANNED", data=data)
    return save(db, experiment, user, "experiment.created")


@router.patch("/experiments/{experiment_id}")
def edit_experiment(experiment_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    experiment = owned(db, Experiment, experiment_id, user)
    if "status" in body:
        if body["status"] not in {"PLANNED", "RUNNING", "COMPLETED", "CANCELED"}:
            fail("无效实验状态")
        experiment.status = body["status"]
    if "title" in body:
        experiment.title = required(body, "title", 500)
    update_data(experiment, experiment_data(body, db, user, experiment.data))
    return save(db, experiment, user, "experiment.updated")
