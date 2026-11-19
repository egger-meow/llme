# 給 Local Codex／Claude Code 的 llme 實作 prompt

從下一行起可直接貼給能讀取本機 `llme` repo 的 coding agent。研究設計文件可作背景，以下 prompt 可獨立使用。

---

請在目前的 **llme repo** 實作 HugAgent 真人資料的個體推理實驗。先讀 repo 的 AGENTS.md、README、現有 model client、資料層、實驗 runner、前端與測試，沿用合適元件，再動手完成。我要得到可執行的實驗、可比較的官方評分，以及出錯時能追到原話的本機圖檢視器。交付時區分已在本機跑過的結果、僅通過 fixture 的項目、需要模型服務的項目。

## 1. 研究問題與範圍

以相同模型和相同可見資料，測試「將某人的訪談 QA 做成可追溯的個人圖，能否比直接給完整 QA 更準確預測他的信念」。保留兩個官方 task、全部 54 位、全部 1,742 題。現階段的產品是非商業研究用的逐題 benchmark 與除錯工具。不要另建一般人側寫產品或公開真人圖。

先完成域內 **raw / graph / flat**。接著做逐題檢視、來源與操作紀錄。跨域作可獨立開啟的第二個實驗。Tree 先具備下述語義與合成測例，真人 Tree ablation 與跨時更新等資料適用性調查後再決定。先用普通資料結構即可，依 repo 選持久層。在第一個資料集不需要部署 Neo4j、向量庫、遠端 MCP server、加跨人檢索、訓練或 model editing。

## 2. 資料與可見欄位合約

固定上游 `jajamoa/HugAgent` tag `data-v1.1`，commit `5388570854cdb630a725c672bd1ccc8de0634728`。讀 `Benchmark/data/` 中兩任務 × 三域的六份 JSONL、`hf/README.md`、`DATA_RELEASE.md`、`Benchmark/data/LICENSE`、`Benchmark/hugagent_eval.py`。優先用固定 revision 的本機資料目錄，可選相同 revision 的 HF `social-atoms/hugagent`，後者的 nested JSON strings 需 decode。輸入路徑、後端與模型從 repo 既有 config／環境變數取，憑證留在本機。

實作資料 adapter 的三個輸出，型別與儲存權限分開：

1. `HistoryView` 給 builder。只有該 scope 已允許、按原序的英文 `question, answer`，提供題內 evidence ref 與 topic。Host 可持有匿名 PID、位置等 metadata。保留原文作引用，模型看到的 QA 順序依官方格式。不要把整個 JSON row 交給模型。
2. `PredictionView` 給 predictor。使用 `demographics`、此條件的歷史表示，以及 `task_question`。T1 附 `answer_options`；T2 附 `question_type, scale` 和存在時的 `reason_text`。保留原題對條件及量尺的英文措辭。路由和評分使用的 `item_id, question_id, reason_code` 無須出現在模型輸入。
3. `ScoringView` 僅給獨立 scorer／離線 leakage audit。T1 包含 `answer, source_qa, reasoning`；T2 包含 `user_answer`。模型輸出的 traces 和可視化的 score overlay 不可逆流進前兩個 view。

**驗收常數。** 依序 healthcare / surveillance / zoning，T1 為 108/122/126，T2 為 472/364/550。54 人皆有三域 T2。T1 共 356，T2 共 1,386，含 opinion 389（基準 77、新情境 312）、reason_evaluation 997。每題 16–44 段 QA。T1 的 A 表正向，B 表負向，三筆官方 gold `A/B`。在這個 revision，逐題用相同 PID、topic 和**完整有序 QA** 核對，T1 唯一 scope 319、T2 唯一 scope 162、交集 21、聯集 460。這些數字是該 fixture 的檢查，勿當所有 dataset 的限制。

**遮蔽測試。** 逐題只以原本 `context_qas` 建圖。稽核程序以精確的 (question, answer) 匹配 T1 `source_qa`，其在本題中命中 0/356，在本人同域 T2 的 context 中命中 271/356（89、100、82）。P07 監控 T1-0009 允許 19 段，T2-0015 允許 20 段，保留問答在後者第 11 段。把這兩個 item 放入隔離測試。不得先將所有同人資料建成一張大圖再刪節點；隱藏的 QA 可能已經進入其他 claim、embedding、summary、alias 或索引。相同可見範圍才共用抽取；快取鍵必須含資料 revision、來源模式、人物、領域、QA內容與順序 digest、builder 模型／prompt／schema／設定。語義相似或只差一筆不算相同範圍。

