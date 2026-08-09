# 简历（AI / LLM / Agent 工程师方向）

> 目标岗位假设：AI/LLM/Agent 工程师（应用/后端方向）。如目标不同可再裁剪关键词。
> 基本信息与教育经历待补充，用【】占位。

## 基本信息

【姓名】｜【电话】｜【邮箱】｜【城市】

## 技能

- Agent 编排：LangGraph StateGraph、条件边回流、单节点可替换、任务级状态隔离
- 评测闭环：golden set、LLM-as-Judge、回归通过率门槛、基准前后对比
- 可靠性工程：指数退避重试、超时降级、结构化输出自愈（重试 + token 扩容）、成功率量化
- RAG 与防幻觉：jieba/BM25 与向量检索、引用核验、论断-证据（Claims-Evidence）接地核查
- 可观测性与流式：SSE 实时推送、事件持久化回放、心跳保活、断线重连、token 用量日志
- 后端：FastAPI、SQLAlchemy、SQLite、Alembic 迁移、任务并发与状态机
- 工程化：Docker、GitHub Actions（ruff + mypy + pytest）、依赖锁定（pip-tools）、一键启动脚本
- 前端：React 18、Vite、Tailwind CSS、EventSource 流式消费

## 项目经历

### Job Copilot —— 求职全生命周期 Agent（独立开发 · 2026.08 - 至今）

**针对简历结构不统一、岗位匹配依赖人工、求职过程缺乏量化反馈与质量保障的问题，完成一站式求职 Agent：覆盖"简历解析 → JD 录入 → 四维匹配 → 自荐信 → 投递管理 → 面试陪练 → 评测回归"完整闭环。系统基于 LangGraph 编排"规则层 + LLM 打分"工作流，配套 jieba/BM25 中文全文检索、SQLite 任务持久化与 SSE 实时推送，并通过 golden set 评测驱动持续改进。**

**核心成果**：评测通过率 100%（golden set 3 用例 × 2 次重跑）、108 项单元测试 + 25 项真实环境功能测试全绿、匹配全程 SSE 实时可见（单 JD 约 10-16 秒完成）。

主要职责（动作 + 技术 + 量化结果）：

1. **评测驱动的质量闭环**：自建 golden set 与三类判定器（区间判定 / LLM-as-Judge / 阈值判定），评测通过率稳定 100%，任何改动先跑基线再合入，解决"怎么证明 Agent 变好了"。
2. **可解释匹配引擎**：实现 LangGraph 三步工作流（规则层关键词重叠 → LLM 四维打分 → 差距归一化），每维附可读理由；修复推理模型偶发全零评分，重试上限 3 次后匹配分稳定在 70~93 区间。
3. **中文全文检索**：用 jieba 分词 + BM25 + SQLite 重写检索层，替换只写不读的 ChromaDB 向量库，中文简历/JD 检索从不可用变为可用，并为 JD 列表新增关键词搜索。
4. **后台任务与实时性**：匹配任务与事件持久化到 SQLite，SSE 从任务表回放并加 10s 心跳；定位并修复"任务完成但前端一直转圈"的会话缓存陈旧 bug（轮询前强制刷新），实测事件流完整推送 started → progress → result → completed。
5. **LLM 可靠性工程**：结构化输出 token 上限提升至 4000（简历 6000）并最多重试 3 次，修复长简历 JSON 截断导致的解析失败；加入 120s 超时、429/5xx 指数退避、json 模式自动降级与 token 用量日志。
6. **数据一致性与工程化**：批量删除 JD 级联清理投递/匹配/面试与索引、投递记录唯一约束、上传失败自动清理孤儿文件；引入 Alembic 迁移、pip-tools 依赖锁定、ruff + CI（lint / 迁移 / 前端构建）；提供双击一键启动脚本并自动校验 LLM 模型配置。

**技术栈**：Python、FastAPI、SQLAlchemy、LangGraph、jieba/BM25、SQLite、OpenAI-compatible LLM、SSE、React 18 + Vite + Tailwind CSS、Docker、GitHub Actions

