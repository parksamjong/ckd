"""
CKD-NEXT 실시간 데이터 생성기
PostgreSQL 8개 테이블에 지속적으로 INSERT/UPDATE/DELETE를 발생시켜
CDC 트리거 → pg_notify → Redis Streams 파이프라인을 지속 구동
"""
import random
import time
import logging
import signal
import threading
from datetime import datetime, date

import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DATAGEN] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ckd.datagen")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "database": "ckd_next", "user": "postgres", "password": "1234",
}

_stop = threading.Event()

STATUSES_SO  = ["OPEN","IN_PROCESS","COMPLETED","CANCELLED"]
STATUSES_DEV = ["OPEN","IN_INVESTIGATION","CLOSED","CANCELLED"]
SEVERITIES   = ["MINOR","MINOR","MINOR","MAJOR","MAJOR","CRITICAL"]
CAPA_STAT    = ["OPEN","IN_PROGRESS","COMPLETED","VERIFIED"]
PROD_STAT    = ["CRTD","REL","PCNF","TECO"]
AR_STAT      = ["OPEN","PARTIAL","CLEARED"]


def get_conn():
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    return conn


def gen_sales_order(cur):
    cid = random.randint(1, 20)
    total = round(random.uniform(1_000_000, 500_000_000), 2)
    order_no = f"SO-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100,999)}"
    cur.execute("""
        INSERT INTO sales_order (order_no, customer_id, order_date, overall_status, total_net_amount)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (order_no, cid, date.today(), "OPEN", total))
    log.info(f"수주 INSERT {order_no} ₩{total:,.0f}")


def update_sales_order(cur):
    cur.execute("SELECT order_id FROM sales_order ORDER BY RANDOM() LIMIT 1")
    r = cur.fetchone()
    if not r: return
    st = random.choice(STATUSES_SO)
    cur.execute("UPDATE sales_order SET overall_status=%s WHERE order_id=%s", (st, r["order_id"]))
    log.info(f"수주 UPDATE order_id={r['order_id']} → {st}")


def gen_deviation(cur):
    cur.execute("SELECT material_id FROM material_master ORDER BY RANDOM() LIMIT 1")
    r = cur.fetchone()
    if not r: return
    sev = random.choice(SEVERITIES)
    dev_id = f"DEV-{datetime.now().strftime('%y%m%d%H%M%S')}"
    cur.execute("""
        INSERT INTO deviation_report (deviation_id, material_id, severity, status, detected_date)
        VALUES (%s, %s, %s, 'OPEN', %s)
        ON CONFLICT DO NOTHING
    """, (dev_id, r["material_id"], sev, date.today()))
    log.info(f"일탈 INSERT {dev_id} [{sev}]")


def update_deviation(cur):
    cur.execute("SELECT deviation_id FROM deviation_report WHERE status='OPEN' ORDER BY RANDOM() LIMIT 1")
    r = cur.fetchone()
    if not r: return
    st = random.choice(STATUSES_DEV)
    cur.execute("UPDATE deviation_report SET status=%s WHERE deviation_id=%s", (st, r["deviation_id"]))
    log.info(f"일탈 UPDATE {r['deviation_id']} → {st}")


def gen_capa(cur):
    cur.execute("""
        SELECT capa_id FROM deviation_report
        WHERE capa_id IS NOT NULL ORDER BY RANDOM() LIMIT 1
    """)
    r = cur.fetchone()
    if not r: return
    capa_id = r["capa_id"]
    act_id = f"ACT-{datetime.now().strftime('%y%m%d%H%M%S')}"
    act_types = ["INVESTIGATION","CORRECTIVE","PREVENTIVE","TRAINING","SOP_UPDATE"]
    cur.execute("""
        INSERT INTO capa_action (action_id, capa_id, action_type, status)
        VALUES (%s, %s, %s, 'OPEN')
        ON CONFLICT DO NOTHING
    """, (act_id, capa_id, random.choice(act_types)))
    log.info(f"CAPA INSERT {act_id}")


def update_capa(cur):
    cur.execute("SELECT action_id FROM capa_action WHERE status IN ('OPEN','IN_PROGRESS') ORDER BY RANDOM() LIMIT 1")
    r = cur.fetchone()
    if not r: return
    st = random.choice(CAPA_STAT)
    cur.execute("UPDATE capa_action SET status=%s WHERE action_id=%s", (st, r["action_id"]))
    log.info(f"CAPA UPDATE {r['action_id']} → {st}")


def update_production(cur):
    cur.execute("SELECT prod_order_id FROM production_order WHERE status IN ('CRTD','REL') ORDER BY RANDOM() LIMIT 1")
    r = cur.fetchone()
    if not r: return
    st = random.choice(PROD_STAT)
    cur.execute("UPDATE production_order SET status=%s WHERE prod_order_id=%s", (st, r["prod_order_id"]))
    log.info(f"생산 UPDATE {r['prod_order_id']} → {st}")


def gen_ar(cur):
    cur.execute("SELECT ar_id, open_amount FROM accounts_receivable ORDER BY RANDOM() LIMIT 1")
    r = cur.fetchone()
    if not r: return
    new_amt = round(float(r["open_amount"]) * random.uniform(0.8, 1.3), 2)
    cur.execute("UPDATE accounts_receivable SET open_amount=%s, ar_status='OPEN', updated_at=NOW() WHERE ar_id=%s",
                (new_amt, r["ar_id"]))
    log.info(f"AR UPDATE {r['ar_id']} open_amount=₩{new_amt:,.0f}")


def update_ar(cur):
    cur.execute("SELECT ar_id, open_amount FROM accounts_receivable WHERE ar_status='OPEN' ORDER BY RANDOM() LIMIT 1")
    r = cur.fetchone()
    if not r: return
    cleared = round(float(r["open_amount"]) * random.uniform(0.2, 1.0), 2)
    st = "CLEARED" if cleared >= float(r["open_amount"]) else "PARTIAL"
    cur.execute("""
        UPDATE accounts_receivable
        SET cleared_amount=%s, ar_status=%s
        WHERE ar_id=%s
    """, (cleared, st, r["ar_id"]))
    log.info(f"AR UPDATE {r['ar_id']} → {st}")


def gen_gl(cur):
    cur.execute("SELECT posting_id, debit_amount FROM gl_posting ORDER BY RANDOM() LIMIT 1")
    r = cur.fetchone()
    if not r: return
    new_amt = round(float(r["debit_amount"] or 0) * random.uniform(0.9, 1.1) + random.uniform(0, 1_000_000), 2)
    cur.execute("UPDATE gl_posting SET debit_amount=%s, updated_at=NOW() WHERE posting_id=%s",
                (new_amt, r["posting_id"]))
    log.info(f"GL UPDATE posting_id={r['posting_id']} ₩{new_amt:,.0f}")


ACTIONS = [
    gen_sales_order, update_sales_order, update_sales_order,
    gen_deviation, update_deviation,
    update_capa, gen_capa,
    update_production,
    gen_ar, update_ar,
    gen_gl,
]


def run_datagen(interval_sec: float = 3.0):
    """interval_sec마다 랜덤 DB 작업 발생"""
    log.info(f"실시간 데이터 생성기 시작 (간격: {interval_sec}초)")
    while not _stop.is_set():
        try:
            conn = get_conn()
            cur  = conn.cursor()
            action = random.choice(ACTIONS)
            action(cur)
            cur.close()
            conn.close()
        except Exception as e:
            log.warning(f"데이터 생성 오류: {e}")
        _stop.wait(interval_sec)
    log.info("데이터 생성기 종료")


def main(interval_sec: float = 3.0):
    def _shutdown(*_):
        log.info("종료 신호")
        _stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    run_datagen(interval_sec)


if __name__ == "__main__":
    import sys
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    main(interval)
