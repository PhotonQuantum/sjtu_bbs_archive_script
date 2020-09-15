import asyncio
from typing import List, Optional

from pysjtu import Session
from itertools import count
import re
from uuid import uuid4
from httpx import AsyncClient, HTTPError, RedirectLoop
import os
import sys

username = sys.argv[0]
password = sys.argv[1]
session = Session(username, password)
image_re = re.compile("\\bhttps?:[^)\'\'\",]+\\.(?:jpg|jpeg|gif|png)")
video_re = re.compile("\\b/uploads[^)\'\'\",]+\\.(?:mp4)")
css_re = re.compile("\\/stylesheets?.*.css")
js_re = re.compile("\\/theme-javascripts?.*.js")
topic = int(sys.argv[2])
output = sys.argv[3]

find_resources = lambda p, x: re.findall(p, x)
resources_map = {}
client = AsyncClient()


def fetch_page(topic: int, page: int) -> Optional[str]:
    while True:
        try:
            r = session.get(f"https://dev.bbs.sjtu.edu.cn/t/topic/{topic}",
                            params={"_escaped_fragment_": True, "page": page})
            break
        except RedirectLoop:
            pass
        except HTTPError as e:
            if e.response.status_code == 404:
                return
    return r.text


async def download(src: str, dest: str):
    if not src.startswith("http"):
        src = f"https://dev.bbs.sjtu.edu.cn{src}"
    if src.endswith("mp4"):
        data = session.get(src).content
    else:
        data = (await client.get(src)).content
    with open(dest, mode="wb") as f:
        f.write(data)


async def main():
    for page in count(1):
        print(f"Downloading page {page}.")
        src = fetch_page(topic, page)
        if not src:
            break
        videos: List[str] = find_resources(video_re, src)
        resources: List[str] = find_resources(image_re, src) + find_resources(js_re, src) + find_resources(css_re,
                                                                                                           src) + videos
        for resource in resources:
            if resource not in resources_map:
                resources_map[resource] = f"{uuid4().hex}.{resource.split('.')[-1]}"
        for old, new in resources_map.items():
            src = src.replace(old, f"resources/{new}")
        for video in videos:
            src = src.replace(f"https://dev.bbs.sjtu.edu.cn{video}", resources_map[video])
        src = src.replace(f"/t/topic/{topic}?page={page + 1}", f"{page + 1}.html")
        src = src.replace(f"/t/topic/{topic}?page={page - 1}", f"{page - 1}.html")
        src = src.replace(f"href=\"/t/topic/{topic}\"", "href=\"1.html\"")
        with open(os.path.join(output, f"{page}.html"), mode="w") as f:
            f.write(src)

    print("Downloading resources.")
    await asyncio.gather(
        *(download(src, os.path.join(output, f"resources/{dest}")) for src, dest in resources_map.items()))


if __name__ == "__main__":
    try:
        os.mkdir(output)
    except FileExistsError:
        pass

    try:
        os.mkdir(os.path.join(output, "resources"))
    except FileExistsError:
        pass

    asyncio.run(main())
