# incident-agent-runtime — V1 TDD Workflow Checklist

版本：Draft 1  
日期：2026-10-07  
需求依據：[incident-agent-runtime-docker-proposal.md](incident-agent-runtime-docker-proposal.md)（下稱 proposal）

本文件把 V1 的實作切成 M0–M5 六個階段。每個階段定義要做到的程度、依序要完成的 red → green slices、不靠測試而靠指令驗證的項目，以及進入下一階段的條件。實作時以本文件決定「現在做哪一步、做到哪裡為止」。

本文件和 proposal 衝突時，以 proposal 為準，並回頭修正本文件。

## 1. 工作規則

### 1.1 Red → Green 迴圈

每個 slice 都照這個順序：

1. 從本階段清單挑**下一個**未完成的 slice。
2. 寫一個測試，描述這個 slice 的行為。
3. 執行測試，**確認它因為預期的原因失敗**（red）。測試錯在 import 或 fixture 而失敗，不算 red。
4. 寫剛好讓它通過的最少程式碼（green）。
5. 執行目前所有 `not llm` 測試，確認全部通過。
6. 勾選該 slice，commit。

規則：

- **一次一個 slice。** 不要先寫完整個階段的測試再一起實作。下一個測試應該根據上一輪學到的東西調整。
- **不預先實作。** 不為後面的 slice 或後面的階段提前加程式碼或參數。
- **重構不在迴圈內。** 重構在階段結束的 review 時做，且重構前後測試都要是綠的。
- **清單可以調整。** 實作中發現某個 slice 應該拆開、合併或改順序，直接修改本文件並在 commit 說明原因；但不得新增 proposal 範圍外的功能。

### 1.2 什麼是好的測試

- 透過**公開介面**（第 2 節的 seams）驗證行為，不測私有函式、不檢查 LangGraph 內部 state、不逐字比對 prompt。
- 測試名稱描述行為，例如 `test_unknown_service_returns_empty_list`。
- 期望值來自獨立來源：proposal 的範例、fixture 的實際內容、手寫的已知字面值。不可以用與實作相同的方法算出期望值。
- 重構後行為沒變，測試就不應該壞。測試因重構而壞，表示它綁了實作細節，要改測試。

### 1.3 Mock / Fake 的邊界

只在系統邊界替換依賴：

| 依賴 | 測試中的處理 | 理由 |
|---|---|---|
| Chat model（agent / report） | 注入 scripted fake model | 外部推論服務，結果不確定 |
| Ollama HTTP（readiness、model-init） | 注入 fake client，或 HTTP 層 stub | 外部服務 |
| 時間 / sleep / retry 等待 | 注入 clock 或使用很小的 timeout | 避免測試變慢、變不穩 |
| PostgreSQL | **不 mock**，使用隔離的 `test-db` | proposal 要求真實 JSONB 整合，禁止用 SQLite 取代 |
| `query_logs` 與日誌 fixture | 預設使用真實實作與 `data/logs.json` | 自己掌控、唯讀且固定 |
| Tool registry | 只在 graph control-flow 測試中可注入 fake registry（例如模擬未知工具、慢工具） | proposal Tier 2 允許 |
| Graph nodes、service、repository | **不 mock** | 自己掌控的內部協作者 |

## 2. 測試 Seams

Seam 是測試觀察行為的公開邊界。**測試只寫在下表列出的 seams。** 開始 M1 之前，這張表要先和專案負責人確認（M0 的出口條件之一）；新增 seam 需要同樣確認。

| ID | Seam | 觀察方式 | 對應 proposal |
|---|---|---|---|
| S1 | `Settings`（pydantic-settings） | 以環境變數建立設定物件 | §8 |
| S2 | `query_logs(service, keyword)` | 直接呼叫函式 | §11 |
| S3 | Report schema + grounding 驗證函式 | 給 report 與 evidence，觀察接受或拒絕 | §12 |
| S4 | `investigate(InvestigationInput) -> InvestigationResult` | 透過 production graph factory 建立，注入 fake model | §6、§10 |
| S5 | Repository（建立 / 取得事件、保存 / 列出報告） | 呼叫 repository 介面，使用 `test-db` | §13 |
| S6 | HTTP API | ASGI test client + `test-db`，只替換模型 adapter | §9 |
| S7 | Migration | 對乾淨的隔離 DB 執行 `alembic upgrade head` | §13 |
| S8 | Model-init 邏輯 | 呼叫初始化函式，注入 fake Ollama client 與 clock，觀察結果與 exit code | §8 |
| S9 | Live smoke | 對已啟動的 API 執行 `scripts.live_smoke` | §15 Tier 4 |