## 3. 比較組及模型接口

| 條件 | 建構 | 預測輸入 |
|---|---|---|
| raw | 無離線建構 | 官方 `build_prompt` 的完整背景、完整原序 QA、原題、選項或量尺 |
| graph | 只從 HistoryView 抽取一次；經工具驗證並 freeze | 用固定順序序列化完整概念、具型別的關係、條件和短證據，替換 QA 區塊 |
| flat | 與 graph 共用同一個凍結 snapshot，不再用 LLM 改寫 | 以固定句型把每個 claim 寫成獨立陳述，包含相同概念標籤、主體、極性、條件、強弱和同一段引用。沒有鄰接索引 |

raw 忠實保留官方 user／system 模板。另兩個條件盡量只換 history block，保留 model、system、人口背景、題幹、量尺、token 上限、解碼設定。模型實際讀圖是文字；記錄 renderer 版本與實際送出的 payload hash。graph 和 flat 的主張清單、語義、引文、順序政策要可做機械核對。主試驗先完整讀入可見材料，三組都只做一次最後預測；不把檢索步數或多輪工具推理混成表示法差異。

至少有三個可測的邏輯介面，可順應現有程式命名：

- `build(history_view, builder_config) -> FrozenSnapshot | BuildFailure`。LLM 可一次取得這個 scope 的 QA 並以 tool call 或等價 schema-constrained JSON 提交 operations。Host 處理驗證、提交、可重試錯誤與 cache。
- `render(snapshot, format, budget_policy) -> text + claim_ids + cited_spans + token_count`。同版同設定得到相同渲染。完整模式不丟 QA／claim，無法容納時回報；另開同 token 預算的比較才可做事先固定的刪節。
- `predict(prediction_view, representation, config) -> {raw_response, usage, finish_reason, provider_request_id?, timing, status}`。T1 要求單一 A/B，T2 要求量尺內裸整數。官方預測檔留原回答。格式和越界另加診斷標記，不用自訂 parser、clamp、偷重試來美化其中一組的官方分數。真正 API 失敗保留 null，照官方規則計分。除錯若要索取引用，另做不影響正式輸出的 diagnostic pass，或展示可見證據；未取得採用證據時，UI 應區別「可見」與「模型自報引用」。

先沿用上游的英文預測 prompt。以下是給建圖模型的起始指令，可依 repo schema 對齊欄位，在看真人分數之前凍結：

```text
You are organizing the supplied interview evidence for a blinded evaluation.
Read only the numbered questions and participant answers in this history.
Submit typed graph operations through graph_propose. Keep concepts traceable
to the speaker's wording. For each claim, record who said it, whose position
it describes, the relation and direction, any stated condition, and whether
it was explicit or inferred. Cite exact spans of the supplied question or
answer; anchor a yes/no reply to both. Preserve qualifications and explicit
strength words. A leading question alone is insufficient evidence.
Keep an unstated comparison or priority unknown. Multiple plausible claims
may coexist if grounded. A model inference must identify supporting text.
Do not assign invented utility weights or infer a lasting change from
question order. If the history supports no relevant relation, return an
empty proposal with a machine-readable status.
```

預測 adapter 支援 chat endpoint／本機 serving 或 repo 現有 client。每個 run 固定 endpoint 類型、模型或 snapshot、溫度（官方預設 0.1）、可用時的 seed、輸出長度、重試政策及並發。builder 與 predictor 的模型及 token 成本分列。與工具選擇不相容的模型可依同一 operation schema 回結構化 JSON，由 host 執行相同驗證。在 manifest 記錄實際採用哪條路徑。

## 4. 圖、工具與事件紀錄

最小資料包含 immutable Evidence、Concept、可被證據支持或質疑的 Claim、可空的 Scope。Claim 必備來源、語義關係、主張者／談論對象、條件、直接或推論。條件未知、同等偏好、不可比較各自處理。初版關係包含 `influences, stance_on, prefers_over, more_important_than`。區分「他描述一般人的看法」和「他自己會怎麼選」。由原文明示的強弱可留原詞，別把一次選 A 自動換成「安全權重 0.8」。如需要超邊，把有 ID 的 Claim 連到多個參與概念、條件與證據即可，先用 repo 易維護的儲存方式。

採 MCP 風格的本機操作 registry，每個 tool 有名稱、description、JSON input/output schema 與可記錄錯誤。Host 綁定當前 scope、角色與可見資料，模型不能選其他人的 scope。最小工具：

