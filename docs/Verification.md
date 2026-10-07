# incident-agent-runtime — V1 Verification Record

本文件記錄實際執行過的驗證。依 proposal §19，「已執行」、「未執行」、「受環境限制」分開列出，未實際執行的項目不標成通過。

Docker 啟動成功、fake-model 測試通過、live-model scenario 成功是三個不同的驗收項目，不能互相代替。

## 1. 驗證環境

| 項目 | 值 |
|---|---|
| OS | 待補 |
| CPU | 待補 |
| GPU | 未使用（CPU 模式） |
| RAM（主機 / Docker 可用） | 待補 |
| Docker Engine / Compose | 待補 |
| Ollama | `ollama/ollama:0.35.1`（server 回報 `ollama version is 0.35.1`） |
| 模型 | `qwen2.5:7b`（digest 待補）；第 1–4 次使用 `llama3.2:3b` |
| PostgreSQL | `postgres:17.10-bookworm` |
| Python 映像 | `python:3.12.15-slim-bookworm` |

## 2. Deterministic 測試（fake model）

| 日期 | 指令 | 結果 |
|---|---|---|
| 2026-10-07 | `docker compose --profile test run --build --rm tests` | 104 passed, 1 deselected（`llm`） |

## 3. 啟動與初始化

| 日期 | 項目 | 結果 |
|---|---|---|
| 2026-10-07 | `docker compose up --build -d`，全新 `ollama_data` volume | `migrate`、`model-init` 皆 `Exited (0)`；`db`、`ollama`、`api` healthy |
| 2026-10-07 | Ollama 映像下載 | 367 秒 |
| 2026-10-07 | `model-init` 首次下載 `llama3.2:3b`（含等待 Ollama 啟動） | 約 88 秒 |
| 2026-10-07 | `GET /ready` | `{"status":"ready"}` |
| 2026-10-07 | 再次執行 `docker compose run --rm model-init` | `Model llama3.2:3b is already available.`，未重新下載 |
| 2026-10-07 | Ollama 對主機開放 port | 否（只有容器內 `11434/tcp`） |

## 4. Live-model scenario（`scripts.live_smoke`）

| # | 日期 | 模型 | 耗時 | 結果 | 說明 |
|---|---|---|---|---|---|
| 1 | 2026-10-07 | `llama3.2:3b` | 53.3 秒 | **FAIL**：report 沒有 hypothesis | 模型呼叫 `query_logs(service="checkout", keyword="14:20")`，把事件描述中的時間當成 keyword；fixture 沒有包含 `14:20` 的行，工具回傳空清單，因此沒有證據可引用。系統行為正確（grounding 未放行虛構證據），問題在模型對 keyword 的理解 |
| 2 | 2026-10-07 | `llama3.2:3b` | > 300 秒 | **FAIL**：504 deadline exceeded | API 重建後的第一次調查；原因未確認（可能是模型重新載入加上 CPU 推論），未保留 Ollama log |
| 3 | 2026-10-07 | `llama3.2:3b` | 43.3 秒 | **FAIL**：report 沒有 hypothesis | 呼叫 `query_logs(service="checkout", keyword="timeout")`，取得 1 行證據，但 report 仍回傳空的 hypotheses |
| 4 | 2026-10-07 | `llama3.2:3b` | 21.5 秒 | **FAIL**：report 沒有 hypothesis | 同第 3 次 |

第 1 次失敗後的調整：agent prompt 與 `query_logs` 的 keyword 說明改為明確表示 keyword 是日誌文字的子字串、不是時間篩選，並建議先不帶 keyword、查無結果時改為不帶 keyword 再查；report prompt 要求有證據時至少提出一個引用證據的 hypothesis。未加入任何替模型決定工具參數的程式分支（proposal §10）。

第 3、4 次的 keyword `"timeout"` 是 prompt 中的範例字，模型直接照抄；之後已移除 prompt 與工具說明中的範例字，改為「先只帶 service 查詢」。

### 更換預設模型

第 3、4 次顯示 `llama3.2:3b` 在取得證據後仍傾向輸出空的 hypotheses。`ChatOllama` 預設以 `json_schema` 模式約束輸出，而 schema 允許空陣列，小模型會選擇最省事的合法輸出。依 proposal §8，預設模型改為 `qwen2.5:7b`（4.7 GB，tool calling 與 JSON 輸出較穩定）。代價是下載較大、需要較多記憶體，CPU 上每次調查較慢。

## 5. 尚未執行

- `qwen2.5:7b` 的 live smoke。
- `pytest -m llm`。
- 一般停止 / 重啟後資料與模型保留（M5）。
- 全新 clone 重現（M5）。
