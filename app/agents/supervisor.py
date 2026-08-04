from sqlalchemy.orm import Session

from app.llm import LLMService
from app.schemas import Intent
from app.services import insight_service

INTENT_PROMPT = (
    "你是 Job Copilot 的意图识别器。把用户消息分类为以下之一：\n"
    "resume_upload / jd_add / match / cover_letter / company_research / market_insight / "
    "application / help\n"
    "示例：\n"
    "- '我要上传简历' -> resume_upload\n"
    "- '帮我加一条 JD' -> jd_add\n"
    "- '匹配一下这个岗位' -> match\n"
    "- '生成自荐信' -> cover_letter\n"
    "- '查一下这家公司的面试流程' -> company_research\n"
    "- '分析近期岗位趋势' -> market_insight\n"
    "- '记录一下投递' -> application\n"
    "- 其他 -> help\n"
    "用户消息：{message}\n"
    '输出 JSON：{{"intent": "...", "target": "公司或岗位名，可为空"}}'
)

INTENT_GUIDANCE = {
    "resume_upload": "请上传简历 PDF，系统会解析并生成结构化简历。",
    "jd_add": "请在岗位 JD 页粘贴 JD 文本或填写 URL。",
    "match": "请进入「匹配与自荐信」页发起匹配。",
    "cover_letter": "先生成匹配结果，然后点击「生成自荐信」。",
    "company_research": "请在岗位 JD 列表中选择一条 JD，点击「企业研究」。",
    "market_insight": "已生成市场洞察报告。",
    "application": "请在投递看板中记录投递状态。",
    "help": "我可以帮你管理简历、JD、匹配、自荐信、企业研究与投递状态。",
}


def classify_intent(message: str, llm: LLMService | None = None) -> dict:
    llm = llm or LLMService()
    prompt = INTENT_PROMPT.format(message=message[:2000])
    return llm.complete_structured([{"role": "user", "content": prompt}], Intent)


def handle_message(
    db: Session | None,
    message: str,
    llm: LLMService | None = None,
) -> dict:
    """意图分类 + 路由。market_insight 直接执行，其余返回引导。"""
    intent = classify_intent(message, llm)["intent"]
    if intent == "market_insight" and db is not None:
        report = insight_service.generate_market_insight(db)
        return {
            "intent": intent,
            "message": INTENT_GUIDANCE[intent],
            "payload": {"report": report},
        }
    return {
        "intent": intent,
        "message": INTENT_GUIDANCE.get(intent, INTENT_GUIDANCE["help"]),
        "payload": {},
    }
