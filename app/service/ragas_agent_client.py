"""RAGAS generation 평가용 agent(/v1/invoke) 연동 클라이언트

generation/all 모드에서 골든셋의 (질문 + 근거 청크)를 agent에 보내 실제 답변을 받아
RagasDatasetItem.response에 채운다. 이후 기존 RAGAS 분석 로직이 그대로 이 response를 사용한다.

설계:
- 호출 인증: 호출자(로그인 유저)의 x-user-passport 헤더(plain JSON 문자열)를 그대로 전달한다.
  agent는 passport를 Primary 인증으로 사용하므로 JWT(Authorization)는 보내지 않는다.
  indexing은 API 요청 시점에 받은 passport 원본을 config["user_passport"]로 들고 있어 그대로 forward한다.
- message에는 청크 전용 슬롯이 없으므로, 근거 청크 + 질문을 마커 텍스트로 직렬화해 넣는다.
- 1:1 호출(질문 1건 = invoke 1회) + 동시성 cap(semaphore). 실패 행은 skip(응답 None) + 로그.
- URL/시나리오ID/타임아웃/동시성은 settings(.env)에서 주입.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _build_invoke_headers(user_passport: str) -> Dict[str, str]:
    """agent /v1/invoke 호출 헤더.

    인증은 x-user-passport(Primary)만 사용한다. agent가 passport를 우선 인증으로
    처리하므로 Authorization(JWT)은 보내지 않는다.
    """
    return {
        "Content-Type": "application/json",
        "x-user-passport": user_passport,
    }


def build_agent_message(question: str, reference_contexts: List[str]) -> str:
    """근거 청크 + 질문을 페르소나가 읽을 마커 텍스트로 직렬화한다."""
    lines: List[str] = ["[근거]"]
    if reference_contexts:
        for ctx in reference_contexts:
            text = (ctx or "").strip()
            if text:
                lines.append(f"- {text}")
    if len(lines) == 1:
        lines.append("- (제공된 근거 없음)")
    lines.append("")
    lines.append("[질문]")
    lines.append(question)
    return "\n".join(lines)


def _generate_unique_id() -> str:
    """고유 ID 생성: 현재시간(YYYYMMDDHHMMSS) + UUID 정수값 조합.

    형식 출처: agent websocket_key_generator._generate_unique_id() 박제.
    """
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
    uuid_int_str = str(uuid.uuid4().int)
    return f"{timestamp_str}_{uuid_int_str}"


def gen_thread_qa_ids() -> Tuple[str, str]:
    """thread_id / qa_id 생성 (agent 정통 형식 YYYYMMDDHHMMSS_UUID정수).

    - 형식 출처: agent websocket_key_generator._generate_unique_id()
    - thread_id / qa_id 모두 호출마다 고유 → 대화 맥락 격리 + 히스토리 덮어쓰기 방지
    - thread_id == qa_id 충돌 시 qa_id 재생성 (agent 동작 박제)
    """
    thread_id = _generate_unique_id()
    qa_id = _generate_unique_id()
    if thread_id == qa_id:
        qa_id = _generate_unique_id()
    return thread_id, qa_id


def extract_answer_text(message: Any) -> Optional[str]:
    """invoke 응답 message(str|list|dict)에서 답변 텍스트를 추출한다."""
    if message is None:
        return None
    if isinstance(message, str):
        text = message.strip()
        return text or None
    if isinstance(message, dict):
        # Claude/구조화 dict는 보통 text 키를 가짐
        text = message.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        return None
    if isinstance(message, list):
        parts = [
            p.get("text", "")
            for p in message
            if isinstance(p, dict) and p.get("text")
        ]
        joined = "\n".join(s for s in parts if s).strip()
        return joined or None
    return None


async def _invoke_one(
    session: aiohttp.ClientSession,
    item: Any,
    user_id: Any,
    evaluation_id: int,
    user_passport: str,
    semaphore: asyncio.Semaphore,
) -> Tuple[int, Optional[str]]:
    """질문 1건을 agent에 보내 답변 텍스트를 반환한다. 실패/인터럽트 시 None."""
    async with semaphore:
        thread_id, qa_id = gen_thread_qa_ids()
        logger.info(
            f"[RAGAS-agent] eval={evaluation_id} row_id={item.id} "
            f"thread_id={thread_id} qa_id={qa_id}"
        )
        body = {
            "scenario_my_page_id": settings.RAGAS_AGENT_SCENARIO_ID,
            "user_id": str(user_id),
            "thread_id": thread_id,
            "qa_id": qa_id,
            "message": build_agent_message(item.user_input, item.reference_contexts),
        }
        headers = _build_invoke_headers(user_passport)
        timeout = aiohttp.ClientTimeout(total=settings.AGENT_TIMEOUT)
        try:
            async with session.post(
                settings.AGENT_INVOKE_URL, json=body, headers=headers, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(
                        f"[RAGAS-agent] invoke 실패 id={item.id} "
                        f"status={resp.status}: {text[:200]}"
                    )
                    return item.id, None
                data = await resp.json()
                if data.get("interrupt"):
                    logger.warning(
                        f"[RAGAS-agent] interrupt 응답 id={item.id} - skip"
                    )
                    return item.id, None
                return item.id, extract_answer_text(data.get("message"))
        except Exception as exc:
            logger.warning(
                f"[RAGAS-agent] invoke 예외 id={item.id}: {type(exc).__name__}: {exc}"
            )
            return item.id, None


def _has_response(item: Any) -> bool:
    """item.response에 공백을 제거하고도 글자가 한 자라도 남으면 True (기존값 존재)."""
    return bool((item.response or "").strip())


async def fill_responses_via_agent(
    dataset: List[Any],
    user_id: Any,
    evaluation_id: int,
    user_passport: str,
) -> Dict[str, Any]:
    """빈 response 행만 agent로 호출해 item.response를 채운다 (1:1 + 동시성 cap).

    - 인증: 호출자의 x-user-passport 헤더(plain JSON 문자열)를 그대로 전달한다.
    - 기존값(공백 제거 후 글자 존재)이 있는 행은 agent 미호출 + 원본 유지(skip).
    - 빈 행 중 실패한 행은 response를 채우지 않고(None 유지) skip하며, 통계를 반환한다.

    Returns:
        {"filled": int, "skipped": List[int], "failed": List[int]}
    """
    if not user_passport:
        raise ValueError("user_passport가 비어 있어 agent 호출 인증이 불가합니다.")

    semaphore = asyncio.Semaphore(settings.RAGAS_AGENT_MAX_CONCURRENCY)

    targets = [item for item in dataset if not _has_response(item)]
    skipped = [item.id for item in dataset if _has_response(item)]

    logger.info(
        f"[RAGAS-agent] response 채우기 시작: 전체 {len(dataset)}건 중 "
        f"생성대상 {len(targets)}건 / 기존값보존(skip) {len(skipped)}건, "
        f"scenario={settings.RAGAS_AGENT_SCENARIO_ID}, "
        f"concurrency={settings.RAGAS_AGENT_MAX_CONCURRENCY}"
    )

    answers: Dict[int, Optional[str]] = {}
    if targets:
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                *[
                    _invoke_one(
                        session, item, user_id, evaluation_id, user_passport, semaphore
                    )
                    for item in targets
                ]
            )
        answers = dict(results)

    filled = 0
    failed: List[int] = []
    for item in targets:
        ans = answers.get(item.id)
        if ans:
            item.response = ans
            filled += 1
        else:
            failed.append(item.id)

    logger.info(
        f"[RAGAS-agent] response 채움 완료: 생성 {filled}건, "
        f"기존값보존 {len(skipped)}건, 실패 {len(failed)}건 (실패 id={failed})"
    )
    return {"filled": filled, "skipped": skipped, "failed": failed}
