import psycopg2, time, sys
from redis.cluster import RedisCluster, ClusterNode

sys.stdout.reconfigure(encoding='utf-8')

REMAP = {
    ("172.20.0.11", 6379): ("localhost", 6379),
    ("172.20.0.12", 6379): ("localhost", 6380),
    ("172.20.0.13", 6379): ("localhost", 6381),
}

conn = psycopg2.connect(host="127.0.0.1", port=5432, database="ckd_next", user="postgres", password="1234")
conn.autocommit = True
cur = conn.cursor()
cur.execute("UPDATE sales_order SET overall_status='C' WHERE order_id=1")
print("DB UPDATE OK - CDC trigger fired")
conn.close()

print("Waiting 5s for Kafka pipeline...")
time.sleep(5)

rc = RedisCluster(
    startup_nodes=[ClusterNode("localhost", 6379)],
    decode_responses=True,
    skip_full_coverage_check=True,
    address_remap=lambda a: REMAP.get(a, a),
)
events = rc.xrevrange("ckd:events:stream", count=5)
print(f"Redis Stream events: {len(events)}")
for eid, fields in events:
    print("  ->", {k: v for k, v in fields.items() if k != "data"})

kpi = rc.get("ckd:kpi:cache")
print("KPI cache:", "HIT" if kpi else "MISS (invalidated = OK)")
rc.close()
