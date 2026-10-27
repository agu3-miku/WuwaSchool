# -*- coding: utf-8 -*-
"""
WuwaSchool · 呜哇校园
------------------------------------------------------------------
一个在命令行里过的同人高中校园模拟游戏。
  · 每按一次回车 = 进入下一天，随机触发事件并做选择
  · 输入 save 存档 / quit 退出 / graph 导出当前事件链图
  · 角色与事件全部外置为同路径下的 JSON，主程序只负责调度
  · mods/ 目录里的 JSON 会自动加载，并在下次启动时再次加载（异常单条跳过，绝不炸档）

依赖：Python 3.9+，标准库而已。
可选：系统装有 graphviz 的 `dot`，则会输出事件链 PNG；没有则退化为 ASCII 文本图。
"""
import json
import os
import random
import re
import sys
from datetime import date

# ═══════════════ 路径约定 ═══════════════
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = BASE
MODS_DIR = os.path.join(BASE, "mods")
SAVE_FILE = os.path.join(BASE, "wuwa_save.json")
CHAR_FILE = os.path.join(DATA_DIR, "characters.json")
EVENT_FILE = os.path.join(DATA_DIR, "events.json")
CHAIN_FILE = os.path.join(DATA_DIR, "chains.json")
GRAPH_DIR = os.path.join(BASE, "graphs")

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
SEASON_CN = ["春", "夏", "秋", "冬"]

# ═══════════════ 工具 ═══════════════
def esc(s: str) -> str:
    """把任意字符串处理成 DOT 安全的 label：引号与反斜杠转义，换行保留。"""
    return s.replace("\\", "\\\\").replace('"', '\\"')

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, int(round(v))))

