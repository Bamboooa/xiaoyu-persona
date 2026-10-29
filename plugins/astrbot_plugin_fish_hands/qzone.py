"""QQ 空间（Qzone）最小客户端。

只做三件事：读某人的说说列表、发一条说说、给某条说说评论。
凭据来自 NapCat 的 get_cookies(domain="qzone.qq.com")，不需要账号密码。

风险提示（写死在代码里，别改松）：
- Qzone 有内容审核，发出去也可能被删；
- 高频操作会触发限制，调用方必须自己有次数上限。
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


def _cookie_dict(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (raw or "").split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            out[k] = v
    return out


def _strip_callback(text: str) -> str:
    t = text.strip()
    m = re.match(r"^\s*[\w$.]+\((.*)\)\s*;?\s*$", t, re.S)
    if m:
        return m.group(1)
    return t


class QzoneClient:
    def __init__(self, cookies_raw: str, bkn: str, self_uin: str):
        self.cookies = _cookie_dict(cookies_raw)
        self.bkn = str(bkn)
        self.uin = str(self_uin)
        self.s = requests.Session()
        self.s.cookies.update(self.cookies)
        self.s.headers.update({"User-Agent": UA})

    # ---------- 读 ----------
    def feeds(self, target_uin: str, num: int = 5) -> dict[str, Any]:
        url = (
            "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/"
            f"emotion_cgi_msglist_v6?uin={target_uin}&ftype=0&sort=0&pos=0"
            f"&num={num}&replynum=0&g_tk={self.bkn}&code=1&format=json"
        )
        r = self.s.get(
            url,
            headers={"Referer": f"https://user.qzone.qq.com/{target_uin}"},
            timeout=20,
        )
        try:
            return json.loads(_strip_callback(r.text))
        except Exception:
            return {"code": -1, "message": "解析失败", "raw": r.text[:300]}

    # ---------- 写 ----------
    def publish(self, text: str) -> dict[str, Any]:
        url = (
            "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/"
            "emotion_cgi_publish_v6"
        )
        data = {
            "syn_tweet_verson": "1",
            "paramstr": "1",
            "who": "1",
            "con": text,
            "feedversion": "1",
            "ver": "1",
            "ugc_right": "1",
            "to_sign": "0",
            "hostuin": self.uin,
            "code": "2",
            "format": "json",
            "qzreferrer": f"https://user.qzone.qq.com/{self.uin}",
            "g_tk": self.bkn,
        }
        r = self.s.post(
            url,
            data=data,
            headers={"Referer": f"https://user.qzone.qq.com/{self.uin}"},
            timeout=20,
        )
        try:
            return json.loads(_strip_callback(r.text))
        except Exception:
            return {"code": -1, "message": "解析失败", "raw": r.text[:300]}

    def comment(self, target_uin: str, tid: str, text: str) -> dict[str, Any]:
        url = (
            "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/"
            f"emotion_cgi_comment_v6?uin={self.uin}&hostuin={target_uin}&tid={tid}"
            f"&content={requests.utils.quote(text)}&format=json&g_tk={self.bkn}"
        )
        r = self.s.post(
            url,
            headers={"Referer": f"https://user.qzone.qq.com/{target_uin}"},
            timeout=20,
        )
        try:
            return json.loads(_strip_callback(r.text))
        except Exception:
            return {"code": -1, "message": "解析失败", "raw": r.text[:300]}
