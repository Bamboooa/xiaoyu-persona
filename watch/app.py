#!/usr/bin/env python3
"""小鱼的家 · 看板

看她在家里做什么。只读，不打扰她。
标准库实现，零依赖。

运行: python3 app.py [端口]
默认只绑 127.0.0.1，走 SSH 隧道访问:
  ssh -L 18088:127.0.0.1:8088 ubuntu@SERVER
然后浏览器打开 http://127.0.0.1:18088
"""

from __future__ import annotations

import html
import json
import mimetypes
import os
import sqlite3
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE = Path(os.environ.get("XY_BASE", "/opt/xiaoyu/cloud/astrbot/data"))
HOME = Path(os.environ.get("XY_HOME", str(BASE / "xiaoyu_home")))
PLUG = BASE / "plugins" / "astrbot_plugin_fish_hands" / "data"
FRIENDS = {"1174659248": "陈天睡大觉", "353126689": "桡枝（关子姐姐）"}

PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>小鱼的家</title>
<style>
*{box-sizing:border-box}
body{margin:0;font:15px/1.85 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
background:#101a1d;color:#b9c6c3;padding:36px 22px 80px;max-width:1040px;margin:0 auto;
background-image:radial-gradient(1100px 520px at 50% -12%, rgba(134,168,162,.05), transparent 72%);
background-attachment:fixed}
h1{font-size:18px;margin:0 0 4px;font-weight:500;color:#e9e7e2;letter-spacing:.6px}
.sub{color:#58706c;font-size:12.5px;margin-bottom:30px;letter-spacing:.3px}
.card{background:#182427;
border:1px solid #212f33;border-top:1px solid #2a383c;border-radius:10px;
padding:20px 22px;margin-bottom:18px;
box-shadow:0 1px 0 rgba(255,255,255,.015) inset}
.card h2{font-size:12.5px;margin:0 0 16px;color:#647b78;font-weight:500;letter-spacing:1px}
.row{display:flex;flex-wrap:wrap;gap:9px}
.tag{background:#1c282b;border:1px solid #243236;border-radius:8px;padding:9px 14px;
font-size:13.5px;color:#a6b5b2}
.tag b{color:#e9e7e2;font-weight:500}
.on{color:#ffc861}.off{color:#58706c}
.tree{font-family:ui-monospace,Consolas,monospace;font-size:13px;line-height:2.1}
.tree a{color:#9db3ae;text-decoration:none;cursor:pointer;transition:color .15s}
.tree a:hover{color:#ffc861}
.tree .d{color:#647b78}
.tree .sz{color:#3d4f52;font-size:11.5px;margin-left:8px}
pre{background:#0d1618;border:1px solid #1c282b;border-radius:8px;padding:15px;
overflow:auto;font-size:12.5px;line-height:1.75;color:#a6b5b2;max-height:520px;
white-space:pre-wrap;word-break:break-word;margin:0}
.item{border-left:1px solid #2a3a3e;padding:7px 0 7px 14px;margin-bottom:10px;font-size:13.5px}
.item .t{color:#4d6461;font-size:11.5px;margin-right:8px;font-variant-numeric:tabular-nums}
.item .who{color:#8ba39a}
.muted{color:#58706c}
.grow{height:4px;background:#1c282b;border-radius:2px;overflow:hidden;margin-top:8px}
.grow i{display:block;height:100%;background:#ffc861;border-radius:2px;
transition:width .6s ease;box-shadow:0 0 8px rgba(255,200,97,.35)}
#file{display:none}
/* 木头：只有一条，像桌沿 */
#deskcard{position:relative;overflow:hidden}
#deskcard::before{content:'';position:absolute;left:0;right:0;top:0;height:1px;
background:linear-gradient(90deg,transparent,#a8825c66 18%,#a8825c66 82%,transparent)}
@keyframes pl{
  0%{box-shadow:0 0 0 0 rgba(255,200,97,.55)}
  70%{box-shadow:0 0 0 10px rgba(255,200,97,0)}
  100%{box-shadow:0 0 0 0 rgba(255,200,97,0)}
}
.close{float:right;color:#566b80;cursor:pointer;font-size:12.5px}
.close:hover{color:#ffd479}
/* 正在做：唯一的一处暖光 */
#doingcard{background:#162023;border-color:#243236;border-top:1px solid #2a383c}
#doingtext{font-size:17px;color:#e9e7e2;letter-spacing:.3px;font-weight:400}
#doingicon{filter:saturate(.9) brightness(1.05)}
@media(max-width:640px){
  body{padding:20px 13px 48px}
  .card{padding:16px 15px;border-radius:9px}
  h1{font-size:16.5px}
  #doingtext{font-size:15px}
}
</style></head><body>
<h1>🐟 小鱼的家</h1>
<div class="sub" id="sub">正在读取…</div>

<div class="card" id="doingcard">
  <h2>她正在做</h2>
  <div class="row" style="align-items:center">
    <div id="doingicon" style="font-size:34px;line-height:1"></div>
    <div>
      <div id="doingtext" style="font-size:18px;color:#e6eef8"></div>
      <div id="doingago" class="muted" style="font-size:12px"></div>
    </div>
    <div id="doingpulse" style="width:10px;height:10px;border-radius:50%;margin-left:auto"></div>
  </div>
</div>

<div class="card"><h2>她现在的样子</h2><div class="row" id="state"></div></div>

<div class="card" id="filebox" style="display:none">
  <h2><span id="fname"></span><span class="close" onclick="document.getElementById('filebox').style.display='none'">关闭</span></h2>
  <pre id="filebody"></pre>
</div>

<div class="card"><h2>她的记忆星空</h2>
<div id="skymap" style="position:relative"></div>
<div id="starhint" class="muted" style="font-size:13px;margin-top:8px"></div>
</div>

<div class="card"><h2>她去过哪儿</h2>
<div id="map"></div>
<div id="legend" class="muted" style="font-size:13px;margin-top:10px"></div>
</div>

<div class="card" id="deskcard"><h2>屋子里的东西</h2><div class="tree" id="tree"></div></div>

<div class="card"><h2>今天写过什么</h2><div id="notes"></div></div>

<div class="card"><h2>她最近经历的事</h2><div id="conv"></div></div>

<div class="card"><h2>她记得的事</h2><div id="mem"></div></div>

<div class="card"><h2>她偷偷做过的事</h2><div id="audit"></div></div>

<script>
const esc = s => (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function get(u){ const r = await fetch(u); return await r.json(); }

function renderTree(nodes, prefix=''){
  return nodes.map(n => {
    if (n.dir) {
      return `<div>${prefix}<span class="d">📁 ${esc(n.name)}/</span></div>` +
             renderTree(n.children||[], prefix + '&nbsp;&nbsp;&nbsp;');
    }
    return `<div>${prefix}<a onclick="openFile('${encodeURIComponent(n.path)}')">${esc(n.name)}</a>` +
           `<span class="sz">${n.size}</span></div>`;
  }).join('');
}

async function openFile(p){
  const d = await get('/api/file?path=' + p);
  document.getElementById('fname').textContent = d.name || '读取失败';
  document.getElementById('filebody').textContent = d.content || d.error || '';
  document.getElementById('filebox').style.display = 'block';
  document.getElementById('filebox').scrollIntoView({behavior:'smooth', block:'center'});
}

/* ---- 记忆星空 ---- */
function hash01(n){ const x = Math.sin(n*127.1+311.7)*43758.5453; return x - Math.floor(x); }

function renderStars(stars){
  const box = document.getElementById('skymap');
  const W=660, H=400, cx=W/2, cy=H/2;
  if(!stars || !stars.length){
    box.innerHTML = '<div class="muted">还没有星星。等她记下第一件事。</div>';
    document.getElementById('starhint').textContent='';
    return;
  }
  const maxR = Math.min(W,H)/2 - 46;
  // 权重范围 → 半径范围：越清晰越靠内
  const ws = stars.map(s=>s.weight);
  const wMax = Math.max(3, ...ws), wMin = Math.min(...ws);
  let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:660px;display:block;margin:0 auto">`;
  s += `<defs>
    <radialGradient id="core"><stop offset="0%" stop-color="#8fd0ff" stop-opacity=".5"/><stop offset="100%" stop-color="#8fd0ff" stop-opacity="0"/></radialGradient>
  </defs>`;
  s += `<circle cx="${cx}" cy="${cy}" r="${maxR+18}" fill="none" stroke="#16233a" stroke-dasharray="2 6"/>`;
  s += `<circle cx="${cx}" cy="${cy}" r="16" fill="url(#core)"/>`;

  const placed = [];
  stars.forEach(st=>{
    // 权重高→靠内；淡出的往外丢
    const norm = wMax===wMin ? 0.5 : (st.weight - wMin)/(wMax - wMin);
    let r = maxR * (1 - norm*0.78);
    if (st.archived) r = maxR * (0.9 + 0.2*hash01(st.id*7));
    const a = hash01(st.id) * Math.PI*2;
    // 避免重叠：同角度附近加点抖动
    const jr = r + (hash01(st.id*13)-0.5)*22;
    const ja = a + (hash01(st.id*29)-0.5)*0.22;
    const x = cx + Math.cos(ja)*jr, y = cy + Math.sin(ja)*jr;
    const size = 1.6 + norm*4.2 + (st.hits?Math.min(2, st.hits*0.3):0);
    const bright = st.archived ? 0.28 : (0.45 + norm*0.55);
    const fill = st.archived ? '#4a6280' : '#cfe9ff';
    placed.push({st,x,y,size});
    s += `<circle class="star" data-i="${placed.length-1}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${size.toFixed(1)}"
            fill="${fill}" opacity="${bright.toFixed(2)}" style="cursor:pointer"/>
          <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(size*2.6).toFixed(1)}"
            fill="url(#core)" opacity="${st.archived?0.06:0.16}" pointer-events="none"/>`;
  });
  s += `</svg>`;
  box.innerHTML = s + `<div id="tip" style="position:absolute;display:none;max-width:320px;
    background:#0a1119;border:1px solid #2a3f57;border-radius:8px;padding:10px 12px;
    font-size:13px;line-height:1.6;color:#cfe4f7;pointer-events:none;z-index:10;
    box-shadow:0 8px 24px rgba(0,0,0,.5)"></div>`;

  const tip = document.getElementById('tip');
  box.querySelectorAll('.star').forEach(el=>{
    el.addEventListener('mouseenter', e=>{
      const p = placed[+el.dataset.i];
      tip.innerHTML = `<div style="color:#8fd0ff;font-size:12px;margin-bottom:4px">
          ${esc(p.st.time)}${p.st.nick?' · '+esc(p.st.nick):''}
          ${p.st.archived?' · <span style="color:#c96">已淡出</span>':''}</div>
        <div>${esc(p.st.text)}</div>
        <div style="color:#4f6a83;font-size:11px;margin-top:6px">
          清晰度 ${p.st.weight} · 想起过 ${p.st.hits} 次</div>`;
      tip.style.display='block';
      const r = box.getBoundingClientRect();
      let lx = e.clientX - r.left + 14, ly = e.clientY - r.top + 14;
      if (lx + 330 > r.width) lx = e.clientX - r.left - 330;
      if (ly + 130 > r.height) ly = e.clientY - r.top - 120;
      tip.style.left = lx+'px'; tip.style.top = ly+'px';
    });
    el.addEventListener('mousemove', e=>{
      const r = box.getBoundingClientRect();
      let lx = e.clientX - r.left + 14, ly = e.clientY - r.top + 14;
      if (lx + 330 > r.width) lx = e.clientX - r.left - 330;
      if (ly + 130 > r.height) ly = e.clientY - r.top - 120;
      tip.style.left = lx+'px'; tip.style.top = ly+'px';
    });
    el.addEventListener('mouseleave', ()=>{ tip.style.display='none'; });
  });

  const live = stars.filter(s=>!s.archived).length;
  const arch = stars.length - live;
  document.getElementById('starhint').innerHTML =
    `一共 ${stars.length} 颗：<b style="color:#cfe9ff">${live}</b> 颗亮着，${arch} 颗淡了。
     中心是现在，越往外越久远；点亮的星星把鼠标放上去看它是什么。`;
}

function renderMap(pts){
  const W=660, H=440, cx=W/2, cy=H/2, R=158;
  if(!pts || !pts.length){
    document.getElementById('map').innerHTML = '<div class="muted">还没出过门</div>';
    document.getElementById('legend').textContent = '';
    return;
  }
  const max = Math.max(...pts.map(p=>p.count));
  let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:660px;display:block;margin:0 auto">`;
  s += `<defs><radialGradient id="glow"><stop offset="0%" stop-color="#8fd0ff" stop-opacity=".55"/><stop offset="100%" stop-color="#8fd0ff" stop-opacity="0"/></radialGradient></defs>`;

  pts.forEach((p,i)=>{
    const a = -Math.PI/2 + i*2*Math.PI/pts.length;
    const x = cx + Math.cos(a)*R, y = cy + Math.sin(a)*R;
    const w = 1 + (p.count/max)*5;
    const op = p.recent ? 0.95 : 0.32;
    s += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#3d7ea8" stroke-width="${w.toFixed(1)}" opacity="${op}" stroke-linecap="round"/>`;
    if (p.recent) s += `<circle cx="${x}" cy="${y}" r="30" fill="url(#glow)"/>`;
    s += `<circle cx="${x}" cy="${y}" r="${p.recent?9:6}" fill="${p.recent?'#8fd0ff':'#33506b'}" stroke="#0d1420" stroke-width="2"/>`;
    const lx = cx + Math.cos(a)*(R+26), ly = cy + Math.sin(a)*(R+26);
    const anchor = Math.abs(Math.cos(a))<0.3 ? 'middle' : (Math.cos(a)>0?'start':'end');
    s += `<text x="${lx}" y="${ly}" fill="${p.recent?'#cfe4f7':'#6b8299'}" font-size="13" text-anchor="${anchor}" dominant-baseline="middle">${p.icon} ${esc(p.name)}</text>`;
    s += `<text x="${lx}" y="${ly+16}" fill="#4f6a83" font-size="11" text-anchor="${anchor}" dominant-baseline="middle">${p.count} 次${p.last?' · '+esc(p.last):''}</text>`;
  });

  // 中心：家
  s += `<circle cx="${cx}" cy="${cy}" r="34" fill="#16233a" stroke="#8fd0ff" stroke-width="1.5"/>`;
  s += `<text x="${cx}" y="${cy-4}" font-size="20" text-anchor="middle">🐟</text>`;
  s += `<text x="${cx}" y="${cy+18}" font-size="11" fill="#8fd0ff" text-anchor="middle">家</text>`;
  s += `</svg>`;
  document.getElementById('map').innerHTML = s;

  const recent = pts.filter(p=>p.recent).map(p=>p.name);
  document.getElementById('legend').innerHTML =
    `线的粗细 = 去的次数 · 亮的是今天去过的` +
    (recent.length ? ` · 今天去过：<b style="color:#8fd0ff">${recent.map(esc).join('、')}</b>` : ' · 今天还没出门');
}

async function load(){
  const o = await get('/api/overview');
  document.getElementById('sub').textContent =
    `${o.now} · 她的家：${o.home}`;

  // 正在做
  const d = o.doing || {};
  document.getElementById('doingicon').textContent = d.icon || '🌙';
  document.getElementById('doingtext').textContent = d.text || '安安静静的';
  document.getElementById('doingago').textContent = d.ago || '';
  const pulse = document.getElementById('doingpulse');
  if (d.live) {
    pulse.style.background = '#ffc861';
    pulse.style.boxShadow = '0 0 0 0 rgba(255,200,97,.55)';
    pulse.style.animation = 'pl 1.8s infinite';
  } else if (d.kind === 'sleep') {
    pulse.style.background = '#3d5570';
    pulse.style.boxShadow = 'none';
    pulse.style.animation = 'none';
  } else {
    pulse.style.background = '#2a3f57';
    pulse.style.boxShadow = 'none';
    pulse.style.animation = 'none';
  }

  const sleepTag = o.asleep
    ? `<div class="tag"><b class="off">在睡</b> 灯关着（已睡 ${o.sleep_hours} 小时）</div>`
    : `<div class="tag"><b class="on">醒着</b> 灯亮着</div>`;
  document.getElementById('state').innerHTML = sleepTag + `
    <div class="tag">等级 <b>${esc(o.level)}</b> · ${o.xp} 点<div class="grow"><i style="width:${o.progress}%"></i></div></div>
    <div class="tag">记得 <b>${o.mem_live}</b> 条 · 淡掉 ${o.mem_archived}</div>
    <div class="tag">日记 <b>${o.note_count}</b> 篇</div>
    <div class="tag">成长：聊 ${o.counts.chat} 次 / 记事 ${o.counts.remember} / 日记 ${o.counts.diary}</div>`;

  document.getElementById('tree').innerHTML = renderTree(o.tree);
  renderStars(o.stars);
  renderMap(o.travel);

  document.getElementById('notes').innerHTML = (o.notes||[]).length
    ? o.notes.map(n => `<div class="item"><span class="t">${n.time}</span>
        <a style="color:#9fc4e8;cursor:pointer" onclick="openFile('${encodeURIComponent(n.path)}')">${esc(n.name)}</a></div>`).join('')
    : '<div class="muted">还没写</div>';

  document.getElementById('conv').innerHTML = (o.conv||[]).length
    ? o.conv.map(c => `<div class="item"><span class="t">${esc(c.t)}</span>
        <span class="who">${esc(c.scene)}｜${esc(c.who)}</span>：${esc(c.text)}</div>`).join('')
    : '<div class="muted">还没有记录</div>';

  document.getElementById('mem').innerHTML = (o.mem||[]).length
    ? o.mem.map(m => `<div class="item"><span class="t">#${m.id} ${esc(m.time)}</span>
        ${esc(m.text)} <span class="muted">（清晰度 ${m.weight}）</span></div>`).join('')
    : '<div class="muted">还没记下什么</div>';

  document.getElementById('audit').innerHTML = (o.audit||[]).length
    ? o.audit.map(a => `<div class="item"><span class="t">${esc(a.ts)}</span>
        ${esc(a.action)} ${a.ok ? '' : '<span style="color:#c96">✗</span>'} ${esc(a.note||'')}</div>`).join('')
    : '<div class="muted">还没有动作</div>';
}
load();
setInterval(load, 10000);
</script></body></html>
"""


def _read_text(p: Path, limit: int = 20000) -> str:
    try:
        return p.read_text("utf-8", errors="replace")[:limit]
    except Exception as e:  # noqa: BLE001
        return f"（读不了：{e}）"


def _safe(path: str) -> Path | None:
    """只允许读她屋里，别让人翻到系统其他东西。"""
    try:
        p = (HOME / unquote(path)).resolve()
        if str(p).startswith(str(HOME.resolve())):
            return p
    except Exception:  # noqa: BLE001
        pass
    return None


def _tree(d: Path, depth: int = 0) -> list[dict]:
    out = []
    if depth > 3:
        return out
    try:
        items = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name))
    except Exception:  # noqa: BLE001
        return out
    for it in items:
        if it.name.startswith("."):
            continue
        try:
            if it.is_dir():
                out.append({"name": it.name, "dir": True,
                            "children": _tree(it, depth + 1)})
            else:
                sz = it.stat().st_size
                out.append({"name": it.name, "dir": False,
                            "path": str(it.relative_to(HOME)),
                            "size": f"{sz}B" if sz < 1024 else f"{sz/1024:.1f}K"})
        except Exception:  # noqa: BLE001
            continue
    return out


def _db(path: Path, sql: str, args: tuple = ()) -> list[tuple]:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()
    except Exception:  # noqa: BLE001
        return []


def _travel() -> list[dict]:
    """她从家出发去过哪儿。统计次数和最近一次。

    数据来自她自己留下的痕迹：RECENT.md、audit.jsonl、CONVERSATION.md。
    """
    import re as _re

    # (显示名, 关键词, 图标, 一句话)
    PLACES = [
        ("B站", ["B站", "bilibili", "BV号", "刷到一条"], "📺", "刷视频"),
        ("网易云", ["听《", "听歌", "网易云", "song"], "🎵", "听歌"),
        ("热搜榜", ["热搜", "热点", "微博", "知乎", "百度"], "🔥", "看热闹"),
        ("网页", ["网页", "read_webpage", "读了"], "🌐", "读东西"),
        ("QQ空间", ["说说", "qzone", "空间"], "📮", "发说说"),
        ("群聊", ["群聊"], "👥", "说话"),
        ("私聊", ["私聊"], "💬", "说话"),
    ]

    corpus: list[tuple[str, str]] = []   # (时间, 文本)

    af = PLUG / "audit.jsonl"
    if af.is_file():
        for ln in af.read_text("utf-8", errors="replace").splitlines():
            try:
                d = json.loads(ln)
                t = (d.get("ts") or "")[5:16]
                blob = f"{d.get('action','')} {d.get('note','')} {json.dumps(d.get('payload') or {}, ensure_ascii=False)}"
                corpus.append((t, blob))
            except Exception:  # noqa: BLE001
                continue

    for fname in ("RECENT.md", "CONVERSATION.md"):
        f = HOME / fname
        if not f.is_file():
            continue
        for ln in f.read_text("utf-8", errors="replace").splitlines():
            m = _re.match(r"^[-\[]?\s*(\d{2}-\d{2} \d{2}:\d{2})", ln.strip())
            corpus.append((m.group(1) if m else "", ln))

    out = []
    for name, kws, icon, tag in PLACES:
        hits = [(t, txt) for t, txt in corpus if any(k.lower() in txt.lower() for k in kws)]
        if not hits:
            continue
        # 最近一次的时间（字符串排序够用，格式统一）
        last = max((t for t, _ in hits if t), default="")
        out.append({
            "name": name, "icon": icon, "tag": tag,
            "count": len(hits),
            "last": last,
            "recent": bool(last) and last >= _today_prefix(),
        })
    out.sort(key=lambda x: -x["count"])
    return out


def _today_prefix() -> str:
    return datetime.now().strftime("%m-%d") + " 00:00"


TOOL_CN = {
    "run_command": ("🔧", "在机器上动手"),
    "listen_music": ("🎵", "在听歌"),
    "search_music": ("🎵", "在找歌"),
    "browse_bilibili": ("📺", "在刷 B 站"),
    "read_webpage": ("🌐", "在读网页"),
    "read_hot_list": ("🔥", "在看热搜"),
    "think_about": ("💭", "在想事情"),
    "remember_moment": ("📝", "在记事"),
    "recall_moments": ("🔍", "在翻记忆"),
    "publish_qzone": ("📮", "在发说说"),
    "comment_qzone": ("📮", "在空间留言"),
    "send_group_file": ("📎", "在传文件"),
    "set_self_longnick": ("✍️", "在改签名"),
    "set_self_avatar": ("🖼️", "在换头像"),
    "poke_someone": ("👉", "在拍人"),
    "react_to_message": ("👍", "在贴表情"),
    "send_private_message": ("💬", "在私聊"),
    "go_to_sleep": ("😴", "准备睡觉"),
    "wake_up": ("☀️", "刚睁开眼"),
    "watch_douyin": ("📱", "在看抖音"),
    "look_up_user": ("👀", "在看人"),
}


def _doing() -> dict:
    """她此刻在干什么。看日志、看审计、看在睡没。"""
    import re as _re
    import subprocess as _sp

    now = time.time()

    # 1. 睡着了吗
    if (HOME / "睡").is_file():
        try:
            hrs = round((now - (HOME / "睡").stat().st_mtime) / 3600, 1)
        except Exception:  # noqa: BLE001
            hrs = 0.0
        return {"icon": "😴", "text": f"睡着了，灯关着（{hrs} 小时）",
                "ago": "现在", "live": False, "kind": "sleep"}

    # 2. 最近的动作（audit 是最可靠的自己的记录）
    last_action, last_ts = "", 0.0
    af = PLUG / "audit.jsonl"
    if af.is_file():
        for ln in af.read_text("utf-8", errors="replace").splitlines()[-5:]:
            try:
                d = json.loads(ln)
                ts = datetime.strptime(d.get("ts", ""), "%Y-%m-%dT%H:%M:%S").timestamp()
                if ts >= last_ts:
                    last_ts, last_action = ts, d.get("action", "")
            except Exception:  # noqa: BLE001
                continue

    # 3. 日志里正在进行的工具调用（最实时）
    live_tool, live_gap = "", 9999.0
    try:
        r = _sp.run(["docker", "logs", "astrbot", "--tail", "150"],
                    capture_output=True, text=True, timeout=12)
        logs = (r.stdout or "") + (r.stderr or "")
        today = datetime.now().strftime("%H:%M:%S")
        for ln in logs.splitlines()[-120:]:
            m = _re.search(r"\[(\d{2}:\d{2}:\d{2})\.\d+\].*使用工具：(\w+)", ln)
            if not m:
                continue
            # 日志只有时分秒：跟当前时间比
            try:
                t = datetime.strptime(m.group(1), "%H:%M:%S").timestamp()
                cur = datetime.strptime(today, "%H:%M:%S").timestamp()
                gap = cur - t
                if gap < 0:
                    gap += 86400
            except Exception:  # noqa: BLE001
                gap = 9999
            if gap < live_gap:
                live_gap, live_tool = gap, m.group(2)
    except Exception:  # noqa: BLE001
        pass

    # 4. 拼结论
    if live_tool and live_gap <= 25:
        icon, text = TOOL_CN.get(live_tool, ("⚙️", f"在做 {live_tool}"))
        return {"icon": icon, "text": text, "ago": "正在进行",
                "live": True, "kind": "working"}

    if last_ts:
        gap = now - last_ts
        if last_action in TOOL_CN:
            icon, text = TOOL_CN[last_action]
        else:
            icon, text = "⚙️", f"刚做过 {last_action}"
        if gap < 120:
            return {"icon": icon, "text": text, "ago": f"{int(gap)} 秒前",
                    "live": True, "kind": "recent"}
        if gap < 3600:
            return {"icon": icon, "text": text, "ago": f"{int(gap/60)} 分钟前",
                    "live": False, "kind": "idle"}
        return {"icon": icon, "text": text, "ago": f"{gap/3600:.1f} 小时前",
                "live": False, "kind": "idle"}

    if live_tool:
        icon, text = TOOL_CN.get(live_tool, ("⚙️", f"在做 {live_tool}"))
        return {"icon": icon, "text": text, "ago": f"{int(live_gap)} 秒前",
                "live": False, "kind": "idle"}

    return {"icon": "🌙", "text": "安安静静的，没在做什么", "ago": "—",
            "live": False, "kind": "idle"}


def _stars() -> list[dict]:
    """她的记忆，全部拿出来——做星空用。清晰的在里圈，淡的飘到外面。"""
    rows = _db(
        PLUG / "moments.db",
        "select id, ts, text, nick, importance, weight, hits, archived"
        " from moments order by id",
    )
    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "time": datetime.fromtimestamp(r[1]).strftime("%m-%d %H:%M"),
            "text": (r[2] or "")[:160],
            "nick": r[3] or "",
            "importance": round(float(r[4] or 0.5), 2),
            "weight": round(float(r[5] or 1.0), 2),
            "hits": int(r[6] or 0),
            "archived": bool(r[7]),
        })
    return out


def overview() -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    asleep = (HOME / "睡").is_file()
    sleep_hours = 0.0
    if asleep:
        try:
            sleep_hours = round((time.time() - (HOME / "睡").stat().st_mtime) / 3600, 1)
        except Exception:  # noqa: BLE001
            pass

    g = _db(PLUG / "growth.db",
            "select xp, chat, remember, shared, diary from growth where id=1")
    xp, chat, rem, shared, diary = g[0] if g else (0, 0, 0, 0, 0)

    LEVELS = [(0, "刚孵出来的小鱼"), (100, "小鲸鱼"), (400, "翘尾巴的鲸"),
              (1200, "成年鲸"), (3000, "鲸王"), (8000, "传说里的鲸")]
    level, base, nxt = LEVELS[0][1], 0, 0
    for need, nm in LEVELS:
        if xp >= need:
            level, base = nm, need
        else:
            nxt = need
            break
    progress = 100 if not nxt else int((xp - base) * 100 / max(1, nxt - base))

    mem = _db(PLUG / "moments.db",
              "select id, ts, text, weight from moments where archived=0 order by weight desc limit 8")
    mem_rows = [{"id": r[0],
                 "time": datetime.fromtimestamp(r[1]).strftime("%m-%d %H:%M"),
                 "text": r[2], "weight": round(float(r[3] or 1), 2)} for r in mem]
    total = _db(PLUG / "moments.db", "select count(*) from moments")
    live = len(mem_rows)
    allc = total[0][0] if total else 0

    notes = []
    nd = HOME / "notes"
    if nd.is_dir():
        for p in sorted(nd.glob("*.md"), reverse=True)[:10]:
            notes.append({"name": p.name,
                          "time": datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M"),
                          "path": str(p.relative_to(HOME))})

    conv = []
    cf = HOME / "CONVERSATION.md"
    if cf.is_file():
        for ln in cf.read_text("utf-8", errors="replace").splitlines()[-25:]:
            ln = ln.strip()
            if not ln:
                continue
            # [10-30 15:22] 私聊｜我：xxx
            t = scene = who = ""
            body = ln
            if ln.startswith("[") and "]" in ln:
                t, rest = ln[1:].split("]", 1)
                body = rest.strip()
                if "｜" in body:
                    scene, body = body.split("｜", 1)
                if "：" in body:
                    who, body = body.split("：", 1)
            conv.append({"t": t, "scene": scene, "who": who, "text": body.strip()[:200]})
    conv.reverse()

    audit = []
    af = PLUG / "audit.jsonl"
    if af.is_file():
        for ln in af.read_text("utf-8", errors="replace").splitlines()[-12:]:
            try:
                d = json.loads(ln)
                audit.append({"ts": (d.get("ts") or "")[5:16],
                              "action": d.get("action", ""),
                              "ok": d.get("ok", True),
                              "note": str(d.get("note") or "")[:80]})
            except Exception:  # noqa: BLE001
                continue
    audit.reverse()

    return {
        "now": now, "home": str(HOME), "asleep": asleep, "sleep_hours": sleep_hours,
        "level": level, "xp": xp, "progress": progress,
        "mem_live": live, "mem_archived": max(0, allc - live),
        "note_count": len(list(nd.glob("*.md"))) if nd.is_dir() else 0,
        "counts": {"chat": chat, "remember": rem, "shared": shared, "diary": diary},
        "tree": _tree(HOME), "notes": notes, "conv": conv,
        "mem": mem_rows, "audit": audit, "travel": _travel(),
        "stars": _stars(), "doing": _doing(),
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 安静点
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if u.path == "/api/overview":
            try:
                return self._send(200, json.dumps(overview(), ensure_ascii=False).encode())
            except Exception as e:  # noqa: BLE001
                return self._send(500, json.dumps({"error": str(e)}, ensure_ascii=False).encode())
        if u.path == "/api/file":
            p = _safe((q.get("path") or [""])[0])
            if not p or not p.is_file():
                return self._send(404, json.dumps({"error": "没有这个文件"}, ensure_ascii=False).encode())
            return self._send(200, json.dumps(
                {"name": p.name, "content": _read_text(p)},
                ensure_ascii=False).encode())
        self._send(404, b'{"error":"404"}')


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
    host = os.environ.get("XY_HOST", "127.0.0.1")
    srv = ThreadingHTTPServer((host, port), H)
    print(f"小鱼的家看板: http://{host}:{port}  (home={HOME})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
