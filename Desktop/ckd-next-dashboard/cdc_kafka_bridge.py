"""
CKD-NEXT CDC → Kafka Bridge
PostgreSQL pg_notify LISTEN → aiokafka Producer → Kafka Topics

토픽 매핑:
  sales_order          → ckd.sales.orders
  deviation_report     → ckd.quality.deviations
  capa_action          → ckd.quality.capa
  production_order     → ckd.production.orders
  purchase_order       → ckd.production.purchases
  accounts_receivable  → ckd.finance.ar
  qm_inspection_lot    → ckd.quality.lots
  gl_posting           → ckd.finance.gl
"""
import asyncio
import json
import logging
import signal
from datetime import datetime

import psycopg2
import psycopg2.extras
import select
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CDC] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ckd.cdc")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "database": "ckd_next", "user": "postgres", "password": "1234",
}
KAFKA_BOOTSTRAP = "localhost:9092"

TABLE_TOPIC_MAP = {
    "sales_order":         "ckd.sales.orders",
    "deviation_report":    "ckd.quality.deviations",
    "capa_action":         "ckd.quality.capa",
    "production_order":    "ckd.production.orders",
    "purchase_order":      "ckd.production.purchases",
    "accounts_receivable": "ckd.finance.ar",
    "qm_inspection_lot":   "ckd.quality.lots",
    "gl_posting":          "ckd.finance.gl",
}

LISTEN_CHANNELS = [f"ckd_cdc_{t}" for t in TABLE_TOPIC_MAP]

_stop_event = asyncio.Event()


def _make_pg_conn():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    for ch in LISTEN_CHANNELS:
        cur.execute(f"LISTEN {ch};")
        log.info(f"LISTEN: {ch}")
    cur.close()
    return conn


async def run_bridge():
    log.info("CDC Bridge 시작")

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode(),
        key_serializer=lambda k: k.encode() if k else None,
        compression_type="gzip",
        request_timeout_ms=10_000,
        retry_backoff_ms=1_000,
    )

    try:
        await producer.start()
        log.info(f"Kafka 연결 OK: {KAFKA_BOOTSTRAP}")
    except KafkaConnectionError as e:
        log.error(f"Kafka 연결 실패: {e}")
        raise

    conn = _make_pg_conn()
    log.info("PostgreSQL CDC LISTEN 대기 시작")

    try:
        while not _stop_event.is_set():
            # non-blocking poll (100ms)
            ready = select.select([conn], [], [], 0.1)[0]
            if ready:
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    channel = notify.channel          # e.g. ckd_cdc_sales_order
                    table   = channel.replace("ckd_cdc_", "")
                    topic   = TABLE_TOPIC_MAP.get(table)
                    if not topic:
                        continue

                    try:
                        payload = json.loads(notify.payload)
                    except json.JSONDecodeError:
                        log.warning(f"JSON 파싱 실패: {notify.payload[:200]}")
                        continue

                    # 메시지 키: 기본키 값
                    after  = payload.get("after") or {}
                    before = payload.get("before") or {}
                    pk = (after or before).get(f"{table.rstrip('s')}_id") or \
                         (after or before).get("id") or "unknown"

                    enriched = {
                        **payload,
                        "topic":  topic,
                        "bridge_ts": datetime.utcnow().isoformat(),
                    }

                    await producer.send(topic, value=enriched, key=str(pk))
                    op = payload.get("op", "?")
                    log.info(f"[{op}] {table} → {topic} (key={pk})")

            await asyncio.sleep(0)   # yield to event loop
    finally:
        conn.close()
        await producer.stop()
        log.info("CDC Bridge 종료")


def main():
    loop = asyncio.new_event_loop()

    def _shutdown():
        log.info("종료 신호 수신")
        _stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass  # Windows

    try:
        loop.run_until_complete(run_bridge())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
