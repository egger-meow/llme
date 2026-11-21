# LLMe · LLM + Me

這個碩士研究想知道，LLM 能從一個人的話裡理解哪些信念、條件與取捨。第一輪選 HugAgent 真人資料，問一個可以逐題核對的問題：**同一個預測模型拿到同一人的同一批訪談，把訪談整理成有證據的圖，會比直接讀完整問答更準嗎？**

| 從哪裡讀 | 內容 |
|---|---|
| [會後現況與預期差異](docs/hugagent/meeting-brief.md) | 從 W7、W8 的構想到資料實查，說明洩漏如何改變建圖方式、第一輪能回答什麼，以及不同結果如何解讀 |
| [會議與第一輪決策](docs/hugagent/round-one.md) | W7、W8 到這輪設計的沿革、資料核對、比較的解讀、後續實作入口 |
| [完整研究設計](docs/hugagent/HugAgent-54-Research-Design.md) | 提供的原稿。含六筆真題、圖語義、工具操作、網站布局、跨域與 Rank |
| [原始實作 prompt](docs/hugagent/LLME-Implementation-Prompt.md) | 保留原稿供未來 coding agent 參考。第一輪請從決策文件末段的交接指令開始 |
| [W7](meetings/W7.pdf) · [W8](meetings/w8.pdf) | 兩次會議投影片 |

目前已完成會議與資料調查、免模型基準核對及實驗設計。Raw、Graph、Flat 的模型成績待正式實驗產生。

## 本機真人資料瀏覽器

以瀏覽器開啟 [HugAgent 資料檢視器](ref/HugAgent/index.html)。資料來源改為 [egger-meow/HugAgent 固定版本](https://github.com/egger-meow/HugAgent/tree/ea0d98111394a017be79cf7a1e6accbe47e95559/Benchmark/data)。六份 JSONL 與 LICENSE 放在 `ref/HugAgent/data`，在 repo 根目錄執行 `python tools/hugagent/build.py` 可驗證六檔雜湊並重建 HTML。下載檔與含訪談的 HTML 依設定留在本機。

先前文件的實查與 scorer 基準使用上游 data-v1.1。fork 的都市分區 Task 2 含有不同的理由題與真人答案，後續評分、理由配對與基準應依 fork 重新計算。兩版在 54 人、1,742 題、460 份訪談輸入、271 題跨題重現遮蔽 QA 的統計一致。