S5 只用於 HTTP API 觀察不到的行為（例如歷史報告保留）。能從 S6 觀察的行為，優先在 S6 測。

## 3. 指令

測試一律在容器內執行，主機不需要 Python。

```bash
# 全部 deterministic 測試（每個 slice 的第 5 步）
docker compose --profile test run --build --rm tests pytest -m "not llm"

# 只跑單一檔案或單一測試（red / green 時使用）
docker compose --profile test run --rm tests pytest tests/<path>.py -k <name>
```

> [!NOTE]
> proposal 把 test profile 放在 M5，但 M1 起就需要真實 PostgreSQL 的測試。因此本文件在 M1 先建立**最小可用**的 `test-db` 與 `tests` service，M5 再補齊網路限制、CI 整合與文件。這只調整順序，不改變 proposal 的需求。

## 4. 待決事項（M0 內決定）

以下是 proposal 沒有完全定義、但會影響測試期望值的地方。M0 結束前要有結論，並寫入 `docs/ImplementationPlan.md`。

| # | 問題 | 建議 |
|---|---|---|
| D1 | 單一輪 tool calls 超過 2 個時，要拒絕還是截斷？ | 拒絕，視為 loop-limit 類錯誤（502）。與 grounding「不默默修補」的原則一致，且不會留下未配對的 tool calls |
| D2 | `title`、`description` 長度上限 | 例如 title 200、description 5000；數值本身不重要，但要固定並出現在 OpenAPI |
| D3 | 錯誤分類的型別設計（provider failure、invalid output、grounding、tool error、loop limit、deadline） | 一組具名 exception，由 API 層集中映射成 HTTP status；不使用廣泛的 `except Exception` |
| D4 | Model-init 的實作位置 | 放在 runtime image 的 Python script，透過 Ollama HTTP API 操作，不依賴 Ollama image 是否有 curl |
| D5 | Readiness 如何判斷 migration 完成 | 比對 DB 中的 Alembic revision 與程式內的 head revision |
| D6 | Seams（第 2 節）是否確認 | 需專案負責人確認 |

---

## M0 — 規劃與版本確認

**本階段做到哪裡：** 只做規劃，不寫產品程式碼，也不寫測試。

- [x] 確認 repo 現況（目前只有 proposal、README、LICENSE），以「從零建立」撰寫計畫。
- [x] 查證並選定相容版本：Python 3.12、FastAPI、Pydantic v2、LangGraph、LangChain Ollama adapter、SQLAlchemy 2.x、psycopg 3、Alembic、pytest 與 async 支援。
- [x] 選定 PostgreSQL 與 Ollama 映像的固定 release tag；可行時記錄 digest。
- [x] 設計 Compose startup / test dependency（`service_healthy`、`service_completed_successfully`）。
- [ ] 決定第 4 節 D1–D6。
- [x] 列出必須實測才能確認的假設，至少包含：
  - [x] `llama3.2:3b` 在選定 Ollama / adapter 版本下能否 tool calling。
  - [x] 同一模型能否穩定產生 structured output。
  - [x] CPU 模式下調查耗時是否在 `INVESTIGATION_TIMEOUT_SECONDS` 內。
- [x] 產出 `docs/ImplementationPlan.md`。

**出口條件：**

- [x] `docs/ImplementationPlan.md` 的每個項目都能對應到 proposal 的章節。
- [x] 第 2 節 seams 已確認。

---

## M1 — 骨架、設定、資料庫、事件 CRUD

**本階段做到哪裡：** API 能啟動、能建立與查詢事件，資料存在真實 PostgreSQL。沒有 graph、沒有模型、沒有 `/investigate`、沒有 `/ready`。

### 先建立（非 TDD，讓迴圈能跑）

