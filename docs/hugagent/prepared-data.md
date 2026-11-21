# 第一輪實驗資料

資料包位於 `ref/HugAgent/prepared/`。它保留 HugAgent 官方 test 的 54 人、356 道 T1、1,386 道 T2。每個實驗組都可用同一組 1,742 個 `item_id` 作答和對分。本機版本來自已同步的 fork，六份 JSONL 均符合 data-v1.1 的 SHA-256。[固定版原檔](https://github.com/egger-meow/HugAgent/tree/2bbd18e76db4be1de3b5bce3b5e239898a6a2750/Benchmark/data) · [版本與驗收](../../ref/HugAgent/prepared/manifest.json)

## 實驗程式從哪裡讀

| 用途 | 檔案與用法 |
|---|---|
| Raw 直接作答 | 每題一列。以 `item_id` 記錄結果，將該列 `messages` 作為官方完整英文 system、user 輸入。[raw_prompts.jsonl](../../ref/HugAgent/prepared/inputs/raw_prompts.jsonl) |
| Graph 建圖 | 每份訪談一列。程式按 `scope_id` 取出 `context_qas` 給建圖器，含依序編號的證據、英文問句和真人回答。[histories.jsonl](../../ref/HugAgent/prepared/inputs/histories.jsonl) |
| Graph、Flat 作答 | 每題一列。`prediction` 含背景、題幹、選項或量尺、適用時的理由文字。由外層的 `task_type` 選官方模板，以 `scope_id` 找到同一份訪談產生的表示，再組成模型輸入。[questions.jsonl](../../ref/HugAgent/prepared/inputs/questions.jsonl) |
| 評分 | 以 `item_id` 對預測。T1 保存 `answer`、被遮住的 `source_qa` 及標註 `reasoning`。三筆官方雙標籤原樣保留為 `A/B`。T2 保存真人問卷的整數 `user_answer`。[answers.jsonl](../../ref/HugAgent/prepared/scoring/answers.jsonl) |
| 研究者索引 | 可查每題的受訪者、主題、任務、問卷題號、`scope_id`、原始檔名與行號，也可按 54 人 × 3 域查看 T1、T2 題數與訪談份數。[items.csv](../../ref/HugAgent/prepared/items.csv) · [participant_counts.csv](../../ref/HugAgent/prepared/participant_counts.csv) |

例如 P07 有 30 題。監控 T1 的兩題分別少一段不同的 QA，T2 的 11 題共用 20 段，所以 13 題要取 **3 份訪談**。都市分區 T1 的 4 題和 T2 的 5 題全都讀同一份 26 段訪談，9 題只用 **1 份**。醫療 8 題使用 2 份。全資料依資料版、本人、主題、完整有序 QA 識別出 460 份。單份訪談內的 `e001` 是第一段可見 QA，跨訪談引用時需連同 `scope_id` 一起保存。原始問答編號可按來源行與陣列位置回查。

## 題數與離線對分

T2 官方 `opinion` 共 389 道，`reason_evaluation` 共 997 道。依題幹可將 389 道再描述為基準支持度 77、經驗或感受 155、假設情境 157。`items.csv` 的 `measure` 是本研究依題幹加的欄位。經驗或感受對應監控 2.2–2.4 與醫療 3.2–3.4，例如「看見監視器時，多常覺得比較安全」。正式評分沿用官方題型與量尺。

- 官方方向算法會將同人同域的基準題配上其他 `opinion` 題，最多 179 對，其中 92 對是假設情境，87 對是經驗或感受。實際計分分母取決於模型輸出能否解析。[方向配對](../../ref/HugAgent/prepared/scoring/direction_pairs.csv)
- 理由排序涵蓋 52 人、994 對。同人、同域、同一問卷題幹下的兩個不同理由才能配對。`gold_sign` 是左題真人分數減右題分數的符號，587 對同分，407 對有高低。後續可直接取用兩道 T2 預測來比較。[理由配對](../../ref/HugAgent/prepared/scoring/rank_pairs.csv)

## 重建與核對

在 repo 根目錄以 Python 3.11 或更新版執行。已有本機來源檔時全程離線。

```powershell
python -X utf8 tools/hugagent/prepare.py
python -X utf8 tools/hugagent/prepare.py --check
```

初次取得資料可執行 `python -X utf8 tools/hugagent/prepare.py --fetch`。程式會從固定 fork commit 補齊六個 JSONL、授權文件與官方評分程式，再核對雜湊。瀏覽器另由 `python -X utf8 tools/hugagent/build.py` 產生。真人資料與衍生檔都在 Git 忽略的 `ref/`，使用條件隨資料包保留。[授權文件](../../ref/HugAgent/prepared/LICENSE)

驗收逐題回讀實驗輸入、檢查欄位與證據編號，並用固定版本的官方 `build_prompt` 比較兩則訊息的完整字串，1,742 題全部相同。356 道 T1 的遮蔽問答在該題訪談逐字命中 0 道，在本人同域的 T2 訪談逐字命中 271 道。官方固定答案與五種子隨機基準均重現先前紀錄。`--check` 另會完整重建並逐檔比對已交付資料。[官方評分程式](https://github.com/egger-meow/HugAgent/blob/2bbd18e76db4be1de3b5bce3b5e239898a6a2750/Benchmark/hugagent_eval.py)
