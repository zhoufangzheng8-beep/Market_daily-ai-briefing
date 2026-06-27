# Market Daily AI Briefing

每日自动生成的「美股盘后边际信息简报」。每个交易日收盘后，由 GitHub Actions 调用
Claude（`claude-opus-4-8`）联网研究当日行情与新闻，按既定模板生成中文简报并提交到
[`briefings/`](briefings/) 目录。

## 运行原理

```
GitHub Actions (cron 每个交易日)
        │
        ▼
scripts/generate_briefing.py
        │  调用 Claude + web_search 工具联网研究
        ▼
briefings/YYYY-MM-DD-美股盘后.md   ──►  自动 commit & push
```

- **数据来源**：Claude 的服务端 `web_search` 工具实时联网（CNBC、Bloomberg、Reuters、
  美联储官网等），无需额外的行情数据 API。
- **模型**：`claude-opus-4-8`，启用 adaptive thinking 与流式输出。
- **格式**：严格套用 [`briefings/2026-06-26-美股盘后.md`](briefings/2026-06-26-美股盘后.md)
  的章节结构（盘面情况 / 边际信息解读 / 关注时间节点 / 核心关注）。

## 一次性配置

在 GitHub 仓库中添加一个 Secret：

1. 打开 **Settings → Secrets and variables → Actions → New repository secret**
2. 名称填 `ANTHROPIC_API_KEY`，值填你的 Anthropic API Key

工作流已声明 `permissions: contents: write`，使用内置的 `GITHUB_TOKEN` 推送，无需额外
配置。

## 自动运行

工作流定义见 [`.github/workflows/daily-briefing.yml`](.github/workflows/daily-briefing.yml)，
默认在 **UTC 22:00（美东 17:00–18:00，美股收盘后）周一至周五**触发。

> 注意：GitHub cron 使用 UTC，不随美国夏令时调整。如需更贴近收盘或捕捉更多盘后新闻，
> 可修改 workflow 中的 `cron` 表达式。

## 手动运行

### 在 GitHub 上触发

**Actions → 每日美股盘后简报 → Run workflow**，可选填：
- `date`：目标交易日 `YYYY-MM-DD`（留空自动推断最近交易日）
- `force`：`true` 时覆盖已存在的简报

### 在本地运行

```bash
pip install -r scripts/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# 自动推断最近交易日
python scripts/generate_briefing.py

# 指定日期 / 覆盖已存在文件
BRIEFING_DATE=2026-06-26 FORCE=1 python scripts/generate_briefing.py
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 是 | Anthropic API Key |
| `BRIEFING_DATE` | 否 | 目标交易日 `YYYY-MM-DD`，缺省按美东时间推断 |
| `FORCE` | 否 | 设为 `1` 时覆盖已存在的简报文件 |

## 免责声明

本仓库内容由 AI 自动生成，仅为信息整理与边际分析，不构成投资建议。行情数据以官方来源
为准。
