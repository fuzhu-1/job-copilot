# Job Copilot

一站式求职 Agent：上传简历 → 结构化确认 → 录入 JD → 匹配打分 → 生成自荐信。

## 功能

- 简历 PDF 解析与 LLM 结构化（人工确认后入库）
- JD 多来源录入（粘贴文本 / URL 抓取 / 批量导入）
- 四维可解释匹配打分 + 差距分析（LangGraph 工作流）
- 自荐信生成 + LLM-as-judge 自检重写
- 投递状态机（非法跳转拦截 / 跟进建议 / 提醒）
- 企业研究（网页搜索 + LLM 报告）
- 市场洞察（技能频次 / 薪资统计 / 城市与公司分布）
- Supervisor 意图识别与助手入口
- 面试陪练（按 JD + 简历定制的多轮模拟面试与 STAR 反馈）
- 评测平台（golden set / LLM-as-judge / 回归通过率 / 可视化报告）
- SSE 实时匹配进度

## 快速开始

### 后端

```bash
cp .env.example .env   # 填入 LLM_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端（开发模式）

```bash
cd app/web
npm install
npm run dev            # http://localhost:5173，/api 自动代理到 8000
```

### Docker

```bash
cp .env.example .env
docker compose up --build
```

## 测试

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```

环境变量补充：`SEARCH_API_KEY`（Tavily，可选；未配置时企业研究降级为纯 LLM 生成）

## 评测

1. 准备 golden set：编辑 `data/golden_set.json`（把示例 ID 替换为真实 resume/jd/match/session ID）。
2. 同步用例：`POST /api/eval/golden/sync`（或前端「评测报告」页点「同步 golden set」）。
3. 运行评测：`POST /api/eval/runs`（或前端点「运行评测」）。
4. 看报告：前端「评测报告」页展示通过率、分类型平均分与历史趋势。

评测基线记录在 `docs/eval-baseline.md`（Phase 4 固化）。

## 架构

FastAPI + LangGraph + ChromaDB + SQLite + React（详见 `docs/superpowers/specs/2026-08-04-job-copilot-design.md`）。