| 名稱 | 可傳入 | 應回傳 |
|---|---|---|
| `evidence_read` | 本 scope 的 evidence refs，或 host 預先提供全部 | 原文 Q／A、欄位與位置 |
| `graph_propose` | request_id、expected_revision、operations[] | draft_id／驗證問題；支援一批內宣告 temp concept 再引用 |
| `graph_commit` | host 提交 validated draft、revision | committed revision、穩定 ID 對照與 events |
| `graph_read` | frozen revision、view，在診斷模式可指定 claim | 具型別的主張、引用與 rendered view |
| `trace_read` | 研究者查 run／item／event range | 可重播的結構化結果，gold 只在 scorer 之後疊加 |

工具 payload 示意。以下語句是自造 fixture，與 HugAgent 真人無關。假設 `E1.answer` 的完整文字是 `I prefer a short report on Fridays.`，`c1/c2` 已在同一 scope 建立，分別表示 short report 和 long report。此句只明說偏好短版，不足以斷言它勝過所有可能格式，故用 `stance_on`。

```json
{
  "request_id": "fixture-op-01",
  "expected_revision": 2,
  "operations": [{
    "op": "add_claim", "temp_id": "r1", "relation": "stance_on",
    "speaker": "participant", "about": "self", "target": "c1",
    "polarity": "positive", "condition": "on Fridays", "basis": "explicit",
    "evidence": [{"id": "E1", "field": "answer", "quote": "I prefer a short report on Fridays."}]
  }]
}
```

Host 根據 quote 解析 canonical span（以 Unicode code point、半開區間或 repo 既有單一約定），無法唯一匹配時要求 offset 和引文確認。批次檢查型別、端點、條件引用、scope、引用存在、衝突狀態與 revision，成功才原子提交；拒絕保留事件及錯誤碼，不部分寫入。相同 request_id＋相同 payload 重試回原結果，相同 ID 不同內容則拒絕。凍結後 prediction session 只讀。每筆 log 至少有 run/scope/request/event IDs、單調 seq、revision 前後、actor、operation、輸入摘要或受控位置、結果／錯誤、模型與設定 hash、evidence refs、tokens、latency。支援以 commit log 離線重建同 hash。記錄外部操作與簡短的證據依據即可。

第一版 operations 可從 `upsert_concept, add_claim, attach_evidence` 開始。合成更正／衝突夾具使用 `challenge_claim, retract_claim, supersede_rule` 分別記反證、撤回、明確取代。保留舊 claim 和原始 evidence，針對失去支持的衍生關係標記待重查。至少測試成功提交、重複請求、舊 revision、跨 scope 引用、引文找不到、批次失敗後的原子性。形如 `{"isError":true,"structuredContent":{"code":"EVIDENCE_OUT_OF_SCOPE","op_index":0,"retryable":false}}` 的回應有助於本機診斷；若日後暴露真正 MCP 端點，再依固定協定版補齊 wire 格式。

資料 adapter 可宣告 `has_within_person_domains, has_hypothetical_scenarios, has_observation_times, has_revision_labels`。HugAgent 前兩項可用，後兩項在此釋出無足夠標註。保留時間為空和自述時間的表達；不要從問答序號推論人改變。子情境是 `subcontext_of(scope, scope)`，規則例外是 `exception_of(rule, rule)`，同條件跨時改變另記 `supersedes`。父層規則未知只可建立局部條件，兩個重疊 sibling 衝突時留下 unresolved。輸入查詢的假設情境可以建 query overlay，不寫回永久 snapshot。用合成 fixture 驗證這些狀態；主實驗不強迫每題建樹。

## 5. 研究者前端

用本機 localhost 的既有前端架構。先完成 item 視圖，再做 run 總覽。桌面左列依原序 QA，中間圖，右列看題目、三組預測及選中 claim；窄螢幕改頁籤。圖能點回證據 span、調回原文、辨認是本人立場或他陳述的一般看法。節點 ID→位置穩定；同題切換不同 revision 不重排全圖。保留 filter、縮放、鍵盤焦點。支持以下三條驗收路徑：

1. 從總覽選「同題 Raw 對、Graph 錯」，打開該題，切三組實際模型輸入，查到缺掉的原話或錯誤主張。Gold 預設折疊，盲審可保持隱藏。
2. 選 scope 的一條 claim，QA 精確引文、條件、方向與出處同步高亮。不存在引用時明示缺項。query-only 的條件標成「題目假設」。人級選單只索引各題授權的 views。
3. 從操作軸點一次 reject 或 commit，比對前後 snapshot，重播成功後顯示相符的 hash。沒有真人時間軸時，頁籤標為「建圖操作紀錄」。對外 demo 與自動截圖全部用合成資料。

