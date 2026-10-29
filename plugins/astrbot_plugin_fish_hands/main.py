"""鱼的手 —— 让 bot 能自己动手改资料 / 点赞。

暴露 6 个 LLM 工具：
- get_my_likes       读：看谁给我点过赞（只读，用来自检链路）
- set_my_nickname    写：改 QQ 昵称
- set_my_longnick    写：改个性签名
- set_my_avatar      写：换头像（传图片 URL 或本地绝对路径）
- set_group_card     写：改自己在某个群里的名片
- like_someone       写：给某人点赞

全部走 NapCat/OneBot11 扩展 API，带每日上限 + 审计日志。
"""

import asyncio
import json
import os
import random
import time
import uuid
from datetime import datetime
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Image
from astrbot.api.star import Context, Star, register

import websockets

from .qzone import QzoneClient

DATA_DIR = Path(__file__).parent / "data"
LIMIT_FILE = DATA_DIR / "daily_counts.json"
STICKER_DIR = Path(r"D:\dsh-workspace\projects\astrbot\data\personas\stickers")
NAPCAT_WS = "ws://127.0.0.1:6700"
PROACTIVE_GROUP = "624707019"
STICKER_PROB = 0.35          # 每次回复顺手带表情包的概率
PROACTIVE_CAP = 8            # 每天主动冒泡上限
AUDIT_FILE = DATA_DIR / "audit.jsonl"

# 每类动作每天的上限（防手抖 + 防腾讯风控）
DAILY_LIMITS = {
    "set_my_nickname": 3,
    "set_my_longnick": 5,
    "set_my_avatar": 3,
    "set_group_card": 3,
    "like_someone": 10,
    "publish_qzone": 1,
    "comment_feed": 3,
    "proactive": 8,
}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load_counts() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        raw = json.loads(LIMIT_FILE.read_text("utf-8"))
    except Exception:
        raw = {}
    if raw.get("date") != _today():
        raw = {"date": _today(), "counts": {}}
    return raw


def _bump(action: str) -> tuple[bool, int, int]:
    """返回 (是否允许, 已用次数, 上限)"""
    st = _load_counts()
    counts = st.setdefault("counts", {})
    used = int(counts.get(action, 0))
    limit = DAILY_LIMITS.get(action, 0)
    if limit and used >= limit:
        return False, used, limit
    counts[action] = used + 1
    LIMIT_FILE.write_text(json.dumps(st, ensure_ascii=False), "utf-8")
    return True, used + 1, limit


def _audit(action: str, payload: dict, ok: bool, note: str = "") -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "ok": ok,
        "note": note,
        "payload": payload,
    }
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