### DeepResearch-Agent —— 多 Agent 自动化研究分析系统（独立开发 · 2026.07 - 至今）

**针对深度调研中信息检索分散、网页深读与来源核验依赖人工、报告质量不稳定且经验难以沉淀复用的问题，完成端到端自动化多 Agent 研究系统：输入课题自动执行"任务拆解 → 资料搜索 → 网页深度阅读 → 知识整理 → 报告撰写 → 质量审查"闭环，输出带来源引用的 Markdown / PDF 报告。系统基于 LangGraph StateGraph 编排 Planner / Researcher / Writer / Reviewer 四类 Agent，配套插件式工具系统、RAG 知识库、双记忆系统，并以评测驱动的回流重写与自进化 Skills 形成持续改进闭环。**

**核心成果**：评测驱动的质量闭环（事实准确率 +92%）、工具调用成功率 67% → 100%、390 项测试用例全绿（385 通过 / 2 环境跳过 / 0 失败）、GitHub Actions CI + Docker 一键部署。

主要职责（动作 + 技术 + 量化结果）：

1. **多 Agent 编排与评测闭环**：通过共享 State + 条件边实现 Reviewer 回流重写（最多 3 轮、中文可操作反馈），Agent 独立配置、单节点可替换；自建 5 课题 golden set 与 LLM-as-Judge 基准，迭代后事实准确率 3.8 → 7.3/10（+92%）、结构完整度 4.9 → 7.5/10（+53%）、引用质量 2.6 → 4.6/10（+77%）、数据点 3.0 → 7.2 个/任务（+140%）。
2. **插件式工具系统与可靠性**：BaseTool + ToolRouter 统一路由搜索/浏览/代码执行/RAG/记忆等工具，新工具注册即扩展；搜索后端可插拔（Tavily / DDG / GitHub / Exa）；为 Researcher 链路加入"搜索后并行浏览 + 全链路来源追踪"，工具调用 3 → 17 次/任务，成功率 67% → 100%（5 课题、86 次真实调用，含 3 次重试 + 指数退避 + UA 轮换）。
3. **RAG 与防幻觉交付物**：文档导入 → 递归分块 → 向量检索，研究中自动标注来源并汇总引用列表；报告内置"引用核验"与"论断-证据"接地核查章节，把可解释性做成可验证交付物。
4. **并发与实时性**：SSE 实时展示 Agent 执行轨迹，并发任务事件按任务级 ContextVar 隔离（双任务并行实测互不串扰）；服务重启后中断任务自动标记 failed，不静默续跑消耗 token。
5. **产品化与工程化**：React 前端支持多任务并行切换、深色/浅色主题、知识库与历史管理；修复 PDF 下载 500 → 200、历史列表 5 → 25+ 条；一键启动脚本自动补依赖/构建前端/检测端口冲突；GitHub Actions 三阶段 CI（ruff + mypy + pytest）。

**技术栈**：Python、FastAPI、LangGraph、ChromaDB、Redis、React 18 + Vite + Tailwind CSS、SSE、Playwright、Docker、GitHub Actions

## 教育经历

【学校】｜【专业】｜【学历】｜【时间】｜【相关课程/荣誉（可选）】

---

# 附：改动说明、数据来源与面试话术版

## 改动说明

- 叙事结构：从"能力罗列"改为"针对痛点 → 完成方案 → 核心结果"句式，第一行给出结论与数字。
- 量化规则：每条 bullet 至少 1 个数字，优先前后对比（67% → 100%、+92%），删除无法核实的数字。
- 弱动词清理：删除"负责/参与/协助"，全部改为"设计/实现/搭建/修复/驱动 + 技术细节 + 结果"。
- 过程分层：简历主体只保留浓缩版过程；"选型 → 实现 → 踩坑 → 落地 → 复盘"完整版放入面试话术。
- ATS：标准栏目标题、纯文本、无表格图片特殊符号。