- [x] `pyproject.toml` + `uv.lock`（runtime 與 dev dependencies 分開）。
- [x] `Dockerfile`：runtime target 與 test target；安裝以 lockfile 為準，不複製主機 `.venv`。
- [x] `.dockerignore`：排除 `.env`、`.venv`、`.git`、暫存檔。
- [x] `compose.yaml`：`db`、`migrate`、`api`，以及 `test` profile 的 `test-db`、`tests`。
- [x] `.env.example`（proposal §8 的預設值）。
- [x] 一個必定通過的 smoke 測試，確認 `tests` service 能連上 `test-db`。

### Red → Green slices

Settings（S1）：

- [x] 未設定可選變數時，套用 proposal 的預設值（`MAX_TOOL_ROUNDS=2`、`GRAPH_RECURSION_LIMIT=16`、兩個 timeout）。
- [x] `LLM_PROVIDER=ollama` 被接受。
- [x] `LLM_PROVIDER` 為其他值時，建立設定失敗。
- [x] 若支援由各欄位組合 `DATABASE_URL`：密碼含 `@`、`:`、`/` 等特殊字元時，組合結果仍能正確解析。

Migration（S7）：

- [x] 對乾淨 DB 執行 `alembic upgrade head` 成功，之後可以建立事件。
- [x] 已有資料時再執行一次 `upgrade head`，既有事件仍在。

Health（S6）：

- [x] `GET /health` 回 200，且不需要模型。

建立事件（S6）：

- [x] `POST /incidents` 合法輸入回 201，body 含 `id`、`title`、`description`、`status="created"`。
- [x] `title`、`description` 前後空白會被去除後保存。
- [x] `title` 為空字串或只有空白時回 422。
- [x] `description` 為空字串或只有空白時回 422。
- [x] 超過長度上限（D2）時回 422。
- [x] OpenAPI schema 中可以看到長度上限。

查詢事件（S6）：

- [x] `GET /incidents/{id}` 回傳事件，`latest_report` 為 `null`。
- [x] 事件不存在時回 404，`detail` 為 `Incident not found`。
- [x] 以新的 application instance（新的 engine / session）建立 test client 後，仍能查到先前建立的事件。

### 指令驗證

- [x] `docker compose config` 成功。
- [x] `docker compose up --build -d db migrate api` 後，`migrate` 以 exit code 0 結束，`curl -f http://localhost:8000/health` 成功。
- [x] API 只綁定主機 `127.0.0.1:8000`；`db` 沒有對主機開放 port。
- [x] Runtime startup 沒有呼叫 `metadata.create_all()`。
- [x] Runtime image 不含 pytest。

**出口條件：**

- [x] 上列 slices 全部勾選，`pytest -m "not llm"` 全綠。
- [x] 指令驗證全部通過。

---

## M2 — 工具、報告 schema、grounding、graph

**本階段做到哪裡：** `investigate()` 能用 fake model 跑完整 graph，回傳經過 schema 與 grounding 驗證的結果。這一階段**不接 DB、不接 API、不接 Ollama**。

### Red → Green slices

`query_logs`（S2）：

- [x] `service="checkout"` 依原順序回傳 fixture 的 3 行。
- [x] 不存在的 service 回傳 `[]`。
- [x] `keyword` 不分大小寫做子字串篩選（例如 `keyword="POOL"` 只回傳 `connection pool exhausted` 那一行）。
- [x] `keyword` 沒有符合的行時回傳 `[]`。
- [x] 從不同的工作目錄呼叫，結果相同（fixture 路徑不依賴 cwd）。

Report schema 與 grounding（S3）：

- [x] proposal §4 的報告範例通過 schema 驗證。
- [x] `confidence` 不是 `low` / `medium` / `high` 時，schema 驗證失敗。
- [x] 缺少必要欄位時，schema 驗證失敗。
- [x] evidence 完整符合工具實際回傳的行時，grounding 通過。
- [x] evidence 是改寫過的句子（例如少了時間戳）時，grounding 拒絕。
- [x] evidence 來自沒有查詢的 service（例如 payment 的行）時，grounding 拒絕。
- [x] evidence 是被 keyword 排除的行時，grounding 拒絕。
- [x] evidence 是事件描述文字時，grounding 拒絕。
- [x] 沒有任何 evidence 時，`hypotheses=[]` 的報告通過。

Graph 正常流程（S4，注入 scripted fake model）：

