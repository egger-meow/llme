# LLMe · LLM + Me

這個碩士研究想知道，LLM 能從一個人的話裡理解哪些信念、條件與取捨。第一輪選 HugAgent 真人資料，問一個可以逐題核對的問題：**同一個預測模型拿到同一人的同一批訪談，把訪談整理成有證據的圖，會比直接讀完整問答更準嗎？**

| 從哪裡讀 | 內容 |
|---|---|
| [第一輪實驗資料](docs/hugagent/prepared-data.md) | 直接取用 Raw 輸入、建圖用訪談、考題與評分答案，以及逐人題數和離線驗收方式 |
| [會後現況與預期差異](docs/hugagent/meeting-brief.md) | 從 W7、W8 的構想到資料實查，說明洩漏如何改變建圖方式、第一輪能回答什麼，以及不同結果如何解讀 |
| [會議與第一輪決策](docs/hugagent/round-one.md) | W7、W8 到這輪設計的沿革、資料核對、比較的解讀、後續實作入口 |
| [完整研究設計](docs/hugagent/HugAgent-54-Research-Design.md) | 提供的原稿。含六筆真題、圖語義、工具操作、網站布局、跨域與 Rank |
| [原始實作 prompt](docs/hugagent/LLME-Implementation-Prompt.md) | 保留原稿供未來 coding agent 參考。第一輪請從決策文件末段的交接指令開始 |
| [W7](meetings/W7.pdf) · [W8](meetings/w8.pdf) | 兩次會議投影片 |

資料已準備到可以接實驗程式。54 位受訪者的 1,742 道題已逐題核對官方 Raw 輸入，460 份訪談各自保留原本能看的 QA。可直接查[每人各域的題數](ref/HugAgent/prepared/participant_counts.csv)與[本機資料版本清單](ref/HugAgent/prepared/manifest.json)。下一階段是實驗環境、建圖與模型預測。

## 本機真人資料瀏覽器

以瀏覽器開啟 [HugAgent 資料檢視器](ref/HugAgent/index.html)。資料來源改為 [egger-meow/HugAgent 固定版本](https://github.com/egger-meow/HugAgent/tree/2bbd18e76db4be1de3b5bce3b5e239898a6a2750/Benchmark/data)。六份 JSONL 與 LICENSE 放在 `ref/HugAgent/data`，在 repo 根目錄執行 `python tools/hugagent/build.py` 可驗證六檔雜湊並重建 HTML。下載檔與含訪談的 HTML 依設定留在本機。

同步後的 fork 六份真人 JSONL 均與研究設計記錄的 data-v1.1 SHA-256 相符。
