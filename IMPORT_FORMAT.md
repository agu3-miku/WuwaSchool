# WuwaSchool · 呜哇校园 —— 导入文件格式规范（mod 手册）

把 `.json` 文件丢进游戏目录下的 `mods/` 文件夹即可，**启动游戏时自动全部载入**，
无需改任何代码。也可以在游戏标题菜单输入 `3` 查看这份说明。

存档文件（`wuwa_save.json`）也是 JSON，但它由游戏自己读写，**别手动改**。

---

## 0. 最小骨架

```json
{
  "type": "character",   // 或 "event"，必填
  "version": 1,          // 可选，规范版本号
  "author": "你的名字",   // 可选
  "description": "加了谁和什么事件", // 可选
  "characters": [],      // 角色 mod 用这个
  "events": []           // 事件 mod 用这个
}
```

`type` 决定解析方式：

| `type` | 作用 | 必填字段 |
|--------|------|----------|
| `"character"` | 只新增 / 覆盖角色卡 | `characters` |
| `"event"` | 新增事件（可顺带声明角色） | `events` |

一个文件可以只做一件事，也可以混着写（事件包里带个 `characters` 数组最省事）。

---

## 1. 角色卡（`type: "character"`）

```json
{
  "type": "character",
  "characters": [
    {
      "name": "长离",              // 必填，唯一 id，重复则覆盖同名角色
      "title": "语文老师 · 长离",   // 可选，显示在好感面板
      "color": "red",              // 可选：cyan/green/yellow/blue/magenta/red/white
      "bio": "新来的代课老师，粉笔灰落在袖口也不拍。",
      "tags": ["知性", "神秘", "火焰"]
    }
  ]
}
```

- 新增角色初始好感度固定为 **10**，不会破坏已有存档（读档时自动补齐）。
- `color` 只影响命令行里的名字着色；填错会回退成白色，不会崩。
- 想给这个角色写专属事件？另写一个 `type: "event"` 的文件，把事件的
  `"character"` 字段写成 `"长离"` 就行（见下）。

---

## 2. 事件（`type: "event"`）

### 2.1 角色专属事件

```json
{
  "type": "event",
  "characters": ["长离"],          // 可选：顺手声明角色，省得再放一个文件
  "events": [
    {
      "id": "changli_first_class", // 必填，唯一。用作防重复，别和别人撞车
      "character": "长离",          // 必填（公共事件除外），挂到这个角色身上
      "day": [3, 30],              // 可选，[最早天数, 最晚天数]，默认 [1,999]
      "weight": 12,                // 可选，越大越容易被抽中，默认 5
      "req_flag": "met_changli",   // 可选，全局 flag 满足才会出现
      "req_char_flag": "homework_done", // 可选，该角色专属 flag
      "req_hp_over": 40,           // 可选，玩家 health 高于此值才可选/才出现
      "text": "她的课代表把作业本递给你：『老师说，这篇要手写批注。』",
      "choices": [
        {
          "text": "认真写满三页批注（体力 -8，健康 -2）",
          "aff": 8,
          "health": -2,
          "stress": -3,
          "energy": -8,
          "flags": ["met_changli", "homework_done"],
          "char_flags": []
        },
        {
          "text": "只写一句『很有意思』就交（傲一下）",
          "aff": -2,
          "stress": 3,
          "energy": -1
        },
        {
          "text": "下课堵她问书里那句话的出处",
          "aff": 10,
          "health": 0,
          "stress": -2,
          "energy": -3,
          "req_hp_over": 30        // 这个选项单独加了体力门槛
        }
      ]
    }
  ]
}
```

### 2.2 公共事件（不挂角色）

把 `"character"` 字段删掉，事件就会进「全校公共事件」池，
谁都可能被牵扯到，用 `aff_all` 让**所有角色**一起变动：

```json
{
  "type": "event",
  "events": [
    {
      "id": "common_sports_day",
      "day": [14, 999],
      "weight": 8,
      "text": "校运会。全班都在看接力最后一棒，你被推上去递水。",
      "choices": [
        { "text": "冲去终点递水", "aff_all": 3, "energy": -10, "health": -2 },
        { "text": "在场边喊加油", "aff_all": 1, "energy": -4, "stress": -3 }
      ]
    }
  ]
}
```

---

