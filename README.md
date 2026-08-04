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

## 架构

FastAPI + LangGraph + ChromaDB + SQLite + React（详见 `docs/superpowers/specs/2026-08-04-job-copilot-design.md`）。