def ask(prompt, choices, default=None):
    """choices: dict{显示用key: 返回值}。输错就重问。直接回车走 default。"""
    keys = list(choices)
    hint = "/".join(keys)
    if default is not None:
        hint += f"（回车={default}）"
    while True:
        try:
            raw = input(f"  › {prompt} [{hint}] ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return choices.get(default) if default is not None else None
        if raw == "" and default is not None:
            return choices[default]
        if raw in choices:
            return choices[raw]
        print("    ← 没看懂，再选一次～")

def log(msg):
    print(msg)

# ═══════════════ 数据容器（纯数据壳，不含调度逻辑）═══════════════
class Character:
    __slots__ = ("id", "name", "title", "color", "style", "quote", "base_aff", "aff",
                 "aff_stage", "first_meet", "flags")
    def __init__(self, d):
        d = {k.replace("-", "_"): v for k, v in d.items()}  # 允许 kebab-case
        self.id = str(d["id"]).strip()
        self.name = str(d.get("name", self.id)).strip() or self.id
        self.title = str(d.get("title", ""))
        self.color = str(d.get("color", "#888888"))
        self.style = str(d.get("style", ""))
        self.quote = str(d.get("quote", ""))
        self.base_aff = clamp(int(d.get("base_aff", 0)))
        self.aff = self.base_aff
        self.aff_stage = 0
        self.first_meet = False
        self.flags = set()

    STAGES = [
        (0,  "擦肩而过"),
        (20, "点头之交"),
        (40, "放学搭子"),
        (60, "心跳是公开秘密"),
        (85, "故事快要写完了"),
    ]
    ENDING_STAGE = 85  # 达到此值才允许收尾专属结局
    @classmethod
    def stage_of(cls, aff):
        n = 0
        for t, _ in cls.STAGES:
            if aff >= t:
                n = t
        return n

    def stage_name(self):
        name = dict(self.STAGES).get(self.aff_stage, "？")
        return f"{name}（{self.aff_stage}）"

    def bump(self, delta, reason=""):
        if delta == 0:
            return 0
        old = self.aff
        self.aff = clamp(self.aff + delta)
        self.aff_stage = self.stage_of(self.aff)
        if reason and abs(delta) >= 8:
            log(f"    ✦ {self.name} 好感 {'↑' if delta>0 else '↓'}{abs(delta)} → {self.aff}  「{reason}」")
        return self.aff - old

    def bar(self, w=14):
        f = self.aff / 100
        filled = int(f * w)
        head = "◆" if self.aff >= 85 else ("●" if self.aff >= 40 else "○")
        return f"{head} {'█'*filled}{'░'*(w-filled)} {self.aff:>3}"

    def to_dict(self):
        return {"id": self.id, "aff": self.aff, "first_meet": self.first_meet,
                "flags": sorted(self.flags)}

    @classmethod
    def from_dict(cls, d):
        c = cls(d)
        c.aff = clamp(int(d.get("aff", c.base_aff)))
        c.aff_stage = cls.stage_of(c.aff)
        c.first_meet = bool(d.get("first_meet", False))
        c.flags = set(str(f) for f in d.get("flags", []))
        return c


class Event:
    __slots__ = ("id", "kind", "owner", "title", "text", "day_min", "day_max",
                 "weight", "once", "req_flags", "block_flags", "cost_hp",
                 "cost_stam", "cost_str", "effects", "next_on", "set_flags",
                 "unlock_chain", "hidden")
    def __init__(self, d):
        d = {k.replace("-", "_"): v for k, v in d.items()}
        self.id = str(d["id"]).strip()
        self.kind = str(d.get("kind", "encounter"))        # public / encounter / weekend / chain
        self.owner = d.get("owner")                         # None 表示全校公共事件
        self.title = str(d.get("title", self.id))
        self.text = str(d.get("text", ""))
        self.day_min = int(d.get("day_min", 1))
        self.day_max = int(d.get("day_max", 9999))
        self.weight = float(d.get("weight", 1.0))
        self.once = bool(d.get("once", False))
        self.req_flags = [str(f) for f in d.get("req_flags", [])]
        self.block_flags = [str(f) for f in d.get("block_flags", [])]
        c = d.get("cost", {})
        if not isinstance(c, dict):
            c = {}
        self.cost_hp = int(c.get("hp", 0))
        self.cost_stam = int(c.get("stam", 0))
        self.cost_str = int(c.get("str", 0))
        self.effects = d.get("effects", [])                 # [{target, aff, hp, stam, str, reason}]
        self.next_on = d.get("next_on", {})                 # {choice_key: next_event_id}
        self.set_flags = [str(f) for f in d.get("set_flags", [])]
        self.unlock_chain = d.get("unlock_chain")           # 触发后解锁的结局链 id
        self.hidden = bool(d.get("hidden", False))

    def available(self, day, flags, day_of_week, used_once):
        if self.id in used_once and self.once:
            return False
        if not (self.day_min <= day <= self.day_max):
            return False
        if self.hidden:
            return False
        for f in self.req_flags:
            if f not in flags:
                return False
        for f in self.block_flags:
            if f in flags:
                return False
        if self.kind == "weekend" and day_of_week not in (5, 6):
            return False
        if self.kind == "chain" and self.owner is None:
            return False
        return True

    def affordable(self, hp, stam, str_):
        return hp - self.cost_hp >= 0 and stam - self.cost_stam >= 0 and str_ - self.cost_str >= 0

    def apply(self, game, choice_key=None, quiet=False):
        """执行代价 + 效果 + 后置标记，返回文本描述列表。"""
        lines = []
        game.hp -= self.cost_hp
        game.stam -= self.cost_stam
        game.str -= self.cost_str
        if self.cost_hp: lines.append(f"健康 -{self.cost_hp}")
        if self.cost_stam: lines.append(f"体力 -{self.cost_stam}")
        if self.cost_str: lines.append(f"压力 -{self.cost_str}（其实是硬扛）")

        chosen = None
        if choice_key and isinstance(self.effects, dict):
            chosen = self.effects.get(choice_key, self.effects.get("*", []))
        elif isinstance(self.effects, dict):
            chosen = self.effects.get("*", [])
        if chosen is None:
            chosen = self.effects

        for eff in chosen if isinstance(chosen, list) else []:
            if not isinstance(eff, dict):
                continue
            tgt = eff.get("target", self.owner)
            if tgt == "@self":
                game.hp = clamp(game.hp + int(eff.get("hp", 0)))
                game.stam = clamp(game.stam + int(eff.get("stam", 0)))
                game.str = clamp(game.str + int(eff.get("str", 0)))
                continue
            if tgt == "@all":
                d = int(eff.get("aff", 0))
                for c in game.chars.values():
                    c.bump(d, eff.get("reason", self.title))
                if d:
                    _who = "全员" if tgt == "@all" else (game.chars[tgt].name if tgt in game.chars else str(tgt))
                    lines.append(f"{_who} 好感 {'+' if d>0 else ''}{d}")
                continue
            c = game.chars.get(str(tgt))
            if not c:
                continue
            d = int(eff.get("aff", 0))
            c.bump(d, eff.get("reason", self.title))
            c.flags.update(str(f) for f in eff.get("set_flags", []))
            if d and not quiet:
                lines.append(f"{c.name} 好感 {'+' if d>0 else ''}{d}")

        for f in self.set_flags:
            game.flags.add(f)
        if self.owner:
            game.chars[self.owner].flags.update(self.set_flags)
        if self.unlock_chain:
            game.chains_active.add(str(self.unlock_chain))
        return lines

    def choices(self):
        """返回 {显示key: 内部key}，没有选项就是纯叙事（自动推进）。"""
        if isinstance(self.effects, dict) and not isinstance(self.effects, list):
            base = {k: k for k in self.effects if k != "*"}
            if base:
                return base
        return {}


class Chain:
    """结局链：一串按序解锁的事件。progress 由 chain_progress[id] 驱动。"""
    __slots__ = ("id", "owner", "name", "description", "color", "nodes", "reward")
    def __init__(self, d):
        d = {k.replace("-", "_"): v for k, v in d.items()}
        self.id = str(d["id"]).strip()
        self.owner = d.get("owner")
        self.name = str(d.get("name", self.id))
        self.description = str(d.get("description", ""))
        self.color = str(d.get("color", "#C77DFF"))
        self.nodes = [str(n).strip() for n in d.get("nodes", [])]
        self.reward = d.get("reward", {})      # 通关奖励 {aff, hp, stam, str, flags}

    def current_event_id(self, prog):
        if prog <= 0:
            return self.nodes[0] if self.nodes else None
        if prog >= len(self.nodes):
            return None
        return self.nodes[prog]


# ═══════════════ 加载层 ═══════════════
class ModLoader:
    """负责把 JSON 吃进来。任何单条错误只警告并跳过，保证坏 mod 不炸档。"""

    def __init__(self):
        self.chars = {}
        self.events = {}
        self.chains = {}
        self.load_order = []          # (来源路径, 类型, id) 用于展示与去重
        self.warnings = []

    # ---------- 通用 ----------
    def _read_json(self, path):
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            self.warnings.append(f"{path} 读取失败，已跳过：{e}")
            return None

    def _register(self, path, kind, obj):
        self.load_order.append((path, kind, obj.id))

    def _load_file(self, path):
        data = self._read_json(path)
        if data is None:
            return
        # 支持两种写法：数组 [...]，或单对象 {...}（type 决定类型）
        if isinstance(data, dict):
            items = [data]
        elif isinstance(data, list):
            items = data
        else:
            self.warnings.append(f"{path} 根节点必须是对象或数组，已跳过")
            return
        for item in items:
            if not isinstance(item, dict) or "id" not in item:
                self.warnings.append(f"{path} 里有一条缺 id 的记录，已跳过")
                continue
            try:
                self._load_one(path, item)
            except Exception as e:
                self.warnings.append(f"{path} › {item.get('id')} 解析失败，已跳过：{e}")

    def _load_one(self, path, item):
        kind = str(item.get("type", "")).lower()
        if kind in ("character", "char", "角色"):
            c = Character(item)
            if c.id in self.chars:
                self.chars[c.id] = c           # 后加载覆盖（mod 可覆盖内置）
            else:
                self.chars[c.id] = c
            self._register(path, "角色", c)
        elif kind in ("chain", "结局链", "结局"):
            ch = Chain(item)
            self.chains[ch.id] = ch
            self._register(path, "结局链", ch)
        else:  # event / 公共事件 / weekend / 默认都当事件
            e = Event(item)
            self.events[e.id] = e
            self._register(path, "事件", e)

    def scan(self):
        """启动时调用：先内置文件，再 mods/，全部吃进来。"""
        self.chars.clear(); self.events.clear(); self.chains.clear()
        self.load_order.clear(); self.warnings.clear()
        for f in (CHAR_FILE, EVENT_FILE, CHAIN_FILE,
                   os.path.join(DATA_DIR, "chain_events.json")):
            self._load_file(f)
        if os.path.isdir(MODS_DIR):
            for name in sorted(os.listdir(MODS_DIR)):
                if name.lower().endswith(".json"):
                    self._load_file(os.path.join(MODS_DIR, name))
        # 校验 chain 引用的事件是否存在
        for ch in self.chains.values():
            miss = [n for n in ch.nodes if n not in self.events]
            if miss:
                self.warnings.append(
                    f"结局链 {ch.id}（{ch.name}）指向了不存在的事件：{', '.join(miss)}；该链可能无法推进到结尾。")

    def summary(self):
        parts = [f"角色 {len(self.chars)}", f"事件 {len(self.events)}", f"结局链 {len(self.chains)}"]
        return " · ".join(parts)


# ═══════════════ 周末行程表 ═══════════════
WEEKEND_PLANS = [
    {
        "id": "lib_study",
        "name": "图书馆 · 死磕错题本",
        "desc": "安静、空调、咖啡续杯。最省心，也最无聊。",
        "cost": {"stam": 12, "str": -10},
        "gain": {"hp": 4, "str": -8},
        "aff": {"@all": 2},
        "text": "图书管理员维里奈把指路灯调到最暗，你翻开错题本。翻到第三页时，有人悄悄在你旁边坐下。",
    },
    {
        "id": "rooftop",
        "name": "天台 · 偷来的午休",
        "desc": "晒太阳、听歌、把便当盒摆成方阵。",
        "cost": {"stam": 6},
        "gain": {"hp": 10, "str": -14},
        "aff": {},
        "text": "天台的风把校服袖子鼓成帆。远处操场有人在练剑道，金属相撞的声音很脆。今天什么都不想做，也挺好。",
    },
    {
        "id": "cram_school",
        "name": "补习班 · 最后一个进门的座位",
        "desc": "压力换成绩，也换一脸倦色。",
        "cost": {"stam": 20, "str": 14},
        "gain": {"str": -4},
        "aff": {"@all": -1},
        "text": "白芷把讲义拍到你桌上：『第 17 题，三种解法，你自己挑最痛的那个背。』黑板上的粉笔灰落了一肩。",
    },
    {
        "id": "club_dojo",
        "name": "道场 · 和散华对打一组",
        "desc": "体力杀手，但靠近她最快的路。",
        "cost": {"stam": 34, "hp": 4},
        "gain": {"hp": -2},
        "aff": {"散华": 6},
        "text": "散华的竹刀压在你肩口，声音不大：『收着力气躲，是打不赢的。』你握紧了柄。",
        "req_flags": [],
        "owner": "散华",
    },
    {
        "id": "greenhouse",
        "name": "花房 · 帮维里奈换盆",
        "desc": "体力中等，心情回满。",
        "cost": {"stam": 16},
        "gain": {"hp": 8, "str": -10},
        "aff": {"维里奈": 6},
        "text": "维里奈把一株快要蔫掉的穗子递给你：『根还活着，你轻点，它怕痒。』土腥气里全是午后阳光的味道。",
        "owner": "维里奈",
    },
    {
        "id": "broadcast_room",
        "name": "广播室 · 秧秧的午间点歌台",
        "desc": "几乎不累，好感稳定升温。",
        "cost": {"stam": 8},
        "gain": {"str": -6},
        "aff": {"秧秧": 5},
        "text": "秧秧把麦克风转过来，眼睛弯着：『点歌栏写着你的名字诶——这首，算我私心的。』杂音里吉他前奏响起来。",
        "owner": "秧秧",
    },
    {
        "id": "infirmary",
        "name": "保健室 · 白芷的强制静养",
        "desc": "回血大户，顺便被她念一顿。",
        "cost": {"stam": 4},
        "gain": {"hp": 22, "str": -12},
        "aff": {"白芷": 4},
        "text": "白芷把帘子拉上，体温计塞过来那一下很凉：『不用我说第二次吧——把眼睛闭上。』",
        "owner": "白芷",
    },
    {
        "id": "night_walk",
        "name": "放学后的河堤 · 随便走走",
        "desc": "随机撞见一个人。",
        "cost": {"stam": 10},
        "gain": {"hp": 6, "str": -8},
        "aff": {},
        "text": "河堤的灯一盏一盏亮起来，影子被拉得很长。你还没想好往哪走，身后有人喊了你的名字。",
    },
]

def run_weekend_plan(game, plan):
    """执行周末行程，返回叙述文本行。"""
    lines = [f"\n  ▸ 周末行程：{plan['name']}"]
    lines.append(f"    {plan['desc']}")
    lines.append(f"    {plan.get('text','')}")
    cost = plan.get("cost", {})
    gain = plan.get("gain", {})
    hp0, st0, sr0 = game.hp, game.stam, game.str
    game.stam -= int(cost.get("stam", 0))
    game.hp -= int(cost.get("hp", 0))
    game.str -= int(cost.get("str", 0))
    game.hp += int(gain.get("hp", 0))
    game.stam += int(gain.get("stam", 0))
    game.str += int(gain.get("str", 0))
    for tgt, d in plan.get("aff", {}).items():
        if tgt == "@all":
            for c in game.chars.values():
                c.bump(d, plan["name"])
        elif tgt in game.chars:
            game.chars[tgt].bump(d, plan["name"])
    lines.append(f"    体力 {st0}→{game.stam}   健康 {hp0}→{game.hp}   压力 {sr0}→{game.str}")
    return lines


# ═══════════════ 游戏世界 ═══════════════
class Game:
    def __init__(self, loader):
        self.loader = loader
        self.chars = {cid: Character.from_dict({s: getattr(c, s)
                                               for s in Character.__slots__})
                      for cid, c in loader.chars.items()}
        self.flags = set()
        self.chain_progress = {cid: 0 for cid in loader.chains}
        self.chains_active = set()          # 已被事件解锁、可推进的链
        self.chains_cleared = set()
        self.used_once = set()
        self.day = 1
        self.term = 1
        self.hp = 80
        self.str = 20
        self.term_start_hp = 80
        self._stam = self.stam_max()      # 当前体力（每天晨间回满，受健康上限约束）
        self.roll_seed = random.randrange(1 << 30)

        self.history = []                  # 最近事件 id，用于降重
        self.log_lines = []                # 今日结算要打印的变动
        self.last_choice = None

    # ---------- 派生属性 ----------
    def stam_max(self):
        return clamp(int(50 + self.hp * 0.5))

    @property
    def stam(self):
        return self._stam
    @stam.setter
    def stam(self, v):
        self._stam = clamp(v, 0, self.stam_max())

    def weekday(self):
        return (self.day - 1) % 7

    def is_weekend(self):
        return self.weekday() in (5, 6)

    def season(self):
        return SEASON_CN[((self.day - 1) // 30) % 4]

    # ---------- 存档 ----------
    def save(self):
        payload = {
            "version": 2,
            "day": self.day, "term": self.term,
            "hp": self.hp, "str": self.str,
            "term_start_hp": self.term_start_hp,
            "roll_seed": self.roll_seed,
            "flags": sorted(self.flags),
            "chains_active": sorted(self.chains_active),
            "chains_cleared": sorted(self.chains_cleared),
            "chain_progress": self.chain_progress,
            "used_once": sorted(self.used_once),
            "chars": [c.to_dict() for c in self.chars.values()],
        }
        tmp = SAVE_FILE + ".tmp"
        import sys as _s
        with open("/tmp/save_diag.txt","w") as _d:
            _d.write(f"cwd={os.getcwd()}\nSAVE_FILE={SAVE_FILE}\ntmp={tmp}\n")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SAVE_FILE)
        return SAVE_FILE

    @classmethod
    def load(cls, loader):
        if not os.path.isfile(SAVE_FILE):
            return None
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            p = json.load(f)
        g = cls(loader)
        g.day = int(p.get("day", 1))
        g.term = int(p.get("term", 1))
        g.hp = clamp(int(p.get("hp", 80)))
        g.str = clamp(int(p.get("str", 20)))
        g.term_start_hp = clamp(int(p.get("term_start_hp", 80)))
        g.roll_seed = int(p.get("roll_seed", g.roll_seed))
        g.flags = set(str(f_) for f_ in p.get("flags", []))
        g.chains_active = set(str(c) for c in p.get("chains_active", []))
        g.chains_cleared = set(str(c) for c in p.get("chains_cleared", []))
        g.chain_progress = {str(k): int(v) for k, v in p.get("chain_progress", {}).items()}
        g.used_once = set(str(e) for e in p.get("used_once", []))
        # 用存档里的角色数据覆盖内置默认值
        for cd in p.get("chars", []):
            cid = str(cd.get("id"))
            if cid in g.chars:
                g.chars[cid] = Character.from_dict(cd)
            else:  # 存档里有而当前 json 没有的角色（旧档/mod 被移除）→ 保留
                g.chars[cid] = Character.from_dict(cd)
        return g

    # ---------- 事件挑选 ----------
    def _candidates(self, kind):
        allf = self.flags | set(f"chain:{c}" for c in self.chains_cleared)
        for e in self.loader.events.values():
            if e.kind != kind:
                continue
            if not e.available(self.day, allf, self.weekday(), self.used_once):
                continue
            yield e

    def _weighted_pick(self, pool):
        pool = list(pool)
        if not pool:
            return None
        # 降重：近期触发过的权重打折
        w = []
        for e in pool:
            wt = e.weight
            recent = self.history.count(e.id)
            wt *= 0.35 ** recent
            if not e.affordable(self.hp, self.stam, self.str):
                wt *= 0.05
            w.append((wt, e))
        total = sum(x[0] for x in w)
        if total <= 0:
            return None
        r = random.random() * total
        for wt, e in w:
            r -= wt
            if r <= 0:
                return e
        return w[-1][1]

    def pick_chain_event(self):
        """优先推进已激活的结局链；返回 (event, chain_id or None)。"""
        for cid in list(self.chains_active):
            if cid in self.chains_cleared:
                continue
            ch = self.loader.chains.get(cid)
            if not ch:
                continue
            prog = self.chain_progress.get(cid, 0)
            eid = ch.current_event_id(prog)
            e = self.loader.events.get(eid)
            if e and e.available(self.day, self.flags, self.weekday(), self.used_once) and e.affordable(self.hp, self.stam, self.str):
                return e, cid
            # 当前节点还没条件触发，先放着，不抢别人的戏
        return None, None

    # ---------- 一天 ----------
    def new_day(self):
        self.log_lines.clear()
        self.history = self.history[-9:]
        self.stam = self.stam_max()
        # 夜间回复：健康越高、压力越低，睡得越香
        rec = int(6 + (self.hp - 50) / 100 * 8 - self.str / 100 * 5)
        self.hp = clamp(self.hp + max(-3, rec))
        self.str = clamp(self.str - 4)

        header = (f"\n{'═'*56}\n"
                  f"  📅  第 {self.day} 天   {WEEKDAY_CN[self.weekday()]}"
                  f"   · 第{self.term}学期 · {self.season()}季"
                  f"   · 体力上限 {self.stam_max()}\n"
                  f"   ❤ 健康 {self.hp}   ⚡体力 {self.stam}   🌀压力 {self.str}")
        log(header)

        if self.is_weekend():
            self._run_weekend()
        else:
            self._run_weekday()

        self._end_of_day()

    def _run_weekend(self):
        plans = [p for p in WEEKEND_PLANS
                 if (not p.get("owner") or p["owner"] in self.chars)
                 and self.stam - int(p.get("cost", {}).get("stam", 0)) >= 0]
        if not plans:
            log("  今天哪儿也去不了，就在教室趴了一整天。")
            return
        keyed = {f"{i+1}": p for i, p in enumerate(plans)}
        if len(keyed) == 1:                       # 只有一个去处，直接去，省一次输入
            p = next(iter(keyed.values()))
            log(f"  周末，你去了 → {p['name']}")
        else:
            log("  周末！想去哪儿？")
            log("\n".join(f"    {k}. {p['name']}  （体力{p.get('cost',{}).get('stam','-')}）{p['desc']}"
                         for k, p in keyed.items()))
            p = ask("选个行程吧", keyed)
            if p is None:                         # 回车/EOF 且只有一个默认之外的选项 → 随机挑一个
                p = random.choice(list(keyed.values()))
                log(f"    ……那就随缘，去了 {p['name']}。")
        for ln in run_weekend_plan(self, p):
            log(ln)

    def _run_weekday(self):
        # 1) 结局链优先：先看已激活的链，再看能不能新开一条
        ev, cid = self.pick_chain_event()
        if ev is None and not self.chains_active:
            # 兜底：链的首个节点若无条件门槛，允许作为稀有偶遇自然开启
            opener = []
            for c in self.loader.chains.values():
                if c.id in self.chains_cleared:
                    continue
                eid = c.current_event_id(0)
                e = self.loader.events.get(eid) if eid else None
                if e and not e.req_flags and e.available(self.day, self.flags,
                                                        self.weekday(), self.used_once):
                    opener.append(e)
            ev = self._weighted_pick(opener)
            if ev:
                cid = next((c.id for c in self.loader.chains.values()
                            if c.nodes and c.nodes[0] == ev.id), None)
                if cid:
                    self.chains_active.add(cid)
        if ev:
            self._play(ev, chain_id=cid)
            if cid:
                self.chain_progress[cid] = self.chain_progress.get(cid, 0) + 1
                ch = self.loader.chains[cid]
                if self.chain_progress[cid] >= len(ch.nodes):
                    self._clear_chain(cid)
            return

        # 2) 公共事件
        pub = self._weighted_pick(self._candidates("public"))
        if pub and random.random() < 0.62:
            self._play(pub)

        # 3) 1~2 次偶遇
        for _ in range(random.choice([1, 1, 1, 2])):
            enc = self._weighted_pick(self._candidates("encounter"))
            if enc:
                self._play(enc)
            if self.stam <= 12:
                break

    def _play(self, ev, chain_id=None):
        self.history.append(ev.id)
        if ev.once:
            self.used_once.add(ev.id)
        prefix = "  🔗【结局链】" if chain_id else ("  📢" if ev.kind == "public" else f"  💬 {self.chars[ev.owner].name if ev.owner and ev.owner in self.chars else '?'}")
        log(f"\n{prefix} {ev.title}")
        if ev.text:
            log(f"    {ev.text}")
        if ev.cost_stam or ev.cost_hp or ev.cost_str:
            log(f"    这一段的代价：体力 {ev.cost_stam}  健康 {ev.cost_hp}  压力 {ev.cost_str}")

        choices = ev.choices()
        if choices:
            ck = ask("你要怎么做", choices, default=list(choices)[0])
            self.last_choice = ck
        else:
            ck = None
            self.last_choice = None

        before = {c.id: c.aff for c in self.chars.values()}
        lines = ev.apply(self, ck)
        delta = {c.id: c.aff - before[c.id] for c in self.chars.values()}
        self.log_lines.append((ev, delta))
        if lines:
            for ln in lines:
                log(f"    › {ln}")
        # 触发后续事件（同一天内链式演出）
        nxt = (ev.next_on or {}).get(ck) or (ev.next_on or {}).get("*")
        if nxt:
            nxt_ev = self.loader.events.get(nxt)
            if nxt_ev and nxt_ev.available(self.day, self.flags, self.weekday(), self.used_once):
                log(f"    ……事情还没完。")
                self._play(nxt_ev, chain_id=chain_id)

    def _clear_chain(self, cid):
        ch = self.loader.chains.get(cid)
        if not ch or cid in self.chains_cleared:
            return
        self.chains_cleared.add(cid)
        self.chains_active.discard(cid)
        rw = ch.reward
        # 结局收尾：把好感钉进「结局」阶段，避免卡在 84
        if ch.owner and ch.owner in self.chars:
            self.chars[ch.owner].aff = max(self.chars[ch.owner].aff, Character.ENDING_STAGE)
            self.chars[ch.owner].aff_stage = Character.ENDING_STAGE
        self.hp = clamp(self.hp + int(rw.get("hp", 0)))
        self.stam = clamp(self.stam + int(rw.get("stam", 0)))
        self.str = clamp(self.str + int(rw.get("str", 0)))
        for f in rw.get("flags", []):
            self.flags.add(str(f))
        # 全员奖励（字段写成 "@all_aff" 以免和角色专属 aff 混淆）
        for c in self.chars.values():
            all_d = int(rw.get("@all_aff", 0))
            if all_d:
                c.bump(all_d, f"结局《{ch.name}》")
            if ch.owner and c.id == ch.owner:
                c.bump(int(rw.get("aff", 0)), f"结局《{ch.name}》")
        log(f"\n  {'🏆'*3}  结局达成：《{ch.name}》")
        log(f"    {ch.description}")
        if ch.owner and ch.owner in self.chars:
            c = self.chars[ch.owner]
            log(f"    ✨ {c.name} 好感 {c.aff} · {c.stage_name()}")
        if rw:
            log(f"    通关回礼：{rw}")

    def _end_of_day(self):
        self.day += 1
        if (self.day - 1) % 7 == 0:
            self._weekly_report()
        if self.day > 1 and (self.day - 1) % 30 == 0:
            self.term += 1
            self.term_start_hp = self.hp
            log(f"\n  📘 第{self.term-1}学期结束。成绩单塞进了抽屉，"
                f"下一学期从健康 {self.hp} 开始。")

    def _weekly_report(self):
        log(f"\n  ── 本周好感速写 ──")
        for c in sorted(self.chars.values(), key=lambda c: c.aff, reverse=True):
            log(f"    {c.bar()}  {c.name} · {c.stage_name()}")
        active = [self.loader.chains[c].name for c in self.chains_active
                  if c not in self.chains_cleared]
        if active:
            log(f"    进行中的故事线：{'、'.join(active)}")

    def status(self):
        log(f"\n  ── 状态 ──────────────────────────")
        log(f"   ❤{self.hp}  ⚡{self.stam}/{self.stam_max()}  🌀{self.str}   "
            f"第{self.day}天 {WEEKDAY_CN[self.weekday()]}")
        for c in sorted(self.chars.values(), key=lambda c: c.aff, reverse=True):
            log(f"     {c.bar()}  {c.name} · {c.stage_name()}")
        if self.chains_active:
            log("   故事线：" + "、".join(self.loader.chains[c].name
                                      for c in self.chains_active
                                      if c not in self.chains_cleared))

    # ---------- 事件链可视化 ----------
    def build_dot(self, fmt="png"):
        """把所有事件与结局链画成 DOT 图。返回 (dot源码, 产物路径 or None)。"""
        gv = ["digraph WuwaSchoolChain {"]
        gv.append('  rankdir=TB; bgcolor="white"; splines=ortho; nodesep=0.45; ranksep=0.75;')
        gv.append('  graph [fontname="WenQuanYi Micro Hei,Noto Sans CJK SC,sans-serif"];')
        gv.append('  node [fontname="WenQuanYi Micro Hei,Noto Sans CJK SC,sans-serif", shape=box, style="rounded,filled", fontsize=11, penwidth=1.2];')
        gv.append('  edge [fontname="WenQuanYi Micro Hei,Noto Sans CJK SC,sans-serif", fontsize=9, color="#9AA0A6"];')
        gv.append('  labelloc="t"; fontsize=20; label="WuwaSchool · 呜哇校园 事件链图谱";')

        # 角色分区
        owned = {}
        for e in self.loader.events.values():
            if e.kind == "chain":
                owned.setdefault(e.owner or "@world", []).append(e)

        # 普通事件节点
        for e in self.loader.events.values():
            color = "#E8F0FE"
            edge_c = "#5B7DB1"
            if e.kind == "chain":
                color = "#F3E8FF"; edge_c = "#9B59B6"
            elif e.kind == "weekend":
                color = "#FFF4E5"; edge_c = "#E0A040"
            elif e.kind == "public":
                color = "#E5F6EE"; edge_c = "#3FA372"
            cid = f"e_{esc(e.id)}"
            label = f"{esc(e.title)}\\n[{esc(e.kind)}]"
            if e.owner and e.owner in self.chars:
                label = f"{esc(self.chars[e.owner].name)}｜{esc(e.title)}\\n[{esc(e.kind)}]"
            gv.append(f'  {cid} [label="{label}", fillcolor="{color}", color="{edge_c}"];')

        # 结局节点
        for c in self.loader.chains.values():
            nid = f"chain_{esc(c.id)}"
            done = c.id in self.chains_cleared
            prog = self.chain_progress.get(c.id, 0)
            label = f"★ {esc(c.name)}\\n进度 {min(prog, len(c.nodes))}/{len(c.nodes)}"
            if done:
                label += "\\n【已达成】"
            gv.append(f'  {nid} [label="{label}", shape=diamond, style="filled", '
                      f'fillcolor="#FFD54F", color="#C79100", penwidth=2.2];')

        # 普通 next_on 边
        for e in self.loader.events.values():
            for ck, nid in (e.next_on or {}).items():
                if nid in self.loader.events:
                    gv.append(f'  e_{esc(e.id)} -> e_{esc(nid)} [label="{esc(ck)}", color="#7F8C8D"];')

        # 结局链顺序边 + 链到首节点
        for c in self.loader.chains.values():
            nodes = [n for n in c.nodes if n in self.loader.events]
            if not nodes:
                continue
            gv.append(f'  chain_{esc(c.id)} -> e_{esc(nodes[0])} [style=dashed, color="{esc(c.color)}", label="序章"];')
            prev = None
            for n in nodes:
                if prev:
                    gv.append(f'  e_{esc(prev)} -> e_{esc(n)} [color="{esc(c.color)}", penwidth=2, arrowhead=normal];')
                prev = n
            gv.append(f'  e_{esc(nodes[-1])} -> chain_{esc(c.id)} [style=dashed, color="{esc(c.color)}", label="结局"];')

        # 同一天偶遇聚类（让图别太散）
        gv.append('  subgraph cluster_day { label="普通日常（按权重随机偶遇，非固定顺序）"; '
                  'style=filled; fillcolor="#FAFBFD"; color="#DADCE0";')
        for e in self.loader.events.values():
            if e.kind not in ("chain",):
                gv.append(f'    e_{esc(e.id)};')
        gv.append('  }')
        gv.append('}')
        dot_src = "\n".join(gv)

        os.makedirs(GRAPH_DIR, exist_ok=True)
        dot_path = os.path.join(GRAPH_DIR, "event_chain.dot")
        with open(dot_path, "w", encoding="utf-8") as f:
            f.write(dot_src)

        out_path = os.path.join(GRAPH_DIR, f"event_chain.{fmt}")
        dot_bin = os.environ.get("DOT_BIN", "/usr/bin/dot")
        if not os.path.isfile(dot_bin):
            # 兜底：试试 PATH
            import shutil
            dot_bin = shutil.which("dot") or dot_bin
        if os.path.isfile(dot_bin):
            rc = os.system(f'{dot_bin!r} -T{fmt} {dot_path!r} -o {out_path!r} 2>/dev/null')
            if rc == 0:
                return dot_src, out_path
            return dot_src, None
        return dot_src, None

    def print_text_graph(self):
        """没有 dot 时的纯文本降级图。"""
        log("\n  事件链文本图（未安装 graphviz，只显示链与关键节点）：")
        for c in self.loader.chains.values():
            prog = self.chain_progress.get(c.id, 0)
            done = c.id in self.chains_cleared
            mark = "✔" if done else f"{min(prog,len(c.nodes))}/{len(c.nodes)}"
            log(f"    ★ {c.name}  [{mark}]")
            line = []
            for i, nid in enumerate(c.nodes):
                e = self.loader.events.get(nid)
                name = e.title if e else f"(缺:{nid})"
                line.append(f"{'●' if i<prog else '○'}{name}")
            log("      " + " → ".join(line))


# ═══════════════ 主循环 ═══════════════
def title():
    print(r"""
  ╔══════════════════════════════════════════╗
  ║     WuwaSchool  ·  呜哇校园              ║
  ║     鸣潮同人 · 高中校园文字模拟          ║
  ║     回车=下一天   save=存档   status=状态 ║
  ║     graph=导出事件链图   quit=退出        ║
  ╚══════════════════════════════════════════╝
""")

def main():
    title()
    loader = ModLoader()
    loader.scan()
    print(f"  📦 已加载：{loader.summary()}")
    if loader.warnings:
        print(f"  ⚠ {len(loader.warnings)} 条 mod 解析警告（已跳过，不影响游玩）：")
        for w in loader.warnings:
            print(f"      · {w}")

    game = None
    if os.path.isfile(SAVE_FILE):
        g = Game.load(loader)
        print(f"\n  检测到存档：第 {g.day} 天，{' / '.join(c.name for c in g.chars.values())}")
        choice = ask("要读档还是开新档", {"读档": "load", "新游戏": "new", "看规范": "doc"}, default="new")
    else:
        choice = "new"
    if choice == "doc":
        md = os.path.join(BASE, "IMPORT_FORMAT.md")
        print("\n  —— IMPORT_FORMAT.md 前 60 行 ——")
        try:
            with open(md, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 60: break
                    print("  " + line.rstrip())
        except FileNotFoundError:
            print("    （没找到 IMPORT_FORMAT.md）")
        return
    elif choice == "load":
        game = Game.load(loader)
        print(f"  ↻ 读档成功，从第 {game.day} 天继续。")
    else:
        game = Game(loader)

    game.status()
    print("\n  开始——每按一次回车，就是新的一天。")

    while True:
        try:
            cmd = input("\n[回车=下一天] › ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n  先走啦，记得 save。")
            break
        if cmd in ("quit", "q", "exit"):
            if ask("确定退出吗", {"存个档再走": "save", "就这样": "bye"}, default="save") == "save":
                game.save(); print(f"  ✓ 已存档 {game.save()}")
            break
        elif cmd == "save":
            p = game.save(); print(f"  ✓ 已存档 → {p}  （下次启动自动读档）"); continue
        elif cmd in ("status", "s"):
            game.status(); continue
        elif cmd in ("graph", "g"):
            src, out = game.build_dot()
            if out:
                print(f"  ✓ 事件链图已生成 → {out}")
                print("    （同时保留了源文件 graphs/event_chain.dot，可自行改样式重渲染）")
            else:
                print("  ⚠ 没找到 graphviz 的 dot，改用文本图：")
                game.print_text_graph()
            continue
        elif cmd in ("mod", "reload"):
            loader.scan(); game.loader = loader
            print(f"  ↻ 重新扫描 mod：{loader.summary()}")
            continue
        elif cmd == "":
            game.new_day()
        else:
            print("  未知指令。回车=下一天 / save / status / graph / quit")


if __name__ == "__main__":
    main()