@register(
    "fish_hands",
    "fish-hands",
    "让 bot 自己改昵称/签名/头像/群名片、给别人点赞，带每日上限与审计日志",
    "0.1.0",
)
class FishHands(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._bg_task = None
        try:
            loop = asyncio.get_event_loop()
            self._bg_task = loop.create_task(self._proactive_loop())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[fish_hands] 主动冒泡任务没起来: {e}")
        logger.info("[fish_hands] 已加载，动作类工具就绪（带每日上限）")

    # ---------- 内部工具 ----------

    @staticmethod
    def _sticker_files() -> list[Path]:
        if not STICKER_DIR.exists():
            return []
        return [
            p
            for p in STICKER_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in (".gif", ".png", ".jpg", ".jpeg", ".webp")
        ]

    async def _ws_call(self, action: str, params: dict):
        async with websockets.connect(NAPCAT_WS, max_size=None) as ws:
            await ws.send(
                json.dumps({"action": action, "params": params, "echo": "fh"},
                           ensure_ascii=False)
            )
            while True:
                ev = json.loads(await ws.recv())
                if ev.get("echo") == "fh":
                    return ev

    # ---------- 顺手带表情包 ----------

    @filter.on_decorating_result()
    async def _sticker_flavor(self, event: AstrMessageEvent):
        try:
            if random.random() > STICKER_PROB:
                return
            result = event.get_result()
            if not result or not getattr(result, "chain", None):
                return
            files = self._sticker_files()
            if not files:
                return
            pick = random.choice(files)
            result.chain.append(Image.fromFileSystem(str(pick)))
            _audit("auto_sticker", {"file": pick.name}, True)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[fish_hands] 附加表情包失败: {e}")

    # ---------- 没人说话时自己冒一句 ----------

    FALLBACK_LINES = (
        "有点困",
        "群里好安静",
        "今天有点没精神",
        "在忙什么",
        "摸鱼中",
        "喝口水",
    )

    async def _idle_line(self) -> str:
        try:
            provider = self.context.get_using_provider()
            if provider is None:
                return random.choice(self.FALLBACK_LINES)
            resp = await provider.text_chat(
                prompt=(
                    "你在一个 QQ 群里，群里现在没人说话，你随口发一句。"
                    "要求：不超过 15 个字，像随手打字，不要问问题、不要总结、不要解释、"
                    "不要用任何符号排版。只输出这一句。"
                ),
                session_id=uuid.uuid4().hex,
                contexts=[],
                persist=False,
            )
            text = (resp.completion_text or "").strip()
            text = text.replace("**", "").replace("*", "").strip()[:30]
            if not text:
                # 推理模型可能把 token 全花在思考上，正文为空——别发空消息
                logger.info("[fish_hands] 冒泡文案为空，改用兜底句子")
                return random.choice(self.FALLBACK_LINES)
            return text
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[fish_hands] 生成冒泡文案失败: {e}")
            return random.choice(self.FALLBACK_LINES)

    async def _proactive_loop(self):
        await asyncio.sleep(240)
        while True:
            try:
                hour = datetime.now().hour
                awake = hour >= 8 or hour <= 1
                ok, used, cap = (True, 0, PROACTIVE_CAP)
                if awake and _load_counts().get("counts", {}).get("proactive", 0) < PROACTIVE_CAP:
                    ok, used, cap = _bump("proactive")
                if awake and ok and random.random() < 0.55:
                    if random.random() < 0.4 and self._sticker_files():
                        pick = random.choice(self._sticker_files())
                        await self._ws_call("send_group_msg", {
                            "group_id": int(PROACTIVE_GROUP),
                            "message": [{"type": "image",
                                         "data": {"file": str(pick)}}],
                        })
                        _audit("proactive_sticker", {"file": pick.name}, True)
                        logger.info(f"[fish_hands] 主动发表情包 {pick.name} ({used}/{cap})")
                    else:
                        line = await self._idle_line()
                        if line:
                            await self._ws_call("send_group_msg", {
                                "group_id": int(PROACTIVE_GROUP),
                                "message": [{"type": "text", "data": {"text": line}}],
                            })
                            _audit("proactive_text", {"text": line}, True)
                            logger.info(f"[fish_hands] 主动冒泡：{line} ({used}/{cap})")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[fish_hands] 冒泡循环出错: {e}")
            await asyncio.sleep(random.randint(1500, 3300))

    # ---------- 只读：自检 ----------

    @filter.llm_tool(name="get_my_profile")
    async def get_my_profile(self, event: AstrMessageEvent):
        """看看我自己的资料：QQ 号、昵称、好友数、所在群数（只读，不改变任何东西）。

        Returns:
            返回自己的账号信息摘要。
        """
        try:
            info = await event.bot.call_action("get_login_info")
            friends = await event.bot.call_action("get_friend_list")
            groups = await event.bot.call_action("get_group_list")
            _audit("get_my_profile", {}, True)
            nick = (info or {}).get("nickname", "")
            uid = (info or {}).get("user_id", "")
            fn = len(friends or [])
            gn = len(groups or [])
            return f"我是 {nick}（{uid}），好友 {fn} 个，在 {gn} 个群里。"
        except Exception as e:
            _audit("get_my_profile", {}, False, str(e))
            return f"读取自己的资料失败：{e}"

    # ---------- 写：改资料 ----------

    @filter.llm_tool(name="set_my_nickname")
    async def set_my_nickname(self, event: AstrMessageEvent, nickname: str):
        """修改我自己的 QQ 昵称。

        Args:
            nickname(string): 新的昵称，1-24 个字，不要带特殊符号
        Returns:
            成功或失败说明。
        """
        nickname = (nickname or "").strip()
        if not nickname:
            return "昵称为空，不做改动。"
        if len(nickname) > 24:
            return "昵称太长（>24），不做改动。"
        ok, used, limit = _bump("set_my_nickname")
        if not ok:
            return f"今天改昵称已经用完（{used}/{limit}），明天再说。"
        try:
            await event.bot.call_action("set_qq_profile", nickname=nickname)
            _audit("set_my_nickname", {"nickname": nickname}, True)
            logger.info(f"[fish_hands] 改昵称 -> {nickname} ({used}/{limit})")
            return f"昵称已改成「{nickname}」（今日 {used}/{limit}）。"
        except Exception as e:
            _audit("set_my_nickname", {"nickname": nickname}, False, str(e))
            return f"改昵称失败：{e}"

    @filter.llm_tool(name="set_my_longnick")
    async def set_my_longnick(self, event: AstrMessageEvent, signature: str):
        """修改我自己的个性签名。

        Args:
            signature(string): 新的个性签名，最多 40 个字
        Returns:
            成功或失败说明。
        """
        signature = (signature or "").strip()
        if not signature:
            return "签名为空，不做改动。"
        if len(signature) > 40:
            return "签名太长（>40），不做改动。"
        ok, used, limit = _bump("set_my_longnick")
        if not ok:
            return f"今天改签名已经用完（{used}/{limit}），明天再说。"
        try:
            await event.bot.call_action("set_self_longnick", longNick=signature)
            _audit("set_my_longnick", {"signature": signature}, True)
            logger.info(f"[fish_hands] 改签名 -> {signature} ({used}/{limit})")
            return f"签名已改成「{signature}」（今日 {used}/{limit}）。"
        except Exception as e:
            _audit("set_my_longnick", {"signature": signature}, False, str(e))
            return f"改签名失败：{e}"

    @filter.llm_tool(name="set_my_avatar")
    async def set_my_avatar(self, event: AstrMessageEvent, image: str):
        """换我自己的头像。

        Args:
            image(string): 图片地址，http(s) URL 或本机绝对路径
        Returns:
            成功或失败说明。
        """
        image = (image or "").strip()
        if not image:
            return "没给图片，不换。"
        if not (image.startswith("http://") or image.startswith("https://") or os.path.isabs(image)):
            return "只接受 http(s) 链接或本机绝对路径。"
        ok, used, limit = _bump("set_my_avatar")
        if not ok:
            return f"今天换头像已经用完（{used}/{limit}），明天再说。"
        try:
            await event.bot.call_action("set_qq_avatar", file=image)
            _audit("set_my_avatar", {"image": image}, True)
            logger.info(f"[fish_hands] 换头像 ({used}/{limit})")
            return f"头像换好了（今日 {used}/{limit}）。"
        except Exception as e:
            _audit("set_my_avatar", {"image": image}, False, str(e))
            return f"换头像失败：{e}"

    @filter.llm_tool(name="set_group_card")
    async def set_group_card(self, event: AstrMessageEvent, card: str, group_id: str = ""):
        """改我在某个群里的群名片。

        Args:
            card(string): 新的群名片，1-20 个字
            group_id(string): 群号；留空则用当前群
        Returns:
            成功或失败说明。
        """
        card = (card or "").strip()
        if not card:
            return "名片为空，不改。"
        gid = (group_id or "").strip() or (event.get_group_id() or "")
        if not gid:
            return "拿不到群号，不改。"
        ok, used, limit = _bump("set_group_card")
        if not ok:
            return f"今天改名片已经用完（{used}/{limit}），明天再说。"
        try:
            await event.bot.call_action(
                "set_group_card", group_id=int(gid), card=card
            )
            _audit("set_group_card", {"card": card, "group_id": gid}, True)
            return f"群 {gid} 的群名片已改成「{card}」。"
        except Exception as e:
            _audit("set_group_card", {"card": card, "group_id": gid}, False, str(e))
            return f"改群名片失败：{e}"

    @filter.llm_tool(name="like_someone")
    async def like_someone(self, event: AstrMessageEvent, user_id: str, times: str = "1"):
        """给某个人（或当前群里的人）点赞。

        Args:
            user_id(string): 对方 QQ 号；留空表示当前说话的人
            times(string): 点赞次数，1-10
        Returns:
            成功或失败说明。
        """
        target = (user_id or "").strip() or str(event.get_sender_id())
        try:
            n = max(1, min(10, int(str(times or "1"))))
        except Exception:
            n = 1
        ok, used, limit = _bump("like_someone")
        if not ok:
            return f"今天点赞已经用完（{used}/{limit}），明天再说。"
        try:
            await event.bot.call_action(
                "send_like", user_id=int(target), times=n
            )
            _audit("like_someone", {"user_id": target, "times": n}, True)
            return f"给 {target} 点了 {n} 个赞。"
        except Exception as e:
            _audit("like_someone", {"user_id": target, "times": n}, False, str(e))
            return f"点赞失败：{e}"

    # ---------- QQ 空间 ----------

    async def _qzone(self, event: AstrMessageEvent) -> QzoneClient:
        ck = await event.bot.call_action("get_cookies", domain="qzone.qq.com")
        info = await event.bot.call_action("get_login_info")
        uin = str((info or {}).get("user_id") or event.get_self_id())
        return QzoneClient(ck.get("cookies", ""), ck.get("bkn", ""), uin)

    @filter.llm_tool(name="read_feeds")
    async def read_feeds(self, event: AstrMessageEvent, uin: str, num: str = "5"):
        """看某个人的空间里最近发了几条说说（只读）。用来知道该评论哪一条。

        Args:
            uin(string): 要看的人的 QQ 号
            num(string): 看几条，1-10
        Returns:
            说说列表：时间、正文片段、tid（tid 是评论时要用的编号）。
        """
        uin = (uin or "").strip()
        if not uin:
            return "没给 QQ 号。"
        try:
            n = max(1, min(10, int(str(num or "5"))))
        except Exception:
            n = 5
        try:
            qz = await self._qzone(event)
            data = qz.feeds(uin, n)
            lst = data.get("msglist") or []
            if not lst:
                return f"{uin} 的空间里没看到说说（可能没发过、或对我不可见，code={data.get('code')}）。"
            lines = []
            for m in lst[:n]:
                body = (m.get("content") or "").replace("\n", " ")[:60]
                lines.append(f"[{m.get('created_time','')}] tid={m.get('tid')} {body}")
            return "\n".join(lines)
        except Exception as e:
            _audit("read_feeds", {"uin": uin}, False, str(e))
            return f"读空间失败：{e}"

    @filter.llm_tool(name="publish_qzone")
    async def publish_qzone(self, event: AstrMessageEvent, text: str):
        """在我自己的 QQ 空间发一条说说（纯文字）。

        Args:
            text(string): 说说正文，最多 100 字，不要带 Markdown 符号
        Returns:
            成功返回说说 tid，失败返回原因。
        """
        text = (text or "").strip()
        if not text:
            return "内容为空，不发。"
        if len(text) > 100:
            return "太长了（>100 字），不发。"
        ok, used, limit = _bump("publish_qzone")
        if not ok:
            return f"今天已经发过说说了（{used}/{limit}），明天再说。"
        try:
            qz = await self._qzone(event)
            r = qz.publish(text)
            code = r.get("code")
            _audit("publish_qzone", {"text": text, "code": code}, code in (0, "0"), str(r)[:200])
            if code in (0, "0"):
                return f"发出去了，tid={r.get('tid')}。"
            return f"没发出去：{r.get('message') or r}"
        except Exception as e:
            _audit("publish_qzone", {"text": text}, False, str(e))
            return f"发说说失败：{e}"

    @filter.llm_tool(name="comment_feed")
    async def comment_feed(
        self, event: AstrMessageEvent, uin: str, text: str, tid: str = ""
    ):
        """去某个人的说说下面留言评论。tid 留空则自动挑他最新的一条。

        Args:
            uin(string): 对方的 QQ 号
            text(string): 评论内容，最多 50 字
            tid(string): 说说的 tid；不确定就留空
        Returns:
            成功或失败说明。
        """
        uin = (uin or "").strip()
        text = (text or "").strip()
        if not uin or not text:
            return "缺 QQ 号或评论内容。"
        if len(text) > 50:
            return "评论太长（>50 字），不发。"
        ok, used, limit = _bump("comment_feed")
        if not ok:
            return f"今天评论次数用完了（{used}/{limit}），明天再说。"
        try:
            qz = await self._qzone(event)
            if not tid:
                data = qz.feeds(uin, 1)
                lst = data.get("msglist") or []
                if not lst:
                    return f"{uin} 最近没有可见的说说，没法留言。"
                tid = str(lst[0].get("tid") or "")
                if not tid:
                    return "拿不到 tid，没法留言。"
            r = qz.comment(uin, str(tid), text)
            code = r.get("code")
            _audit("comment_feed", {"uin": uin, "tid": tid, "text": text, "code": code},
                   code in (0, "0"), str(r)[:200])
            if code in (0, "0"):
                return f"留言成功了（tid={tid}）。"
            return f"没留上：{r.get('message') or r}"
        except Exception as e:
            _audit("comment_feed", {"uin": uin, "tid": tid, "text": text}, False, str(e))
            return f"留言失败：{e}"

    # ---------- 表情包 ----------

    @filter.llm_tool(name="send_sticker")
    async def send_sticker(
        self, event: AstrMessageEvent, name: str = "", url: str = ""
    ):
        """发一张表情包。用 name 从本地表情库里挑，或用 url 发网上的图。

        Args:
            name(string): 表情包名/关键词，比如「无语」「笑」「猫」，从本地库里模糊匹配
            url(string): 图片直链；给了 url 就忽略 name
        Returns:
            发出去了返回「发了」，没有合适的返回原因。
        """
        try:
            if url:
                await event.send(MessageChain([Image.fromURL(url.strip())]))
                _audit("send_sticker", {"url": url}, True)
                return "发了"
            key = (name or "").strip()
            files = []
            if STICKER_DIR.exists():
                files = [
                    p
                    for p in STICKER_DIR.iterdir()
                    if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp")
                ]
            if not files:
                return "表情库里还没有图。"
            if key:
                hit = [p for p in files if key in p.stem or p.stem in key]
            else:
                hit = []
            if not hit:
                hit = files
            pick = random.choice(hit)
            await event.send(MessageChain([Image.fromFileSystem(str(pick))]))
            _audit("send_sticker", {"name": key, "file": pick.name}, True)
            return "发了"
        except Exception as e:
            _audit("send_sticker", {"name": name, "url": url}, False, str(e))
            return f"发表情包失败：{e}"

    async def terminate(self):
        logger.info("[fish_hands] 已卸载")

