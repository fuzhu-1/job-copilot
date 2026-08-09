# Job Copilot 更新说明

## 2026-08-09：审计整改 + 可用性修复（24 个提交）

本次更新基于代码审计报告（[audit-report-2026-08.md](./audit-report-2026-08.md)）完成整改，并在真实环境全流程验证（[test-eval-2026-08-09.md](./test-eval-2026-08-09.md)）。

### 新增功能

- 中文全文检索：用「jieba 分词 + BM25 + SQLite」替换 ChromaDB，简历/JD 检索真正支持中文；JD 列表新增关键词搜索（`GET /api/jds?q=`）
- 市场洞察支持中文技能词统计，并过滤中英文停用词与数字噪音
- 匹配任务持久化：任务与事件写入数据库，SSE 从任务表回放，支持断线重连后补推
- 双击一键启动：项目根目录 `一键启动.bat`（自动加载配置、校验模型、清理端口、启动服务、打开浏览器）
- golden set 可移植化：`python scripts/seed_eval_data.py` 用确定性 ID 生成评测样例，任何环境可复现评测
- 真实环境冒烟测试脚本：`python scripts/feature_test.py`（25 项功能自动化回归）

### 修复

- 匹配页一直"匹配中"：SSE 读取会话缓存旧快照导致完成事件不可见，改为轮询前强制刷新
- 匹配任务完成后状态仍为 running，现正确落库 completed；服务重启自动标记中断任务
- 简历解析偶发失败：LLM 结构化输出 token 上限提升（默认 4000/简历 6000），无效输出最多重试 3 次
- 前端将连接中断误判为任务失败：区分任务错误与传输错误，自动重连并限次
- 批量删除 JD 现在级联清理投递、匹配、面试与检索索引
- 同一岗位禁止重复创建投递记录；上传解析失败自动清理孤儿文件
- 匹配全零评分重试加强（最多 3 次），golden 区间按实测校准

### 性能与工程化

- 匹配图改为按默认 LLM 缓存，避免每次匹配重复编译
- 列表接口消除 N+1 查询（投递、面试）
- LLM 层加入超时、429/5xx 指数退避重试、json 模式自动降级、token 用量日志
- 引入 Alembic 数据库迁移（`python -m alembic upgrade head`）
- 依赖锁定：pip-tools 生成 requirements.txt / requirements-dev.txt（精确版本）
- CI 增强：ruff 代码检查 + Alembic 迁移验证 + 前端构建

### 使用注意

- LLM 模型需与 API Key 匹配：当前配置为 `deepseek-v4-flash`（一键脚本会自动校验并修正）
- 旧 ChromaDB 数据目录 `data/chroma` 已废弃删除，检索索引迁移到 `data/search.db`
- 数据库中存在历史测试 JD 时可在「岗位 JD」页批量删除

## 更早记录

（项目早期提交记录见 git log，本次起维护 CHANGELOG。）
