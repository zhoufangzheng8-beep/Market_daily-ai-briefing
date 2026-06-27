#!/usr/bin/env python3
"""每日美股盘后简报自动生成脚本。

调用 Claude（claude-opus-4-8）并启用 web search 服务端工具，联网研究最近一个
美股交易日的盘后情况，按既定模板生成中文「美股盘后边际信息简报」，写入
briefings/ 目录。

环境变量：
  ANTHROPIC_API_KEY  必填，Anthropic API Key
  BRIEFING_DATE      可选，目标交易日 YYYY-MM-DD；缺省时按美东时间推断最近交易日
  FORCE              可选，设为 "1" 时覆盖已存在的简报文件

用法：
  python scripts/generate_briefing.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-8"
# 仓库根目录（脚本位于 <root>/scripts/）
ROOT = Path(__file__).resolve().parent.parent
BRIEFINGS_DIR = ROOT / "briefings"

# 美东时间（不含夏令时切换的精确处理，仅用于推断"最近交易日"，模型会以联网结果为准）
US_EASTERN = timezone(timedelta(hours=-4))


def latest_trading_day() -> str:
    """按美东时间推断最近一个交易日（周末回退到周五）。仅作初值，最终以联网结果为准。"""
    now_et = datetime.now(US_EASTERN)
    d = now_et.date()
    # 周六(5)回退1天，周日(6)回退2天
    if d.weekday() == 5:
        d -= timedelta(days=1)
    elif d.weekday() == 6:
        d -= timedelta(days=2)
    return d.isoformat()


SYSTEM_PROMPT = """你是一名资深美股策略分析师，为中文读者撰写「美股盘后边际信息简报」。

你必须使用 web_search 工具联网核实当日真实行情与新闻，严禁编造数据。研究时优先
查阅 CNBC、Bloomberg、Reuters、TheStreet、MarketWatch、美联储官网等可靠来源，
覆盖：三大指数（纳指/标普500/道指）与罗素2000的收盘点位及涨跌幅、当周表现、
领涨领跌板块、当日龙头个股及异动原因、宏观事件（美联储、通胀、就业数据）、
产业与并购新闻、资金轮动特征，以及未来 7–30 天的关键时间节点。

输出要求：
- 全文使用简体中文，纯 Markdown，不要包裹在代码块里，不要任何前言或寒暄。
- 严格遵循下方模板的章节结构、标题层级与表格格式。
- 「边际信息解读」是核心：解释当日盘面真正的驱动因素及其边际意义，而非简单复述行情。
- 数据务必标注来源；无法核实的数字不要写，宁缺毋滥。
- 结尾保留数据来源说明与免责声明。

模板（严格套用结构，内容替换为当日真实信息）：

# 美股盘后边际信息简报

**数据截止时间**：{DATE}（周X）美股收盘后（美东时间）

---

## 1. 盘面情况

### 大盘
| 指数 | 收盘 | 涨跌幅 | 当周 |
|------|------|--------|------|
| 纳斯达克综合 | … | … | … |
| 标普500 | … | … | … |
| 道琼斯 | … | … | … |
| 罗素2000（小盘） | … | … | … |

- **关键位置/特征**：…
- **结构分化**：…

### 主要板块
- **领涨**：…
- **领跌**：…

### 龙头股
| 个股 | 涨跌幅 | 简要原因 |
|------|--------|----------|
| … | … | … |

---

## 2. 边际信息解读（今日盘面的真正驱动）

**核心边际 1｜<标题>（<类别>）**
…

**核心边际 2｜……**
…

（按当日实际情况列 2–4 条核心边际，并在结尾用「前情衔接」一段串联近期脉络。）

---

## 3. 未来中短期关注时间节点（7–30天内）

按时间顺序（美东时间，部分为常规发布窗口，最终以官方为准）：

| 时间窗口 | 事件 | 关注点 |
|----------|------|--------|
| … | … | … |

---

## 【核心关注】

- **风险点**：…
- **机会点**：…
- **关键验证窗口**：…

---

*数据来源：…。本简报仅为信息整理与边际分析，不构成投资建议。*
"""


def build_user_prompt(date: str) -> str:
    return (
        f"请联网研究 {date}（美东时间）美股收盘后的情况，并据此撰写当日的"
        f"「美股盘后边际信息简报」。\n\n"
        f"注意：{date} 是按日期推断的目标交易日，请先用 web search 核实该日是否为"
        f"实际交易日；若当日休市，请改为研究最近一个已收盘的交易日，并在简报的"
        f"「数据截止时间」中使用真实交易日日期。\n\n"
        f"完成研究后，严格按系统提示中的模板输出完整简报正文。"
    )


def generate(date: str) -> str:
    """调用 Claude 生成简报正文，返回 Markdown 文本。"""
    client = anthropic.Anthropic()  # 从 ANTHROPIC_API_KEY 读取

    messages = [{"role": "user", "content": build_user_prompt(date)}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12}]

    # 服务端 web search 可能多轮，最多重试若干次处理 pause_turn；用流式避免超时。
    max_continuations = 6
    final = None
    for _ in range(max_continuations):
        with client.messages.stream(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT.replace("{DATE}", date),
            tools=tools,
            messages=messages,
        ) as stream:
            final = stream.get_final_message()

        if final.stop_reason != "pause_turn":
            break
        # 服务端工具循环达上限，回填后继续
        messages.append({"role": "assistant", "content": final.content})

    if final is None:
        raise RuntimeError("未能获得模型响应")

    if final.stop_reason == "refusal":
        raise RuntimeError(f"模型拒绝生成：{final.stop_details}")

    text = "".join(b.text for b in final.content if b.type == "text").strip()
    if not text:
        raise RuntimeError("模型未返回正文内容")
    return text


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("错误：未设置 ANTHROPIC_API_KEY 环境变量", file=sys.stderr)
        return 1

    date = os.environ.get("BRIEFING_DATE", "").strip() or latest_trading_day()
    force = os.environ.get("FORCE", "") == "1"

    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRIEFINGS_DIR / f"{date}-美股盘后.md"

    if out_path.exists() and not force:
        print(f"简报已存在，跳过：{out_path}（设置 FORCE=1 可覆盖）")
        return 0

    print(f"正在生成 {date} 的美股盘后简报…")
    body = generate(date)
    out_path.write_text(body + "\n", encoding="utf-8")
    print(f"已写入：{out_path}（{len(body)} 字符）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
