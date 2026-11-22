# 模型怎麼讀、怎麼寫、怎麼交卷

**建圖模型可以提議寫入。Host 檢查原文、決定能否提交。預測模型只讀一次凍結的表示，交一次答案。評分器等作答封存後才開答案。** 以下是第一輪擬採用的契約。樹與主張的語義沿用[目前設計](../graph-tree-design.md)；這份文件把它接到[實驗流程](experiment-plan.md)。

## 資料由誰拿到

| 階段 | Host 的資料鍵 | 實際送到模型 | 產出 |
|---|---|---|---|
| 建圖 | 從 `prepared/inputs/histories.jsonl` 讀 `scope_id, context_qas[]` | 一份依原序完整給出的英文 `evidence_id, question, answer`，連續編號 e001 起，加上固定的抽取提示與工具規格 | 一個已凍結快照或明確的失敗紀錄 |
| Raw 預測 | `prepared/inputs/raw_prompts.jsonl` 的 `item_id, messages` | 官方完整 system 與 user 訊息 | 原始字串或失敗 |
| Graph／Flat 預測 | `prepared/inputs/questions.jsonl` 的 `item_id, scope_id, task_type, prediction`，及已凍結快照 | 同一官方模板框架，替換訪談內容。每組都看到相同 `demographics, task_question`，T1 有 `answer_options`，T2 有 `scale`，理由題另有 `reason_text` | 原始字串或失敗 |
| 評分與診斷 | 用 `item_id` 接回 `prepared/scoring/answers.jsonl`、配對表，以及 scorer 所需的固定原檔欄位 | 離線運算。T1 的 `source_qa, reasoning, answer` 與 T2 的 `user_answer` 都留在這一端 | 官方、補充與稽核各表 |

同一個 `e001` 在不同訪談可能是兩段完全不同的話。永久證據鍵用 `(scope_id, evidence_id, field, start, end)`。編號、人物 ID、資料域、題號、問卷代碼與原始訪談跳號留給 host 路由；從原話自然讀出議題是允許的。建圖與預測使用不同的工作階段，原始資料、快取、工具與重試上下文都遵守這個邊界。[資料包欄位](prepared-data.md)

## 建圖和讀圖的本機工具

| 呼叫者與操作 | 最小輸入 → 輸出 | 驗收 |
|---|---|---|
| Builder · `evidence_read` | 當前 session 的本地 evidence IDs → 指定 Q/A 及可引用的欄位 | 不接受任意 scope、路徑或跨題搜尋。建圖開始已收到整份訪談，可回讀短答的對應問句 |
| Builder · `graph_propose` | `request_id, expected_revision, operations[], done` → `draft_id, base_revision` 或帶操作位置的錯誤 | 一批內先宣告暫時 ID 再引用。提出 `done` 表示完整讀完；合法空圖須顯式附 `no_supported_claims` |
| Host · `graph_commit` | 已驗證 draft、預期 revision → revision、穩定 ID 對照、事件序號 | 一次交易提交整批；回覆舊 revision 時先重新對齊。只有有明確完成訊號的成功終態能 freeze |
| Host · `graph_read` | 凍結快照、revision、`view=graph_text / flat_text` → 英文內容、內容清單、引文位置與 hash | 第一輪完整輸出。如遇合法空圖，兩組使用同一句中性空表示。研究者另可查節點、條件與例外路徑 |
| Runner · `predict` | 組裝完成的兩則訊息、固定推論設定 → `response_text`、狀態、用量與服務端識別 | 新對話，模型無寫回工具。T1 期望一個選項字母，T2 期望量尺內整數。原文照存，交卷後才解析 |
| 研究者 · `trace_read` | `run_id, item_id` 或 scope、revision、事件範圍 → 當次輸入、輸出與已記錄操作 | 同一題的三臂可並排；盲審階段遮住組別成績與 gold。正式結果封存後才在研究者檢視中疊加答案 |

這裡的「MCP 風格」指每個操作有明確型別、角色、可記錄的輸入輸出與錯誤。第一版可用程序內呼叫。Provider 有原生 tool calling 時送相同工具規格，僅能輸出文字時讓模型回傳同 schema 的 JSON envelope，交同一個驗證器。正式 run 鎖定傳輸方式。預測端保留官方純文字回覆語義，避免某一組獨享 provider 強制選項。

### 一筆操作如何成為模型讀到的東西

以下是自造例子。訪談中對「週五你喜歡什麼格式？」的回答是 `I prefer a short report on Fridays.`。假設先前已在同一 scope 宣告 `short_report` 與 `friday`。這一批的輸入形狀如下。

```json
{
  "request_id": "example-2",
  "expected_revision": 1,
  "done": true,
  "operations": [{
    "op": "add_claim",
    "temp_id": "local1",
    "holder": "participant",
    "about": "self",
    "relation": "stance_on",
    "args": {"target": "short_report"},
    "outcome": "positive",
    "basis": "explicit",
    "applicability": "usual",
    "condition_id": "friday",
    "evidence": [{"id": "e001", "field": "answer", "quote": "I prefer a short report on Fridays."}]
  }]
}
```