- [ ] Agent 不呼叫工具 → 產生報告，`evidence=[]`、`tool_calls=[]`。
- [ ] Agent 呼叫 `query_logs(service="checkout")` 一次 → evidence 為 checkout 的 3 行，`tool_calls` 記錄工具名稱與已驗證的參數，並產生報告。
- [ ] 工具執行後，agent 下一次收到的訊息包含 tool result，且 `tool_call_id` 與該次呼叫相符（由 fake model 記錄收到的輸入來觀察）。
- [ ] 兩輪工具呼叫時，evidence 累積；完全相同的行只保留一次，順序維持首次出現的順序。
- [ ] Report model 收到的 evidence 與 `InvestigationResult.evidence` 一致。
- [ ] `InvestigationResult` 能序列化成 JSON，且不含 LangChain / LangGraph 型別。

Graph 失敗流程（S4）：

- [ ] Agent 呼叫未知工具 → 回報 tool error。
- [ ] 工具參數無效（缺少 `service`、型別錯誤）→ 回報 tool error。
- [ ] 完成 `MAX_TOOL_ROUNDS` 輪後 agent 仍要求工具 → 回報 loop-limit failure，不產生報告。
- [ ] 單一輪 tool calls 超過 2 個 → 依 D1 的決定處理。
- [ ] 把 `GRAPH_RECURSION_LIMIT` 設得比正常流程所需更小 → 回報明確的錯誤，而不是框架的原始例外。
- [ ] Report model 回傳不符合 schema 的內容 → 回報 invalid structured output。
- [ ] Report 引用了沒有取得的 evidence → 回報 grounding violation，不刪除或修補該 evidence。
- [ ] Fake model 回應時間超過整體 deadline → 回報 deadline exceeded。
- [ ] Fake model 拋出連線類錯誤 → 回報 provider failure。

State 隔離（S4）：

- [ ] 同一個 compiled graph 連續執行兩次，第二次結果不含第一次的 evidence 或 messages。
- [ ] 同時（`asyncio.gather`）執行兩次不同 service 的調查，各自的 evidence 不互相混入。

### 指令驗證

- [ ] 所有 nodes 為 `async def`，graph 由 `ainvoke` 驅動。
- [ ] Graph nodes 中沒有任何 DB 存取。
- [ ] `investigate()` 的參數與回傳只使用 Pydantic schema，不依賴 HTTP request 或 ORM 物件。

**出口條件：**

- [ ] 上列 slices 全部勾選，`pytest -m "not llm"` 全綠。
- [ ] 第 4 節 D1、D3 的決定已反映在測試中。

---

## M3 — Application service、investigate endpoint、persistence

**本階段做到哪裡：** 用 fake model 完成「建立 → 調查 → 查詢」的 API vertical slice，結果存在真實 PostgreSQL。仍然不接 Ollama。

### 先建立（非 TDD）

- [ ] `investigation_reports` 資料表的 Alembic migration（若 M1 只建了 `incidents`）。
- [ ] Composition：test 只替換模型 adapter，graph、tool registry、repository 都使用 production factory。

### Red → Green slices

成功流程（S6）：

- [ ] `POST /incidents/{id}/investigate` 回 200，body 含 `incident_id`、`report_id`、`status="completed"`、`report`。
- [ ] 調查成功後，`GET /incidents/{id}` 的 `status` 為 `completed`。
- [ ] `latest_report` 包含 report ID、建立時間、report、evidence、tool-call 紀錄。
- [ ] Fake model 呼叫 `query_logs(service="checkout")` 時，保存的 evidence 等於真實 fixture 的 checkout 3 行（證明使用的是 production graph 與真實工具）。
- [ ] 保存的 `model_name` 等於設定的 `LLM_MODEL`。
- [ ] 以新的 application instance 查詢，仍取得相同的報告。

歷史報告：

- [ ] 同一事件循序調查兩次，第二次的 `report_id` 大於第一次，`latest_report` 是第二次（S6）。
- [ ] 調查兩次後，兩筆報告都還存在（S5）。

錯誤映射（S6）：

