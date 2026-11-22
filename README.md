# LLMe · LLM + Me

這個碩士研究想知道，LLM 能從一個人的話裡理解哪些信念、條件與取捨。第一輪選 HugAgent 真人資料，問一個可以逐題核對的問題：**同一個預測模型拿到同一人的同一批訪談，把訪談整理成有證據的圖，會比直接讀完整問答更準嗎？**

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

資料已準備到可以接實驗程式。54 位受訪者的 1,742 道題已逐題核對官方 Raw 輸入，460 份訪談各自保留原本能看的 QA。可直接查[每人各域的題數](ref/HugAgent/prepared/participant_counts.csv)與[本機資料版本清單](ref/HugAgent/prepared/manifest.json)。下一階段是實驗環境、建圖與模型預測。

## 本機真人資料瀏覽器

### 第一輪 runner

從 repo 根目錄使用 Python 3.11 以上。下列命令可離線驗證資料路由、三組各 1,742 格作答及官方評分。fixture 使用固定 A／1 與合法空圖，僅用來檢查管線。輸出目錄在 Git 忽略的 `ref/experiments/`。

```powershell
python -m llme.run --output ref/experiments/plan-v1 preflight
python -m llme.inference --run fixture-v1 --offline-fixture
python -m llme.run --output ref/experiments/fixture-v1/report score --responses ref/experiments/fixture-v1
```

正式執行時在本機環境設定 `GEMINI_API_KEY` 和 `GEMINI_MODEL`（確切模型 ID）。金鑰只放環境變數。例：`python -m llme.inference --run google-v1 --max-calls 10` 最多送出十次請求，先進行建圖。相同命令從 SQLite 已保存的工作繼續，每次執行有新的請求額度。此上限以次數計，費用上限須另在供應端管理。請勿對同一 run 同時啟動兩個程序。更換模型或抽取程式須使用新的 run 名稱。完成後以同一個 score 指令換成該 run 的路徑評分。報告目錄必須是新目錄。[Google 模型端點](https://ai.google.dev/api/generate-content)

每份訪談只交一次完整 JSON 提議，原提議和已接受的快照存於 `events.sqlite`。格式與引用驗證失敗會留下拒絕原因，該訪談的 Graph／Flat 以缺答計分。服務連線錯誤會中止，可續跑。報表含三組官方分數、逐題 CSV、配對差值與區間 HTML、理由排序 CSV。進階多批修圖、人工盲審及費率預檢仍依研究計畫擴充。

### 瀏覽原始資料

以瀏覽器開啟 [HugAgent 資料檢視器](ref/HugAgent/index.html)。資料來源改為 [egger-meow/HugAgent 固定版本](https://github.com/egger-meow/HugAgent/tree/2bbd18e76db4be1de3b5bce3b5e239898a6a2750/Benchmark/data)。六份 JSONL 與 LICENSE 放在 `ref/HugAgent/data`，在 repo 根目錄執行 `python tools/hugagent/build.py` 可驗證六檔雜湊並重建 HTML。下載檔與含訪談的 HTML 依設定留在本機。

同步後的 fork 六份真人 JSONL 均與研究設計記錄的 data-v1.1 SHA-256 相符。
