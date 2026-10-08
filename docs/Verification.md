# incident-agent-runtime — V1 Verification Record

本文件記錄實際執行過的驗證。依 proposal §19，「已執行」、「未執行」、「受環境限制」分開列出，未實際執行的項目不標成通過。

Docker 啟動成功、fake-model 測試通過、live-model scenario 成功是三個不同的驗收項目，不能互相代替。

## 1. 驗證環境

| 項目 | 值 |
|---|---|
| OS | Windows 11 專業版（10.0.22631），Docker Desktop（Linux containers） |
| CPU | 13th Gen Intel Core i5-13500（14 核心 / 20 執行緒）；Docker 可用 20 CPU |
| GPU | 未使用（CPU 模式） |
| RAM | 主機 15.6 GB；Docker 可用約 7.6 GB（8,116,666,368 bytes） |
| Docker Engine / Compose | 29.8.0 / v5.5.1 |
| Ollama | `ollama/ollama:0.35.1`（server 回報 `ollama version is 0.35.1`） |
| 模型 | `qwen2.5:7b`，`ollama list` ID `845dbda0ea48`，4.7 GB；第 1–4 次使用 `llama3.2:3b`（ID `a80c4f17acd5`，2.0 GB） |
| PostgreSQL | `postgres:17.10-bookworm` |
| Python 映像 | `python:3.12.15-slim-bookworm` |

## 2. Deterministic 測試（fake model）

| 日期 | 指令 | 結果 |
|---|---|---|
| 2026-10-07 | `docker compose --profile test run --build --rm tests` | 104 passed, 1 deselected（`llm`） |
| 2026-10-07 | 同上（M4 結束時） | 105 passed, 1 deselected（`llm`） |

### GitHub Actions

| 日期 | 觸發 | 結果 |
|---|---|---|
| 2026-10-08 | PR（`feat/m5-ci`） | 第一次 `Lockfile` 失敗：`astral-sh/setup-uv@v10` 不存在（該 action 只發布完整版本 tag），改為固定 v10.2.0 的 commit 後 4 個 job 全數通過 |
| 2026-10-08 | push 到 `main`（改寫 commit 作者後重建 repo） | 4 個 job 全數通過 |
| 2026-10-08 | PR（`feat/m5-pull-progress`） | 4 個 job 全數通過；`protect-main` ruleset 生效後的第一個 PR |

失敗時上傳 log artifact 的步驟已設定，但尚未遇到失敗，因此未實際觸發過。

## 3. 啟動與初始化

| 日期 | 項目 | 結果 |
|---|---|---|
| 2026-10-07 | `docker compose up --build -d`，全新 `ollama_data` volume | `migrate`、`model-init` 皆 `Exited (0)`；`db`、`ollama`、`api` healthy |
| 2026-10-07 | Ollama 映像下載 | 367 秒 |
| 2026-10-07 | `model-init` 首次下載 `llama3.2:3b`（含等待 Ollama 啟動） | 約 88 秒 |
| 2026-10-07 | `GET /ready` | `{"status":"ready"}` |
| 2026-10-07 | 再次執行 `docker compose run --rm model-init` | `Model llama3.2:3b is already available.`，未重新下載 |
| 2026-10-07 | 預設模型改為 `qwen2.5:7b` 後 `docker compose up --build -d` | `model-init` 重新執行並下載新模型，`Model qwen2.5:7b is available.`；`api` healthy，`/ready` 回 ready |
| 2026-10-07 | Ollama 對主機開放 port | 否（只有容器內 `11434/tcp`） |

## 4. Live-model scenario（`scripts.live_smoke`）

