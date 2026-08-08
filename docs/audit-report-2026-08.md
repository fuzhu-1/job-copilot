# Job Copilot 调研与架构评审报告

> 日期：2026-08-09　范围：全量代码阅读 + 测试实跑（91/91 通过）+ 公开库生态调研

## 一、总体结论

项目完成度高、思路清晰，**不需要推倒重来**。分层（API → services → agents/tools/workflow → 存储）对这个体量是合适的，人机协同边界、可解释打分、golden set 回归都是亮点。

真正的架构级问题只有两个：

1. **向量层只有写入、没有检索**，ChromaDB 是"死重"；
2. **后台任务用裸线程 + 进程内队列**，只能支撑单机单进程演示。

其余问题集中在工程化（LLM 层健壮性、依赖锁定、迁移、CI）和少量功能缺口（中文分词、删除清理、SSE 竞态）。

## 二、公开库调研速览（2026-08）

| 领域 | 当前选择 | 调研到的替代/更优方案 | 建议 |
|------|----------|----------------------|------|
| Agent 编排 | LangGraph（实际是 3 节点线性图） | Pydantic AI（类型安全、轻量）、OpenAI Agents SDK、LangGraph v1 | 保持 LangGraph 也可以，但线性图没必要背框架；若扩到真正的多步循环再上 LangGraph |
| 向量存储 | ChromaDB（只写不读） | sqlite-vec（并入现有 SQLite）、或直接移除 | 要么接通真实检索，要么删掉，二选一 |
| 中文嵌入 | 自制 token 哈希（对中文几乎无效） | Qwen3-Embedding（中文 MTEB 第一）、BGE-M3（多语言+稀疏）、text-embedding-3-small（API）；BM25+jieba 作为确定性基线 | 用 API 嵌入或本地小模型；纯离线可先用 BM25+jieba |
| 结构化输出 | 提示词 + JSON 解析重试 | OpenAI Structured Outputs（json_schema strict）、instructor | 升级，显著降低解析失败率 |
| PDF/简历解析 | PyMuPDF 纯文本 | Docling（版面理解）、PaddleOCR（中文扫描件 OCR） | 文本型 PDF 现状够用；扫描简历按需加 OCR |
| 网页搜索 | Tavily / DuckDuckGo HTML 抓取 | Exa、Serper、自托管 SearXNG+Crawl4AI | Tavily 保留；DDG 抓 HTML 是脆弱点，失败要能感知 |
| 评测 | 自研 golden set + judge | promptfoo（MIT，2026 被 OpenAI 收购）、DeepEval | 自研方案与业界 EDD 模式一致，可保留；需要 prompt/红队测试时引入 promptfoo |
| 后台任务 | threading.Thread + 内存队列 | ARQ（异步 FastAPI 首选）、Celery（重型）、FastAPI BackgroundTasks | 单机可用；要部署多进程/持久化前迁移到 ARQ |
| 可观测性 | 无 | Langfuse（开源，OTel 标准）、LangSmith | 接入后可追踪每次 LLM 调用的 token/延迟/成本 |

同类项目参照：BossHunter（采集→AI 评分→人工确认→发送→监测，人机协同思路一致）、autopilot-jobhunt（每日扫描+LLM 打分）、yekwennnn/job-copilot（中文求职助手 v3.0）。本项目差异点是完整的 Web 界面和评测闭环；BossHunter 等做到了自动投递，本项目刻意不做，是合规上的正确选择。

## 三、问题清单（按优先级）

### P0：建议尽快处理

1. **向量检索形同虚设**
   - `app/vector_store.py:77` 的 `query()` 全项目无调用方，ChromaDB 只写不读（`app/services/jd_service.py:17`、`app/services/resume_service.py:45`）。
   - 自制哈希嵌入按空格分词（`app/vector_store.py:22`），中文文本几乎不分词，检索质量趋近于零；README 宣称的"向量检索"未兑现。
   - 建议：短期直接移除 ChromaDB 减小依赖和镜像体积；若要做"相似岗位/语义召回"，用 Qwen3-Embedding 或 BGE-M3（API 或本地），并配 BM25+jieba 做混合检索。

2. **中文规则信号缺失**
   - `app/utils/text.py:4` 的 `extract_terms` 只匹配 ASCII，中文 JD/简历的关键词重叠率恒近 0，规则层信号对中文用户形同虚设。
   - 连带影响：市场洞察的 `top_skills`（`app/services/insight_service.py:46`）统计不到中文技能词。
   - 建议：引入 jieba 分词，规则层和市场洞察都走分词后的词频。

