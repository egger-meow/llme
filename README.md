# LLMe · LLM + Me

這個碩士研究想知道，LLM 能從一個人的話裡理解哪些信念、條件與取捨。第一輪選 HugAgent 真人資料，問一個可以逐題核對的問題：**同一個預測模型拿到同一人的同一批訪談，把訪談整理成有證據的圖，會比直接讀完整問答更準嗎？**

**[第一次實驗｜研究背景、結果與分析](docs/hugagent/experiment-01/README.md)**。P01–P10、P44 共 11 人、380 題。Graph 與 Raw 的因果方向正確率幾乎持平；在量表題上，直接讀訪談的 Raw 在三個領域都最接近本人。報告收錄同批固定答案基準、逐題勝負數、配對差異圖、題型分析與限制，可直接在 GitHub 閱讀。

**[本機逐題互動報告](ref/experiments/cohort/index.html)** 可從總覽點進分組或判分不同的題目，並排核對本人答案、Raw／Graph／Flat 的原始輸出與評分。在逐題頁選「開啟 Graph 關係圖」，點節點或箭頭可讀原話。Tree 頁依同一份訪談的條件整理主張。

從 repo 根目錄執行 `python -m llme.cohort` 可用已保存的 11 次實驗離線重建。P01 選用 `P01-resumed`，P07 選用 `p07-recovered`。產生器核對實際提示詞、建圖快照、作答匯出及各 run 的官方評分，再重算合併結果與受訪者配對區間。總覽、逐題、Graph 與 Tree 均內嵌於同一個 HTML。建圖重播及完整提示詞連回相鄰 run 的 `audit.html`。含真人原文的輸出保存在本機 `ref/experiments/`。

| 從哪裡讀 | 內容 |
|---|---|
| [第一輪實驗實作計畫](docs/hugagent/experiment-plan.md) | 研究者審核入口。從 460 份允許訪談走到三組模型預測、離線重播與成本，列出工作順序和驗收方式。 |
| [LLM 接口](docs/hugagent/experiment-interfaces.md) · [結果表與分析計畫](docs/hugagent/analysis-plan.md) · [本週八分鐘 meeting](docs/hugagent/meeting-experiment-plan.md) | 核對模型能讀寫什麼、哪些結果能回答原問題，以及如何用 P07 的真題向老師說明。 |
| [互動式個人情境樹](docs/tree-review/index.html) | 直接用瀏覽器開啟。在 P46 的都市分區分枝內展開局部條件樹，點節點內的關係箭頭讀主張與訪談依據；切到工廠案例可檢查兩個兄弟分枝同時生效。 |
| [Graph、Tree 與 LLM 接口審核稿](docs/graph-tree-design.md) | P46 的真例與 W7 工廠的兄弟分支，說明何時要跨分支查例外，以及不同情境如何引用本人重視的概念。末段記錄已同意的推論原則與待審設計。 |
| [第一輪實驗資料](docs/hugagent/prepared-data.md) | 直接取用 Raw 輸入、建圖用訪談、考題與評分答案，以及逐人題數和離線驗收方式 |
| [會後現況與預期差異](docs/hugagent/meeting-brief.md) | 從 W7、W8 的構想到資料實查，說明洩漏如何改變建圖方式、第一輪能回答什麼，以及不同結果如何解讀 |
| [會議與第一輪決策](docs/hugagent/round-one.md) | W7、W8 到這輪設計的沿革、資料核對、比較的解讀、後續實作入口 |
| [完整研究設計](docs/hugagent/HugAgent-54-Research-Design.md) | 提供的原稿。含六筆真題、圖語義、工具操作、網站布局、跨域與 Rank |
| [原始實作 prompt](docs/hugagent/LLME-Implementation-Prompt.md) | 保留原稿供查閱。後續實作以研究者審核後的第一輪實驗計畫與接口為準。 |
| [W7](meetings/W7.pdf) · [W8](meetings/w8.pdf) | 兩次會議投影片 |

資料已準備到可以接實驗程式。54 位受訪者的 1,742 道題已逐題核對官方 Raw 輸入，460 份訪談各自保留原本能看的 QA。可直接查[每人各域的題數](ref/HugAgent/prepared/participant_counts.csv)與[本機資料版本清單](ref/HugAgent/prepared/manifest.json)。下面的指令可以從建圖一路跑到評分。

## 本機真人資料瀏覽器

### 第一輪 runner

從 repo 根目錄使用 Python 3.11 以上。下列命令可離線驗證資料路由、三組各 1,742 格作答及官方評分。fixture 使用固定 A／1 與合法空圖，僅用來檢查管線。輸出目錄在 Git 忽略的 `ref/experiments/`。

```powershell
python -m llme.run --output ref/experiments/plan-v1 preflight
python -m llme.inference --run fixture-v1 --offline-fixture
python -m llme.run --output ref/experiments/fixture-v1/report score --responses ref/experiments/fixture-v1
```

