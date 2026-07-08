"""
CKD-NEXT CDC → Redis Streams Bridge (Kafka 대체)
PostgreSQL pg_notify LISTEN → Redis XADD (Stream) + PUBLISH (PubSub)

Kafka 클러스터 외부 IP(192.168.56.20) 라우팅 불가 환경에서
Redis Streams를 메인 이벤트 버스로 활용.

Redis 구조:
  ckd:stream:{table}   STREAM  테이블별 이벤트 (maxlen 5000)
  ckd:events:stream    STREAM  통합 이벤트 로그 (maxlen 10000)
  ckd:alerts:critical  ZSET    Critical 알람
  ckd:realtime         PubSub  실시간 WebSocket 브로드캐스트
"""
import asyncio
import json
import logging
import select
import signal
from datetime import datetime

import psycopg2
import psycopg2.extensions
from redis.cluster import RedisCluster, ClusterNode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CDC-REDIS] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ckd.cdc_redis")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "database": "ckd_next", "user": "postgres", "password": "1234",
}

REMAP = {
    ("172.20.0.11", 6379): ("localhost", 6379),
    ("172.20.0.12", 6379): ("localhost", 6380),
    ("172.20.0.13", 6379): ("localhost", 6381),
}

TABLE_CHANNELS = [
    "ckd_cdc_sales_order",
    "ckd_cdc_deviation_report",
    "ckd_cdc_capa_action",
    "ckd_cdc_production_order",
    "ckd_cdc_purchase_order",
    "ckd_cdc_accounts_receivable",
    "ckd_cdc_qm_inspection_lot",
    "ckd_cdc_gl_posting",
]

_stop_event = asyncio.Event()


def _get_redis():
    return RedisCluster(
        startup_nodes=[ClusterNode("localhost", 6379)],
        decode_responses=True,
        skip_full_coverage_check=True,
        address_remap=lambda a: REMAP.get(a, a),
        socket_connect_timeout=3,
        socket_timeout=3,
    )


def _get_pg_conn():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    for ch in TABLE_CHANNELS:
        cur.execute(f"LISTEN {ch};")
    cur.close()
    log.info(f"PostgreSQL LISTEN 등록: {len(TABLE_CHANNELS)}개 채널")
    return conn


def _make_summary(table: str, op: str, after: dict) -> str:
    if table == "sales_order":
        return f"수주 {after.get('order_no','?')} {op} [{after.get('overall_status','')}]"
    if table == "deviation_report":
        return f"일탈 {after.get('deviation_id','?')} {op} [{after.get('severity','')}]"
    if table == "capa_action":
        return f"CAPA {after.get('action_id','?')} {op} [{after.get('status','')}]"
    if table == "production_order":
        return f"생산오더 {after.get('prod_order_id','?')} {op}"
    if table == "accounts_receivable":
        amt = after.get("open_amount", 0)
        return f"AR {after.get('ar_id','?')} {op} ₩{float(amt or 0):,.0f}"
    return f"{table} {op}"


def handle_notify(notify, rc: RedisCluster):
    channel = notify.channel
    table   = channel.replace("ckd_cdc_", "")
    try:
        payload = json.loads(notify.payload)
    except json.JSONDecodeError:
        log.warning(f"JSON 파싱 실패: {notify.payload[:100]}")
        return

    op    = payload.get("op", "?")
    after = payload.get("after") or {}
    before= payload.get("before") or {}
    ts    = payload.get("ts", 0)

    # 1. 통합 Stream + 테이블별 Stream에 이벤트 기록
    event_fields = {
        "op": op, "table": table,
        "data": json.dumps(after or before, ensure_ascii=False, default=str),
        "ts": str(ts),
        "bridge_ts": datetime.utcnow().isoformat(),
    }
    try:
        rc.xadd("ckd:events:stream", event_fields, maxlen=10000, approximate=True)
        rc.xadd(f"ckd:stream:{table}", event_fields, maxlen=5000, approximate=True)
    except Exception as e:
        log.error(f"Redis XADD 오류: {e}")
        return

    # 2. Critical 일탈 → ZSET 알람
    if table == "deviation_report" and after.get("severity") in ("CRITICAL", "MAJOR"):
        if op in ("INSERT", "UPDATE"):
            alert = json.dumps({
                "id": after.get("deviation_id","?"),
                "sev": after.get("severity",""),
                "status": after.get("status",""),
                "ts": ts,
            }, ensure_ascii=False)
            try:
                rc.zadd("ckd:alerts:critical", {alert: float(ts)})
                rc.zremrangebyrank("ckd:alerts:critical", 0, -51)
            except Exception as e:
                log.warning(f"ZADD 오류: {e}")

    # 3. KPI 캐시 무효화
    if op in ("INSERT", "UPDATE", "DELETE"):
        try:
            rc.delete("ckd:kpi:cache")
        except Exception:
            pass

    # 4. Pub/Sub 브로드캐스트
    broadcast = json.dumps({
        "type": "cdc_event",
        "topic": f"ckd.{table}",
        "op": op, "table": table,
        "summary": _make_summary(table, op, after),
        "ts": ts,
    }, ensure_ascii=False, default=str)
    try:
        rc.publish("ckd:realtime", broadcast)
    except Exception as e:
        log.warning(f"PUBLISH 오류: {e}")

    log.info(f"[{op}] {table} → Stream + PubSub 완료")


async def run():
    log.info("CDC-Redis Bridge 시작")

    # Redis 연결
    rc = _get_redis()
    rc.ping()
    log.info("Redis Cluster 연결 OK")

    # PostgreSQL 연결
    conn = _get_pg_conn()
    log.info("PostgreSQL LISTEN 대기 시작")

    loop = asyncio.get_event_loop()

    def _poll():
        while not _stop_event.is_set():
            ready = select.select([conn], [], [], 0.1)[0]
            if ready:
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    handle_notify(notify, rc)

    # 블로킹 poll을 별도 스레드에서 실행
    await loop.run_in_executor(None, _poll)

    conn.close()
    rc.close()
    log.info("CDC-Redis Bridge 종료")


def main():
    loop = asyncio.new_event_loop()

    def _shutdown(*_):
        log.info("종료 신호 수신")
        _stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_until_complete(run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
