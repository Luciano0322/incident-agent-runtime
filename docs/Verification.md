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
| Ollama | `ollama/ollama:0.35.1`（server 版本待補） |
| 模型 | `llama3.2:3b`（digest 待補） |
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

第 1 次失敗後的調整：agent prompt 與 `query_logs` 的 keyword 說明改為明確表示 keyword 是日誌文字的子字串、不是時間篩選，並建議先不帶 keyword、查無結果時改為不帶 keyword 再查；report prompt 要求有證據時至少提出一個引用證據的 hypothesis。未加入任何替模型決定工具參數的程式分支（proposal §10）。

## 5. 尚未執行

- 調整 prompt 後的 live smoke。
- `pytest -m llm`。
- 一般停止 / 重啟後資料與模型保留（M5）。
- 全新 clone 重現（M5）。
