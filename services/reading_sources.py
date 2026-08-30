"""权威英文来源的最小化适配层。

只返回标题、日期、URL 和有限事实摘要；网站不保存媒体全文。
"""

from html.parser import HTMLParser
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import requests


MAX_RESPONSE_BYTES = 700_000
MAX_FACT_CHARS = 6_000
TIMEOUT = 12

SOURCE_DEFINITIONS = (
    {
        'name': '新华社英文网',
        'listing': 'https://english.news.cn/',
        'hosts': {'english.news.cn', 'www.news.cn', 'news.cn'},
    },
    {
        'name': '中国政府网英文版',
        'listing': 'https://english.www.gov.cn/news/',
        'hosts': {'english.www.gov.cn', 'www.gov.cn'},
    },
    {
        'name': 'China Daily',
        'listing': 'https://global.chinadaily.com.cn/',
        'hosts': {'global.chinadaily.com.cn', 'www.chinadaily.com.cn', 'chinadaily.com.cn'},
    },
    {
        'name': 'CGTN',
        'listing': 'https://news.cgtn.com/',
        'hosts': {'news.cgtn.com', 'www.cgtn.com', 'cgtn.com'},
    },
)

TOPIC_TERMS = {
    '健康': ('health', 'medical', 'doctor', 'fitness', 'hospital', 'nutrition'),
    '教育': ('education', 'student', 'school', 'teacher', 'learning', 'university'),
    '文化': ('culture', 'museum', 'heritage', 'history', 'art', 'tradition'),
    '环境': ('environment', 'climate', 'wetland', 'biodiversity', 'ecology', 'green'),
    '社会': ('society', 'community', 'public service', 'employment', 'people', 'digital literacy'),
    '科技': ('technology', 'science', 'robot', 'artificial intelligence', 'research', 'space'),
}


class SourceFetchError(RuntimeError):
    pass


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.paragraphs = []
        self.title_parts = []
        self._href = None
        self._anchor_text = []
        self._in_title = False
        self._in_p = False
        self._p_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self._href = attrs.get('href')
            self._anchor_text = []
        elif tag == 'title':
            self._in_title = True
        elif tag == 'p':
            self._in_p = True
            self._p_text = []

    def handle_data(self, data):
        if self._href is not None:
            self._anchor_text.append(data)
        if self._in_title:
            self.title_parts.append(data)
        if self._in_p:
            self._p_text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self._href is not None:
            text = ' '.join(''.join(self._anchor_text).split())
            if text:
                self.links.append((self._href, text))
            self._href = None
            self._anchor_text = []
        elif tag == 'title':
            self._in_title = False
        elif tag == 'p' and self._in_p:
            text = ' '.join(''.join(self._p_text).split())
            if len(text) >= 45:
                self.paragraphs.append(text)
            self._in_p = False
            self._p_text = []


def _is_public_host(hostname):
    if not hostname or hostname.lower() in {'localhost'}:
        return False
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SourceFetchError('来源域名无法解析。') from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if any((address.is_private, address.is_loopback, address.is_link_local,
                address.is_multicast, address.is_reserved, address.is_unspecified)):
            return False
    return True


def _definition_for(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname:
        raise SourceFetchError('只允许 HTTPS 权威来源。')
    host = parsed.hostname.lower()
    for definition in SOURCE_DEFINITIONS:
        if host in definition['hosts']:
            if not _is_public_host(host):
                raise SourceFetchError('来源地址不得指向本机或内网。')
            return definition
    raise SourceFetchError('该域名不在文章来源白名单中。')


def secure_fetch(url):
    current = url
    for _ in range(4):
        definition = _definition_for(current)
        try:
            response = requests.get(
                current,
                headers={'User-Agent': 'CET-Reading-Curator/1.0 (+local learning tool)'},
                timeout=TIMEOUT,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise SourceFetchError('权威来源暂时无法访问。') from exc
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location')
            if not location:
                raise SourceFetchError('来源返回了无效跳转。')
            current = urljoin(current, location)
            continue
        if response.status_code != 200:
            raise SourceFetchError(f'来源返回 HTTP {response.status_code}。')
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            raise SourceFetchError('来源不是可处理的 HTML 文章。')
        chunks, total = [], 0
        for chunk in response.iter_content(16_384):
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise SourceFetchError('来源页面超出体积限制。')
            chunks.append(chunk)
        response.encoding = response.encoding or response.apparent_encoding or 'utf-8'
        return b''.join(chunks).decode(response.encoding, errors='replace'), current, definition
    raise SourceFetchError('来源跳转次数过多。')


def _parse_page(html):
    parser = _PageParser()
    parser.feed(html)
    return parser


def discover_candidates(topic, exclude_urls=None):
    terms = TOPIC_TERMS.get(topic, ())
    excluded = set(exclude_urls or ())
    candidates = []
    for definition in SOURCE_DEFINITIONS:
        try:
            html, final_url, _ = secure_fetch(definition['listing'])
        except SourceFetchError:
            continue
        parser = _parse_page(html)
        for href, text in parser.links:
            absolute = urljoin(final_url, href)
            if absolute in excluded:
                continue
            try:
                target_def = _definition_for(absolute)
            except SourceFetchError:
                continue
            lowered = text.lower()
            score = sum(1 for term in terms if term in lowered)
            if score:
                candidates.append({
                    'url': absolute, 'title': text, 'source_name': target_def['name'], 'score': score,
                })
    candidates.sort(key=lambda item: (-item['score'], item['source_name'], item['title']))
    return candidates[:24]


def fetch_fact_brief(candidate):
    html, final_url, definition = secure_fetch(candidate['url'])
    parser = _parse_page(html)
    title = ' '.join(''.join(parser.title_parts).split()) or candidate.get('title') or '未命名来源'
    paragraphs = parser.paragraphs[:14]
    if len(paragraphs) < 2:
        raise SourceFetchError('来源页面没有足够的可核验文字。')
    fact_text = '\n'.join(paragraphs)
    fact_text = fact_text[:MAX_FACT_CHARS]
    date_match = re.search(r'\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b', html)
    published = '-'.join(date_match.groups()) if date_match else ''
    return {
        'source_name': definition['name'],
        'source_url': final_url,
        'source_title': title[:300],
        'source_published_at': published,
        'fact_brief': fact_text,
    }