## 6. 評測、可重現與延伸

- 一份 manifest 記 data commit、檔案 hash、全部 item IDs、run_id、模型與 prompt/schema/renderer hash、資料可見模式及成本。全量預測可斷點續跑。每個 arm × item 只收一份有效回應；成本應含失敗重試及離線抽取，區分首次與重用。可先印 dry-run 成本估算。無模型服務時仍完成資料、原版基準、fixture、重播和 UI 的可測部分，如實報告真實 LLM 執行情況。
- 正式 scorer 使用上游 `Benchmark/hugagent_eval.py --data-dir <pinned-data> --score <responses.jsonl> --model <run-label> --out <result.json>`。固定版本資料，不以紙上或舊版本的模型分數代替本機 Raw。每行一個 `item_id` 搭原始字串 `response`。報 BSI accuracy、BDU 容差 accuracy、標準化 MAE、方向分數與有效配對數、ATI、unparsed，加每域與三種 T2 子型。官方 overall 為三域等權，方向使用模型預測的基準與情境，不給模型真人基準。全量可配方向最多 83/75/21 對，共 179。免模型 majority 應為 63.64／56.07／1.73／15.34／0.76，5-seed random 為 50.51／44.44／1.81／47.93／0.12（上述五個指標順序）。
- 預先凍結主要終點 T1 accuracy、T2 normalized MAE。輸出 Graph−Raw、Graph−Flat 配對差、以 54 人為 cluster 的 95% bootstrap 區間及每人／域分母。保留同一人全域及所有 arm 的配對；重抽同一人時給複本的 PID/item IDs 獨立命名或以權重計算，避免 scorer 去重。用獨立 synthetic 或自造資料調 prompt。任何根據真人錯題做出的下一版標為探索性，保留原 run。
- 第二階段以 `source_domain → target_domain` 配置實作論文三組同人 swap：healthcare → surveillance，surveillance → zoning，zoning → healthcare。目標人和題目不變，三個 arm 都只能取本人指定來源域唯一 T2 evidence view 的 QA。目標域 QA、答案、已建過的目標圖不能當輸入。核對所有預測的 evidence provenance，獨立報跨域成績；兩來源推一個目標的版本另外標記。這個實驗不混入官方域內主表。
- 增加一個**只需離線評分**的次要指標來檢驗 W7 的 rank 想法。從 `reason_evaluation` 依 PID、topic、question_id 在 `r_` 前的題幹 ID 分組。對不同理由產生無序配對，比較兩個真人分數與同一 arm 兩個預測分數的符號。此版涵蓋 52 人、262 組、994 對，其中 587 對真人同分、407 對有嚴格高低。報三類命中、嚴格高低子集命中（預測同分算錯）、有效覆蓋和逐人結果。未解析預測保留分母，另外列數量。不要將這個附加分數併入 ATI 或當成真實取捨的標籤。先用已交出的數字，不為此增加 API 呼叫。
- 保留可延伸的圖品質人工標註接口。不要以 gold 的 `source_qa` 作 retrieval target 或把模型 auto-grade 當真人評定。若要測 Tree，先統計可辨別父／子規則的案例，再拿同一規則資料做 flat routing vs tree routing。若真實資料無持續更新標籤，該能力留作合成驗收／將來換資料集測試。

## 7. 完成順序與交付

1. 讀 repo 後直接實作 audit、獨立 allowlist 與官方 scorer 接點，先過 54/1,742/460/271 和免模型基準。
2. 實作模型 adapter、抽取、fixture tool log、snapshot、Raw／Graph／Flat 三臂及端到端小樣本。確認原始 Raw prompt 與 upstream 相同，graph/flat 確實使用同一份抽取。真實題只作凍結後的工程 smoke；第一版開發用合成資料。
3. 凍結 manifest，使用已配置且授權的模型端點與預算跑可用的全量 54 人實驗。留下可續跑的結果。模型／預算不可用時列出實際 blocker、目前已驗證的範圍與單一步驟的全量執行命令，不能填入假數據。
4. 串起 item 檢視、操作軸、run 總覽與 paired 分析；以一個合成案例驗證 UI 和重播。交付 repo 現有慣例下的執行入口與精簡 README（資料版、dry-run、full run、重評、開 UI）。報告要能追到 manifest、每題原始回答與官方分數。

完成條件是「在完全相同的官方題目上，比得出 Graph vs Raw，並能用 Flat 和原話解釋差異」。不要拿更多頁面、更多工具或更複雜的 Tree 取代這件事。
