# PROGRESS — linkedin-job-agent

> 由 git 歷史產生的進度快照。權威的當前狀態請以下方「延伸文件」與最新 commit 為準。

## 同步狀態

| 項目 | 值 |
|---|---|
| 作用分支 | `main` |
| Remote | https://github.com/shaun0457/linkedin-job-agent |
| Commit 數 | 35 |
| 首次 commit | 2026-03-26 |
| 最近 commit | 2026-08-16 |
| 工作區未提交項目 | 1 |
| Code graph 快照 | `graphify-out/graph.json` |

## 最近里程碑

- `2026-08-16` chore(gitignore): exclude coverage artifacts and personal resume files
- `2026-04-04` feat: v2.0 upgrade — personalized scoring, tiered notifications, multi-keyword search
- `2026-04-03` feat: add time filter, /time command, and auto-expand retry
- `2026-04-03` refactor: change AI scoring from filter to tier labels (🟢🟡🔴)
- `2026-04-03` test: improve scorer and pipeline coverage (92% → 94%)
- `2026-04-03` feat: add AI job scoring with Gemini before tailoring
- `2026-04-03` docs: add AI job scoring to PRD and update CLAUDE.md
- `2026-04-03` fix: update scraper for new Apify actor input schema
- `2026-03-28` chore: change Resume Matcher default port from 8000 to 8001
- `2026-03-27` docs: add architecture overview and reference links to CLAUDE.md
- `2026-03-27` docs: rewrite CLAUDE.md to 61 lines (How-only rules)
- `2026-03-27` Add project documentation: BRAINSTORMING, PRD, and CLAUDE

## 延伸文件（當前狀態與下一步的真實來源）

- [`BACKLOG.md`](./BACKLOG.md)

## Code graph

本 repo 附帶 graphify 產生的程式碼結構快照，可直接查詢：

```bash
graphify explain "<符號名稱>"      # 說明某個節點與其鄰居
graphify path "<A>" "<B>"          # 兩個節點間的最短路徑
graphify affected "<符號名稱>"     # 反向追蹤受影響範圍
graphify query "<問題>"            # BFS 走訪回答問題
```

快照僅涵蓋純程式碼目錄（AST 抽取，未做語意分群）。文件類檔案需要 LLM API key 才能納入。
