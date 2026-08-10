import datetime
import html
import json
import re
import sys
import urllib.request

BASE = "https://sapphireyoung.com"
TITLES_URL = BASE + "/api/json_titles"
TIMEOUT = 30

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def http_get(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _unescape(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value).strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _first(pattern: str, text: str, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def scene_by_name(name: str) -> list[dict]:
    # 与网站前端 autocomplete 一致:拉全量标题列表,本地做大小写不敏感的包含匹配
    if not name:
        return []
    text = http_get(TITLES_URL)
    try:
        titles = json.loads(text)  # [["Title","slug"], ...]
    except json.JSONDecodeError:
        print("[SapphireYoung] failed to parse json_titles", file=sys.stderr)
        return []

    needle = name.lower()
    results = []
    for title, slug in titles:
        if needle in title.lower():
            results.append(
                {
                    "url": f"{BASE}/video/{slug}/",
                    "title": title,
                }
            )
    return results


def scene_by_query_fragment(args: dict) -> dict:
    url = args.get("url") or (args.get("urls") or [None])[0]
    if not url:
        title = args.get("title")
        return {"title": title} if title else {}
    return scrape_scene(url)


def scrape_scene(url: str) -> dict:
    text = http_get(url)

    video_text = _first(
        r'<div class="video-text">(.*?)<!--Video player END-->', text, re.S
    )
    if video_text is None:
        return {"url": url}

    title = _first(r'<h1[^>]*class="video-title"[^>]*>(.*?)</h1>', video_text, re.S)

    poster = _first(r'<video[^>]*poster="([^"]+)"', text)
    if poster:
        poster = poster if poster.startswith("http") else "https:" + poster

    date_raw = _first(r"Added on:\s*(.*?)\s*<", video_text)
    date = None
    if date_raw:
        date_norm = re.sub(r"\s+", " ", date_raw).strip()
        try:
            date = datetime.datetime.strptime(date_norm, "%b %d, %Y").strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass

    details = _first(
        r'<div[^>]*style="[^"]*color:\s*white[^"]*"[^>]*>(.*?)</div>', video_text, re.S
    )

    tags = []
    tags_block = _first(
        r'<div[^>]*class="[^"]*model-tags[^"]*"[^>]*>(.*?)</div>', video_text, re.S
    )
    if tags_block:
        for m in re.finditer(r"<a[^>]*>(.*?)</a>", tags_block, re.S):
            tag = _unescape(m.group(1))
            if tag:
                tags.append({"name": tag})

    result = {"url": url}
    if title:
        result["title"] = title
    if poster:
        result["image"] = poster
    if date:
        result["date"] = date
    if details and details.strip():
        result["details"] = _unescape(details)
    result["studio"] = {"name": "Sapphire Young"}
    result["performers"] = [{"name": "Sapphire Young"}]
    if tags:
        result["tags"] = tags
    return result


if __name__ == "__main__":
    operation = sys.argv[1] if len(sys.argv) > 1 else ""
    args = {}
    if not sys.stdin.isatty():
        try:
            args = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(69)

    result = None
    if operation == "scene-by-name":
        result = scene_by_name(args.get("name", ""))
    elif operation == "scene-by-query-fragment":
        result = scene_by_query_fragment(args)

    print(json.dumps(result))
