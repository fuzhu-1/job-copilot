"""Job Copilot 功能完备性测试驱动（真实环境冒烟测试）。

用法: python scripts/feature_test.py
会创建带"自检"前缀的测试数据，结束后自动清理测试 JD（级联删除投递/匹配/面试）。
"""

import json
import time
import uuid
from pathlib import Path

import fitz
import httpx

BASE = "http://127.0.0.1:8000"
PREFIX = "自检"
RESULTS: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"name": name, "ok": ok, "detail": detail})
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name} {detail}")


def post(path: str, payload: dict | None = None, timeout: float = 180) -> dict:
    r = httpx.post(BASE + path, json=payload, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def get(path: str, timeout: float = 60) -> dict:
    r = httpx.get(BASE + path, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def make_resume_pdf(path: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "李四", fontsize=20, fontname="china-s")
    page.insert_text((72, 100), "邮箱：lisi@example.com", fontname="china-s")
    page.insert_text((72, 120), "教育背景：XX大学 软件工程 硕士", fontname="china-s")
    page.insert_text((72, 140), "技能：Python、FastAPI、MySQL、Redis", fontname="china-s")
    page.insert_text((72, 160), "项目：智能客服系统，基于 RAG 的检索问答", fontname="china-s")
    page.insert_text((72, 180), "经历：某公司 后端实习生，负责接口开发与性能优化", fontname="china-s")
    doc.save(path)
    doc.close()


def stream_task(task_id: str, timeout: float = 180) -> list[dict]:
    events: list[dict] = []
    with httpx.stream("GET", f"{BASE}/api/matches/{task_id}/stream", timeout=timeout) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def main() -> None:
    # 1. 健康检查
    try:
        data = get("/health", timeout=10)
        record("健康检查", data.get("status") == "ok", str(data))
    except Exception as exc:
        record("健康检查", False, str(exc))
        return

    created_jd_ids: list[str] = []
    created_notes: list[str] = []

    try:
        # 2. 简历上传 + 确认
        pdf = Path("data") / f"_feature_{uuid.uuid4().hex[:8]}.pdf"
        make_resume_pdf(str(pdf))
        with open(pdf, "rb") as f:
            r = httpx.post(
                f"{BASE}/api/resume/upload",
                files={"file": ("feature.pdf", f, "application/pdf")},
                timeout=180,
            )
        if r.status_code >= 400:
            raise RuntimeError(f"resume upload -> {r.status_code}: {r.text[:200]}")
        resume = r.json()
        pdf.unlink(missing_ok=True)
        record("简历上传+LLM结构化", resume["status"] == "pending_confirmation", f"name={resume['structured'].get('name')}")
        confirm = post(
            f"/api/resume/{resume['resume_id']}/confirm",
            {"structured": resume["structured"]},
            timeout=30,
        )
        record("简历人工确认", confirm.get("status") == "confirmed", str(confirm))

        # 3. JD 文本录入
        jd1 = post(
            "/api/jds",
            {
                "source": "text",
                "text": f"{PREFIX}公司A 招聘 后端开发工程师，要求熟悉 Python、FastAPI、MySQL",
            },
        )
        created_jd_ids.append(jd1["jd_id"])
        record("JD 文本录入", bool(jd1.get("title")), f"title={jd1.get('title')}")

        # 4. JD URL 录入（抓取公开页面，可能失败降级）
        try:
            jd2 = post(
                "/api/jds",
                {"source": "url", "url": "https://example.com"},
                timeout=60,
            )
            created_jd_ids.append(jd2["jd_id"])
            record("JD URL 录入", True, f"title={jd2.get('title')}")
        except Exception as exc:
            record("JD URL 录入", False, str(exc))

        # 5. JD 批量录入
        batch = post(
            "/api/jds/batch",
            {
                "texts": [
                    f"{PREFIX}公司B 招聘 前端工程师，熟悉 React 与 TypeScript",
                    f"{PREFIX}公司C 招聘 算法工程师，熟悉机器学习与深度学习",
                ]
            },
            timeout=180,
        )
        created_jd_ids.extend(batch.get("jd_ids", []))
        record("JD 批量录入", len(batch.get("jd_ids", [])) == 2, str(batch))

        # 6. JD 列表 + 关键词检索
        lst = get("/api/jds")
        record("JD 列表", len(lst.get("jds", [])) >= 3, f"count={len(lst.get('jds', []))}")
        search = get("/api/jds?q=机器学习")
        record("JD 关键词检索", any(PREFIX in j.get("company", "") for j in search.get("jds", [])), f"count={len(search.get('jds', []))}")

        # 7. 市场洞察
        insight = post("/api/insights/market", timeout=60)
        record(
            "市场洞察",
            insight.get("report", {}).get("total_jds", 0) >= 4,
            f"total_jds={insight.get('report', {}).get('total_jds')}",
        )

        # 8. 匹配（SSE 实时）
        match = post(
            "/api/matches",
            {"resume_id": resume["resume_id"], "jd_ids": created_jd_ids[:2]},
            timeout=30,
        )
        events = stream_task(match["task_id"], timeout=240)
        types = [e.get("type") for e in events]
        record(
            "匹配+SSE 实时进度",
            "completed" in types and "match_result" in types,
            " -> ".join(types),
        )

        # 9. 自荐信
        result_events = [e for e in events if e.get("type") == "match_result"]
        match_id = result_events[0]["result"]["match_id"] if result_events else None
        if match_id:
            cover = post(f"/api/matches/{match_id}/cover-letter", {"match_id": match_id, "tone": "standard"}, timeout=180)
            record("自荐信生成+评审", bool(cover.get("content")), f"judge={cover.get('judge_score')}")

        # 10. 投递看板
        if match_id:
            app = post("/api/applications", {"match_id": match_id}, timeout=30)
            app_id = app.get("application_id")
            record("创建投递记录", bool(app_id), f"status={app.get('current_status')}")
            trans = post(f"/api/applications/{app_id}/status", {"target_status": "screening"}, timeout=30)
            record("投递状态流转", trans.get("current_status") == "screening", str(trans.get("current_status")))
            custom = post(f"/api/applications/{app_id}/custom-statuses", {"status": "笔试", "from_status": "screening", "next": ["interview"]}, timeout=30)
            record("自定义状态", "笔试" in custom.get("custom_statuses", {}).get("screening", []), str(custom.get("custom_statuses")))
            apps = get("/api/applications")
            record("投递列表", any(a.get("application_id") == app_id for a in apps.get("applications", [])), f"count={len(apps.get('applications', []))}")
            reminders = get("/api/applications/reminders")
            record("跟进提醒接口", isinstance(reminders.get("reminders"), list), f"count={len(reminders.get('reminders', []))}")

        # 11. 面试陪练
        interview = post("/api/interviews/sessions", {"jd_id": created_jd_ids[0], "resume_id": resume["resume_id"]}, timeout=120)
        session_id = interview.get("session_id")
        record("面试会话创建", bool(session_id), f"q={interview.get('messages', [{}])[0].get('content', '')[:40]}")
        if session_id:
            resp = post(f"/api/interviews/sessions/{session_id}/respond", {"answer": "我用 FastAPI 开发过 RAG 检索服务，优化了响应延迟"}, timeout=120)
            record("面试回答评分+追问", resp.get("score", 0) > 0 and bool(resp.get("next_question")), f"score={resp.get('score')}")

        # 12. 面试备注
        note = post("/api/interviews/notes", {"date": "2026-08-09", "title": "自检备注", "note": "功能测试"}, timeout=30)
        created_notes.append(note.get("note_id"))
        record("面试备注创建", bool(note.get("note_id")), str(note.get("note_id")))
        notes = get("/api/interviews/notes")
        record("面试备注列表", any(n.get("note_id") == note.get("note_id") for n in notes.get("notes", [])), f"count={len(notes.get('notes', []))}")

        # 13. 企业研究（需联网搜索，失败时降级）
        try:
            research = post(f"/api/jds/{created_jd_ids[0]}/research", timeout=120)
            report = research.get("report", {})
            record("企业研究", bool(report.get("company")) or bool(report.get("tips")), f"company={report.get('company')}")
        except Exception as exc:
            record("企业研究", False, str(exc))

        # 14. 助手意图识别
        agent = post("/api/agent/message", {"message": "帮我匹配一下岗位"}, timeout=120)
        record("Supervisor 意图识别", bool(agent.get("intent")), f"intent={agent.get('intent')}")

        # 15. 系统自检（golden set 评测）
        try:
            ev = post("/api/eval/runs", timeout=300)
            metrics = ev.get("metrics", {})
            record("系统自检评测", metrics.get("pass_rate", 0) >= 0.66, f"pass_rate={metrics.get('pass_rate')}")
        except Exception as exc:
            record("系统自检评测", False, str(exc))

    except Exception as exc:
        record("测试流程异常", False, str(exc))
    finally:
        # 清理测试 JD（级联删除其投递/匹配/面试）
        if created_jd_ids:
            try:
                post("/api/jds/batch-delete", {"jd_ids": created_jd_ids}, timeout=60)
                record("清理测试 JD", True, f"deleted={len(created_jd_ids)}")
            except Exception as exc:
                record("清理测试 JD", False, str(exc))
        for note_id in created_notes:
            try:
                r = httpx.delete(f"{BASE}/api/interviews/notes/{note_id}", timeout=30)
                record("清理测试备注", r.status_code == 200, note_id)
            except Exception as exc:
                record("清理测试备注", False, str(exc))

    passed = sum(1 for x in RESULTS if x["ok"])
    print(f"\n===== 汇总: {passed}/{len(RESULTS)} 通过 =====")
    for x in RESULTS:
        if not x["ok"]:
            print(f"  FAIL {x['name']}: {x['detail']}")


if __name__ == "__main__":
    main()