正式執行時在本機環境設定 `GEMINI_API_KEY` 和 `GEMINI_MODEL`（確切模型 ID）。金鑰只放環境變數。例：`python -m llme.inference --run google-v1 --max-calls 10 --policy ref/google-run.json` 最多送出十次請求，先進行建圖。相同命令從 SQLite 已保存的工作繼續，每次執行有新的請求額度。複製 configs/google-run.example.json 到 ref/google-run.json，填寫同一模型 ID、官方輸入／輸出容量、核准的美元預算、適用於所有級距的最高輸入／輸出單價（美元／百萬 token），並記錄費率來源與日期。每次生成前用 Google countTokens 取得完整訊息的輸入數，加上設定的最大輸出預留金額。保守預留跨續跑累計，含送達未知的請求；預留額可能高於最後帳單。--max-calls 只計生成，另有計數請求。請勿對同一 run 同時啟動兩個程序。更換模型或抽取程式須使用新的 run 名稱。完成後以同一個 score 指令換成該 run 的路徑評分。報告目錄必須是新目錄。[Google 模型端點](https://ai.google.dev/api/generate-content)

每份訪談只交一次完整 JSON 提議，原提議和已接受的快照存於 `events.sqlite`。格式與引用驗證失敗會留下拒絕原因，該訪談的 Graph／Flat 以缺答計分。服務連線錯誤會中止，可續跑。報表含三組官方分數、逐題 CSV、配對差值與區間 HTML、理由排序 CSV。盲審資料包在評分時產生。多批修圖與 Tree 路由留給後續實驗。

### 瀏覽原始資料

以瀏覽器開啟 [HugAgent 資料檢視器](ref/HugAgent/index.html)。資料來源改為 [egger-meow/HugAgent 固定版本](https://github.com/egger-meow/HugAgent/tree/2bbd18e76db4be1de3b5bce3b5e239898a6a2750/Benchmark/data)。六份 JSONL 與 LICENSE 放在 `ref/HugAgent/data`，在 repo 根目錄執行 `python tools/hugagent/build.py` 可驗證六檔雜湊並重建 HTML。下載檔與含訪談的 HTML 依設定留在本機。

同步後的 fork 六份真人 JSONL 均與研究設計記錄的 data-v1.1 SHA-256 相符。

### 實驗流程與建圖重播

執行 `python -m llme.audit ref/experiments/fixture-v1`，用瀏覽器開啟該目錄的 `audit.html`。推論中也能匯出，重新執行即可更新。將官方評分輸出至該次執行的 `report` 子目錄後再次匯出，即可從同頁查看結果和配對差異圖。

每份訪談的起點以 scope 和原始問答計算 SHA-256。每筆新增主張包含完整內容、引文和上一筆雜湊。匯出時重新計算操作鏈、檢查引文並重建 Graph 和 Flat，與保存的快照比對。舊版執行從原始模型回覆重建，畫面會標明。時間軸表示一份提議的套用順序。模型版本更新後重新推論可能產生不同回覆。

### 接上金鑰前的架構驗收

用 `python -m unittest discover -s tests -v` 在本機演練截斷回覆、未知送達、中斷後續跑、模型修訂漂移，以及預測 prompt 遭竄改。測試使用自造問答和本機模擬回覆。

每次真實請求先登記 attempt。若送出後連線中斷，下次執行會列出該工作的 ID。確認舊程序已停止，且接受該次可能重複計費，才在原命令加上 `--retry-uncertain JOB`。服務端回傳截斷時會保存原文與結束原因，該工作以失敗計。服務端回報的模型修訂在 run 中改變時，整次 run 標為無效。

逐題表同列官方解析與整句嚴格解析。評分頁連到域別、逐題差異、方向配對、Rank 分母及 token 用量表。能從同一份保存的回答重算報告。正式費率與模型容量由研究者在接 key 時填入 policy。盲審只交付 report/reviewer 子目錄；研究者保留 unblinding.csv。依 phase1 先獨立讀原話，再讀 phase2 比較有沒有漏抽。

完整離線故障演練可在新的 run 名稱加上 `--offline-fixture --exercise-failures`，會產生一份僅含原始問答證據的備援圖、其餘含主張的圖及不同組別的合成答案。正式模式在第一個預測前先驗全體已渲染 prompt 的 token 數。報表的 artifacts.json 記錄每個檔案與分析程式的 SHA-256，可比對獨立重評結果。

第一輪範圍、驗收證據及正式開跑邊界整理在[接 key 前的架構驗收](docs/hugagent/pre-key-audit.md)。

### 從一題開始

將 `.env.example` 複製到 repo 根目錄的 `.env`，把 API key 填在 `GEMINI_API_KEY=` 後面。範本已填入 Gemini 3.5 Flash-Lite 的容量和 Standard 付費文字費率。預算預設為 0.25 美元。容量的單位是每次請求的 token 數，單價是每百萬 token 的美元數。換模型時同步更新容量、單價和查價日期。[官方容量](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) · [官方費率](https://ai.google.dev/gemini-api/docs/pricing)

```powershell
python -m llme.inference --run pilot-p07 --participant P07 --limit 1 --preview
python -m llme.inference --run pilot-p07 --participant P07 --limit 1 --max-calls 4 --finish
```

第一行只預覽規模。第二行執行單題試跑，最多生成四次。終端機會顯示進度。完成後開啟 `ref/experiments/pilot-p07/audit.html` 看建圖與評分，`usage.json` 記錄 token 與估計費用。進行中可執行 `python -m llme.audit ref/experiments/pilot-p07` 更新 HTML 快照。


### 建圖輸出異常與舊實驗補跑

每份訪談都會產生 Graph 和 Flat，兩組使用完全相同的內容。建圖器回傳陣列或省略可選欄位時，程式會修復格式。部分主張無法驗證時，保留能對回原話的主張；完全無可用主張時，逐段保存問答證據並標記 `evidence_only`，繼續三組預測。稽核頁可檢視原始回覆、修復項目與實際送入模型的內容。分析時可依建圖狀態分組。

舊版實驗可在新目錄用 `--recover-from 原run名稱` 補跑。例如 `python -m llme.inference --run p07-recovered --recover-from p07 --participant P07 --max-calls 20 --finish`。沿用原始回覆和預留帳本，只生成缺少的預測。使用個別核准的預算時可另外傳入 `--policy`。
