"""
CKD-NEXT Kafka Consumer → Redis
Kafka Topics → Redis Cache 갱신 + Redis Pub/Sub 실시간 브로드캐스트

Redis 구조:
  ckd:kpi:cache         HASH   KPI 집계값 캐시 (TTL 15s)
  ckd:events:stream     STREAM 전체 이벤트 로그 (maxlen 5000)
  ckd:alerts:critical   ZSET   Critical 알람 (score=timestamp)
  ckd:realtime          PubSub 채널 → FastAPI WebSocket 브로드캐스트
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONSUMER] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ckd.consumer")

KAFKA_BOOTSTRAP = "localhost:9092"
REDIS_URL       = "redis://localhost:6379/0"

TOPICS = [
    "ckd.sales.orders",
    "ckd.quality.deviations",
    "ckd.quality.capa",
    "ckd.production.orders",
    "ckd.production.purchases",
    "ckd.finance.ar",
    "ckd.quality.lots",
    "ckd.finance.gl",
]


def _alert_severity(payload: dict) -> str | None:
    after = payload.get("after") or {}
    sev = after.get("severity", "")
    return sev if sev in ("CRITICAL", "MAJOR") else None


async def handle_message(topic: str, payload: dict, redis: aioredis.Redis):
    op    = payload.get("op", "?")
    table = payload.get("table", "")
    after = payload.get("after") or {}
    ts    = payload.get("ts", 0)

    # ── 1. Redis Stream에 모든 이벤트 기록 ─────────────────────
    await redis.xadd(
        "ckd:events:stream",
        {
            "topic": topic, "op": op, "table": table,
            "data": json.dumps(after, ensure_ascii=False, default=str),
            "ts": str(ts),
        },
        maxlen=5000,
        approximate=True,
    )

    # ── 2. 토픽별 전용 처리 ─────────────────────────────────────
    if topic == "ckd.quality.deviations":
        sev = _alert_severity(payload)
        if sev and op in ("INSERT", "UPDATE"):
            dev_id = after.get("deviation_id", "?")
            score  = float(ts)
            await redis.zadd(
                "ckd:alerts:critical",
                {json.dumps({"id": dev_id, "sev": sev, "status": after.get("status", ""),
                             "ts": ts}, ensure_ascii=False): score}
            )
            await redis.zremrangebyrank("ckd:alerts:critical", 0, -51)  # 최대 50개

    # ── 3. KPI 캐시 무효화 (다음 조회 시 DB 재조회) ─────────────
    if op in ("INSERT", "UPDATE"):
        await redis.delete("ckd:kpi:cache")

    # ── 4. Redis Pub/Sub 실시간 브로드캐스트 ─────────────────────
    broadcast = json.dumps({
        "type": "cdc_event",
        "topic": topic,
        "op": op,
        "table": table,
        "summary": _make_summary(topic, op, after),
        "ts": ts,
    }, ensure_ascii=False, default=str)
    await redis.publish("ckd:realtime", broadcast)

    log.info(f"[{op}] {table} → Redis Stream + PubSub 완료")


def _make_summary(topic: str, op: str, after: dict) -> str:
    if topic == "ckd.sales.orders":
        return f"수주 {after.get('order_no','?')} {op} (상태:{after.get('overall_status','')})"
    if topic == "ckd.quality.deviations":
        return f"일탈 {after.get('deviation_id','?')} {op} [{after.get('severity','')}]"
    if topic == "ckd.quality.capa":
        return f"CAPA {after.get('action_id','?')} {op} (상태:{after.get('status','')})"
    if topic == "ckd.production.orders":
        return f"생산오더 {after.get('prod_order_id','?')} {op}"
    if topic == "ckd.finance.ar":
        amt = after.get('open_amount', 0)
        return f"AR {after.get('ar_id','?')} {op} ₩{float(amt or 0):,.0f}"
    return f"{topic.split('.')[-1]} {op}"


async def run_consumer():
    log.info("Kafka Consumer 시작")
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)

    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="ckd-dashboard-consumer",
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await consumer.start()
    log.info(f"구독 토픽: {TOPICS}")

    try:
        async for msg in consumer:
            try:
                await handle_message(msg.topic, msg.value, redis)
            except Exception as e:
                log.error(f"메시지 처리 오류: {e}", exc_info=True)
    finally:
        await consumer.stop()
        await redis.aclose()
        log.info("Kafka Consumer 종료")


if __name__ == "__main__":
    asyncio.run(run_consumer())