Host 先回 `{"draft_id":"d2","base_revision":1}`。提交後回 `{"revision":2,"id_map":{"local1":"c9"},"event_seq":7}`，凍結後兩個 renderer 都讀 c9。Graph 文字可以寫成 `C1=short report | K1=Friday | c9: participant, about self, stance_on(C1)=positive, usual when K1, explicit`；Flat 寫成 `The participant explicitly says they generally favor a short report on Fridays.`。兩者附上**同一段** e001.answer 引文，host 的對照表都指回 c9。萬一抽成「他寧可短報也不要詳細報告」，程式可驗出這句引文確實存在；「詳細報告」這個比較對象缺乏支持，須靠語義稽核發現。

### 樹裡的資料怎麼進來

| 對象 | 第一輪寫入與讀出 |
|---|---|
| 大情境與子情境 | 人／議題作研究者導覽。局部條件由 `add_condition` 建立，存邏輯組合、原意、父條件與首次建立原因。兄弟可以同時成立，共用概念保留同 ID；這種共用限於同一可見 scope 的模型表示 |
| 節點裡的圖 | `upsert_concept, add_claim, attach_evidence, challenge_claim` 保存誰持有判斷、談誰、端點角色、方向／程度、條件、明說／推論、引文與支持或反證。推論須有依據、可逐條更正。短答「對」應一起引用提問與回答 |
| 哪條規則是例外 | `add_exception(local_claim, default_claim, evidence)` 指名改哪條規則。限定同主體、同一判斷及相容範圍。第一輪建議有直接依據才把覆寫送入 Graph／Flat，間接猜到的連結列入候選。Flat 也完整寫出何時哪一判斷取代哪一判斷 |
| 後續才測的能力 | 研究端可演示 `resolve(question_slot, conditions)`，節點同時命中、條件未知、父層無規則、衝突都可保存。本人更正／跨時用新證據、`retract_claim / supersede_rule` 與版本處理。HugAgent 沒有受訪者審過這張圖的標籤 |

兩種渲染共用一個確定排序的內容清單，對每條列出語義欄位、引文區間、支持／反證、已核可的覆寫及所引用對象。Graph 以共享 ID 連起，Flat 用固定句型把對象與條件展開；推論標記、未決矛盾、程度和否定都要保留。先比清單，再用盲讀抽查兩種文字是否真的保留語義。凍結時把渲染器版號、成品字串與 hash 都存下。不能只靠兩份相同 ID 清單證明英文意思相同。

## 模型、失敗與重播

- **模型層。** 統一接受有序 `messages`、可選工具規格、model revision、輸出上限、溫度及 provider 支援的解碼設定。回傳原始 text 或 tool calls、finish reason、服務端模型／request ID、input/output/cached tokens、延遲及錯誤類別。缺少的計量填缺值並標來源。預檢時逐項驗證能否鎖模型、能否關閉截斷、能否計費與限制上下文；所有比較臂都用同一預測設定。
- **建圖上限。** 建議以一次完整提議為目標，合成預演後凍結每 scope 的總輪數、修正輪數、輸出與費用上限，以及允許的分批方式。達上限尚未完成則標 `build_failed`，保留部分操作供診斷。依賴它的 Graph／Flat 題次都記原因，Raw 獨立繼續。合法完成的零主張圖照常作答。
- **模板與容量。** 用 pinned 官方組裝方式重建 header／footer，對三臂做「取走訪談區後逐字相同」檢查。完整包入背景、題、工具定義與輸出預留後才核對 context window。正式預測前，遇到超出容量的實際輸入就回報，重新核定能容下的設定並更版；完整主表禁止靜默截斷。
- **原子性。** 同一 session 的 request ID 與相同 payload 重送回原結果；相同 ID 不同內容拒絕。錯誤如 `OUT_OF_SCOPE, SPAN_AMBIGUOUS, STALE_REVISION, UNKNOWN_ENDPOINT` 回傳本批位置，拒絕整批。引文位置是指定原欄位的 Unicode code point 半開區間，逐字核對。驗條件包含／例外方向與環，允許原話支持的偏好循環。
- **可續跑。** 工作鍵為 `(run_id, scope_id, build_config_hash)` 與 `(run_id, item_id, arm, replicate)`；先持久化工作與 attempt，再送出。逾時、限流使用同政策做有限重試。送達狀態未知時優先用服務端 request ID 核對，有冪等支援時沿用同鍵；無法核對時標明可能重複計費。每格只接受一個按既定 attempt 順序選定的終態。模型已交的越界或格式錯誤原樣評分，禁止靠重新問到合法或看 gold 挑答案。
- **事件與快取。** 保存邏輯工作鍵、request、單調 seq、actor、事件類型、前後 revision、完整操作內容及 ID 映射的本機引用、設定 hash、狀態、錯誤與用量。內容雜湊固定序列化與欄位排序，排除時間戳／計費等易變 metadata。快取鍵含 dataset revision、scope、builder 模型與抽取提示、工具/schema、解碼及完成策略。版本或允許的 QA 不同就無法命中舊快取。
- **重播驗收。** 從空圖只重放 committed ops → 比快照 hash → 用同版本渲染器比 Graph／Flat 完整字串 → 比實際 request → 把封存的原始回答交官方 scorer → 比結果表底數。每一步指出第一個差異。模型內部思路無法由這條操作紀錄還原。

**尚待研究者凍結的接口決定。** 有據推論可納入已取得同意。候選覆寫是否供模型作答、實際的 builder/predictor revision、provider 傳輸模式與每份訪談的輪數／費用上限仍屬提案。這些項目寫進 run manifest 後，才有一套能照規格比較的第一輪接口。