3. **SSE 事件丢失竞态 + 任务不可恢复**
   - 后台线程发布事件（`app/events.py:18`），客户端订阅在 POST 之后（`app/main.py:199-247`）；若任务先完成、后订阅，事件全部丢失，SSE 会一直挂起。
   - 任务用 `threading.Thread`（`app/main.py:220`），进程重启即丢，多 worker 部署时事件总线各进程不互通。
   - 建议：建任务表持久化状态，SSE 先查任务状态再订阅；事件写入数据库或 Redis stream；加心跳与超时兜底。

4. **删除操作不清理关联数据**
   - 批量删 JD（`app/main.py:158`）不删向量、不级联 match/application，留下孤儿数据；SQLite 默认不强制外键。
   - 建议：定义级联关系 + 删除时同步清理向量；application 对 match 加唯一约束防重复投递记录。

5. **安全边界（若部署到公网）**
   - CORS 全开（`app/main.py:50`）、无鉴权；URL 抓取（`app/tools/jd_fetcher.py:20`）无 SSRF 防护、无响应大小上限；上传（`app/main.py:80`）无大小限制、全量读内存。
   - 建议：至少加文件大小/URL 校验；对外发布前加简单鉴权（单用户 token 即可）。

### P1：值得投入的工程化

6. **LLM 层健壮性**：无超时/退避/429 重试/成本追踪；结构化输出靠"提示词+重试一次"（`app/llm.py`）。建议改用 `response_format=json_schema` 或 instructor，并加指数退避。
7. **可观测性**：接入 Langfuse 或结构化日志，记录每次 LLM 调用的模型、token、耗时，排查问题效率会高很多。
8. **数据库迁移**：目前只有 `create_all`（`app/db.py`），引入 Alembic 才能安全演进 schema。
9. **依赖可复现**：`requirements.txt` 全部是 `>=` 未锁版本，且与 `pyproject.toml` 重复维护；建议统一为一份锁文件（uv/poetry），CI 加缓存。
10. **匹配图重复编译**：`app/services/match_service.py:26` 每次匹配都重建并编译 LangGraph，改为模块级单例。
11. **N+1 查询**：面试列表（`app/main.py:344`）和投递列表（`app/services/application_service.py:137`）逐条查 JD 名，改为 join。
12. **评测可移植性**：golden set 里的 resume_id/jd_id 是本地数据库 UUID（`data/golden_set.json`），新环境无法直接跑；当前也没有 interview 用例。建议提供"注入样例数据"的初始化脚本。
13. **前端工程**：`App.jsx` 是单体状态容器，无数据请求层（react-query/SWR）、无 TypeScript、无前端测试；CI 也不构建前端。至少加一个 `npm run build` 进 CI。
14. **CI/代码规范**：CI（`.github/workflows/ci.yml`）只有 pytest，无 ruff、无类型检查、无依赖缓存；建议补上。
15. **文档断链**：README 引用的设计文档 `docs/superpowers/specs/2026-08-04-job-copilot-design.md` 不存在。
16. **小瑕疵**：上传解析失败后孤儿文件不清理；JD 重复录入无去重。

### P2：产品增强方向

- 批量匹配/JD 录入改为并发执行（当前串行，多岗位时很慢）。
- 投递提醒改为真正的定时任务推送（当前是查询时计算）。
- 市场洞察按城市×技能组合细化，对求职者更有指导性。
- 面试陪练增加追问轮次控制、语音输入（如需）。

## 四、架构结论

**不需要重新设计，需要按优先级"还债"。** 当前分层对这个规模是合理的，且有几个值得保留的设计：

- 人机协同：简历强制人工确认、Agent 不自动投递；
- 可解释性：四维打分 + 每维理由；
- 质量闭环：golden set + 回归门槛，改动前先跑基线；
- 确定性优先：市场洞察用聚合统计而非纯 LLM 生成。

触发重新设计的信号（现阶段都不满足）：

- 需要多用户/对外部署 → 先补鉴权、任务队列、SSRF 防护；
- 前端面板持续膨胀 → 再引入路由与状态管理；
- 出现真正的多步 Agent 循环（检索→反思→重写）→ 再让 LangGraph 派上用场，或评估 Pydantic AI。

## 五、建议路线图

| 阶段 | 内容 | 预估 |
|------|------|------|
| 短期 | 向量层二选一（移除或接通）、jieba 分词、SSE 竞态修复、删除级联清理 | 1-2 天 |
| 中期 | LLM 结构化输出升级、Alembic、依赖锁定、CI 增强、golden set 可移植 | 2-3 天 |
| 长期 | ARQ 任务队列 + Langfuse 可观测性 + 鉴权/多用户 | 按需 |