| # | 日期 | 模型 | 耗時 | 結果 | 說明 |
|---|---|---|---|---|---|
| 1 | 2026-10-07 | `llama3.2:3b` | 53.3 秒 | **FAIL**：report 沒有 hypothesis | 模型呼叫 `query_logs(service="checkout", keyword="14:20")`，把事件描述中的時間當成 keyword；fixture 沒有包含 `14:20` 的行，工具回傳空清單，因此沒有證據可引用。系統行為正確（grounding 未放行虛構證據），問題在模型對 keyword 的理解 |
| 2 | 2026-10-07 | `llama3.2:3b` | > 300 秒 | **FAIL**：504 deadline exceeded | API 重建後的第一次調查；原因未確認（可能是模型重新載入加上 CPU 推論），未保留 Ollama log |
| 3 | 2026-10-07 | `llama3.2:3b` | 43.3 秒 | **FAIL**：report 沒有 hypothesis | 呼叫 `query_logs(service="checkout", keyword="timeout")`，取得 1 行證據，但 report 仍回傳空的 hypotheses |
| 4 | 2026-10-07 | `llama3.2:3b` | 21.5 秒 | **FAIL**：report 沒有 hypothesis | 同第 3 次 |
| 5 | 2026-10-07 | `qwen2.5:7b` | 未記錄 | **FAIL**：502 `Agent model call failed: `（訊息空白） | 模型下載後的第一次調查。推測為首次載入 4.7 GB 模型加上 CPU 處理超過單次請求 120 秒上限（`httpx.ReadTimeout` 的訊息為空字串）；未保留 Ollama log，原因未確認。之後錯誤訊息改為在訊息空白時顯示例外類型 |
| 6 | 2026-10-07 | `qwen2.5:7b` | 223.3 秒 | **PASS** | `query_logs(service="checkout")` → `query_logs(service="checkout", keyword="timeout")`；hypothesis「database connection pool exhaustion」（high），引用 14:21、14:22 兩行 |
| 7 | 2026-10-07 | `qwen2.5:7b` | 100.3 秒 | **PASS** | 工具呼叫同第 6 次；hypothesis 與引用相同，next steps 略有不同 |

人工檢查（第 6、7 次）：假設與 checkout fixture 的內容相符（連線逾時 → 連線池耗盡 → 重試），引用的兩行皆為工具實際回傳的完整行，建議的下一步對應該假設。此結果代表端到端流程在此環境可行，不代表之後每次推論都會成功；7 次中 2 次成功，皆為 `qwen2.5:7b`。

第 1 次失敗後的調整：agent prompt 與 `query_logs` 的 keyword 說明改為明確表示 keyword 是日誌文字的子字串、不是時間篩選，並建議先不帶 keyword、查無結果時改為不帶 keyword 再查；report prompt 要求有證據時至少提出一個引用證據的 hypothesis。未加入任何替模型決定工具參數的程式分支（proposal §10）。

第 3、4 次的 keyword `"timeout"` 是 prompt 中的範例字，模型直接照抄；之後已移除 prompt 與工具說明中的範例字，改為「先只帶 service 查詢」。

### 更換預設模型

第 3、4 次顯示 `llama3.2:3b` 在取得證據後仍傾向輸出空的 hypotheses。`ChatOllama` 預設以 `json_schema` 模式約束輸出，而 schema 允許空陣列，小模型會選擇最省事的合法輸出。依 proposal §8，預設模型改為 `qwen2.5:7b`（4.7 GB，tool calling 與 JSON 輸出較穩定）。代價是下載較大、需要較多記憶體，CPU 上每次調查較慢。

### 本機環境限制：HTTPS 攔截

此機器的端點防護軟體會以自有根憑證重新簽發 HTTPS 連線，Ollama 容器下載模型時出現 `x509: certificate signed by unknown authority`。處理方式為本機專用、不提交的 `compose.override.yaml`：以 `ollama/ollama:0.35.1` 為基底 build 一個加入該根憑證並設定 `SSL_CERT_DIR` 的映像。此機器的 Docker 服務無法讀取使用者目錄的 bind mount，因此改用 build 方式。專案本身的設定未變更。

### `pytest -m llm`

| 日期 | 指令 | 結果 |
|---|---|---|
| 2026-10-08 | `docker compose --profile test run --build --rm -e OLLAMA_BASE_URL=http://ollama:11434 tests pytest -m llm` | **PASS**：1 passed, 106 deselected，199.94 秒（`qwen2.5:7b`） |

## 5. 尚未執行

- 單次請求逾時（120 秒）與整體 deadline（300 秒）在 CPU 跑 7B 模型時是否足夠：第 6 次耗時 223 秒，接近 deadline。
- 一般停止 / 重啟後資料與模型保留（M5）。
- 全新 clone 重現（M5）。
