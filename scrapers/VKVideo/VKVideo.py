from datetime import datetime
from urllib.request import build_opener, HTTPCookieProcessor, Request
from http.cookiejar import CookieJar
from urllib.parse import urlencode
import json
import re
import sys

# 上传者(作者)字段去向:
#  - False(默认):作者作为 Performer(个人使用时推荐)
#  - True(开源发布时改这里):作者作为 Studio
# 开源到社区仓库前,请把下面的值改成 True 并提交
AUTHOR_AS_STUDIO = False

TIMEOUT = 30

jar = CookieJar()
opener = build_opener(HTTPCookieProcessor(jar))
opener.addheaders = [
    (
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ),
    ("Accept", "*/*"),
    ("Accept-Language", "en-US,en;q=0.9,ru;q=0.8"),
]


def http_get(url: str) -> str:
    req = Request(url)
    with opener.open(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_post(url: str, data: dict) -> str:
    body = urlencode(data).encode()
    req = Request(url, data=body)
    req.add_header("Referer", url)
    req.add_header("X-Requested-With", "XMLHttpRequest")
    with opener.open(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_video_data(video_id: str) -> dict | None:
    # VK pages are SPAs, the metadata is loaded via an internal AJAX endpoint.
    # Getting the cookies from the main page first is required to pass the 418 check.
    http_get("https://vk.com/")
    try:
        text = http_post(
            "https://vk.com/al_video.php",
            {"act": "show", "video": video_id, "al": 1},
        )
    except Exception as exc:
        print(f"[VKVideo] failed to fetch {video_id}: {exc}", file=sys.stderr)
        return None
    try:
        payload = json.loads(text)["payload"]
    except (ValueError, KeyError):
        print(f"[VKVideo] unexpected response for {video_id}", file=sys.stderr)
        return None
    if payload[0] not in (0, "0"):
        print(f"[VKVideo] VK returned an error for {video_id}", file=sys.stderr)
        return None

    return payload[1][4] if len(payload) > 1 else {}


def to_scraped_scene(data: dict) -> dict | None:
    mv_data = data.get("mvData") or {}
    modal = data.get("videoModalInfoData") or {}

    title = mv_data.get("title")
    if not title:
        print("[VKVideo] no title found in VK response", file=sys.stderr)
        return None

    scene = {
        "title": title,
    }

    author = mv_data.get("authorNameGenitive")
    if author:
        if AUTHOR_AS_STUDIO:
            scene["studio"] = {"name": author}
        else:
            scene["performers"] = [{"name": author}]

    if ts := modal.get("date"):
        scene["date"] = datetime.fromtimestamp(ts).date().isoformat()

    # Use the player jpg (16:9, no black bars) rather than the info thumbnail (4:3 letterboxed)
    if thumb := data.get("player", {}).get("params", [{}])[0].get("jpg"):
        scene["image"] = thumb

    return scene


def scene_by_url(url: str) -> dict | None:
    # e.g. https://vkvideo.ru/video-68349831_167890341
    match = re.search(r"/(?:video|clip)(-?\d+_\d+)", url)
    if not match:
        print(f"[VKVideo] could not extract video ID from URL: {url}", file=sys.stderr)
        return None
    video_id = match.group(1)
    if not (data := fetch_video_data(video_id)):
        return None
    return to_scraped_scene(data)


if __name__ == "__main__":
    operation = sys.argv[1] if len(sys.argv) > 1 else ""
    args = {}
    if not sys.stdin.isatty():
        try:
            args = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(69)

    result = None
    if operation in ("scene-by-url", "scene-by-query-fragment"):
        result = scene_by_url(args.get("url", ""))

    print(json.dumps(result))
