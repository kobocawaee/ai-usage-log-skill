---
name: ai-usage-log
description: 把 Claude Code 的對話紀錄（.jsonl）整理成「AI 使用紀錄表（.xlsx）」、關鍵畫面圖片（.png）與完整文字紀錄（.md），用於課程的 AI 應用文件。使用者輸入 /ai-usage-log、提到整理 AI 使用紀錄、文件 (g)、或要把對話紀錄轉成表格／截圖時使用。
---

# ai-usage-log：AI 使用紀錄自動整理

目標：依固定模板，從對話紀錄產生三樣東西，作為課程「AI 應用文件」的素材。

- 紀錄表 `.xlsx`：每個任務一列、有下拉選單
- 關鍵畫面 `.png`：把對話片段排版成卡片，內容與原文逐字一致
- 完整文字紀錄 `.md`：去掉工具細節、只留人與 AI 的對話

**核心原則**：紀錄表要證明的是「人有在判斷」。「人工判斷與修正」欄只能寫對話中真的發生過的事；
**第 5 步使用者確認前，不可以寫入任何檔案。** 不要編造理由。

下文的 `<skill>` 指本檔所在資料夾（腳本在 `<skill>/scripts/`）。

**`<proj>` 一律是目前的工作目錄（使用者開啟 Claude Code 的那個資料夾）。** 即使使用者提供的 `.jsonl` 路徑屬於別的專案，
也**不可**改用那個專案當 `<proj>`：設定檔、輸出資料夾、工作檔、狀態檔全都只寫在目前的工作目錄之下，
**不可寫入、修改或覆蓋 `.jsonl` 所屬專案裡的任何檔案**（那份紀錄只讀取）。
圖片若已有同名檔，`render_cards.py` 會拒絕覆蓋（見第 6 步）；其他輸出檔若已存在同名，也要先告知使用者，不可直接覆蓋。
所有路徑都以引號包住（路徑可能含中文與空白）。

## 0. 前置檢查

skill 使用自己專用的 Python 環境（位於 `~/.claude/ai-usage-log-venv`，不會動到系統 Python）。先執行：

```
python "<skill>/scripts/setup_env.py"
```

（系統上 `python` 不存在時改用 `py`。）它會在環境缺失或套件不齊時自動建立並安裝（第一次約一兩分鐘，請先告訴使用者要等一下），
**最後一行輸出的是專用環境的 python 路徑，記為 `<py>`**。之後所有腳本都用 `"<py>"` 執行，不要用系統的 `python`。
已經準備好時，這個指令只需不到一秒。Chromium 安裝失敗時圖片會退回只輸出 HTML，流程不會失敗，但請提醒使用者。

## 1. 讀設定檔

讀 `<proj>/ai-usage-log.config.json`。不存在就**只問一件事：姓名**（例如「徐啟翔」，也可以是大家都認得的綽號），
其餘用預設建立（`timezone: Asia/Taipei`、`output_dir: ai-log`、`workbook: ai-log/G-AI使用紀錄-<姓名>.xlsx`、
**不需要成員編號，也不需要全組成員清單**：每個人在自己的電腦產生自己的 Excel，檔名帶姓名就能辨識；紀錄表沒有「成員」欄。
姓名會用在檔名與圖片上的發言標籤，不可含 `\ / : * ? " < > |`。
若設定檔裡有舊版的 `member`、`members` 欄位，直接忽略，不要再向使用者詢問。
活動與採用程度清單見下）。範例：

```json
{
  "member_name": "王小明",
  "timezone": "Asia/Taipei", "card_theme": "light", "output_dir": "ai-log", "image_dir": "ai-log/images", "workbook": "ai-log/G-AI使用紀錄-王小明.xlsx",
  "activities": ["需求", "設計", "程式", "測試", "除錯", "審查", "文件", "管理"],
  "adoption_levels": ["直接採用", "小幅修改", "大幅修改", "僅參考", "不採用"]
}
```

首次建立時提醒：建議在 `.gitignore` 加入原始 `.jsonl`、`ai-log/.draft/`，只提交 `.xlsx`、`.png`、`.md`。
工作檔（conversation.json、草稿）放在 `<proj>/<output_dir>/.draft/<session前8碼>/`。