- [ ] 對不存在的事件調查 → 404 `Incident not found`。
- [ ] Provider failure → 502。
- [ ] Invalid structured output → 502。
- [ ] Grounding violation → 502。
- [ ] 未知工具 / 參數無效 → 502。
- [ ] Loop limit → 502。
- [ ] Deadline exceeded → 504。
- [ ] 非預期的程式錯誤 → 500，**不會**被歸類成 502。
- [ ] 錯誤回應的 `detail` 不含資料庫密碼或 stack trace。

失敗時的資料狀態（S6）：

- [ ] 第一次調查就失敗 → `status` 維持 `created`，`latest_report` 為 `null`。
- [ ] 已有成功報告後再次調查失敗 → `status` 維持 `completed`，`latest_report` 仍是先前那筆。

### Review 項目（以 code review 確認，不寫測試）

- [ ] 載入事件使用短 transaction，轉成 input snapshot 後關閉 session。
- [ ] 調查在 DB transaction 外執行，期間不持有 row lock。
- [ ] 報告 insert 與事件 status 更新在同一個新 transaction 中 commit 或 rollback。
- [ ] async route 中沒有阻塞的 DB I/O；沒有跨 thread 共用 Session。
- [ ] 沒有廣泛的 `except Exception` 把所有錯誤轉成 502。

**出口條件：**

- [ ] 上列 slices 全部勾選，`pytest -m "not llm"` 全綠。
- [ ] Review 項目全部確認。

---

## M4 — Ollama、model-init、readiness、真實模型

**本階段做到哪裡：** 完整 Compose 能從乾淨 volume 啟動，`/ready` 正確反映依賴狀態，真實模型至少完成一次 checkout 調查。

### Red → Green slices

Readiness（S6，注入 fake Ollama client）：

- [ ] DB、migration、Ollama、模型都正常 → `GET /ready` 回 200。
- [ ] DB 無法連線 → 503。
- [ ] DB 的 migration 不是 head（D5）→ 503。
- [ ] Ollama 無法連線 → 503。
- [ ] Ollama 可連線但設定的模型不存在 → 503。
- [ ] `/ready` 不呼叫推論（fake inference client 被呼叫時直接讓測試失敗）。

Model-init（S8，注入 fake Ollama client 與 clock）：

- [ ] 模型已存在 → 不下載，exit code 0。
- [ ] 模型不存在 → 下載後確認模型可查得，exit code 0。
- [ ] 下載回報成功，但模型仍查不到 → 非零 exit code。
- [ ] Ollama 在重試上限內一直無法連線 → 非零 exit code，錯誤訊息說明原因與重試次數。
- [ ] Ollama 在重試上限內恢復連線 → 繼續完成初始化。

Ollama adapter（以 HTTP 層 stub 驗證）：

- [ ] `LLM_REQUEST_TIMEOUT_SECONDS` 實際套用到請求。
- [ ] 連線失敗、HTTP 5xx → 轉成 provider failure。

Live 測試設定：

- [ ] `@pytest.mark.llm` 的測試在預設 `pytest` 執行中被排除。
- [ ] 有明確的指令可以只執行 `llm` 測試，且該指令使用真實 Ollama adapter，不使用 fake。

### 指令驗證

- [ ] 刪除 `ollama_data` 後 `docker compose up --build -d`：`model-init` 下載成功並以 exit code 0 結束，`migrate` 也是 0。
- [ ] 初始化期間 `api` 不啟動；完成後 `curl -f http://localhost:8000/ready` 成功。
- [ ] Ollama healthcheck 不依賴映像中不存在的工具（例如 curl）。
- [ ] Ollama 沒有對主機開放 port。
- [ ] 再次執行 `model-init` 會跳過下載。
- [ ] `docker compose exec api python -m scripts.live_smoke` 成功：
  - [ ] 真實模型呼叫了 `query_logs(service="checkout")`。
  - [ ] 報告 schema 合法，至少一個 hypothesis，`recommended_next_steps` 非空。
  - [ ] 所有 evidence 完整符合工具實際結果。
  - [ ] GET 取回相同報告。
- [ ] 人工確認報告的假設與 checkout 日誌相關。
- [ ] 若 `llama3.2:3b` 無法通過，更換模型並記錄原因與通過的版本。
- [ ] 在 `docs/Verification.md` 記錄這次 live 結果：模型名稱、digest、Ollama 版本、硬體、初始化與調查耗時。

**出口條件：**

