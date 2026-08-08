# 面试问答准备（Job Copilot）

## 1. 为什么用 LangGraph 而不是 LangChain Agent / CrewAI？

需要可控的有状态工作流：规则节点（关键词重叠）→ LLM 打分 → 差距归一化，节点边界
清晰、可单测；LangGraph 的显式图结构让「每一步做了什么」可观测，配合 SSE 展示执行
轨迹，面试演示直观。CrewAI 偏高层封装，灵活性不足；LangChain Agent 的隐式循环
不利于错误定位。

## 2. 怎么证明你的 Agent 变好了？

golden set 评测：人工标注期望结果（匹配分数区间、自荐信关键词、陪练总结阈值），
三类判定器分别用确定性区间、LLM-as-judge、阈值判定；跑完聚合通过率与分类型平均分。
任何改动先跑评测，指标不低于基线才合入，防止「修 A 坏 B」。

## 3. LLM-as-judge 会不会自欺？

会，所以有三道防线：golden set 期望由人工标注；judge 只负责给分，不参与生成；
设计上保留人工抽样复核（每周抽 10% 复核校准），且 judge 与生成用同一模型时
会在报告中标注风险。现阶段 judge 用于自检重写循环，最终裁决仍是人工。

## 4. 简历解析不准怎么办？

两条路：解析后强制人工确认点，未确认不入库；解析失败降级为纯文本 + 提示改用
粘贴输入。PDF 扫描件走 OCR 开关（可选增强）。人机协同是刻意设计：LLM 擅长结构化
提取，人负责最终确认。

## 5. 匹配分数可解释吗？怎么做的？

四维拆解：skill_match / experience_match / education_match / hard_requirements，
每维 0-100 并附一句理由；规则层先算关键词重叠率作为信号喂给 LLM，避免纯黑盒。
权重可配置，总分 = 加权和，前端雷达图展示。

## 6. 反爬/合规怎么办？

JD 来源以用户提供为主（粘贴/上传/URL），浏览器自动化仅限公开页面，不做登录态
爬取；失败时降级提示手动粘贴。Agent 不自动投递，最终动作留给用户，规避合规与
稳定性风险。

## 7. SSE 实时展示怎么实现的？

进程内线程安全事件总线：后台线程跑匹配任务并 publish 事件，SSE 生成器订阅队列，
用 `asyncio.to_thread(queue.get)` 轮询；事件类型包括 started / match_progress /
match_result / completed / error，前端 EventSource 按类型消费。

## 8. 状态机怎么防非法跳转？

默认转移表定义合法路径（applied→screening→interview→offer→accepted/rejected，
含退回边），每单可注册自定义状态及其下一步；目标状态不在 allowed_next 集合即
抛 ValueError，API 层转 422 并提示合法路径。

## 9. 多 Agent 之间怎么通信？

服务层编排为主（简历/JD/匹配/自荐信是串行管道），Supervisor 做意图分类与路由；
评测 runner 复用各服务，把 golden case 逐条跑出指标。通信通过 SQLAlchemy 共享
状态与 Pydantic 结构化结果，避免 Agent 间直接耦合。

## 10. 项目最大的坑是什么？

LLM 结构化输出不稳定（非 JSON/字段缺失）：解法是 Pydantic schema 校验 + 带错误
信息重试一次 + 纯文本降级；另一个坑是向量库方案过重且中文检索失效，后来把
ChromaDB 换成「jieba 分词 + BM25 + SQLite」的轻量本地检索，离线可跑、无模型下载。