## 2. 選擇對話

使用者若給了 `.jsonl` 路徑就直接用。否則：

```
"<py>" "<skill>/scripts/find_sessions.py" --project "<proj>" --state "<proj>/<output_dir>/.ai-usage-log-state.json"
```

把結果給使用者選（預設只列未處理的；`--all` 列全部）。

**給使用者選的時候，主要顯示「標題」**（和 VS Code 對話清單看到的名稱相同），再附日期；
不要只寫 session 編號或「N 次人工輸入」，一般人看不懂。例如：「Sports-center PRD 的 Epic 與 Story 清單（11/3）」。
**排除目前這個對話本身**（標題通常像「/ai-usage-log …」、時間是現在），它是在執行本 skill，不是要記錄的內容。
若使用者想整理的對話沒出現在清單，請他說出對話的標題或大約日期，不要讓他猜編號。

## 3. 解析

```
"<py>" "<skill>/scripts/parse_session.py" "<session.jsonl>" -o "<work>/conversation.json" --tz <timezone>
```

`conversation.json` 含 `stats`、`subagents`、`messages`（`idx`、`role`、`local` 時間、`text`、`tools`）。

## 4. 草擬（需要你的判斷）

**只讀 `conversation.json`，不要直接讀原始 `.jsonl`。** 若超過約 60,000 字，分段讀取、分段草擬。

### 4.1 切成「列」
- 一列 = 一個任務：從人提出要求，到 AI 交出結果、人做出判斷為止。
- 同一任務多次來回合併成一列；中途有重要的人工判斷（否決、改方向）就拆成獨立一列，或在判斷欄逐點列出。
- 純閒聊、問路不記。一段 1～2 小時的對話通常 3～8 列。

### 4.2 「人工判斷與修正」欄規則
1. 只寫對話中真的發生過的判斷（人的輸入：否決、修改、補充條件、選擇選項、要求重做、指出錯誤）。AI 自己提出、人只回「好」的，不能寫成人的判斷。
2. 要具體：「AI 原本怎麼做 → 人改成什麼 → 為什麼」。
   - ✗「AI 寫得不錯，有稍微修改。」
   - ✓「AI 預設新規則與原規則混編；我要求新規則從 R10 起編號、不更動 R1～R9，讓之後的測試案例能對應規則編號。」
3. 直接採用也要寫怎麼確認的（例如「逐條對照 PRD §8.1 確認範圍一致後採用」）；對話裡看不出怎麼確認就走第 4 點。
4. 找不到依據：以 `[待確認] ` 開頭，簡述 AI 推測的內容，讓使用者補充。**不可編造理由。**
5. 只有指令、沒有理由：只寫做了什麼，理由寫 `[待補理由]`。

### 4.3 兩份草稿 JSON（寫到 `<work>/`）

`cards.json`（給圖片與文字紀錄）：

```json
{
  "header": "Claude Code＋**/bmad-prd**｜2026-10-30",
  "source": "<session-id>.jsonl",
  "member_name": "王小明",
  "file_prefix": "1030_PRD_王小明",
  "tool_label": "Claude Code",
  "image_dir": "images",
  "cards": [
    {"no": "01", "title": "下達指令", "kind": "人的輸入", "messages": [0]},
    {"no": "02", "title": "回答 9 題，並要求新規則從 R10 編號", "kind": "人工決策", "messages": [2]},
    {"no": "03", "title": "問題數 55 → 29", "kind": "AI 產出", "messages": [5]}
  ]
}
```

- `file_prefix` = `<MMDD>_<任務簡稱>_<成員姓名>`；任務簡稱 2～8 字，不含空白與 `\ / : * ? " < > |`。
- `header` 中用 `**…**` 包住 skill 名稱（如 `**/bmad-prd**`），圖片頂列會顯示成粗體，和手動製作的參考風格一致；沒有用 skill 就不用加。
- `kind` 只能是 `人的輸入`、`人工決策`、`AI 產出`。`messages` 是 `conversation.json` 的 `idx`。
- 每列至少一張「人的指令或判斷」；AI 產出有關鍵數字時加一張 AI 產出。每張圖對應表中一列，一列可有多張圖。