- [ ] 上列 slices 全部勾選，`pytest -m "not llm"` 全綠。
- [ ] 至少一次 live smoke 成功，且已記錄。

---

## M5 — Test profile、CI、文件、重現性

**本階段做到哪裡：** 從全新 clone 能重現，CI gates 能跑，README 的「待補」全部填上。

### 測試環境補齊

- [ ] `tests` service 不啟動 Ollama、不下載模型、不需要 LLM API key。
- [ ] 測試執行時，模型位址指向無效位址；任何未經 fake 的 provider 呼叫都會立刻失敗，而不是嘗試連網。
- [ ] `test-db` 不使用應用的 `postgres_data` volume。
- [ ] 測試 setup 會在隔離 DB 上執行 migrations。

### GitHub Actions

- [ ] `uv.lock` 一致性檢查。
- [ ] Deterministic unit / graph tests。
- [ ] 真實 PostgreSQL 的 API tests。
- [ ] Runtime image build。
- [ ] Migration 與不含模型的容器 smoke check（獨立 override / profile，只測 liveness 與基本 incident API）。
- [ ] `docker compose config` 驗證。
- [ ] 失敗時上傳 log artifacts。
- [ ] CI 不 pull、不呼叫任何 LLM。

### 重現性驗證

- [ ] 全新 clone，依 README 的 bash 步驟啟動成功。
- [ ] 依 README 的 PowerShell 步驟啟動成功（或明確記錄未在 Windows 上驗證）。
- [ ] `docker compose down` 後 `docker compose up -d`，既有事件與報告仍在，模型不需重新下載。
- [ ] README 的「更換模型」步驟實際執行一次並確認可用；不可用則修正 README。
- [ ] `docker compose down -v` 會清空資料與模型，行為與 README 描述一致。

### 文件

- [ ] README 與 README-zhtw 的「待補 / TBD」全部填上：repository URL、驗證過的模型、digest、Ollama 版本、硬體、首次下載時間、`llm` suite 指令。
- [ ] README 的指令、API、錯誤碼與實作一致。
- [ ] `docs/Verification.md` 記錄 OS、CPU / GPU、RAM、Docker / Compose 版本、映像與套件版本、模型名稱與 digest、初始化與調查耗時。
- [ ] `docs/Verification.md` 把「已執行」、「未執行」、「受環境限制」三類驗證分開列出。

**出口條件：**

- [ ] proposal §19 Definition of Done 全部勾選（見第 5 節對照）。

---

## 5. Definition of Done 對照

proposal §19 每一項在哪個階段完成：

| DoD 項目 | 階段 |
|---|---|
| 新環境僅需 Git + Docker / Compose | M1 建立，M5 驗證 |
| README 提供 shell 與 PowerShell 方式 | M5 |
| `docker compose up --build -d` 自動建立 schema、下載模型 | M1（schema）、M4（模型） |
| migrate / model-init 成功結束，api / db / ollama 正常 | M4 |
| `/ready` 正確反映依賴不足，且不執行推論 | M4 |
| 首次下載、失敗與重試方式可從 README 理解 | M5 |
| 固定映像版本與 `uv.lock` 已提交 | M0 選定，M1 提交 |
| 建立 incident | M1 |
| 真實 graph / model 執行調查 | M4 |
| checkout 場景真的呼叫 `query_logs` | M2（fake）、M4（live） |
| report schema 與 grounding 通過 | M2 |
| 報告、evidence、tool-call metadata 保存 | M3 |
| GET 回傳最新報告與來源 | M3 |
| down / up 後既有事件與報告仍存在 | M5 |
| Ollama 模型不因一般容器重建而遺失 | M4、M5 |
| 預設測試無真實模型、無 API key | M1 起，M5 強化 |
| API tests 使用隔離的 PostgreSQL | M1 |
| Error / loop-limit / timeout 有 deterministic coverage | M2、M3 |
| GitHub Actions 必要 gates 通過 | M5 |
| 至少一個 live scenario 成功紀錄 | M4 |
| Verification 記錄環境資訊 | M4 開始，M5 完成 |
| 已執行、未執行、受環境限制的驗證分開 | M5 |

Docker 啟動成功、fake-model tests 通過、live-model scenario 成功是三個不同的驗收項目，不能互相代替。