## 数据来源清单

| 数据 | 来源（可复核） |
|------|------|
| Job Copilot：108 项单元测试全绿 | `pytest tests/ -q` 输出（108 passed） |
| Job Copilot：25/25 真实环境功能测试 | `scripts/feature_test.py` 运行结果 |
| Job Copilot：评测通过率 100% | golden set 3 用例连续两次 3/3（docs/eval-baseline.md） |
| Job Copilot：匹配分 70~93、SSE 约 10 秒 | docs/test-eval-2026-08-09.md 实测记录 |
| DeepResearch-Agent：基准 +92%/+53%/+77%/+140% | README 基准表（5 课题 LLM-as-Judge） |
| DeepResearch-Agent：385 passed / 2 skipped | 测试评估报告 2026-08-09 |
| DeepResearch-Agent：成功率 67% → 100%（86 次调用） | 测试评估报告与提交记录 |
| DeepResearch-Agent：PDF 500 → 200、历史 5 → 25 | 测试评估报告（提交 562e6d5 / c69522f） |

> 待补充/待核实：【姓名电话邮箱】、教育经历；如含实习/工作经历，提供原始信息后按同规则改写。

## 面试话术版（选型 → 实现 → 踩坑 → 落地 → 复盘）

### Job Copilot

- 选型：匹配引擎对比过"纯 LLM 黑盒打分"与"规则+LLM 混合"，选择 LangGraph StateGraph 显式编排规则层 → LLM 打分 → 差距归一化三节点——节点边界清晰可单测，规则重叠率作为信号喂给 LLM，避免纯凭感觉；检索层对比 ChromaDB 与自建方案，最终选 jieba + BM25 + SQLite，理由是中文分词可控、零联网模型下载、单文件持久化。
- 实现：FastAPI 后端 + React 前端，LangGraph 匹配工作流，SQLite 任务表持久化匹配事件，SSE 从任务表回放进度；LLM 层统一封装超时/重试/json 模式降级。
- 踩坑：① 匹配页"一直匹配中"——SSE 用同一 SQLAlchemy 会话反复读任务，身份映射返回缓存旧快照，完成事件永远读不到；② 长简历 JSON 截断——v4 推理模型 reasoning 占 token，2000 上限不够；③ 模型名配错（deepseek-chat 不存在），LLM 全功能异常；④ 评测偶发全零分。
- 落地：SSE 轮询前强制刷新 + 心跳保活 + 前端区分连接中断；token 上限 4000/6000 + 最多 3 次重试；一键脚本自动校验模型列表并修正；全零评分重试加强 + golden 区间校准。
- 复盘：所有踩坑转成回归测试（108 项）与真实环境冒烟测试（25 项）；golden set 基线成为合入门槛。

### DeepResearch-Agent

- 选型：对比 ReAct / Plan-and-Execute / STORM 后选 LangGraph StateGraph——条件边回流、单节点可替换、状态可持久化；搜索后端做可插拔（Tavily/DDG/GitHub/Exa）避免单点依赖。
- 实现：Planner / Researcher / Writer / Reviewer 四类 Agent + ToolRouter 插件工具 + RAG 知识库 + 双记忆；SSE 按任务级 ContextVar 隔离事件。
- 踩坑：① golden set 一测现原形——事实准确率 3.8、引用质量 2.6；② 工具成功率仅 67%；③ PDF 下载 500（报告含 `|` 与加粗标记导致 reportlab 解析失败）；④ 历史列表只显示 5 条；⑤ 并发任务 SSE 事件串线。
- 落地：Reviewer 回流重写 + 并行浏览 + 重试退避 + UA 轮换；PDF 渲染器加 markdown 表格渲染与异常兜底；分页修复；ContextVar 任务级隔离；CI + Docker + 一键启动收口。
- 复盘：评测固化为 5 课题基准集，改动先跑基准再合入；每个踩坑转成回归测试防复发。
