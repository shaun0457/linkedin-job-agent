# LinkedIn Job Agent — Brainstorming & Design Decisions

**Date:** 2026-03-27
**Participants:** Cheng Ting Chen (User), Claude (Developer)

---

## Problem Statement

### 核心痛點 (Priority Order)

1. **手動逛 LinkedIn 耗時** — 每天花大量時間在 LinkedIn 上搜尋符合條件的職缺
2. **手動調整履歷繁瑣** — 為每個職缺手動修改履歷，反覆複製貼上
3. **容易漏掉適合的職缺** — 除了 LinkedIn，大公司（如 TSMC）有自己的招聘頁面，需要多個來源

### 用戶背景

- **雙碩士學位**：Computational Engineering + Mechanical Engineering (TU Darmstadt)
- **定位**：AI/ML Engineer，專注於工業應用和 Predictive Maintenance
- **求職策略**：主動求人（自己尋找職缺），不被動等企業招聘

---

## Solution Vision

### 核心目標：半自動化求職輔助系統

**不是完全自動化，而是智能助手**：
- 系統自動爬取 + 過濾 + 調整履歷
- 用戶審核並確認是否投遞
- 目標：減少手動操作時間，確保投遞品質

```
每日時刻表（台灣時間）
┌─────────────────────────────────┐
│ 8:00 AM   │ 爬職缺 → tailoring → 通知  │
│ 6:00 PM   │ 爬職缺 → tailoring → 通知  │
└─────────────────────────────────┘
用戶在 Telegram 上審核 → 確認投遞
```

### 關鍵特性

1. **自動爬取**：LinkedIn（Apify）+ 大公司招聘頁面（待實現）
2. **智能過濾**：用 Resume Matcher 計算匹配度，只推薦高相關職缺
3. **自動 Tailoring**：基於職缺描述，自動調整履歷關鍵字和內容
4. **用戶審核**：Telegram 命令行，確認/跳過/修改
5. **履歷追蹤**：記錄已投遞的職缺，避免重複投遞

---

## 架構決策

### 為什麼選這些技術？

| 組件 | 選擇 | 原因 |
|------|------|------|
| **求人源** | Apify LinkedIn Scraper | 穩定、大規模、不違反 LinkedIn ToS（官方推薦） |
| **履歷優化** | Resume Matcher 自建 Fork | 完全可控、支持本地化、開源可靠 |
| **通知渠道** | Telegram Bot | 即時、互動、無需額外 App |
| **定時執行** | APScheduler (本地) | 簡單、無依賴、適合個人用途 |
| **數據存儲** | SQLite | 輕量級、無服務器、夠用 |
| **測試** | pytest + 94% coverage | 保證代碼品質，快速迭代 |

### 架構圖

```
┌─────────────────────────────────────────────────────────┐
│                   Telegram Bot (User Interface)         │
│  /run, /status, /pending, /retry, /config, /health     │
└────────────────┬────────────────────────────────────────┘
                 │ (確認/跳過)
┌────────────────▼────────────────────────────────────────┐
│              Pipeline Orchestrator (main.py)             │
│  • APScheduler (8:00, 18:00)                            │
│  • 調用 run_pipeline()                                  │
└────────────────┬────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐  ┌──────────┐  ┌─────────────┐
│ Scraper │  │ Improver │  │   Notifier  │
│ (Apify)│  │ (RM API) │  │  (Telegram) │
└────────┘  └──────────┘  └─────────────┘
    │            │            │
    └────────────┼────────────┘
                 │
                 ▼
            ┌──────────┐
            │  SQLite  │
            │ (Dedup)  │
            └──────────┘
```

---

## 功能路線圖

### Phase 1 ✅ (Completed)

- [x] LinkedIn 爬蟲 (Apify)
- [x] Resume Matcher 整合
- [x] Telegram Bot 基礎命令
- [x] SQLite 去重
- [x] 日程排程 (APScheduler)
- [x] TDD 測試框架 (157 tests, 94% coverage)

### Phase 2 (當前優先級)

- [ ] 大公司求人源 (TSMC, Google, Meta 等)
- [ ] 履歷內容擴充 (更詳細的背景資訊)
- [ ] 部署指南 (CLAUDE.md)
- [ ] 多源去重 (LinkedIn + 公司招聘頁面)

### Phase 3 (未來考慮)

- [ ] RM 雲端部署 (真正的完全自動化)
- [ ] 職缺推薦引擎 (基於過往申請的反饋)
- [ ] 人力資源數據分析 (投遞率、回應率等)
- [ ] 求職進度追蹤 (面試邀約、拒絕、offer)

---

## 已做的決策

### 為什麼有兩份履歷？
**決策已修正**：不需要「computational」vs「mechanical」的二選一。
- 用戶有雙碩士學位，定位本身就是「Computational + Mechanical」
- 應該有一份**綜合主履歷**，在 RM 中自動優化針對不同職缺
- ✅ 已實現：多時間點定時任務 (8:00 + 18:00)

### 本地 vs 遠程
**決策**：保持本地運行（APScheduler）+ 建議用戶未來考慮部署
- ✅ 理由：RM 本地運行，無法用遠程 Agent（localhost 限制）
- 📌 未來改進：Deploy RM 到雲端後，才能實現真正的「無需電腦開著」

### 完全自動化 vs 半自動化
**決策**：半自動化（用戶確認後再投遞）
- ✅ 理由：投遞是不可逆操作，用戶應該總是有最終決策權
- 🎯 目標：減少手動操作時間，不是完全放棄控制

---

## 未解決的問題（需要討論）

### Q1: 大公司求人源如何爬取？
- TSMC、Google、Meta 等有各自招聘頁面
- 需要為每個公司寫爬蟲？還是用通用爬蟲 + 手動配置？
- 優先級：是否現在實現？

### Q2: 如何評估職缺匹配度？
- 目前是 RM 的分數，但用戶想「不漏掉適合的」
- 需要更積極的推薦還是更嚴格的過濾？
- 是否需要加入「關鍵詞警報」（自動標記 ML/Robotics 職缺）？

### Q3: 投遞後的追蹤？
- 投遞了多少份？回應率如何？
- 是否需要整合面試日程、offer 追蹤？
- 超出當前 scope 嗎？

---

## 技術棧確認

- **Language**: Python 3.12
- **CLI/Bot**: python-telegram-bot v21
- **Scraping**: Apify SDK
- **Resume Optimization**: Resume Matcher (shaun0457 fork)
- **Database**: SQLite3
- **Testing**: pytest + pytest-asyncio (157 tests, 94% coverage)
- **Scheduling**: APScheduler
- **Code Quality**: TDD + 80% coverage minimum
- **Git**: Conventional commits, squash merge on main

---

## 下一步

1. ✅ 完成 Brainstorming
2. → 撰寫 PRD.md（產品需求文件）
3. → 撰寫 CLAUDE.md（開發指南）
4. → 開始 Phase 2 實現（大公司求人源）