## 3. 字段速查表

### 事件对象

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `id` | string | — | **必填**，唯一标识，防短期重复触发 |
| `character` | string | 无 | 角色名；省略 = 公共事件 |
| `day` | [min, max] | `[1,999]` | 触发天数窗口 |
| `weight` | int | `5` | 抽取权重 |
| `req_flag` | string | 无 | 需玩家 `flags` 里已有该标记 |
| `req_char_flag` | string | 无 | 需该角色 `char_flags` 里已有该标记 |
| `req_hp_over` | int | 无 | 玩家健康值高于此才出现/才可选 |
| `text` | string | — | 事件正文，支持 `\n` |
| `choices` | array | `[]` | 至少 1 项；不满足 `req_hp_over` 的选项会隐藏 |

### 选项对象

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 显示给玩家的选项文案（建议把数值代价写进去） |
| `aff` | int | **该角色**好感度变化，可负 |
| `aff_all` | int | **全部角色**好感度变化，可负 |
| `health` | int | 健康值变化（-100~+100 会被自动夹取） |
| `stress` | int | 压力值变化，越高越累 |
| `energy` | int | 体力变化；体力上限 = `50 + 健康×0.5` |
| `flags` | string[] | 触发后写入**全局**标记，用于事件链 |
| `char_flags` | string[] | 触发后写入**该角色**专属标记 |
| `req_hp_over` | int | 该选项单独的健康门槛（选项会变灰/隐藏） |

> 数值会被自动 `clamp(0,100)`。体力还会被当天的体力上限卡住。

---

## 4. 事件链怎么写（flag 串联）

用 `flags` / `char_flags` 串连续剧情，同一个角色的三段式示例：

```json
{ "id": "cf_1_meet", "character": "长离", "day": [3,999], "weight": 10,
  "text": "……第一次在走廊撞见她，粉笔灰落在袖口。",
  "choices": [
    { "text": "帮她拍掉袖口的灰", "aff": 6, "flags": ["met_changli"], "energy": -1 }
  ] },
{ "id": "cf_2_follow", "character": "长离", "day": [4,999], "weight": 10,
  "req_flag": "met_changli",
  "text": "她认出你了：『昨天那个不怕粉笔灰的。』",
  "choices": [
    { "text": "装傻笑一下", "aff": 4 },
    { "text": "承认是自己", "aff": 8, "char_flags": ["changli_knows_name"] }
  ] },
{ "id": "cf_3_night", "character": "长离", "day": [6,999], "weight": 8,
  "req_char_flag": "changli_knows_name",
  "text": "放学后办公室只剩她一个，灯下摊着那本批注过的书。",
  "choices": [
    { "text": "敲敲门进去", "aff": 12, "stress": -4, "energy": -3 }
  ] }
```

`seen` 去重只记最近 **60** 条事件，所以几天后同一事件可能再来一次——这正好适合「日常校园」的调子。

---

## 5. 数值手感参考（写给写 mod 的你）

| 量级 | 感觉 |
|------|------|
| `aff` ±3~5 | 普通日常，一句闲聊 |
| `aff` ±6~9 | 有明显态度的一次互动 |
| `aff` ±10~12 | 剧情节点 / 表白级 |
| `energy` -8~-10 | 熬夜 / 体育 / 搬东西，真的累 |
| `health` -3~-4 | 硬撑一天，第二天体力上限会掉 |
| `stress` -4~-5 | 被治愈了一下；+3 以上是添堵 |

好感阶段：`0`擦肩而过 → `20`认识的名字 → `40`会打招呼了 →
`60`想多待一会儿 → `80`特别的那个 → `100`心跳是公开秘密。

---

## 6. 排错小贴士

- 文件必须是 **UTF-8 无 BOM** 的 `.json`，逗号、引号别漏。
- 游戏启动时会打印每条 mod 的载入结果；报错那一条会被**跳过**而不崩游戏。
- `character` 写错成不存在的名字，事件会变成公共事件（不会报错，但没人认领 `aff`）。
- 想热重载？在标题菜单重开一次游戏就行，`mods/` 每次启动都会全扫。
- 不想玩某个 mod：把文件移出 `mods/` 文件夹即可，存档不受影响（存档只记 mod 文件名）。

---

祝你写出全校心跳加速的校园日常。