`draft.json`（給紀錄表，欄位對應 SPEC 4.1）：

```json
{
  "session_id": "<完整 session-id>",
  "outputs": ["ai-log/images/1030_PRD_王小明_01.png", "ai-log/1030_PRD_王小明_對話紀錄.md"],
  "rows": [{
    "date": "2026-10-30", "activity": "需求", "task": "…", "tool": "Claude Code＋bmad-prd",
    "prompt": "…「原文」…", "output": "…", "judgment": "…", "adoption": "小幅修改",
    "images": [{"file": "1030_PRD_王小明_02.png", "kind": "人工決策"}], "other_files": ["docs/prd.md"],
    "section": "B（需求）", "source": "abcd1234 19:45–20:19"
  }]
}
```

`source` = `session-id 前 8 碼` ＋ 空白 ＋ `起–迄`（使用者時區、`HH:MM`，用 `–`）。用來去重，格式請照寫。
`images` 的每一項用 `{"file": 檔名, "kind": 該張卡片的類型}`（類型同 cards.json 的 `kind`），Excel 會寫成「[人工決策] images/…png」，方便之後把表格交給 AI 整理文件時分辨哪張是人的 Prompt、哪張是 AI 回復。
`activity`、`adoption` 必須是設定檔清單中的值。`judgment` 不可空白。

## 5. 呈現草稿並等待確認（必要，不可跳過）

在對話中用表格列出每一列：日期、軟工活動、具體工作、判斷摘要、採用程度、配的圖片（編號＋標題＋類型）。
**明確標出所有 `[待確認]`、`[待補理由]`。** 請使用者確認或修改，改完再呈現一次。
沒有使用者明確同意，不進第 6 步。

## 6. 產出（確認後依序執行）

```
"<py>" "<skill>/scripts/render_cards.py" "<work>/conversation.json" "<work>/cards.json" "<proj>/<image_dir>" --theme <card_theme>
"<py>" "<skill>/scripts/write_transcript.py" "<work>/conversation.json" "<work>/cards.json" "<proj>/<output_dir>/<file_prefix>_對話紀錄.md"
"<py>" "<skill>/scripts/write_workbook.py" "<work>/draft.json" --config "<proj>/ai-usage-log.config.json"
```

- 圖片統一放在 `<proj>/<image_dir>`（預設 `ai-log/images/`）；文字紀錄與 xlsx 放在 `<output_dir>`。cards.json 的 `image_dir` 是「相對於文字紀錄」的圖片資料夾名稱。
- 圖片與文字紀錄會自動遮罩敏感資訊（金鑰、email、家目錄、密碼）。
- `<card_theme>` 取自設定檔的 `card_theme`（`light` 或 `dark`，沒寫就用 `light`）。
- `render_cards.py` 回傳 3 表示目標資料夾已有同名圖片，**程式不會覆蓋**。把清單告訴使用者，問他要換 `file_prefix` 還是取代；
  只有使用者明確同意取代，才在同一行後面加 `--overwrite` 重跑。
- 找不到 Playwright/Chromium 時 `render_cards.py` 只輸出 HTML 並印出安裝指令，請轉告使用者。
- `write_workbook.py` 回傳 2 表示 Excel 正開著該檔：請使用者關閉後，**只重跑這一行**（草稿已保留）。
- 同一 session、時間重疊的列會自動略過，並在輸出中說明。

## 7. 自我檢查

- 實際打開至少 2 張圖片看過：中文正常、數字與編號和原文一致（尤其「9. …」不可被改成 3.）。
- 用 openpyxl 讀回 xlsx：列數正確、`紀錄表` 有 2 個下拉選單（軟工活動、採用程度）。
- 有問題就修正後重跑該步驟。

## 8. 回報

列出：產出檔案的位置（xlsx、png、md）、新增列數、被略過的重複列，以及所有含 `[待確認]`／`[待補理由]` 的列號——提醒使用者到 Excel 補上。
