"""Ground fact checks in provider-returned citations, never invented model URLs."""
from urllib.parse import urlsplit
import re

from .schemas_ai import FactCheck


def safe_source(source):
    if not isinstance(source, dict):
        return None
    citation = source.get('url_citation', source)
    if not isinstance(citation, dict):
        return None
    url = citation.get('url', '')
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password:
            return None
    except (ValueError, TypeError):
        return None
    return {'url': url, 'title': str(citation.get('title') or parsed.hostname)[:300]}


def grounded_checks(draft, sources):
    allowed = {source['url'] for source in sources}
    checks = []
    for check in draft.checks[:10]:
        if re.search(r'作者.{0,20}(真实性|资质)|账号资质|身份真实性', check.claim + check.finding):
            continue
        urls = [url for url in check.source_urls if url in allowed]
        result = check.model_copy(update={'source_urls': urls})
        if not urls:
            result = FactCheck(claim=check.claim, status='unverified', finding='未查询到足够的可追溯来源，暂不能确认此事实。',
                               recommendation='请重点检查文案涉及的日期、数字和事件关系，补充依据后再使用。', source_urls=[])
        checks.append(result)
    return checks
