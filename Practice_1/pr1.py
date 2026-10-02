#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поиск по архиву Common Crawl через CDX-индекс с опциональной загрузкой WARC."""

import argparse
import gzip
import json
import re
import sys
from io import BytesIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate
from warcio.archiveiterator import ArchiveIterator

# UTF-8 для Windows-консоли
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

CDX_BASE = "https://index.commoncrawl.org/"
DATA_BASE = "https://data.commoncrawl.org/"
COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"

HEADERS = {
    "User-Agent": "cc-search-homework/1.0 (student project)"
}

# Технические страницы, которые не нужны в результатах
SKIP_PARTS = ("robots.txt", "/sitemap", ".pdf", ".xml", ".rss")

ERRORS: list[dict] = []


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ---------- индексы ----------

def get_recent_indexes(n: int) -> list[str]:
    """n последних индексов Common Crawl."""
    try:
        resp = requests.get(COLLINFO_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        collections = resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Не удалось получить список индексов: {e}") from e
    if not collections:
        raise RuntimeError("Список индексов Common Crawl пуст")
    return [c["id"] for c in collections[:n]]


# ---------- CDX ----------

def cdx_query(index: str, domain: str, limit: int) -> list[dict]:
    """Записи CDX по домену (keywords фильтруются позже, локально)."""
    params = {
        "url": domain,
        "matchType": "domain",
        "output": "json",
        "limit": limit,
    }
    url = f"{CDX_BASE}{index}-index"

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
    except requests.RequestException as e:
        log(f"CDX-запрос к {index} для {domain} не удался: {e}")
        ERRORS.append({"stage": "cdx", "index": index,
                       "domain": domain, "error": str(e)})
        return []

    records = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def is_skipped(url: str) -> bool:
    low = url.lower()
    return any(part in low for part in SKIP_PARTS)


def url_matches_any(url: str, keywords: list[str]) -> bool:
    """Слабая проверка URL: хотя бы одно слово."""
    low = url.lower()
    return any(kw.lower() in low for kw in keywords)


def title_from_url(url: str) -> str:
    tail = url.rstrip("/").split("/")[-1] or url
    tail = re.sub(r"\.(html?|php|aspx?)$", "", tail, flags=re.I)
    return tail.replace("-", " ").replace("_", " ").strip() or url


# ---------- WARC ----------

def fetch_warc_record(filename: str, offset: int, length: int) -> bytes:
    url = DATA_BASE + filename
    headers = dict(HEADERS)
    headers["Range"] = f"bytes={offset}-{offset + length - 1}"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.content


def parse_warc_record(compressed_bytes: bytes):
    try:
        decompressed = gzip.decompress(compressed_bytes)
    except OSError:
        decompressed = compressed_bytes

    for record in ArchiveIterator(BytesIO(decompressed)):
        if record.rec_type == "response":
            content = record.content_stream().read()
            return content, record.http_headers
    return None, None


def extract_title_and_text(content: bytes, http_headers):
    charset = "utf-8"
    if http_headers:
        ct = http_headers.get("Content-Type", "") or ""
        m = re.search(r"charset=([\w-]+)", ct, re.I)
        if m:
            charset = m.group(1)

    try:
        html = content.decode(charset, errors="replace")
    except LookupError:
        html = content.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    return title, text


def make_snippet(text: str, keywords: list[str], radius: int = 120) -> str:
    low = text.lower()
    for kw in keywords:
        idx = low.find(kw.lower())
        if idx != -1:
            start = max(0, idx - radius)
            end = min(len(text), idx + len(kw) + radius)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet += "..."
            return snippet
    return text[:200] + ("..." if len(text) > 200 else "")


# ---------- CLI ----------

def parse_args():
    p = argparse.ArgumentParser(
        description="Поиск по архиву Common Crawl через CDX-индекс."
    )
    p.add_argument("keywords", nargs="+", help="Одно или несколько ключевых слов")
    p.add_argument("--domain", nargs="+", default=["pstu.ru"],
                   help="Домены (по умолчанию pstu.ru)")
    p.add_argument("--limit", type=int, default=10,
                   help="Максимум результатов на домен (по умолчанию 10)")
    p.add_argument("--show-text", action="store_true",
                   help="Загрузить WARC-фрагмент и показать текст страницы")
    p.add_argument("--crawls", type=int, default=3,
                   help="Сколько последних краулов использовать (по умолчанию 3)")
    p.add_argument("--index", help="Явно задать один индекс Common Crawl")
    p.add_argument("--style", default="grid",
                   choices=["plain", "grid", "pipe", "markdown"],
                   help="Стиль таблицы tabulate")
    return p.parse_args()


# ---------- main ----------

def main():
    args = parse_args()

    if args.limit < 1:
        log("--limit должен быть >= 1")
        sys.exit(2)

    # 1. Индексы
    try:
        indexes = [args.index] if args.index else get_recent_indexes(args.crawls)
    except Exception as e:
        log(f"Не удалось получить список индексов: {e}")
        sys.exit(1)

    log(f"Используется индексов: {len(indexes)} ({', '.join(indexes)})")
    log(f"Ключевые слова: {args.keywords}")
    log(f"Домены: {', '.join(args.domain)}")

    # 2. CDX
    seen_urls: set[str] = set()
    candidates: list[dict] = []

    total = len(indexes) * len(args.domain)
    step = 0
    for idx in indexes:
        for dom in args.domain:
            step += 1
            log(f"[{step}/{total}] {idx}: CDX-запрос по домену {dom}...")
            recs = cdx_query(idx, dom, args.limit * 20)
            log(f"[{step}/{total}] {idx}: получено {len(recs)} записей")
            for r in recs:
                url = r.get("url", "")
                if not url or url in seen_urls or is_skipped(url):
                    continue
                seen_urls.add(url)
                r["_domain"] = dom
                candidates.append(r)

    # 3. Предфильтр по URL.
    #    С --show-text он не нужен: точная фильтрация пойдёт по тексту.
    #    Без --show-text — это единственный доступный фильтр.
    if args.show_text:
        url_filtered = candidates
        log(f"Уникальных URL в CDX: {len(candidates)}. "
            f"Фильтр по keywords будет применён к тексту страниц.")
    else:
        url_filtered = [r for r in candidates
                        if url_matches_any(r["url"], args.keywords)]
        log(f"Уникальных URL в CDX: {len(candidates)}; "
            f"прошли предфильтр по URL: {len(url_filtered)}")

    if not url_filtered:
        print("Ничего не найдено. Без --show-text фильтр идёт только по URL. "
              "Для полнотекстового поиска добавьте --show-text.")
        return

    # 4. Обработка
    rows: list[list[str]] = []
    per_domain: dict[str, int] = {d: 0 for d in args.domain}

    if not args.show_text:
        # Лёгкий режим: только CDX-индекс
        for rec in url_filtered:
            dom = rec.get("_domain", "")
            if per_domain.get(dom, 0) >= args.limit:
                continue
            url = rec.get("url", "")
            ts = rec.get("timestamp", "")
            date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else ts
            rows.append([url, date_str, title_from_url(url), ""])
            per_domain[dom] = per_domain.get(dom, 0) + 1
    else:
        # Тяжёлый режим: WARC по каждому кандидату
        n = len(url_filtered)
        for i, rec in enumerate(url_filtered, 1):
            dom = rec.get("_domain", "")
            # Лимит проверяем ДО вывода прогресса — иначе в логе будут
            # строки для записей, которые уже не попадут в таблицу.
            if per_domain.get(dom, 0) >= args.limit:
                continue

            url = rec.get("url", "")
            ts = rec.get("timestamp", "")
            date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else ts

            filename = rec.get("filename")
            offset = rec.get("offset")
            length = rec.get("length")
            if not filename or offset is None or length is None:
                continue

            try:
                offset, length = int(offset), int(length)
                log(f"[{i}/{n}] WARC: {url}")
                compressed = fetch_warc_record(filename, offset, length)
                content, http_headers = parse_warc_record(compressed)
                if content is None:
                    continue

                title, text = extract_title_and_text(content, http_headers)
                if not title:
                    title = title_from_url(url)

                # Точная фильтрация: ВСЕ ключевые слова должны быть в тексте
                low = text.lower()
                if not all(kw.lower() in low for kw in args.keywords):
                    continue

                snippet = make_snippet(text, args.keywords)
                rows.append([url, date_str, title, snippet])
                per_domain[dom] = per_domain.get(dom, 0) + 1
            except Exception as e:
                log(f"Ошибка обработки {url}: {e}")
                ERRORS.append({"stage": "warc", "url": url, "error": str(e)})
                continue

    # 5. Вывод
    if not rows:
        print("Ничего не найдено.")
    else:
        headers = ["URL", "Дата", "Заголовок", "Фрагмент"]
        print(tabulate(rows, headers=headers, tablefmt=args.style))
        log(f"Показано результатов: {len(rows)}")

    # 6. Журнал ошибок (с накоплением между запусками)
    if ERRORS:
        prev: list[dict] = []
        path = Path("errors.json")
        if path.exists():
            try:
                prev = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                prev = []
        path.write_text(
            json.dumps(prev + ERRORS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log(f"Записано {len(ERRORS)} ошибок в errors.json")


if __name__ == "__main__":
    main()