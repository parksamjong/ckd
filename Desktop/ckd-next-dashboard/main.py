"""
CKD-NEXT 종합 운영 대시보드
FastAPI + WebSocket 실시간 모니터링
+ RDF/OWL 온톨로지 + NetworkX 지식 그래프 + Neo4j Cypher + Vector RAG + GraphRAG
+ Kafka CDC + Redis 캐시/PubSub
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

# Redis 캐시 레이어 (Redis 없으면 graceful fallback)
try:
    import redis_cache as _rc
    _REDIS_ENABLED = True
except ImportError:
    _REDIS_ENABLED = False

# KG 모듈 (지연 임포트 — 서버 시작 속도 유지)
_kg_modules_loaded = False
_ontology_mod = None
_builder_mod = None
_vectorrag_mod = None
_neo4j_mod = None
_graphrag_mod = None


def _load_kg_modules():
    global _kg_modules_loaded, _ontology_mod, _builder_mod, _vectorrag_mod, _neo4j_mod, _graphrag_mod
    if not _kg_modules_loaded:
        import kg_ontology as _o
        import kg_builder as _b
        import kg_vectorrag as _v
        import kg_neo4j as _n
        import kg_graphrag as _g
        _ontology_mod = _o
        _builder_mod = _b
        _vectorrag_mod = _v
        _neo4j_mod = _n
        _graphrag_mod = _g
        _kg_modules_loaded = True

@asynccontextmanager
async def lifespan(application: FastAPI):
    # ── 시작 ──────────────────────────────────────────────────
    if _REDIS_ENABLED:
        await _rc.init_redis()
        # Redis Pub/Sub → WebSocket 브로드캐스트 백그라운드 태스크
        asyncio.ensure_future(_redis_pubsub_broadcaster())
    yield
    # ── 종료 ──────────────────────────────────────────────────
    if _REDIS_ENABLED:
        await _rc.close_redis()


app = FastAPI(title="CKD-NEXT 대시보드", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "ckd_next",
    "user": "postgres",
    "password": "1234",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


def fetch_kpis():
    """전체 KPI 데이터 수집"""
    conn = get_conn()
    cur = conn.cursor()

    data = {}

    # ── 매출 KPI ──
    cur.execute("""
        SELECT
          COUNT(*) AS total_orders,
          SUM(CASE WHEN overall_status NOT IN ('C','X') THEN 1 ELSE 0 END) AS open_orders,
          SUM(CASE WHEN overall_status = 'C' THEN 1 ELSE 0 END) AS completed_orders,
          COALESCE(SUM(total_net_amount), 0) AS total_net_value
        FROM sales_order
    """)
    data["sales"] = dict(cur.fetchone())

    cur.execute("""
        SELECT billing_date::text AS date,
               SUM(total_value) AS daily_revenue
        FROM billing_document
        GROUP BY billing_date
        ORDER BY billing_date
    """)
    data["billing_trend"] = [dict(r) for r in cur.fetchall()]

    # ── 재무 KPI ──
    cur.execute("""
        SELECT
          COALESCE(SUM(open_amount), 0) AS ar_open,
          COALESCE(SUM(cleared_amount), 0) AS ar_cleared,
          COUNT(*) AS ar_count,
          SUM(CASE WHEN ar_status = 'OPEN' THEN 1 ELSE 0 END) AS ar_open_count
        FROM accounts_receivable
    """)
    data["finance_ar"] = dict(cur.fetchone())

    cur.execute("""
        SELECT
          COALESCE(SUM(gross_amount), 0) AS ap_total,
          SUM(CASE WHEN clearing_status = 'O' THEN gross_amount ELSE 0 END) AS ap_open,
          COUNT(*) AS ap_count
        FROM accounts_payable_document
    """)
    data["finance_ap"] = dict(cur.fetchone())

    cur.execute("""
        SELECT document_type,
               SUM(COALESCE(debit_amount,0)) AS total_debit
        FROM gl_posting
        WHERE document_type IN ('RV','KR','SA','AF','WA')
        GROUP BY document_type
        ORDER BY total_debit DESC
    """)
    data["gl_by_type"] = [dict(r) for r in cur.fetchall()]

    # ── 생산 KPI ──
    cur.execute("""
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN status IN ('REL','PCNF') THEN 1 ELSE 0 END) AS in_progress,
          SUM(CASE WHEN status = 'TECO' THEN 1 ELSE 0 END) AS completed,
          SUM(CASE WHEN status = 'CRTD' THEN 1 ELSE 0 END) AS created
        FROM production_order
    """)
    data["production"] = dict(cur.fetchone())

    cur.execute("""
        SELECT order_type,
               COUNT(*) AS cnt,
               COALESCE(SUM(order_qty), 0) AS planned,
               COALESCE(SUM(confirmed_qty), 0) AS confirmed
        FROM production_order
        GROUP BY order_type
    """)
    data["production_by_type"] = [dict(r) for r in cur.fetchall()]

    # ── 품질 KPI ──
    cur.execute("""
        SELECT
          COUNT(*) AS total_deviations,
          SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical,
          SUM(CASE WHEN severity = 'MAJOR' THEN 1 ELSE 0 END) AS major,
          SUM(CASE WHEN severity = 'MINOR' THEN 1 ELSE 0 END) AS minor,
          SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) AS open_dev,
          SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) AS closed_dev
        FROM deviation_report
    """)
    data["quality_deviation"] = dict(cur.fetchone())

    cur.execute("""
        SELECT
          COUNT(*) AS total_oos,
          SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) AS open_oos,
          SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) AS closed_oos,
          SUM(CASE WHEN assignable_cause IS NULL THEN 1 ELSE 0 END) AS critical_oos
        FROM out_of_specification
    """)
    data["quality_oos"] = dict(cur.fetchone())

    cur.execute("""
        SELECT
          COUNT(*) AS total_complaints,
          SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) AS open_complaints,
          SUM(CASE WHEN recall_required = true THEN 1 ELSE 0 END) AS critical_complaints
        FROM product_complaint
    """)
    data["quality_complaint"] = dict(cur.fetchone())

    cur.execute("""
        SELECT
          COUNT(*) AS total_capa,
          SUM(CASE WHEN status = 'OPEN' OR status = 'IN_PROGRESS' THEN 1 ELSE 0 END) AS open_capa,
          SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_capa,
          SUM(CASE WHEN target_date < CURRENT_DATE AND status != 'COMPLETED' THEN 1 ELSE 0 END) AS overdue_capa
        FROM capa_action
    """)
    data["quality_capa"] = dict(cur.fetchone())

    # ── HR KPI ──
    cur.execute("""
        SELECT
          COUNT(*) AS total_emp
        FROM employee
    """)
    data["hr"] = dict(cur.fetchone())

    cur.execute("""
        SELECT
          COUNT(*) AS total_leaves,
          SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_leaves
        FROM leave_request
    """)
    data["hr_leave"] = dict(cur.fetchone())

    # ── 최근 Deviation (실시간 모니터링용) ──
    cur.execute("""
        SELECT deviation_id, description AS title, severity, status, detected_date::text
        FROM deviation_report
        ORDER BY detected_date DESC
        LIMIT 8
    """)
    data["recent_deviations"] = [dict(r) for r in cur.fetchall()]

    # ── 최근 GL 전표 ──
    cur.execute("""
        SELECT DISTINCT document_number, document_type, posting_date::text,
               header_text,
               SUM(COALESCE(debit_amount,0)) AS total_debit
        FROM gl_posting
        GROUP BY document_number, document_type, posting_date, header_text
        ORDER BY posting_date DESC
        LIMIT 10
    """)
    data["recent_journals"] = [dict(r) for r in cur.fetchall()]

    # ── Open PO 현황 ──
    cur.execute("""
        SELECT po_id, vendor_id, po_date::text, total_value AS total_amount,
               po_status AS status, currency
        FROM purchase_order
        WHERE po_status NOT IN ('COMPLETED', 'CANCELLED', 'CLOSED')
        ORDER BY po_date DESC
        LIMIT 6
    """)
    data["open_pos"] = [dict(r) for r in cur.fetchall()]

    # ── QM 검사 현황 ──
    cur.execute("""
        SELECT lot_id, material_id, plant_id, usage_decision AS lot_status,
               inspection_start::text AS planned_start
        FROM qm_inspection_lot
        ORDER BY inspection_start DESC NULLS LAST
        LIMIT 6
    """)
    data["inspection_lots"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    data["timestamp"] = datetime.now().isoformat()
    return data


# WebSocket 연결 관리
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data, default=str, ensure_ascii=False)
        for ws in self.active[:]:
            try:
                await ws.send_text(msg)
            except Exception:
                self.active.remove(ws)


manager = ConnectionManager()


async def _redis_pubsub_broadcaster():
    """Redis Pub/Sub에서 CDC 이벤트를 수신해 WebSocket으로 브로드캐스트."""
    async def _on_msg(data: str):
        try:
            payload = json.loads(data)
            await manager.broadcast({
                "type":    "cdc_event",
                "topic":   payload.get("topic", ""),
                "op":      payload.get("op", ""),
                "summary": payload.get("summary", ""),
                "ts":      payload.get("ts", 0),
            })
        except Exception:
            pass
    try:
        await _rc.subscribe_realtime(_on_msg)
    except Exception as e:
        import logging
        logging.getLogger("ckd.main").warning(f"Redis PubSub 브릿지 종료: {e}")


@app.websocket("/ws/monitor")
async def websocket_monitor(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Redis 캐시 우선 조회, 없으면 DB 조회 후 캐시 저장
            if _REDIS_ENABLED:
                cached = await _rc.get_kpi_cache()
                if cached:
                    kpis = cached
                else:
                    kpis = fetch_kpis()
                    await _rc.set_kpi_cache(kpis)
            else:
                kpis = fetch_kpis()
            await ws.send_text(json.dumps(kpis, default=str, ensure_ascii=False))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.get("/api/kpis")
async def api_kpis():
    if _REDIS_ENABLED:
        cached = await _rc.get_kpi_cache()
        if cached:
            return cached
    data = fetch_kpis()
    if _REDIS_ENABLED:
        await _rc.set_kpi_cache(data)
    return data


@app.get("/")
def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


# ══════════════════════════════════════════════════════════════
# Redis / Kafka 상태 API
# ══════════════════════════════════════════════════════════════

@app.get("/api/infra/status")
async def api_infra_status():
    redis_info = await _rc.redis_info() if _REDIS_ENABLED else {"available": False}
    return {
        "redis": redis_info,
        "kafka": {
            "brokers": ["ckd-kafka:9095"],
            "replication_factor": 1,
            "auto_create_topics": True,
            "status": "ckd-kafka running (port 9095)",
        },
        "kafka_topics": [
            "ckd.sales.orders", "ckd.quality.deviations", "ckd.quality.capa",
            "ckd.production.orders", "ckd.production.purchases",
            "ckd.finance.ar", "ckd.quality.lots", "ckd.finance.gl",
        ],
        "cdc_tables": [
            "sales_order", "deviation_report", "capa_action",
            "production_order", "purchase_order",
            "accounts_receivable", "qm_inspection_lot", "gl_posting",
        ],
        "devops": {
            "ansible":   {"status": "ACTIVE", "desc": "CKD-NEXT 서버 자동 배포 플레이북 12개"},
            "helm":      {"status": "ACTIVE", "desc": "ckd-next Helm Chart v2.0.0, K8s 1.29"},
            "istio":     {"status": "ACTIVE", "desc": "서비스 메시 v1.20, mTLS 전체 적용"},
            "terraform": {"status": "ACTIVE", "desc": "AWS EKS + RDS + ElastiCache IaC"},
            "soar":      {"status": "ACTIVE", "desc": "Critical 일탈 자동 JIRA 티켓 생성"},
        },
    }


@app.get("/api/infra/events")
async def api_infra_events(count: int = Query(50, le=500)):
    if not _REDIS_ENABLED:
        return []
    events = await _rc.get_recent_events(count)
    return events


@app.get("/api/infra/alerts")
async def api_infra_alerts(limit: int = Query(20, le=100)):
    if not _REDIS_ENABLED:
        return {"alerts": [], "redis_available": False}
    alerts = await _rc.get_critical_alerts(limit)
    return {"alerts": alerts, "count": len(alerts)}


# ══════════════════════════════════════════════════════════════
# KG API 엔드포인트
# ══════════════════════════════════════════════════════════════

@app.get("/api/ontology")
def api_ontology():
    _load_kg_modules()
    return _ontology_mod.get_ontology_summary()


@app.get("/api/ontology/topology")
def api_ontology_topology():
    """OWL ObjectProperty 기반 NetworkX 토폴로지 분석 + vis.js 그래프."""
    import networkx as nx
    _load_kg_modules()
    mod = _ontology_mod

    # ObjectProperty로 방향 그래프 구성
    G = nx.DiGraph()
    COLORS = {
        "Material": "#58a6ff", "RawMaterial": "#79c0ff", "PackagingMaterial": "#a5d6ff",
        "FinishedGood": "#cae8ff", "Customer": "#3fb950", "SalesOrder": "#56d364",
        "SalesOrderItem": "#7ee787", "BillingDocument": "#d29922", "Invoice": "#e3b341",
        "Vendor": "#ffa657", "PurchaseOrder": "#f0883e", "GoodsReceipt": "#db6d28",
        "ProductionOrder": "#bc8cff", "Batch": "#d2a8ff", "BOM": "#e8d5ff",
        "DeviationReport": "#f85149", "OOS": "#ff7b72", "CapaAction": "#ffa198",
        "Employee": "#39c5cf", "Department": "#21c4cb",
    }
    node_groups = {}
    for cls, label in mod.OWL_CLASSES:
        node_groups[cls] = label

    # 노드 추가 (모든 클래스)
    for cls, label in mod.OWL_CLASSES:
        G.add_node(cls, label=label)

    # 서브클래스 엣지
    subclass_map = {"RawMaterial": "Material", "PackagingMaterial": "Material", "FinishedGood": "Material"}
    for child, parent in subclass_map.items():
        G.add_edge(child, parent, label="subClassOf", weight=1)

    # ObjectProperty 엣지
    for prop, dom, rng, label in mod.OWL_OBJ_PROPS:
        G.add_edge(dom, rng, label=prop, weight=2)

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    # 중심성 계산
    try:
        pagerank = nx.pagerank(G, alpha=0.85)
        betweenness = nx.betweenness_centrality(G, normalized=True)
        in_deg  = dict(G.in_degree())
        out_deg = dict(G.out_degree())
    except Exception:
        pagerank = {}; betweenness = {}
        in_deg = dict(G.in_degree()); out_deg = dict(G.out_degree())

    # vis.js 노드/엣지
    vis_nodes = []
    for cls, label in mod.OWL_CLASSES:
        pr   = pagerank.get(cls, 0)
        bet  = betweenness.get(cls, 0)
        sz   = int(12 + pr * 200)
        sz   = max(10, min(sz, 40))
        col  = COLORS.get(cls, "#8b949e")
        vis_nodes.append({
            "id": cls, "label": cls,
            "title": (f"<b>{cls}</b><br>{label}<br>"
                      f"PageRank: {pr:.4f} | Betw: {bet:.4f}<br>"
                      f"In: {in_deg.get(cls,0)} | Out: {out_deg.get(cls,0)}"),
            "size": sz,
            "color": {"background": col, "border": "#fff3", "highlight": {"background": col, "border": "#fff"}},
            "font": {"color": "#fff", "size": 11, "bold": False, "strokeWidth": 2, "strokeColor": "#00000099"},
            "shape": "ellipse",
        })

    vis_edges = []
    for i, (src, dst, data) in enumerate(G.edges(data=True)):
        prop_label = data.get("label", "")
        weight = data.get("weight", 1)
        vis_edges.append({
            "id": i, "from": src, "to": dst,
            "label": prop_label,
            "width": 1 + weight * 0.5,
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
            "color": {"color": "#ffffff55" if weight > 1 else "#ffffff22", "highlight": "#fff"},
            "font": {"color": "#aaa", "size": 9, "align": "middle", "strokeWidth": 1, "strokeColor": "#0d1117"},
            "smooth": {"type": "curvedCW", "roundness": 0.15},
            "dashes": weight == 1,
        })

    # 토폴로지 전역 메트릭
    UG = G.to_undirected()
    components = list(nx.connected_components(UG))
    top5 = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "nodes": vis_nodes,
        "edges": vis_edges,
        "topology": {
            "node_count": n_nodes,
            "edge_count": n_edges,
            "density": round(nx.density(G), 4),
            "components": len(components),
            "largest_component": max(len(c) for c in components) if components else 0,
            "avg_in_degree": round(sum(in_deg.values()) / n_nodes if n_nodes else 0, 2),
        },
        "top_nodes": [{"cls": c, "label": node_groups.get(c,""), "pagerank": round(v,4)} for c,v in top5],
    }


@app.get("/api/kg/graph")
def api_kg_graph():
    _load_kg_modules()
    G, vis_data, metrics = _builder_mod.get_graph_cache()
    return {"vis": vis_data, "metrics": metrics}


@app.get("/api/kg/metrics")
def api_kg_metrics():
    _load_kg_modules()
    _, _, metrics = _builder_mod.get_graph_cache()
    return metrics


@app.get("/api/vectorrag/stats")
def api_vectorrag_stats():
    _load_kg_modules()
    idx = _vectorrag_mod.get_vector_index()
    return idx.get_stats()


@app.get("/api/vectorrag/search")
def api_vectorrag_search(q: str = Query("일탈"), top_k: int = Query(8)):
    _load_kg_modules()
    return {"query": q, "results": _vectorrag_mod.vector_search(q, top_k=top_k)}


@app.get("/api/neo4j/preview")
def api_neo4j_preview():
    _load_kg_modules()
    return _neo4j_mod.get_neo4j_preview()


@app.get("/api/neo4j/cypher", response_class=PlainTextResponse)
def api_neo4j_cypher():
    _load_kg_modules()
    return _neo4j_mod.generate_cypher_script()


@app.get("/api/graphrag/query")
def api_graphrag_query(q: str = Query("Critical 일탈 CAPA 현황"), top_k: int = Query(8)):
    _load_kg_modules()
    return _graphrag_mod.graphrag_query(q, top_k=top_k)


@app.get("/api/overview-graph")
def api_overview_graph():
    import psycopg2, psycopg2.extras
    DB = {"host":"127.0.0.1","port":5432,"database":"ckd_next","user":"postgres","password":"1234"}
    conn = psycopg2.connect(**DB, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    nodes, edges = [], []
    node_ids = set()

    def add_node(nid, label, group, title=""):
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({"id": nid, "label": label, "group": group, "title": title or label})

    # 자재 (상위 8개) — material_no를 키로 사용 (prod/dev 테이블과 공통)
    cur.execute("""
        SELECT mm.material_id, mm.material_no, COALESCE(md.material_desc, mm.material_no) AS desc
        FROM material_master mm
        LEFT JOIN material_description md ON md.material_id=mm.material_id AND md.language_code='KO'
        ORDER BY mm.material_id LIMIT 8
    """)
    mat_rows = cur.fetchall()
    mat_by_no  = {}   # material_no  → nid
    mat_by_iid = {}   # material_id(int) → nid
    for r in mat_rows:
        nid = f"MAT:{r['material_id']}"
        add_node(nid, r['material_no'], "Material", r['desc'])
        mat_by_no[r['material_no']] = nid
        mat_by_iid[r['material_id']] = nid
    mnos = tuple(mat_by_no.keys())
    miids = tuple(mat_by_iid.keys())

    # 수주 → 자재 연결 (sales_order_item.material_id = int)
    if miids:
        ph = ",".join(["%s"]*len(miids))
        cur.execute(f"""
            SELECT DISTINCT so.order_id, so.order_no, so.overall_status, soi.material_id
            FROM sales_order so JOIN sales_order_item soi ON soi.order_id=so.order_id
            WHERE soi.material_id IN ({ph}) LIMIT 10
        """, miids)
        for r in cur.fetchall():
            nid = f"SO:{r['order_id']}"
            add_node(nid, r['order_no'] or f"SO:{r['order_id']}", "SalesOrder", f"상태:{r['overall_status']}")
            mid_nid = mat_by_iid.get(r['material_id'])
            if mid_nid:
                edges.append({"from": mid_nid, "to": nid, "label": "contains"})

    # 생산오더 → 자재 연결 (production_order.material_id = material_no 형식)
    if mnos:
        ph2 = ",".join(["%s"]*len(mnos))
        cur.execute(f"""
            SELECT prod_order_id, material_id, status
            FROM production_order WHERE material_id IN ({ph2}) LIMIT 10
        """, mnos)
        po_ids = []   # (prod_order_id, nid)
        for r in cur.fetchall():
            nid = f"PO:{r['prod_order_id']}"
            add_node(nid, r['prod_order_id'], "ProductionOrder", f"상태:{r['status']}")
            mid_nid = mat_by_no.get(r['material_id'])
            if mid_nid:
                edges.append({"from": mid_nid, "to": nid, "label": "produces"})
            po_ids.append((r['prod_order_id'], nid))

    # 일탈 → 자재 연결 (deviation_report.material_id = material_no 형식)
    if mnos:
        cur.execute(f"""
            SELECT deviation_id, material_id, severity, status, capa_id
            FROM deviation_report WHERE material_id IN ({ph2}) LIMIT 10
        """, mnos)
        dev_rows = cur.fetchall()
        dev_by_capaid = {}   # capa_id → dev nid
        for r in dev_rows:
            nid = f"DEV:{r['deviation_id']}"
            add_node(nid, r['deviation_id'], "DeviationReport", f"심각도:{r['severity']} 상태:{r['status']}")
            mid_nid = mat_by_no.get(r['material_id'])
            if mid_nid:
                edges.append({"from": mid_nid, "to": nid, "label": "hasDeviation"})
            if r['capa_id']:
                dev_by_capaid[r['capa_id']] = nid

        # CAPA → 일탈 (capa_action.capa_id = deviation_report.capa_id)
        if dev_by_capaid:
            cids = tuple(dev_by_capaid.keys())
            ph3 = ",".join(["%s"]*len(cids))
            cur.execute(f"""
                SELECT action_id, capa_id, action_type, status
                FROM capa_action WHERE capa_id IN ({ph3}) LIMIT 10
            """, cids)
            for r in cur.fetchall():
                nid = f"CAPA:{r['action_id']}"
                add_node(nid, f"CAPA {r['action_id']}", "CapaAction", f"유형:{r['action_type']} 상태:{r['status']}")
                dev_nid = dev_by_capaid.get(r['capa_id'])
                if dev_nid:
                    edges.append({"from": dev_nid, "to": nid, "label": "hasCapa"})

    conn.close()

    GROUP_COLORS = {
        "Material":        "#58a6ff",
        "SalesOrder":      "#3fb950",
        "ProductionOrder": "#d29922",
        "DeviationReport": "#f85149",
        "CapaAction":      "#bc8cff",
    }
    for n in nodes:
        col = GROUP_COLORS.get(n["group"], "#8b949e")
        n["color"] = {"background": col, "border": "#ffffff44",
                      "highlight": {"background": col, "border": "#fff"}}
        n["font"] = {"color": "#fff", "size": 13, "bold": True,
                     "strokeWidth": 2, "strokeColor": "#00000099"}
        n["shape"] = "ellipse"
        n["borderWidth"] = 2

    for i, e in enumerate(edges):
        e["id"] = i
        e["arrows"] = {"to": {"enabled": True, "scaleFactor": 0.7}}
        e["color"] = {"color": "#ffffff44", "highlight": "#fff"}
        e["font"] = {"color": "#ccc", "size": 10, "align": "middle",
                     "strokeWidth": 2, "strokeColor": "#0d1117"}
        e["smooth"] = {"type": "curvedCW", "roundness": 0.2}
        e["width"] = 1.5

    return {"nodes": nodes, "edges": edges,
            "legend": [{"group": k, "color": v} for k, v in GROUP_COLORS.items()]}


@app.get("/api/graph")
def api_tab_graph(tab: str = Query("sales")):
    import psycopg2, psycopg2.extras
    DB = {"host":"127.0.0.1","port":5432,"database":"ckd_next","user":"postgres","password":"1234"}
    conn = psycopg2.connect(**DB, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    nodes, edges = [], []
    node_set = set()
    COLORS = {
        "Customer":"#58a6ff","SalesOrder":"#3fb950","BillingDocument":"#d29922",
        "Material":"#58a6ff","DeviationReport":"#f85149","CapaAction":"#bc8cff","InspectionLot":"#ffa657",
        "ProductionOrder":"#d29922","Vendor":"#3fb950","PurchaseOrder":"#ffa657",
        "System":"#ff9500","Alert":"#f85149","Action":"#bc8cff","Finance":"#58a6ff","Production":"#3fb950",
    }
    def add_node(nid, label, group, title=""):
        if nid not in node_set:
            node_set.add(nid)
            col = COLORS.get(group, "#8b949e")
            nodes.append({"id":nid,"label":label,"group":group,"title":title or label,
                "color":{"background":col,"border":"#ffffff44","highlight":{"background":col,"border":"#fff"}},
                "font":{"color":"#fff","size":13,"bold":True,"strokeWidth":2,"strokeColor":"#00000099"},
                "shape":"ellipse","borderWidth":2})
    def add_edge(from_id, to_id, label=""):
        edges.append({"id":len(edges),"from":from_id,"to":to_id,"label":label,
            "arrows":{"to":{"enabled":True,"scaleFactor":0.7}},
            "color":{"color":"#ffffff44","highlight":"#fff"},
            "font":{"color":"#ccc","size":10,"align":"middle","strokeWidth":2,"strokeColor":"#0d1117"},
            "smooth":{"type":"curvedCW","roundness":0.2},"width":1.5})

    if tab == "sales":
        cur.execute("SELECT customer_id, customer_name FROM customer_master ORDER BY customer_id LIMIT 8")
        custs = cur.fetchall()
        for c in custs:
            lbl = (c['customer_name'] or '')[:12] or f"C{c['customer_id']}"
            add_node(f"C:{c['customer_id']}", lbl, "Customer")
        if custs:
            cids = tuple(c['customer_id'] for c in custs)
            ph = ",".join(["%s"]*len(cids))
            cur.execute(f"SELECT order_id, order_no, customer_id, overall_status FROM sales_order WHERE customer_id IN ({ph}) LIMIT 12", cids)
            for r in cur.fetchall():
                nid = f"SO:{r['order_id']}"
                add_node(nid, r['order_no'], "SalesOrder", f"상태:{r['overall_status']}")
                add_edge(f"C:{r['customer_id']}", nid, "수주")
        cur.execute("SELECT billing_id, billing_type, sold_to_party FROM billing_document LIMIT 10")
        for r in cur.fetchall():
            nid = f"BL:{r['billing_id']}"
            add_node(nid, r['billing_id'], "BillingDocument", f"유형:{r['billing_type']}")
            cnid = f"C:{r['sold_to_party']}"
            if cnid in node_set:
                add_edge(cnid, nid, "청구")

    elif tab == "quality":
        cur.execute("""
            SELECT mm.material_no, COALESCE(md.material_desc, mm.material_no) AS desc
            FROM material_master mm
            LEFT JOIN material_description md ON md.material_id=mm.material_id AND md.language_code='KO'
            ORDER BY mm.material_id LIMIT 8
        """)
        mats = cur.fetchall(); mnos = [r['material_no'] for r in mats]
        for r in mats:
            add_node(f"M:{r['material_no']}", r['material_no'], "Material", r['desc'])
        if mnos:
            ph = ",".join(["%s"]*len(mnos))
            cur.execute(f"SELECT deviation_id, material_id, severity, status, capa_id FROM deviation_report WHERE material_id IN ({ph}) LIMIT 12", tuple(mnos))
            devs = cur.fetchall(); capa_map = {}
            for r in devs:
                nid = f"D:{r['deviation_id']}"
                add_node(nid, r['deviation_id'], "DeviationReport", f"심각:{r['severity']} {r['status']}")
                add_edge(f"M:{r['material_id']}", nid, "일탈")
                if r['capa_id']: capa_map[r['capa_id']] = nid
            if capa_map:
                ph2 = ",".join(["%s"]*len(capa_map))
                cur.execute(f"SELECT action_id, capa_id, action_type, status FROM capa_action WHERE capa_id IN ({ph2}) LIMIT 10", tuple(capa_map))
                for r in cur.fetchall():
                    nid = f"CA:{r['action_id']}"
                    add_node(nid, f"CAPA {r['action_id']}", "CapaAction", f"{r['action_type']} {r['status']}")
                    dev = capa_map.get(r['capa_id'])
                    if dev: add_edge(dev, nid, "조치")
        cur.execute("SELECT lot_id, material_id, lot_origin FROM qm_inspection_lot LIMIT 8")
        for r in cur.fetchall():
            nid = f"L:{r['lot_id']}"
            add_node(nid, r['lot_id'], "InspectionLot", f"기원:{r['lot_origin']}")
            mnid = f"M:{r['material_id']}"
            if mnid in node_set: add_edge(mnid, nid, "검사")

    elif tab == "production":
        cur.execute("""
            SELECT mm.material_no, COALESCE(md.material_desc, mm.material_no) AS desc
            FROM material_master mm
            LEFT JOIN material_description md ON md.material_id=mm.material_id AND md.language_code='KO'
            ORDER BY mm.material_id LIMIT 8
        """)
        mats = cur.fetchall(); mnos = [r['material_no'] for r in mats]
        for r in mats:
            add_node(f"M:{r['material_no']}", r['material_no'], "Material", r['desc'])
        if mnos:
            ph = ",".join(["%s"]*len(mnos))
            cur.execute(f"SELECT prod_order_id, material_id, status FROM production_order WHERE material_id IN ({ph}) LIMIT 10", tuple(mnos))
            for r in cur.fetchall():
                nid = f"PO:{r['prod_order_id']}"
                add_node(nid, r['prod_order_id'], "ProductionOrder", f"상태:{r['status']}")
                add_edge(f"M:{r['material_id']}", nid, "생산")
        cur.execute("SELECT vendor_id, vendor_name FROM vendor_master ORDER BY vendor_id LIMIT 6")
        vends = cur.fetchall(); vids = [r['vendor_id'] for r in vends]
        for r in vends:
            add_node(f"V:{r['vendor_id']}", (r['vendor_name'] or r['vendor_id'])[:14], "Vendor")
        if vids:
            ph = ",".join(["%s"]*len(vids))
            cur.execute(f"""
                SELECT po.po_id, po.vendor_id, poi.material_id
                FROM purchase_order po JOIN purchase_order_item poi ON poi.po_id=po.po_id
                WHERE po.vendor_id IN ({ph}) LIMIT 12
            """, tuple(vids))
            for r in cur.fetchall():
                nid = f"PU:{r['po_id']}"
                add_node(nid, r['po_id'], "PurchaseOrder")
                add_edge(f"V:{r['vendor_id']}", nid, "공급")
                mnid = f"M:{r['material_id']}"
                if mnid in node_set: add_edge(nid, mnid, "원자재")

    elif tab == "monitor":
        add_node("SYS", "CKD-NEXT", "System", "운영 모니터링 허브")
        cur.execute("SELECT deviation_id, severity, status FROM deviation_report WHERE severity='CRITICAL' AND status NOT IN ('CLOSED','CANCELLED') LIMIT 6")
        for r in cur.fetchall():
            nid = f"D:{r['deviation_id']}"
            add_node(nid, r['deviation_id'], "Alert", f"Critical [{r['status']}]")
            add_edge("SYS", nid, "Critical")
        cur.execute("SELECT action_id, capa_id, status FROM capa_action WHERE status NOT IN ('COMPLETED','CANCELLED') LIMIT 5")
        for r in cur.fetchall():
            nid = f"CA:{r['action_id']}"
            add_node(nid, f"CAPA {r['action_id']}", "Action", f"{r['status']} [{r['capa_id']}]")
            add_edge("SYS", nid, "미완료 CAPA")
        cur.execute("SELECT ar_id, customer_id, open_amount FROM accounts_receivable WHERE ar_status='OPEN' AND open_amount>0 LIMIT 5")
        for r in cur.fetchall():
            nid = f"AR:{r['ar_id']}"
            add_node(nid, f"AR {r['ar_id']}", "Finance", f"미수 ₩{float(r['open_amount']):,.0f}")
            add_edge("SYS", nid, "미수채권")
        cur.execute("SELECT prod_order_id, material_id, status FROM production_order WHERE status IN ('REL','PCNF') LIMIT 5")
        for r in cur.fetchall():
            nid = f"PROD:{r['prod_order_id']}"
            add_node(nid, r['prod_order_id'], "Production", f"생산중 [{r['status']}]")
            add_edge("SYS", nid, "진행생산")

    conn.close()
    return {"nodes": nodes, "edges": edges}


# ────────────────────────────────────────────────────────────────
# NetworkX 전체 토폴로지 분석 엔드포인트
# ────────────────────────────────────────────────────────────────
@app.get("/api/topology")
def api_topology(tab: str = Query("sales")):
    """NetworkX 기반 그래프 토폴로지 메트릭 계산."""
    import networkx as nx

    # /api/graph와 동일한 방식으로 그래프 데이터 구성
    graph_data = api_tab_graph(tab)
    nodes_raw = graph_data["nodes"]
    edges_raw = graph_data["edges"]

    if not nodes_raw:
        return {"metrics": {}, "nodes": [], "topology": {}}

    # NetworkX DiGraph 구성
    G = nx.DiGraph()
    for n in nodes_raw:
        G.add_node(n["id"], label=n.get("label",""), group=n.get("group",""))
    for e in edges_raw:
        G.add_edge(e["from"], e["to"], label=e.get("label",""))

    UG = G.to_undirected()

    # ── 중심성 지표 계산 ──
    try:
        degree_c    = nx.degree_centrality(G)
        between_c   = nx.betweenness_centrality(G, normalized=True)
        in_degree   = dict(G.in_degree())
        out_degree  = dict(G.out_degree())
    except Exception:
        degree_c    = {}
        between_c   = {}
        in_degree   = dict(G.in_degree())
        out_degree  = dict(G.out_degree())

    try:
        closeness_c = nx.closeness_centrality(UG)
    except Exception:
        closeness_c = {}

    try:
        pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
    except Exception:
        pagerank = {}

    # ── 토폴로지 전역 지표 ──
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    try:
        density = nx.density(G)
    except Exception:
        density = 0.0

    components = list(nx.weakly_connected_components(G))
    n_components = len(components)
    largest_component = max(len(c) for c in components) if components else 0

    try:
        avg_degree = sum(dict(UG.degree()).values()) / n_nodes if n_nodes else 0
    except Exception:
        avg_degree = 0.0

    # ── 노드별 메트릭 병합 ──
    enriched_nodes = []
    for n in nodes_raw:
        nid = n["id"]
        deg_c = round(degree_c.get(nid, 0), 4)
        bet_c = round(between_c.get(nid, 0), 4)
        clo_c = round(closeness_c.get(nid, 0), 4)
        pr    = round(pagerank.get(nid, 0), 4)
        ind   = in_degree.get(nid, 0)
        outd  = out_degree.get(nid, 0)

        # 중요도에 따라 크기 조절 (size 8~30)
        importance = pr if pr else deg_c
        node_size  = int(10 + importance * 120)
        node_size  = max(8, min(node_size, 30))

        enriched = dict(n)
        enriched["size"] = node_size
        enriched["title"] = (
            f"<b>{n.get('label','')}</b> [{n.get('group','')}]<br>"
            f"PageRank: {pr:.4f} | Degree: {deg_c:.4f}<br>"
            f"Betweenness: {bet_c:.4f} | Closeness: {clo_c:.4f}<br>"
            f"In-degree: {ind} | Out-degree: {outd}"
        )
        enriched["_metrics"] = {
            "degree_centrality": deg_c,
            "betweenness_centrality": bet_c,
            "closeness_centrality": clo_c,
            "pagerank": pr,
            "in_degree": ind,
            "out_degree": outd,
        }
        enriched_nodes.append(enriched)

    # ── Top-5 중심 노드 ──
    sorted_by_pr = sorted(enriched_nodes, key=lambda x: x["_metrics"]["pagerank"], reverse=True)
    top5_nodes   = [{"id": x["id"], "label": x.get("label",""), "group": x.get("group",""),
                     "pagerank": x["_metrics"]["pagerank"],
                     "betweenness": x["_metrics"]["betweenness_centrality"]}
                    for x in sorted_by_pr[:5]]

    # 직렬화 전 _metrics 제거
    for n in enriched_nodes:
        n.pop("_metrics", None)

    return {
        "nodes": enriched_nodes,
        "edges": edges_raw,
        "topology": {
            "node_count": n_nodes,
            "edge_count": n_edges,
            "density": round(density, 4),
            "components": n_components,
            "largest_component": largest_component,
            "avg_degree": round(avg_degree, 2),
        },
        "top_nodes": top5_nodes,
    }


DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CKD-NEXT 종합 운영 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #21262d;
    --border: #30363d;
    --accent: #58a6ff;
    --green: #3fb950;
    --yellow: #d29922;
    --red: #f85149;
    --orange: #e3b341;
    --text: #c9d1d9;
    --text-dim: #8b949e;
    --purple: #bc8cff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; }

  /* ── Header ── */
  .header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky; top: 0; z-index: 100;
  }
  .header-left { display: flex; align-items: center; gap: 12px; }
  .logo { width: 32px; height: 32px; background: var(--accent); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 900; color: #fff; font-size: 16px; }
  .header h1 { font-size: 16px; font-weight: 700; color: #fff; }
  .header .sub { font-size: 11px; color: var(--text-dim); }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.6;transform:scale(1.2)} }
  .status-label { font-size: 11px; color: var(--green); font-weight: 600; }
  .last-update { font-size: 11px; color: var(--text-dim); }

  /* ── Tab Navigation ── */
  .tabs { display: flex; gap: 4px; padding: 12px 24px 0; background: var(--surface); border-bottom: 1px solid var(--border); }
  .tab { padding: 8px 16px; border-radius: 6px 6px 0 0; cursor: pointer; color: var(--text-dim); font-weight: 500; border: 1px solid transparent; border-bottom: none; transition: all .2s; }
  .tab:hover { color: var(--text); background: var(--surface2); }
  .tab.active { color: var(--accent); background: var(--bg); border-color: var(--border); }

  /* ── Layout ── */
  .main { padding: 20px 24px; }
  .panel { display: none; }
  .panel.active { display: block; }

  /* ── Grid ── */
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
  .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px; }
  .grid-21 { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; margin-bottom: 16px; }
  .grid-12 { display: grid; grid-template-columns: 1fr 2fr; gap: 12px; margin-bottom: 16px; }
  @media(max-width:900px){.grid-4,.grid-3{grid-template-columns:repeat(2,1fr)}.grid-2,.grid-21,.grid-12{grid-template-columns:1fr}}

  /* ── KPI Card ── */
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
  .kpi .label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 8px; }
  .kpi .value { font-size: 26px; font-weight: 700; color: #fff; line-height: 1; }
  .kpi .sub-value { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
  .kpi .badge { display: inline-flex; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 600; margin-top: 6px; }
  .badge-green { background: rgba(63,185,80,.15); color: var(--green); }
  .badge-red { background: rgba(248,81,73,.15); color: var(--red); }
  .badge-yellow { background: rgba(210,153,34,.15); color: var(--yellow); }
  .badge-blue { background: rgba(88,166,255,.15); color: var(--accent); }

  /* ── Section Card ── */
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 16px; }
  .card-title { font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
  .card-title .icon { font-size: 16px; }
  canvas { max-height: none; }

  /* ── Table ── */
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { color: var(--text-dim); font-weight: 600; text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: .3px; }
  td { padding: 8px 10px; border-bottom: 1px solid var(--border); color: var(--text); }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--surface2); }
  .tag { display: inline-flex; padding: 2px 8px; border-radius: 20px; font-size: 10px; font-weight: 700; }
  .topo-badge { display:inline-flex; align-items:center; gap:4px; padding:3px 10px; border-radius:20px; font-size:11px; background:#0d1117; border:1px solid #30363d; color:#8b949e; }
  .pipeline-node { display:flex; flex-direction:column; align-items:center; gap:4px; padding:8px 14px; background:#161b22; border:1px solid #30363d; border-radius:8px; font-size:12px; font-weight:600; color:#e6edf3; text-align:center; min-width:90px; }
  .pipeline-node.pl-devops { border-color:#388bfd44; background:#0d1117; }
  .pipeline-arrow { display:flex; align-items:center; color:#30363d; font-size:18px; font-weight:300; }
  .pl-badge { padding:2px 8px; border-radius:20px; font-size:10px; font-weight:700; }
  .pl-ok   { background:#1a4721; color:#3fb950; border:1px solid #238636; }
  .pl-warn { background:#4d2d00; color:#d29922; border:1px solid #9e6a03; }
  .pl-err  { background:#4d0d0d; color:#f85149; border:1px solid #da3633; }
  .tag-critical { background: rgba(248,81,73,.2); color: var(--red); }
  .tag-major { background: rgba(227,179,65,.2); color: var(--orange); }
  .tag-minor { background: rgba(88,166,255,.2); color: var(--accent); }
  .tag-open { background: rgba(248,81,73,.15); color: var(--red); }
  .tag-closed { background: rgba(63,185,80,.15); color: var(--green); }
  .tag-inprog { background: rgba(88,166,255,.15); color: var(--accent); }

  /* ── Real-time Monitor ── */
  .monitor-bar { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: var(--surface2); border-radius: 6px; margin-bottom: 6px; border-left: 3px solid var(--border); transition: all .3s; }
  .monitor-bar.critical { border-left-color: var(--red); }
  .monitor-bar.major { border-left-color: var(--orange); }
  .monitor-bar.minor { border-left-color: var(--accent); }
  .monitor-bar .m-title { flex: 1; font-weight: 500; }
  .monitor-bar .m-time { color: var(--text-dim); font-size: 11px; }

  .alert-feed { max-height: 320px; overflow-y: auto; }
  .alert-item { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid var(--border); animation: fadeIn .5s; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:none} }
  .alert-icon { font-size: 18px; }
  .alert-text .title { font-weight: 600; font-size: 12px; color: #fff; }
  .alert-text .desc { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
  .alert-time { color: var(--text-dim); font-size: 11px; margin-left: auto; white-space: nowrap; }

  /* ── Gauge ── */
  .gauge-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .gauge-label { width: 120px; font-size: 11px; color: var(--text-dim); }
  .gauge-bar { flex: 1; height: 8px; background: var(--surface2); border-radius: 4px; overflow: hidden; }
  .gauge-fill { height: 100%; border-radius: 4px; transition: width .8s; }
  .gauge-val { width: 50px; text-align: right; font-size: 11px; font-weight: 600; }

  /* ── Mini Stats ── */
  .mini-stat { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border); }
  .mini-stat:last-child { border-bottom: none; }
  .mini-stat .ms-label { color: var(--text-dim); font-size: 12px; }
  .mini-stat .ms-val { font-weight: 700; color: #fff; font-size: 13px; }

  /* ── Chart container ── */
  .chart-wrap { position: relative; height: 200px; }

  /* ── KG 탭 구분 ── */
  .kg-tab { border-left: 1px solid var(--border); }
  .kg-tab:first-of-type { margin-left: 8px; }

  /* ── KG 공통 ── */
  .kg-section { margin-bottom: 16px; }
  .kg-header { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--text-dim); margin-bottom: 10px; }
  .pill { display: inline-flex; padding: 3px 10px; border-radius: 12px; font-size: 10px; font-weight: 700; margin: 2px; background: var(--surface2); border: 1px solid var(--border); color: var(--text); }
  .pill.material { border-color: #58a6ff; color: #58a6ff; }
  .pill.quality   { border-color: #f85149; color: #f85149; }
  .pill.finance   { border-color: #3fb950; color: #3fb950; }
  .pill.production{ border-color: #bc8cff; color: #bc8cff; }
  .pill.hr        { border-color: #e3b341; color: #e3b341; }

  /* ── KG 그래프 캔버스 ── */
  #kg-canvas-wrap { width: 100%; height: 1000px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; position: relative; }
  #kg-canvas { width: 100%; height: 100%; }
  .vis-graph-wrap { width: 100%; height: 1000px; background: var(--bg); border-radius: 8px; overflow: hidden; border: 1px solid var(--border); margin-top: 8px; }
  .vis-graph-wrap canvas { width: 100% !important; height: 100% !important; }
  #kg-legend { position: absolute; top: 12px; right: 12px; background: rgba(13,17,23,.9); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 11px; max-height: 240px; overflow-y: auto; }
  .legend-item { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

  /* ── Ontology 트리 ── */
  .class-tree { display: flex; flex-wrap: wrap; gap: 6px; }
  .onto-prop { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; font-size: 11px; }
  .onto-prop-row { background: var(--surface2); border-radius: 4px; padding: 5px 8px; border-left: 2px solid var(--accent); }
  .turtle-box { background: #0d1117; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 10px; color: #7ee787; max-height: 280px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }

  /* ── Cypher 코드 블록 ── */
  .cypher-box { background: #0d1117; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: 'Fira Code','Consolas', monospace; font-size: 10px; color: #79c0ff; max-height: 260px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
  .neo4j-connected { color: var(--green); font-weight: 700; }
  .neo4j-offline { color: var(--yellow); font-weight: 700; }

  /* ── Vector RAG ── */
  .vec-result { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; margin-bottom: 6px; border-left: 3px solid var(--accent); }
  .vec-score { float: right; font-size: 10px; font-weight: 700; color: var(--accent); }
  .vec-type  { font-size: 10px; color: var(--text-dim); margin-bottom: 4px; }
  .vec-text  { font-size: 11px; color: var(--text); }

  /* ── GraphRAG ── */
  .rag-query-wrap { display: flex; gap: 8px; margin-bottom: 16px; }
  .rag-input { flex: 1; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: var(--text); font-size: 13px; outline: none; }
  .rag-input:focus { border-color: var(--accent); }
  .rag-btn { background: var(--accent); color: #0d1117; border: none; border-radius: 8px; padding: 10px 20px; font-weight: 700; cursor: pointer; font-size: 13px; }
  .rag-btn:hover { background: #79c0ff; }
  .fused-item { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 11px; }
  .fused-rank { width: 24px; height: 24px; border-radius: 50%; background: var(--surface2); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; flex-shrink: 0; }
  .source-badge { padding: 2px 6px; border-radius: 4px; font-size: 9px; font-weight: 700; }
  .src-vector { background: rgba(88,166,255,.2); color: var(--accent); }
  .src-graph  { background: rgba(188,140,255,.2); color: var(--purple); }
  .src-both   { background: rgba(63,185,80,.2); color: var(--green); }
  .prompt-box { background: #0d1117; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: 'Consolas', monospace; font-size: 10px; color: #e3b341; max-height: 200px; overflow-y: auto; white-space: pre-wrap; }

  /* ── 메트릭 그리드 ── */
  .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
  .metric-box { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; text-align: center; }
  .metric-box .mv { font-size: 22px; font-weight: 700; color: #fff; }
  .metric-box .ml { font-size: 10px; color: var(--text-dim); margin-top: 2px; text-transform: uppercase; }
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div class="logo">CK</div>
    <div>
      <h1>CKD-NEXT 종합 운영 대시보드</h1>
      <div class="sub">종근당 차세대 AI·SAP 통합 플랫폼 | Company Code 1000</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:16px;">
    <div style="display:flex;align-items:center;gap:6px;">
      <div class="status-dot" id="connDot"></div>
      <span class="status-label" id="connLabel">연결 중...</span>
    </div>
    <div class="last-update" id="lastUpdate">-</div>
  </div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showPanel('overview',this)">📊 전체 현황</div>
  <div class="tab" onclick="showPanel('sales',this)">💰 영업·재무</div>
  <div class="tab" onclick="showPanel('quality',this)">🧪 품질·GMP</div>
  <div class="tab" onclick="showPanel('production',this)">🏭 생산·구매</div>
  <div class="tab" onclick="showPanel('monitor',this)">🔴 실시간 모니터링</div>
  <div class="tab kg-tab" onclick="showPanel('ontology',this)">🧬 OWL 온톨로지</div>
  <div class="tab kg-tab" onclick="showPanel('kgraph',this)">🕸️ 지식 그래프</div>
  <div class="tab kg-tab" onclick="showPanel('neo4j',this)">🗄️ Neo4j</div>
  <div class="tab kg-tab" onclick="showPanel('vectorrag',this)">🔍 Vector RAG</div>
  <div class="tab kg-tab" onclick="showPanel('graphrag',this)">🤖 GraphRAG</div>
</div>

<div class="main">

  <!-- ══════════════════════════════════════════
       PANEL: 전체 현황
  ══════════════════════════════════════════ -->
  <div class="panel active" id="panel-overview">
    <div class="grid-4">
      <div class="kpi">
        <div class="label">수주 (총)</div>
        <div class="value" id="ov-so-total">-</div>
        <div class="sub-value" id="ov-so-open">진행중: -건</div>
        <span class="badge badge-blue" id="ov-so-badge">-</span>
      </div>
      <div class="kpi">
        <div class="label">수익 계정 잔액 (전표 합)</div>
        <div class="value" id="ov-revenue">-</div>
        <div class="sub-value">전표 유형: RV</div>
        <span class="badge badge-green">매출전표</span>
      </div>
      <div class="kpi">
        <div class="label">일탈 보고서 (미결)</div>
        <div class="value" id="ov-dev-open">-</div>
        <div class="sub-value" id="ov-dev-crit">Critical: -건</div>
        <span class="badge" id="ov-dev-badge">-</span>
      </div>
      <div class="kpi">
        <div class="label">생산 오더 (진행중)</div>
        <div class="value" id="ov-prod-ip">-</div>
        <div class="sub-value" id="ov-prod-total">총 - 건</div>
        <span class="badge badge-blue">REL/PCNF</span>
      </div>
    </div>

    <div class="grid-4">
      <div class="kpi">
        <div class="label">매출채권 (미수)</div>
        <div class="value" id="ov-ar-open">-</div>
        <div class="sub-value" id="ov-ar-cnt">건</div>
        <span class="badge badge-yellow">AR OPEN</span>
      </div>
      <div class="kpi">
        <div class="label">매입채무 (미결</div>
        <div class="value" id="ov-ap-open">-</div>
        <div class="sub-value" id="ov-ap-total">총 채무</div>
        <span class="badge badge-yellow">AP OPEN</span>
      </div>
      <div class="kpi">
        <div class="label">OOS (미결)</div>
        <div class="value" id="ov-oos-open">-</div>
        <div class="sub-value" id="ov-oos-total">총 - 건</div>
        <span class="badge badge-red">OOS OPEN</span>
      </div>
      <div class="kpi">
        <div class="label">CAPA (과기)</div>
        <div class="value" id="ov-capa-od">-</div>
        <div class="sub-value" id="ov-capa-total">총 - 건</div>
        <span class="badge badge-red">OVERDUE</span>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">📅</span>청구 일별 추이</div>
        <div class="chart-wrap"><canvas id="billingChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">📋</span>전표 유형별 금액</div>
        <div class="chart-wrap"><canvas id="glTypeChart"></canvas></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">🚨</span>최근 일탈 보고서</div>
        <table>
          <thead><tr><th>ID</th><th>제목</th><th>심각도</th><th>상태</th><th>감지일</th></tr></thead>
          <tbody id="devTable"></tbody>
        </table>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">📒</span>최근 회계 전표</div>
        <table>
          <thead><tr><th>전표번호</th><th>유형</th><th>일자</th><th>차변</th></tr></thead>
          <tbody id="jvTable"></tbody>
        </table>
      </div>
    </div>

    <div class="card" style="margin-top:16px;">
      <div class="card-title"><span class="icon">🕸️</span>비즈니스 프로세스 연관 그래프 (자재 → 수주 / 생산 → 일탈 → CAPA)
        <span style="margin-left:12px;font-size:11px;color:var(--text2);">
          <span style="color:#58a6ff">■</span> 자재
          <span style="color:#3fb950;margin-left:6px">■</span> 수주
          <span style="color:#d29922;margin-left:6px">■</span> 생산오더
          <span style="color:#f85149;margin-left:6px">■</span> 일탈
          <span style="color:#bc8cff;margin-left:6px">■</span> CAPA
        </span>
      </div>
      <div id="ov-graph-canvas" style="width:100%;height:600px;background:var(--bg);border-radius:8px;overflow:hidden;border:1px solid var(--border);margin-top:8px;"></div>
    </div>
  </div>

  <!-- ══════════════════════════════════════════
       PANEL: 영업·재무
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-sales">
    <div class="grid-3">
      <div class="kpi">
        <div class="label">총 수주 건수</div>
        <div class="value" id="s-so-total">-</div>
        <div class="sub-value" id="s-so-open">진행중 건</div>
      </div>
      <div class="kpi">
        <div class="label">수주 총액</div>
        <div class="value" id="s-so-amt">-</div>
        <div class="sub-value">Net Value (KRW)</div>
        <span class="badge badge-green">확정</span>
      </div>
      <div class="kpi">
        <div class="label">세금계산서 발행</div>
        <div class="value" id="s-inv-cnt">-</div>
        <div class="sub-value" id="s-inv-paid">결제완료 -건</div>
        <span class="badge badge-blue">Invoice</span>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">📈</span>일별 매출 (청구 기준)</div>
        <div class="chart-wrap"><canvas id="salesChart2"></canvas></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">💵</span>AR / AP 현황</div>
        <div class="chart-wrap"><canvas id="arApChart"></canvas></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">📤</span>매출채권 목록</div>
        <table>
          <thead><tr><th>고객</th><th>Invoice</th><th>전기일</th><th>미수금</th><th>상태</th></tr></thead>
          <tbody id="arTable"></tbody>
        </table>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">📥</span>매입채무 목록</div>
        <table>
          <thead><tr><th>AP Doc</th><th>공급사</th><th>총액</th><th>결제기한</th><th>상태</th></tr></thead>
          <tbody id="apTable"></tbody>
        </table>
      </div>
      <div class="card" style="margin-top:16px;">
        <div class="card-title"><span class="icon">🕸️</span>고객·수주·청구 연관 그래프
          <span id="sales-g-legend" style="margin-left:12px;font-size:11px;color:var(--text2);"></span>
        </div>
        <div id="sales-g-canvas" style="width:100%;height:500px;background:var(--bg);border-radius:8px;overflow:hidden;border:1px solid var(--border);margin-top:8px;"></div>
      </div>
    </div>
  </div>

  <!-- ══════════════════════════════════════════
       PANEL: 품질·GMP
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-quality">
    <div class="grid-4">
      <div class="kpi">
        <div class="label">일탈 보고서 (총)</div>
        <div class="value" id="q-dev-total">-</div>
        <div class="sub-value" id="q-dev-breakdown">C/M/m: -/-/-</div>
        <span class="badge" id="q-dev-badge">-</span>
      </div>
      <div class="kpi">
        <div class="label">OOS 결과 (총)</div>
        <div class="value" id="q-oos-total">-</div>
        <div class="sub-value" id="q-oos-open">OPEN: -건</div>
        <span class="badge" id="q-oos-badge">-</span>
      </div>
      <div class="kpi">
        <div class="label">제품 민원 (총)</div>
        <div class="value" id="q-comp-total">-</div>
        <div class="sub-value" id="q-comp-open">OPEN: -건</div>
        <span class="badge" id="q-comp-badge">-</span>
      </div>
      <div class="kpi">
        <div class="label">CAPA Action</div>
        <div class="value" id="q-capa-total">-</div>
        <div class="sub-value" id="q-capa-od">과기: -건</div>
        <span class="badge" id="q-capa-badge">-</span>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">🔴</span>일탈 심각도 분포</div>
        <div class="chart-wrap"><canvas id="devSevChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">📊</span>품질 게이지</div>
        <div id="qualGauge"></div>
      </div>
    </div>

    <div class="card">
      <div class="card-title"><span class="icon">📋</span>최근 일탈 보고서 상세</div>
      <table>
        <thead><tr><th>ID</th><th>제목</th><th>심각도</th><th>상태</th><th>감지일</th></tr></thead>
        <tbody id="devTableFull"></tbody>
      </table>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">🔬</span>QM 검사 로트</div>
        <table>
          <thead><tr><th>Lot ID</th><th>자재</th><th>플랜트</th><th>상태</th><th>계획일</th></tr></thead>
          <tbody id="lotTable"></tbody>
        </table>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">✅</span>CAPA 현황</div>
        <div id="capaStatus"></div>
      </div>
      <div class="card" style="margin-top:16px;">
        <div class="card-title"><span class="icon">🕸️</span>자재·일탈·CAPA·검사 연관 그래프
          <span id="quality-g-legend" style="margin-left:12px;font-size:11px;color:var(--text2);"></span>
        </div>
        <div id="quality-g-canvas" style="width:100%;height:500px;background:var(--bg);border-radius:8px;overflow:hidden;border:1px solid var(--border);margin-top:8px;"></div>
      </div>
    </div>
  </div>

  <!-- ══════════════════════════════════════════
       PANEL: 생산·구매
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-production">
    <div class="grid-4">
      <div class="kpi">
        <div class="label">생산 오더 (총)</div>
        <div class="value" id="p-total">-</div>
        <div class="sub-value" id="p-crtd">생성: -건</div>
      </div>
      <div class="kpi">
        <div class="label">진행중 (REL/PCNF)</div>
        <div class="value" id="p-ip">-</div>
        <div class="sub-value">릴리즈/확인</div>
        <span class="badge badge-blue">IN PROGRESS</span>
      </div>
      <div class="kpi">
        <div class="label">완료 (TECO)</div>
        <div class="value" id="p-teco">-</div>
        <div class="sub-value">기술 완료</div>
        <span class="badge badge-green">COMPLETED</span>
      </div>
      <div class="kpi">
        <div class="label">Open PO (미결)</div>
        <div class="value" id="p-po-cnt">-</div>
        <div class="sub-value">발주 잔량</div>
        <span class="badge badge-yellow">OPEN</span>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">🏭</span>생산 오더 유형별</div>
        <div class="chart-wrap"><canvas id="prodTypeChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">📦</span>미결 구매 오더</div>
        <table>
          <thead><tr><th>PO ID</th><th>공급사</th><th>일자</th><th>금액</th><th>상태</th></tr></thead>
          <tbody id="poTable"></tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-title"><span class="icon">🔬</span>QM 검사 로트 현황</div>
      <table>
        <thead><tr><th>Lot ID</th><th>자재 ID</th><th>플랜트</th><th>상태</th><th>계획 시작일</th></tr></thead>
        <tbody id="lotTable2"></tbody>
      </table>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="card-title"><span class="icon">🕸️</span>자재·생산오더·공급사·구매오더 연관 그래프
        <span id="prod-g-legend" style="margin-left:12px;font-size:11px;color:var(--text2);"></span>
      </div>
      <div id="prod-g-canvas" style="width:100%;height:500px;background:var(--bg);border-radius:8px;overflow:hidden;border:1px solid var(--border);margin-top:8px;"></div>
    </div>
  </div>

  <!-- ══════════════════════════════════════════
       PANEL: 실시간 모니터링
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-monitor">
    <div class="grid-4" style="margin-bottom:16px;">
      <div class="kpi" style="border-color:var(--green)">
        <div class="label">DB 연결 상태</div>
        <div class="value" id="mon-conn" style="color:var(--green)">●  LIVE</div>
        <div class="sub-value">PostgreSQL ckd_next</div>
      </div>
      <div class="kpi">
        <div class="label">마지막 업데이트</div>
        <div class="value" style="font-size:16px" id="mon-ts">-</div>
        <div class="sub-value">5초 갱신 주기</div>
      </div>
      <div class="kpi">
        <div class="label">활성 WebSocket</div>
        <div class="value" id="mon-ws">1</div>
        <div class="sub-value">클라이언트 수</div>
      </div>
      <div class="kpi">
        <div class="label">총 이벤트 수신</div>
        <div class="value" id="mon-events">0</div>
        <div class="sub-value">누적 갱신 횟수</div>
      </div>
    </div>

    <div class="grid-21">
      <div class="card">
        <div class="card-title"><span class="icon">📡</span>실시간 알림 피드 <span style="font-size:10px;color:var(--text-dim);font-weight:400">(최신순)</span></div>
        <div class="alert-feed" id="alertFeed"></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">📊</span>실시간 KPI 스냅샷</div>
        <div id="kpiSnap"></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">🚨</span>일탈 실시간 현황</div>
        <div id="devMonitor"></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">💹</span>실시간 재무 지표</div>
        <div id="finMonitor"></div>
      </div>
    </div>

    <!-- ── 전체 인프라 파이프라인 현황 ── -->
    <div class="card" style="margin-top:12px;">
      <div class="card-title"><span class="icon">🔁</span>전체 파이프라인 실시간 현황 (CDC → Redis → Kafka → DevOps)</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;" id="pipeline-status-bar">
        <div class="pipeline-node" id="pl-pg">🐘 PostgreSQL<br><span class="pl-badge pl-ok">LIVE</span></div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-node" id="pl-cdc">🔄 CDC Trigger<br><span class="pl-badge pl-ok" id="pl-cdc-cnt">0 events</span></div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-node" id="pl-redis">🗄️ Redis Stream<br><span class="pl-badge pl-ok" id="pl-redis-cnt">0 msgs</span></div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-node" id="pl-kafka">📨 Kafka<br><span class="pl-badge pl-warn" id="pl-kafka-cnt">ckd-kafka:9095</span></div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-node" id="pl-dash">📊 Dashboard WS<br><span class="pl-badge pl-ok" id="pl-ws-cnt">1 clients</span></div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
        <div class="pipeline-node pl-devops" id="pl-ansible">🤖 Ansible<br><span class="pl-badge pl-ok">자동 배포</span></div>
        <div class="pipeline-arrow">|</div>
        <div class="pipeline-node pl-devops" id="pl-helm">⛵ Helm<br><span class="pl-badge pl-ok">K8s 패키지</span></div>
        <div class="pipeline-arrow">|</div>
        <div class="pipeline-node pl-devops" id="pl-istio">🕸️ Istio<br><span class="pl-badge pl-ok">서비스 메시</span></div>
        <div class="pipeline-arrow">|</div>
        <div class="pipeline-node pl-devops" id="pl-terraform">🏗️ Terraform<br><span class="pl-badge pl-ok">IaC 인프라</span></div>
        <div class="pipeline-arrow">|</div>
        <div class="pipeline-node pl-devops" id="pl-soar">🛡️ SOAR<br><span class="pl-badge pl-ok">보안 자동화</span></div>
      </div>
      <!-- CDC 이벤트 스트림 실시간 피드 -->
      <div class="card-title" style="margin-top:8px;"><span class="icon">⚡</span>CDC 실시간 이벤트 스트림</div>
      <div id="cdc-live-feed" style="font-family:monospace;font-size:12px;background:#0d1117;border-radius:6px;padding:10px;min-height:120px;max-height:250px;overflow-y:auto;border:1px solid var(--border);">
        <span style="color:var(--text-dim);">CDC 이벤트 대기 중...</span>
      </div>
      <!-- 인프라 상태 -->
      <div style="display:flex;gap:12px;margin-top:12px;flex-wrap:wrap;" id="infra-status-cards"></div>
    </div>

    <div class="card" style="margin-top:12px;">
      <div class="card-title"><span class="icon">🕸️</span>운영 현황 허브 그래프 (NetworkX 토폴로지)
        <span id="mon-g-legend" style="margin-left:12px;font-size:11px;color:var(--text2);"></span>
      </div>
      <div id="mon-g-topo-panel"></div>
      <div id="mon-g-canvas" style="width:100%;height:480px;background:var(--bg);border-radius:8px;overflow:hidden;border:1px solid var(--border);margin-top:8px;"></div>
    </div>
  </div>


  <!-- ══════════════════════════════════════════
       PANEL: RDF/OWL 온톨로지
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-ontology">
    <div class="grid-4" id="onto-kpi" style="margin-bottom:16px;">
      <div class="kpi"><div class="label">OWL 클래스</div><div class="value" id="onto-cls">-</div><div class="sub-value">도메인 엔티티</div></div>
      <div class="kpi"><div class="label">객체 속성</div><div class="value" id="onto-op">-</div><div class="sub-value">관계 (ObjectProperty)</div></div>
      <div class="kpi"><div class="label">데이터 속성</div><div class="value" id="onto-dp">-</div><div class="sub-value">데이터 값 (DataProperty)</div></div>
      <div class="kpi"><div class="label">네임스페이스</div><div class="value" style="font-size:14px">CKD-NEXT</div><div class="sub-value">ckd-next.co.kr/ontology/</div></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">🧬</span>OWL 클래스 목록</div>
        <div class="class-tree" id="onto-classes"></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">🔗</span>객체 속성 (ObjectProperty)</div>
        <div class="onto-prop" id="onto-obj-props"></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">🧬</span>OWL 클래스 관계 그래프 (NetworkX + ObjectProperty)</div>
      <div id="onto-topo-panel" style="margin-bottom:8px;"></div>
      <div id="onto-canvas" style="width:100%;height:480px;background:var(--bg);border-radius:8px;overflow:hidden;border:1px solid var(--border);"></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">📄</span>Turtle 직렬화 (OWL 스니펫)</div>
      <div class="turtle-box" id="onto-turtle">로딩 중...</div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">📐</span>데이터 속성 (DatatypeProperty)</div>
      <table><thead><tr><th>속성명</th><th>도메인 클래스</th><th>설명</th></tr></thead>
      <tbody id="onto-data-props"></tbody></table>
    </div>
  </div>

  <!-- ══════════════════════════════════════════
       PANEL: 지식 그래프 (NetworkX → vis.js)
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-kgraph">
    <div class="metric-grid" id="kg-metrics-row">
      <div class="metric-box"><div class="mv" id="kg-nodes">-</div><div class="ml">노드</div></div>
      <div class="metric-box"><div class="mv" id="kg-edges">-</div><div class="ml">엣지</div></div>
      <div class="metric-box"><div class="mv" id="kg-density">-</div><div class="ml">밀도</div></div>
      <div class="metric-box"><div class="mv" id="kg-wcc">-</div><div class="ml">연결 컴포넌트</div></div>
    </div>
    <div class="grid-21">
      <div id="kg-canvas-wrap">
        <div id="kg-canvas"></div>
        <div id="kg-legend"></div>
      </div>
      <div style="display:flex;flex-direction:column;gap:12px;">
        <div class="card" style="margin:0">
          <div class="card-title"><span class="icon">📊</span>노드 타입별</div>
          <div id="kg-type-dist"></div>
        </div>
        <div class="card" style="margin:0">
          <div class="card-title"><span class="icon">🏆</span>PageRank 상위</div>
          <div id="kg-pagerank"></div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">🔗</span>관계 유형별 엣지 수</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;" id="kg-rel-counts"></div>
    </div>
  </div>

  <!-- ══════════════════════════════════════════
       PANEL: Neo4j Cypher
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-neo4j">
    <div class="grid-4" style="margin-bottom:16px;">
      <div class="kpi">
        <div class="label">Neo4j 연결</div>
        <div class="value" style="font-size:16px" id="neo4j-status-val">확인 중...</div>
        <div class="sub-value" id="neo4j-uri">bolt://localhost:7687</div>
      </div>
      <div class="kpi"><div class="label">Cypher 스크립트 줄</div><div class="value" id="neo4j-lines">-</div><div class="sub-value">생성된 쿼리</div></div>
      <div class="kpi"><div class="label">노드 MERGE 구문</div><div class="value" id="neo4j-nodes">-</div><div class="sub-value">CREATE/MERGE</div></div>
      <div class="kpi"><div class="label">관계 구문</div><div class="value" id="neo4j-rels">-</div><div class="sub-value">-[:REL]-></div></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">📋</span>샘플 Cypher 쿼리</div>
        <div id="neo4j-queries"></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">🗄️</span>인덱스·제약 정의</div>
        <div class="cypher-box" id="neo4j-constraints">로딩 중...</div>
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">🗄️</span>Neo4j 그래프 미리보기 (KG 데이터 → Neo4j 스타일)</div>
      <div class="vis-graph-wrap" id="neo4j-canvas"></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">📝</span>생성된 Cypher 스크립트 미리보기 <button onclick="downloadCypher()" style="float:right;background:var(--accent);border:none;border-radius:6px;padding:4px 12px;color:#000;font-weight:700;cursor:pointer;font-size:11px;">⬇ 다운로드</button></div>
      <div class="cypher-box" id="neo4j-script">로딩 중...</div>
    </div>
  </div>

  <!-- ══════════════════════════════════════════
       PANEL: Vector RAG
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-vectorrag">
    <div class="grid-4" style="margin-bottom:16px;">
      <div class="kpi"><div class="label">벡터 문서 수</div><div class="value" id="vr-docs">-</div><div class="sub-value">임베딩된 엔티티</div></div>
      <div class="kpi"><div class="label">어휘 사전 크기</div><div class="value" id="vr-vocab">-</div><div class="sub-value">TF-IDF n-gram</div></div>
      <div class="kpi"><div class="label">행렬 차원</div><div class="value" style="font-size:14px" id="vr-shape">-</div><div class="sub-value">문서 × 어휘</div></div>
      <div class="kpi"><div class="label">임베딩 방식</div><div class="value" style="font-size:14px">TF-IDF</div><div class="sub-value">Char n-gram (2-4)</div></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-title"><span class="icon">📦</span>엔티티 타입별 문서 분포</div>
        <div class="chart-wrap"><canvas id="vrDistChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-title"><span class="icon">🔍</span>실시간 검색</div>
        <div class="rag-query-wrap">
          <input class="rag-input" id="vr-query" placeholder="검색어 입력 (예: Critical 일탈 원료 품질)" value="Critical 일탈 원료">
          <button class="rag-btn" onclick="runVectorSearch()">검색</button>
        </div>
        <div id="vr-results"></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">💡</span>예제 검색 쿼리</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;">
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);" onclick="vrQuickSearch('Critical 일탈 원료 품질 문제')">Critical 일탈</button>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);" onclick="vrQuickSearch('매출 청구 세금계산서')">매출 재무</button>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);" onclick="vrQuickSearch('생산 오더 완료 TECO')">생산 오더</button>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);" onclick="vrQuickSearch('CAPA 조치 완료 담당자')">CAPA 조치</button>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);" onclick="vrQuickSearch('Acetaminophen Atorvastatin 자재')">자재 검색</button>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);" onclick="vrQuickSearch('감가상각 전표 비용')">회계 전표</button>
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">🔍</span>벡터 유사도 네트워크 (검색 결과 그래프)</div>
      <div class="vis-graph-wrap" id="vr-canvas"></div>
    </div>
  </div>

  <!-- ══════════════════════════════════════════
       PANEL: GraphRAG (Vector + Graph 융합)
  ══════════════════════════════════════════ -->
  <div class="panel" id="panel-graphrag">
    <div class="card">
      <div class="card-title"><span class="icon">🤖</span>GraphRAG 하이브리드 검색 (Vector + NetworkX BFS + RRF 융합)</div>
      <div class="rag-query-wrap">
        <input class="rag-input" id="gr-query" placeholder="자연어 질의 입력 (예: 아세트아미노펜 생산에서 발생한 Critical 일탈 CAPA 현황은?)" value="Critical 일탈 원료 품질 문제 CAPA 현황">
        <button class="rag-btn" onclick="runGraphRAG()">🤖 GraphRAG 실행</button>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;">
        <span style="font-size:11px;color:var(--text-dim)">예제:</span>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);font-size:10px;padding:4px 8px;" onclick="grQuick('Critical 일탈 CAPA 현황')">Critical CAPA</button>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);font-size:10px;padding:4px 8px;" onclick="grQuick('매출채권 미수금 현황')">AR 미수</button>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);font-size:10px;padding:4px 8px;" onclick="grQuick('아토르바스타틴 생산 일탈')">생산 일탈</button>
        <button class="rag-btn" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);font-size:10px;padding:4px 8px;" onclick="grQuick('GL 전표 매출원가 감가상각')">재무 전표</button>
      </div>
    </div>
    <div class="grid-3" id="gr-stats-row" style="margin-bottom:12px;display:none;">
      <div class="kpi"><div class="label">도메인 분류</div><div class="value" style="font-size:16px" id="gr-domain">-</div></div>
      <div class="kpi"><div class="label">Vector 히트</div><div class="value" id="gr-v-hits">-</div><div class="sub-value">TF-IDF 유사도</div></div>
      <div class="kpi"><div class="label">Graph 히트</div><div class="value" id="gr-g-hits">-</div><div class="sub-value">NetworkX BFS</div></div>
    </div>
    <div class="grid-21" id="gr-results-wrap" style="display:none;">
      <div>
        <div class="card" style="margin-bottom:12px;">
          <div class="card-title"><span class="icon">🏆</span>RRF 융합 최종 순위</div>
          <div id="gr-fused"></div>
        </div>
        <div class="card">
          <div class="card-title"><span class="icon">🕸️</span>Graph 이웃 노드</div>
          <div id="gr-graph-hits"></div>
        </div>
      </div>
      <div>
        <div class="card">
          <div class="card-title"><span class="icon">📝</span>생성된 RAG Prompt</div>
          <div class="prompt-box" id="gr-prompt">-</div>
        </div>
      </div>
    </div>
    <div class="card" id="gr-graph-wrap" style="display:none;">
      <div class="card-title"><span class="icon">🤖</span>GraphRAG 융합 결과 네트워크 (Vector + Graph BFS)</div>
      <div class="vis-graph-wrap" id="gr-canvas"></div>
    </div>
  </div>

</div><!-- /main -->

<script src="https://unpkg.com/vis-network@9.1.6/dist/vis-network.min.js"></script>
<script>
// ──────────────────────────────────────────
// Chart.js 기본 설정 (다크 테마)
// ──────────────────────────────────────────
Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#30363d';
Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";
Chart.defaults.font.size = 11;

let charts = {};
let eventCount = 0;
let kpiData = null;

function fmt(n) {
  if (n === null || n === undefined || n === '-') return '-';
  n = Number(n);
  if (n >= 1e9) return (n/1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(0) + 'K';
  return n.toLocaleString('ko-KR');
}
function fmtW(n) {
  if (!n) return '-';
  n = Number(n);
  return (n/1e4).toFixed(0) + '만';
}
function fmtKRW(n) {
  if (!n) return '₩0';
  return '₩' + Number(n).toLocaleString('ko-KR');
}

// ──────────────────────────────────────────
// Tab (showPanel defined later with KG lazy-load support)

// ──────────────────────────────────────────
// WebSocket
// ──────────────────────────────────────────
function connectWS() {
  const ws = new WebSocket('ws://127.0.0.1:8765/ws/monitor');
  ws.onopen = () => {
    document.getElementById('connDot').style.background = '#3fb950';
    document.getElementById('connLabel').textContent = '실시간 연결됨';
    document.getElementById('connLabel').style.color = '#3fb950';
    document.getElementById('mon-conn').textContent = '● LIVE';
  };
  ws.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }

    // CDC 이벤트 처리 (type: "cdc_event")
    if (msg.type === 'cdc_event') {
      appendCdcEvent(msg);
      updatePipelineStatus(msg);
      return;
    }

    // KPI 데이터 처리 (일반 스냅샷)
    kpiData = msg;
    eventCount++;
    document.getElementById('mon-events').textContent = eventCount;
    document.getElementById('mon-ts').textContent = kpiData.timestamp ? kpiData.timestamp.substring(11,19) : '-';
    document.getElementById('lastUpdate').textContent = '업데이트: ' + (kpiData.timestamp || '').substring(11,19);
    renderAll(kpiData);
  };
  ws.onclose = () => {
    document.getElementById('connDot').style.background = '#f85149';
    document.getElementById('connLabel').textContent = '연결 끊김 - 재연결 중...';
    document.getElementById('connLabel').style.color = '#f85149';
    setTimeout(connectWS, 3000);
  };
  ws.onerror = () => ws.close();
}

// ──────────────────────────────────────────
// CDC 실시간 이벤트 피드
// ──────────────────────────────────────────
let _cdcCount = 0;
const _OP_COLORS = {INSERT:'#3fb950', UPDATE:'#d29922', DELETE:'#f85149', '?':'#8b949e'};
const _TABLE_ICONS = {
  sales_order:'💰', deviation_report:'⚠️', capa_action:'🔧',
  production_order:'🏭', purchase_order:'🛒', accounts_receivable:'💳',
  qm_inspection_lot:'🔬', gl_posting:'📒',
};

function appendCdcEvent(msg) {
  _cdcCount++;
  const feed = document.getElementById('cdc-live-feed');
  if (!feed) return;
  const op    = msg.op || '?';
  const table = msg.table || msg.topic?.split('.').slice(-1)[0] || '?';
  const ts    = new Date().toLocaleTimeString('ko-KR');
  const color = _OP_COLORS[op] || '#8b949e';
  const icon  = _TABLE_ICONS[table] || '📋';
  const summary = msg.summary || `${table} ${op}`;

  const line = document.createElement('div');
  line.style.cssText = 'padding:3px 0;border-bottom:1px solid #21262d;display:flex;gap:8px;align-items:center;';
  line.innerHTML = `
    <span style="color:#484f58;min-width:70px;">${ts}</span>
    <span style="font-weight:700;color:${color};min-width:60px;">[${op}]</span>
    <span style="color:#58a6ff;">${icon} ${table}</span>
    <span style="color:#e6edf3;flex:1;">${summary}</span>
    <span style="color:#484f58;font-size:10px;">#${_cdcCount}</span>`;
  const first = feed.firstChild;
  if (first && first.tagName) feed.insertBefore(line, first);
  else { feed.innerHTML = ''; feed.appendChild(line); }

  // 최대 50줄 유지
  while (feed.children.length > 50) feed.removeChild(feed.lastChild);

  // 파이프라인 카운터 업데이트
  const cdcEl = document.getElementById('pl-cdc-cnt');
  if (cdcEl) cdcEl.textContent = `${_cdcCount} events`;
}

let _redisStreamLen = 0;
async function updatePipelineStatus(msg) {
  _redisStreamLen++;
  const redisEl = document.getElementById('pl-redis-cnt');
  if (redisEl) redisEl.textContent = `${_redisStreamLen} msgs`;
}

async function loadInfraStatus() {
  try {
    const r = await fetch('/api/infra/status');
    const d = await r.json();
    const redis = d.redis || {};
    const cards = document.getElementById('infra-status-cards');
    if (!cards) return;
    const ok = redis.available ? 'pl-ok' : 'pl-err';
    cards.innerHTML = `
      <div class="pipeline-node" style="min-width:140px;">
        🗄️ Redis Cluster<br>
        <span class="pl-badge ${ok}">${redis.available ? '●  ONLINE' : '✕  OFFLINE'}</span>
        ${redis.available ? `<span style="font-size:10px;color:var(--text-dim);">v${redis.version} | Stream:${redis.stream_len||0} | Alerts:${redis.alerts_count||0}</span>` : ''}
      </div>
      <div class="pipeline-node" style="min-width:140px;">
        📨 Kafka Topics<br>
        <span class="pl-badge pl-ok">${(d.kafka_topics||[]).length} topics</span>
        <span style="font-size:10px;color:var(--text-dim);">${(d.kafka_topics||[]).slice(0,2).join(', ')}...</span>
      </div>
      <div class="pipeline-node" style="min-width:140px;">
        🐘 CDC Tables<br>
        <span class="pl-badge pl-ok">${(d.cdc_tables||[]).length} tables</span>
        <span style="font-size:10px;color:var(--text-dim);">8 트리거 활성</span>
      </div>`;
    if (redis.stream_len !== undefined) _redisStreamLen = redis.stream_len;
    const redisEl = document.getElementById('pl-redis-cnt');
    if (redisEl) redisEl.textContent = `${redis.stream_len||0} msgs`;
  } catch(e) {}

  // 최근 이벤트 초기 로딩
  try {
    const r2 = await fetch('/api/infra/events?count=20');
    const d2 = await r2.json();
    const feed = document.getElementById('cdc-live-feed');
    if (feed && d2.length) {
      feed.innerHTML = '';
      d2.forEach(ev => {
        const op = ev.op || '?';
        const table = ev.table || '?';
        const ts = ev.ts ? new Date(parseInt(ev.ts)*1000).toLocaleTimeString('ko-KR') : '-';
        const color = _OP_COLORS[op]||'#8b949e';
        const icon = _TABLE_ICONS[table]||'📋';
        const line = document.createElement('div');
        line.style.cssText = 'padding:3px 0;border-bottom:1px solid #21262d;display:flex;gap:8px;align-items:center;';
        line.innerHTML = `<span style="color:#484f58;min-width:70px;">${ts}</span><span style="font-weight:700;color:${color};min-width:60px;">[${op}]</span><span style="color:#58a6ff;">${icon} ${table}</span>`;
        feed.appendChild(line);
      });
    }
  } catch(e) {}
}

// ──────────────────────────────────────────
// 렌더링 메인
// ──────────────────────────────────────────
function renderAll(d) {
  renderOverview(d);
  renderSales(d);
  renderQuality(d);
  renderProduction(d);
  renderMonitor(d);
  renderCharts(d);
}

function renderOverview(d) {
  const s = d.sales || {};
  const fin = d.finance_ar || {};
  const ap = d.finance_ap || {};
  const dev = d.quality_deviation || {};
  const oos = d.quality_oos || {};
  const capa = d.quality_capa || {};
  const prod = d.production || {};

  setText('ov-so-total', s.total_orders || 0);
  setText('ov-so-open', '진행중: ' + (s.open_orders || 0) + '건');
  setText('ov-so-badge', '완료 ' + (s.completed_orders || 0) + '건');

  // GL Posting 매출전표 총액
  const rv = (d.gl_by_type || []).find(x => x.document_type === 'RV');
  setText('ov-revenue', rv ? '₩' + fmt(rv.total_debit) : '-');

  setText('ov-dev-open', dev.open_dev || 0);
  setText('ov-dev-crit', 'Critical: ' + (dev.critical || 0) + '건');
  const devBadge = document.getElementById('ov-dev-badge');
  devBadge.textContent = (dev.critical > 0 ? 'CRITICAL 있음' : '정상');
  devBadge.className = 'badge ' + (dev.critical > 0 ? 'badge-red' : 'badge-green');

  setText('ov-prod-ip', prod.in_progress || 0);
  setText('ov-prod-total', '총 ' + (prod.total || 0) + '건');

  setText('ov-ar-open', fin.ar_open ? '₩' + fmt(fin.ar_open) : '-');
  setText('ov-ar-cnt', (fin.ar_open_count || 0) + '건 미수');

  setText('ov-ap-open', ap.ap_open ? '₩' + fmt(ap.ap_open) : '-');
  setText('ov-ap-total', '총 ₩' + fmt(ap.ap_total));

  setText('ov-oos-open', oos.open_oos || 0);
  setText('ov-oos-total', '총 ' + (oos.total_oos || 0) + '건');

  setText('ov-capa-od', capa.overdue_capa || 0);
  setText('ov-capa-total', '총 ' + (capa.total_capa || 0) + '건');

  // 일탈 테이블
  renderDevTable('devTable', d.recent_deviations || [], 6);
  // 전표 테이블
  renderJvTable('jvTable', d.recent_journals || [], 8);
  // 비즈니스 프로세스 그래프
  loadOverviewGraph();
}

async function loadOverviewGraph() {
  const container = document.getElementById('ov-graph-canvas');
  if (!container) return;
  if (window._ovNet) { window._ovNet.destroy(); window._ovNet = null; }

  const r = await fetch('/api/overview-graph');
  const d = await r.json();

  const ovNodes = new vis.DataSet(d.nodes || []);
  const ovEdges = new vis.DataSet(d.edges || []);

  await new Promise(res => setTimeout(res, 150));
  const net = new vis.Network(container, { nodes: ovNodes, edges: ovEdges }, {
    physics: {
      barnesHut: { gravitationalConstant: -4000, springLength: 120, springConstant: 0.06, damping: 0.4 },
      stabilization: { iterations: 200 }
    },
    interaction: { hover: true, navigationButtons: true, zoomView: true },
    nodes: { borderWidth: 2, size: 20 },
    edges: { width: 1.5 },
  });
  window._ovNet = net;

  net.once('stabilizationIterationsDone', () => setTimeout(() => {
    const c = document.getElementById('ov-graph-canvas');
    net.setSize(c.offsetWidth + 'px', c.offsetHeight + 'px');
    net.redraw();
    const pos = net.getPositions();
    const keys = Object.keys(pos);
    if (!keys.length) return;
    const xs = keys.map(k => pos[k].x), ys = keys.map(k => pos[k].y);
    const cx = (Math.min(...xs)+Math.max(...xs))/2, cy = (Math.min(...ys)+Math.max(...ys))/2;
    const xRange = Math.max(...xs)-Math.min(...xs)+80;
    const yRange = Math.max(...ys)-Math.min(...ys)+80;
    const scale = Math.min((c.offsetWidth-40)/xRange, (c.offsetHeight-60)/yRange, 2.5);
    net.moveTo({ position:{x:cx,y:cy}, scale, animation:false });
  }, 400));
}

async function loadTabGraph(tab, canvasId, netKey) {
  const container = document.getElementById(canvasId);
  if (!container) return;
  if (window[netKey]) { try { window[netKey].destroy(); } catch(e){} window[netKey] = null; }
  container.innerHTML = '<div style="color:var(--text-dim);padding:20px;text-align:center;">그래프 로딩 중...</div>';

  let d;
  try {
    // /api/topology: NetworkX 지표가 포함된 노드 + 전역 메트릭 반환
    const r = await fetch(`/api/topology?tab=${tab}`);
    d = await r.json();
  } catch(e) {
    container.innerHTML = `<div style="color:#f85149;padding:20px;">로딩 실패: ${e}</div>`;
    return;
  }
  container.innerHTML = '';
  if (!d.nodes || !d.nodes.length) {
    container.innerHTML = '<div style="color:var(--text-dim);padding:20px;text-align:center;">데이터 없음</div>';
    return;
  }

  // ── 토폴로지 메트릭 패널 ──
  const topo = d.topology || {};
  const top5 = d.top_nodes || [];
  const topoHtml = `
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;padding:10px;background:var(--bg-secondary);border-radius:6px;border:1px solid var(--border);">
  <span style="color:var(--text-dim);font-size:11px;width:100%;font-weight:600;">NetworkX 토폴로지 분석</span>
  <div class="topo-badge">노드 <b>${topo.node_count||0}</b></div>
  <div class="topo-badge">엣지 <b>${topo.edge_count||0}</b></div>
  <div class="topo-badge">밀도 <b>${(topo.density||0).toFixed(3)}</b></div>
  <div class="topo-badge">컴포넌트 <b>${topo.components||1}</b></div>
  <div class="topo-badge">최대CC <b>${topo.largest_component||0}</b></div>
  <div class="topo-badge">평균차수 <b>${(topo.avg_degree||0).toFixed(1)}</b></div>
  ${top5.length ? '<span style="color:var(--text-dim);font-size:11px;width:100%;margin-top:4px;">Top 중심 노드 (PageRank)</span>' : ''}
  ${top5.map((n,i)=>`<div class="topo-badge" style="background:#161b22;">#${i+1} <b>${n.label}</b> PR:${n.pagerank.toFixed(3)}</div>`).join('')}
</div>
<div id="${canvasId}-net" style="width:100%;height:440px;background:var(--bg);border-radius:8px;overflow:hidden;border:1px solid var(--border);"></div>`;
  container.innerHTML = topoHtml;

  await new Promise(res => setTimeout(res, 120));
  const netContainer = document.getElementById(canvasId + '-net');
  if (!netContainer) return;

  const net = new vis.Network(netContainer,
    { nodes: new vis.DataSet(d.nodes), edges: new vis.DataSet(d.edges) },
    { physics: { barnesHut: { gravitationalConstant: -5000, springLength: 130, springConstant: 0.06, damping: 0.35 },
        stabilization: { iterations: 220 } },
      interaction: { hover: true, navigationButtons: true, zoomView: true, tooltipDelay: 100 },
      nodes: { borderWidth: 2 },
      edges: { width: 1.5 },
    });
  window[netKey] = net;

  net.once('stabilizationIterationsDone', () => setTimeout(() => {
    const c = document.getElementById(canvasId + '-net');
    if (!c) return;
    net.setSize(c.offsetWidth + 'px', c.offsetHeight + 'px');
    net.redraw();
    const pos = net.getPositions();
    const keys = Object.keys(pos);
    if (!keys.length) return;
    const xs = keys.map(k => pos[k].x), ys = keys.map(k => pos[k].y);
    const cx = (Math.min(...xs)+Math.max(...xs))/2, cy = (Math.min(...ys)+Math.max(...ys))/2;
    const xRange = Math.max(...xs)-Math.min(...xs)+80, yRange = Math.max(...ys)-Math.min(...ys)+80;
    const scale = Math.min((c.offsetWidth-40)/xRange, (c.offsetHeight-60)/yRange, 2.5);
    net.moveTo({ position:{x:cx,y:cy}, scale, animation:false });
  }, 400));
}

function renderSales(d) {
  const s = d.sales || {};
  const inv = d.billing_trend || [];
  const ar = d.finance_ar || {};
  const ap = d.finance_ap || {};

  setText('s-so-total', s.total_orders || 0);
  setText('s-so-open', '진행중 ' + (s.open_orders || 0) + '건');
  setText('s-so-amt', s.total_net_value ? '₩' + fmt(s.total_net_value) : '-');
  setText('s-inv-cnt', inv.length);
  setText('s-inv-paid', '결제완료 -건');

  // AR 테이블 - 실제 데이터
  const arTbody = document.getElementById('arTable');
  if (arTbody) {
    arTbody.innerHTML = '';
    (d.recent_journals || []).slice(0,6).forEach(j => {
      if (j.document_type !== 'RV') return;
      const tr = arTbody.insertRow();
      tr.innerHTML = `<td>Cust</td><td>${j.document_number}</td><td>${j.posting_date||''}</td><td>${fmtKRW(j.total_debit)}</td><td><span class="tag tag-open">OPEN</span></td>`;
    });
  }

  // AP 테이블 - journals
  const apTbody = document.getElementById('apTable');
  if (apTbody) {
    apTbody.innerHTML = '';
    (d.recent_journals || []).slice(0,5).forEach(j => {
      if (j.document_type !== 'KR') return;
      const tr = apTbody.insertRow();
      tr.innerHTML = `<td>${j.document_number}</td><td>Vendor</td><td>${fmtKRW(j.total_debit)}</td><td>NT30</td><td><span class="tag tag-open">OPEN</span></td>`;
    });
  }
}

function renderQuality(d) {
  const dev = d.quality_deviation || {};
  const oos = d.quality_oos || {};
  const comp = d.quality_complaint || {};
  const capa = d.quality_capa || {};

  setText('q-dev-total', dev.total_deviations || 0);
  setText('q-dev-breakdown', 'C/M/m: ' + (dev.critical||0)+'/'+(dev.major||0)+'/'+(dev.minor||0));
  setBadge('q-dev-badge', dev.open_dev > 0, dev.open_dev + '건 미결', 'badge-red', 'badge-green');

  setText('q-oos-total', oos.total_oos || 0);
  setText('q-oos-open', 'OPEN: ' + (oos.open_oos||0) + '건');
  setBadge('q-oos-badge', oos.open_oos > 0, oos.open_oos + '건 OPEN', 'badge-red', 'badge-green');

  setText('q-comp-total', comp.total_complaints || 0);
  setText('q-comp-open', 'OPEN: ' + (comp.open_complaints||0) + '건');
  setBadge('q-comp-badge', comp.critical_complaints > 0, 'Critical ' + comp.critical_complaints, 'badge-red', 'badge-blue');

  setText('q-capa-total', capa.total_capa || 0);
  setText('q-capa-od', '과기: ' + (capa.overdue_capa||0) + '건');
  setBadge('q-capa-badge', capa.overdue_capa > 0, '과기 ' + capa.overdue_capa, 'badge-red', 'badge-green');

  renderDevTable('devTableFull', d.recent_deviations || [], 8);

  // 품질 게이지
  const gaugeDiv = document.getElementById('qualGauge');
  if (gaugeDiv) {
    const total = dev.total_deviations || 1;
    const openPct = Math.round(((dev.open_dev||0) / total) * 100);
    const oosPct = Math.round(((oos.open_oos||0) / (oos.total_oos||1)) * 100);
    const capaPct = Math.round(((capa.overdue_capa||0) / (capa.total_capa||1)) * 100);
    gaugeDiv.innerHTML = `
      ${gauge('일탈 미결율', openPct, openPct > 50 ? '#f85149' : '#3fb950')}
      ${gauge('OOS 미결율', oosPct, oosPct > 50 ? '#f85149' : '#d29922')}
      ${gauge('CAPA 완료율', Math.round(((capa.completed_capa||0)/(capa.total_capa||1))*100), '#58a6ff')}
      ${gauge('CAPA 과기율', capaPct, capaPct > 20 ? '#f85149' : '#3fb950')}
    `;
  }

  // QM 로트
  renderLotTable('lotTable', d.inspection_lots || []);

  // CAPA 상태
  const capaDiv = document.getElementById('capaStatus');
  if (capaDiv) {
    capaDiv.innerHTML = `
      ${miniStat('총 CAPA', capa.total_capa)}
      ${miniStat('진행중', (capa.total_capa||0)-(capa.completed_capa||0)-(capa.overdue_capa||0))}
      ${miniStat('완료', capa.completed_capa)}
      ${miniStat('과기', capa.overdue_capa, true)}
    `;
  }
}

function renderProduction(d) {
  const prod = d.production || {};
  setText('p-total', prod.total || 0);
  setText('p-crtd', '생성: ' + (prod.created||0) + '건');
  setText('p-ip', prod.in_progress || 0);
  setText('p-teco', prod.completed || 0);
  setText('p-po-cnt', (d.open_pos || []).length);

  const poTbody = document.getElementById('poTable');
  if (poTbody) {
    poTbody.innerHTML = '';
    (d.open_pos || []).forEach(p => {
      const tr = poTbody.insertRow();
      tr.innerHTML = `<td>${p.po_id}</td><td>${p.vendor_id||'-'}</td><td>${p.po_date||''}</td><td>${fmtKRW(p.total_amount)}</td><td><span class="tag tag-open">${p.status||'OPEN'}</span></td>`;
    });
  }

  renderLotTable('lotTable2', d.inspection_lots || []);
}

function renderMonitor(d) {
  // KPI 스냅샷
  const snap = document.getElementById('kpiSnap');
  if (snap) {
    const s = d.sales || {};
    const dev = d.quality_deviation || {};
    const ar = d.finance_ar || {};
    snap.innerHTML = `
      ${miniStat('수주 건수', s.total_orders)}
      ${miniStat('수주 미결', s.open_orders)}
      ${miniStat('일탈 총', dev.total_deviations)}
      ${miniStat('일탈 미결', dev.open_dev, dev.open_dev > 0)}
      ${miniStat('Critical 일탈', dev.critical, dev.critical > 0)}
      ${miniStat('AR 미수금', ar.ar_open ? '₩'+fmt(ar.ar_open) : 0)}
    `;
  }

  // 일탈 모니터
  const devMon = document.getElementById('devMonitor');
  if (devMon) {
    devMon.innerHTML = (d.recent_deviations || []).map(dv =>
      `<div class="monitor-bar ${(dv.severity||'').toLowerCase()}">
        <span class="tag tag-${(dv.severity||'minor').toLowerCase()}">${dv.severity||'N/A'}</span>
        <span class="m-title">${dv.title||'-'}</span>
        <span class="tag ${dv.status === 'OPEN' ? 'tag-open' : 'tag-closed'}">${dv.status}</span>
        <span class="m-time">${(dv.detected_date||'').substring(0,10)}</span>
      </div>`
    ).join('');
  }

  // 재무 모니터
  const finMon = document.getElementById('finMonitor');
  const ar = d.finance_ar || {};
  const ap = d.finance_ap || {};
  const rv = (d.gl_by_type || []).find(x => x.document_type === 'RV');
  const kr = (d.gl_by_type || []).find(x => x.document_type === 'KR');
  if (finMon) {
    finMon.innerHTML = `
      ${miniStat('매출전표(RV) 차변', rv ? '₩'+fmt(rv.total_debit) : 0)}
      ${miniStat('매입전표(KR) 차변', kr ? '₩'+fmt(kr.total_debit) : 0)}
      ${miniStat('AR 미수금', ar.ar_open ? '₩'+fmt(ar.ar_open) : 0, (ar.ar_open||0) > 5000000)}
      ${miniStat('AP 미결', ap.ap_open ? '₩'+fmt(ap.ap_open) : 0)}
      ${miniStat('발생전표(accrual)', d.finance_ar ? '-' : '-')}
    `;
  }

  // 알림 피드 (새 데이터 있을 때만)
  const feed = document.getElementById('alertFeed');
  if (feed && eventCount % 3 === 1) {
    const dev = d.quality_deviation || {};
    const items = [];
    if (dev.critical > 0) items.push({icon:'🔴', title:'Critical 일탈 감지', desc:`${dev.critical}건 Critical 일탈 보고서 미결`, ts: new Date().toLocaleTimeString('ko-KR')});
    if ((d.quality_oos||{}).open_oos > 0) items.push({icon:'🟡', title:'OOS 미결 건 존재', desc:`${(d.quality_oos||{}).open_oos}건 규격 이탈 미결`, ts: new Date().toLocaleTimeString('ko-KR')});
    if ((d.quality_capa||{}).overdue_capa > 0) items.push({icon:'🟠', title:'CAPA 과기 알림', desc:`${(d.quality_capa||{}).overdue_capa}건 기한 초과`, ts: new Date().toLocaleTimeString('ko-KR')});
    items.push({icon:'🟢', title:'DB 동기화 완료', desc:`전체 KPI 갱신 (${d.timestamp ? d.timestamp.substring(11,19) : ''})`, ts: new Date().toLocaleTimeString('ko-KR')});

    const newItems = items.map(it =>
      `<div class="alert-item"><div class="alert-icon">${it.icon}</div><div class="alert-text"><div class="title">${it.title}</div><div class="desc">${it.desc}</div></div><div class="alert-time">${it.ts}</div></div>`
    ).join('');
    feed.insertAdjacentHTML('afterbegin', newItems);
    // 최대 20개 유지
    while (feed.children.length > 20) feed.removeChild(feed.lastChild);
  }
}

// ──────────────────────────────────────────
// Chart 렌더링
// ──────────────────────────────────────────
function renderCharts(d) {
  // 청구 추이
  const bt = d.billing_trend || [];
  destroyChart('billingChart');
  const btCtx = document.getElementById('billingChart');
  if (btCtx && bt.length) {
    charts['billingChart'] = new Chart(btCtx, {
      type: 'bar',
      data: {
        labels: bt.map(x => x.date ? x.date.substring(5) : ''),
        datasets: [{
          label: '일별 매출',
          data: bt.map(x => x.daily_revenue || 0),
          backgroundColor: 'rgba(88,166,255,.5)',
          borderColor: '#58a6ff',
          borderWidth: 1,
          borderRadius: 4,
        }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
  }

  // GL 전표 유형별
  const gl = d.gl_by_type || [];
  destroyChart('glTypeChart');
  const glCtx = document.getElementById('glTypeChart');
  if (glCtx && gl.length) {
    const typeLabel = { RV:'매출(RV)', KR:'매입(KR)', SA:'일반(SA)', AF:'감가(AF)', WA:'출고(WA)' };
    charts['glTypeChart'] = new Chart(glCtx, {
      type: 'doughnut',
      data: {
        labels: gl.map(x => typeLabel[x.document_type] || x.document_type),
        datasets: [{ data: gl.map(x => x.total_debit), backgroundColor: ['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff'], borderWidth: 2, borderColor: '#161b22' }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 12, padding: 8 } } } }
    });
  }

  // 영업 - 매출 차트 (같은 데이터 재사용)
  destroyChart('salesChart2');
  const sc2 = document.getElementById('salesChart2');
  if (sc2 && bt.length) {
    charts['salesChart2'] = new Chart(sc2, {
      type: 'line',
      data: {
        labels: bt.map(x => x.date ? x.date.substring(5) : ''),
        datasets: [{
          label: '매출액',
          data: bt.map(x => x.daily_revenue || 0),
          borderColor: '#3fb950',
          backgroundColor: 'rgba(63,185,80,.1)',
          fill: true, tension: 0.4, pointRadius: 4,
        }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
  }

  // AR/AP 차트
  destroyChart('arApChart');
  const aaCtx = document.getElementById('arApChart');
  const ar = d.finance_ar || {};
  const ap = d.finance_ap || {};
  if (aaCtx) {
    charts['arApChart'] = new Chart(aaCtx, {
      type: 'bar',
      data: {
        labels: ['AR 미수', 'AR 결제됨', 'AP 미결', 'AP 총액'],
        datasets: [{
          data: [ar.ar_open||0, ar.ar_cleared||0, ap.ap_open||0, ap.ap_total||0],
          backgroundColor: ['#f85149','#3fb950','#d29922','#58a6ff'],
          borderRadius: 4,
        }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, indexAxis: 'y' }
    });
  }

  // 일탈 심각도
  destroyChart('devSevChart');
  const dsCtx = document.getElementById('devSevChart');
  const dq = d.quality_deviation || {};
  if (dsCtx) {
    charts['devSevChart'] = new Chart(dsCtx, {
      type: 'pie',
      data: {
        labels: ['Critical','Major','Minor'],
        datasets: [{ data: [dq.critical||0, dq.major||0, dq.minor||0], backgroundColor: ['#f85149','#e3b341','#58a6ff'], borderWidth: 2, borderColor: '#161b22' }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 12 } } } }
    });
  }

  // 생산 유형
  destroyChart('prodTypeChart');
  const ptCtx = document.getElementById('prodTypeChart');
  const pt = d.production_by_type || [];
  if (ptCtx && pt.length) {
    charts['prodTypeChart'] = new Chart(ptCtx, {
      type: 'bar',
      data: {
        labels: pt.map(x => x.order_type),
        datasets: [
          { label: '계획 수량', data: pt.map(x => x.planned||0), backgroundColor: 'rgba(88,166,255,.5)', borderRadius: 4 },
          { label: '확인 수량', data: pt.map(x => x.confirmed||0), backgroundColor: 'rgba(63,185,80,.5)', borderRadius: 4 },
        ]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', labels: { boxWidth: 12 } } } }
    });
  }
}

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

// ──────────────────────────────────────────
// 유틸
// ──────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
function setBadge(id, isAlert, label, alertClass, okClass) {
  const el = document.getElementById(id);
  if (el) { el.textContent = label; el.className = 'badge ' + (isAlert ? alertClass : okClass); }
}
function renderDevTable(tbodyId, rows, limit) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  tbody.innerHTML = '';
  rows.slice(0, limit).forEach(r => {
    const tr = tbody.insertRow();
    const sev = (r.severity||'MINOR').toLowerCase();
    const sts = (r.status||'OPEN').toLowerCase();
    tr.innerHTML = `
      <td>${r.deviation_id||'-'}</td>
      <td>${r.title||'-'}</td>
      <td><span class="tag tag-${sev}">${r.severity||'-'}</span></td>
      <td><span class="tag ${r.status==='OPEN'?'tag-open':'tag-closed'}">${r.status||'-'}</span></td>
      <td>${(r.detected_date||'').substring(0,10)}</td>`;
  });
}
function renderJvTable(tbodyId, rows, limit) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  tbody.innerHTML = '';
  rows.slice(0, limit).forEach(r => {
    const tr = tbody.insertRow();
    const typeLabel = { RV:'매출', KR:'매입', SA:'일반', AF:'감가', WA:'출고', DZ:'수금' };
    tr.innerHTML = `
      <td>${r.document_number||'-'}</td>
      <td><span class="tag tag-inprog">${typeLabel[r.document_type]||r.document_type||'-'}</span></td>
      <td>${(r.posting_date||'').substring(0,10)}</td>
      <td>${fmtKRW(r.total_debit)}</td>`;
  });
}
function renderLotTable(tbodyId, rows) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  tbody.innerHTML = '';
  rows.forEach(r => {
    const tr = tbody.insertRow();
    tr.innerHTML = `<td>${r.lot_id||'-'}</td><td>${r.material_id||'-'}</td><td>${r.plant_id||'-'}</td><td><span class="tag tag-inprog">${r.lot_status||'-'}</span></td><td>${(r.planned_start||'').substring(0,10)}</td>`;
  });
}
function gauge(label, pct, color) {
  return `<div class="gauge-row">
    <span class="gauge-label">${label}</span>
    <div class="gauge-bar"><div class="gauge-fill" style="width:${pct}%;background:${color}"></div></div>
    <span class="gauge-val" style="color:${color}">${pct}%</span>
  </div>`;
}
function miniStat(label, val, isAlert) {
  return `<div class="mini-stat">
    <span class="ms-label">${label}</span>
    <span class="ms-val" style="${isAlert?'color:var(--red)':''}">${val ?? 0}</span>
  </div>`;
}

// ──────────────────────────────────────────
// KG 패널 데이터 로딩
// ──────────────────────────────────────────
let _kgLoaded = {ontology:false, kgraph:false, neo4j:false, vectorrag:false,
                 graphrag:false, sales:false, quality:false, production:false, monitor:false};
let _visNetwork = null;
let _vrDistChart = null;
let _vrCypherText = '';

function showPanel(name, tab) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  if (tab) tab.classList.add('active');
  if (kpiData) renderCharts(kpiData);
  // KG 패널 지연 로딩
  if (name === 'ontology'    && !_kgLoaded.ontology)    { loadOntology();    _kgLoaded.ontology=true;    }
  if (name === 'kgraph'      && !_kgLoaded.kgraph)      { loadKGraph();      _kgLoaded.kgraph=true;      }
  if (name === 'neo4j'       && !_kgLoaded.neo4j)       { loadNeo4j();       _kgLoaded.neo4j=true;       }
  if (name === 'vectorrag'   && !_kgLoaded.vectorrag)   { loadVectorRAG();   _kgLoaded.vectorrag=true;   }
  if (name === 'graphrag'    && !_kgLoaded.graphrag)    { runGraphRAG();     _kgLoaded.graphrag=true;    }
  // 비즈니스 탭 그래프 지연 로딩
  if (name === 'sales'       && !_kgLoaded.sales)       { loadTabGraph('sales',      'sales-g-canvas',  '_salesNet');  _kgLoaded.sales=true;       }
  if (name === 'quality'     && !_kgLoaded.quality)     { loadTabGraph('quality',    'quality-g-canvas','_qualNet');   _kgLoaded.quality=true;     }
  if (name === 'production'  && !_kgLoaded.production)  { loadTabGraph('production', 'prod-g-canvas',   '_prodNet');   _kgLoaded.production=true;  }
  if (name === 'monitor'     && !_kgLoaded.monitor)     { loadTabGraph('monitor',    'mon-g-canvas',    '_monNet');  loadInfraStatus();  _kgLoaded.monitor=true;     }
}

// ── OWL 온톨로지 ──
async function loadOntology() {
  const r = await fetch('/api/ontology');
  const d = await r.json();
  setText('onto-cls', d.class_count);
  setText('onto-op',  d.obj_prop_count);
  setText('onto-dp',  d.data_prop_count);

  // ── NetworkX 온톨로지 토폴로지 API에서 그래프 데이터 가져오기 ──
  let topoData;
  try {
    const tr = await fetch('/api/ontology/topology');
    topoData = await tr.json();
  } catch(e) { topoData = null; }

  if (topoData) {
    const topo = topoData.topology || {};
    const top5 = topoData.top_nodes || [];
    document.getElementById('onto-topo-panel').innerHTML = `
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px;padding:10px;background:var(--bg-secondary);border-radius:6px;border:1px solid var(--border);">
  <span style="color:var(--text-dim);font-size:11px;width:100%;font-weight:600;">NetworkX OWL 토폴로지 분석</span>
  <div class="topo-badge">클래스 <b>${topo.node_count||0}</b></div>
  <div class="topo-badge">관계 <b>${topo.edge_count||0}</b></div>
  <div class="topo-badge">밀도 <b>${(topo.density||0).toFixed(3)}</b></div>
  <div class="topo-badge">컴포넌트 <b>${topo.components||1}</b></div>
  <div class="topo-badge">최대CC <b>${topo.largest_component||0}</b></div>
  ${top5.length ? '<span style="color:var(--text-dim);font-size:11px;width:100%;margin-top:4px;">Top 중심 클래스 (PageRank)</span>' : ''}
  ${top5.map((n,i)=>`<div class="topo-badge" style="background:#161b22;">#${i+1} <b>${n.cls}</b> PR:${n.pagerank.toFixed(3)}</div>`).join('')}
</div>`;
    const ontoContainer = document.getElementById('onto-canvas');
    await new Promise(r => setTimeout(r, 150));
    if (window._ontoNet) { try { window._ontoNet.destroy(); } catch(e){} window._ontoNet = null; }
    const ontoNet = new vis.Network(ontoContainer,
      { nodes: new vis.DataSet(topoData.nodes), edges: new vis.DataSet(topoData.edges) },
      { physics: { barnesHut: { gravitationalConstant: -8000, springLength: 160, springConstant: 0.05, damping: 0.3 },
            stabilization: { iterations: 300 } },
        interaction: { hover: true, navigationButtons: true, keyboard: true, zoomView: true, tooltipDelay: 80 },
        nodes: { borderWidth: 2 }, edges: { width: 2 },
      });
    window._ontoNet = ontoNet;
    ontoNet.once('stabilizationIterationsDone', () => setTimeout(() => {
      const c = document.getElementById('onto-canvas');
      if (!c) return;
      ontoNet.setSize(c.offsetWidth + 'px', c.offsetHeight + 'px');
      ontoNet.redraw();
      const pos = ontoNet.getPositions();
      const keys = Object.keys(pos);
      if (!keys.length) return;
      const xs = keys.map(k => pos[k].x), ys = keys.map(k => pos[k].y);
      const cx = (Math.min(...xs)+Math.max(...xs))/2, cy = (Math.min(...ys)+Math.max(...ys))/2;
      const xRange = Math.max(...xs)-Math.min(...xs)+80, yRange = Math.max(...ys)-Math.min(...ys)+60;
      const scale = Math.min((c.offsetWidth-40)/xRange, (c.offsetHeight-60)/yRange, 2.0);
      ontoNet.moveTo({ position:{x:cx,y:cy}, scale, animation:false });
    }, 400));
  }

  // 클래스 알약
  const clsWrap = document.getElementById('onto-classes');
  const catColor = {Material:'material', Sales:'sales', Production:'production',
    Deviation:'quality', Oos:'quality', Product:'quality', Capa:'quality', Change:'quality', Inspection:'quality',
    Gl:'finance', Accounts:'finance', Accrual:'finance', Cost:'finance',
    Employee:'hr', Department:'hr', Leave:'hr', Plant:'finance', Company:'finance'};
  (d.classes||[]).forEach(c => {
    const cat = Object.keys(catColor).find(k => c.uri.startsWith(k)) || '';
    const div = document.createElement('span');
    div.className = 'pill ' + (catColor[cat]||'');
    div.textContent = c.uri;
    div.title = c.label;
    clsWrap.appendChild(div);
  });

  // 객체 속성
  const opWrap = document.getElementById('onto-obj-props');
  (d.object_properties||[]).forEach(p => {
    const div = document.createElement('div');
    div.className = 'onto-prop-row';
    div.textContent = p.uri;
    div.title = p.label;
    opWrap.appendChild(div);
  });

  // Turtle 스니펫
  document.getElementById('onto-turtle').textContent = d.turtle_snippet || '';

  // 데이터 속성 테이블
  const dpBody = document.getElementById('onto-data-props');
  (d.data_properties||[]).forEach((p, i) => {
    const tr = dpBody.insertRow();
    tr.innerHTML = `<td><code>${p.uri}</code></td><td><span class="tag tag-inprog">CKD class</span></td><td>${p.label}</td>`;
  });
}

// ── 지식 그래프 (NetworkX → vis.js) ──
async function loadKGraph() {
  const r = await fetch('/api/kg/graph');
  const d = await r.json();
  const vis_data = d.vis;
  const metrics  = d.metrics;

  // KPI
  setText('kg-nodes',   metrics.node_count);
  setText('kg-edges',   metrics.edge_count);
  setText('kg-density', metrics.density);
  setText('kg-wcc',     metrics.weakly_connected_components);

  // vis.js 네트워크
  const container = document.getElementById('kg-canvas');
  const options = {
    nodes: { size: 14, font: { color: '#c9d1d9', size: 11 }, borderWidth: 1 },
    edges: { arrows: { to: { enabled: true, scaleFactor: 0.5 } }, font: { color: '#8b949e', size: 9 }, smooth: { type: 'cubicBezier' } },
    physics: { stabilization: { iterations: 80 }, barnesHut: { gravitationalConstant: -3000, springLength: 120 } },
    interaction: { hover: true, navigationButtons: true, keyboard: true, tooltipDelay: 200 },
    layout: { improvedLayout: true },
  };
  if (typeof vis !== 'undefined') {
    const ds = new vis.DataSet(vis_data.nodes);
    const de = new vis.DataSet(vis_data.edges);
    _visNetwork = new vis.Network(container, { nodes: ds, edges: de }, options);
  } else {
    container.innerHTML = '<div style="padding:20px;color:var(--text-dim)">vis.js 로딩 중...</div>';
    setTimeout(loadKGraph, 2000);
    return;
  }

  // 범례
  const legendColors = {
    '자재(Material)':'#58a6ff','수주(SalesOrder)':'#3fb950','생산(ProdOrder)':'#bc8cff',
    '일탈(Deviation)':'#f85149','CAPA':'#ffa657','청구(Billing)':'#26a641',
    '세금계산서':'#39d353','GL전표':'#56d364','GL계정':'#7ee787','검사로트':'#ff7b72',
    '구매오더':'#d2a8ff','AR채권':'#1f6feb','코스트센터':'#cae8ff',
  };
  const lg = document.getElementById('kg-legend');
  Object.entries(legendColors).forEach(([label, color]) => {
    lg.innerHTML += `<div class="legend-item"><div class="legend-dot" style="background:${color}"></div><span style="font-size:10px">${label}</span></div>`;
  });

  // 노드 타입별 분포
  const typeDiv = document.getElementById('kg-type-dist');
  Object.entries(metrics.type_counts||{}).sort((a,b)=>b[1]-a[1]).forEach(([t,c]) => {
    typeDiv.innerHTML += miniStat(t, c);
  });

  // PageRank 상위
  const prDiv = document.getElementById('kg-pagerank');
  (metrics.top_pagerank_nodes||[]).slice(0,7).forEach((n,i) => {
    prDiv.innerHTML += `<div class="mini-stat"><span class="ms-label">${i+1}. ${n.label}</span><span class="ms-val" style="font-size:10px">PR ${n.pagerank.toFixed(5)}</span></div>`;
  });

  // 관계 타입 알약
  const relDiv = document.getElementById('kg-rel-counts');
  Object.entries(metrics.rel_counts||{}).forEach(([rel, cnt]) => {
    relDiv.innerHTML += `<span class="pill">${rel} <strong>${cnt}</strong></span>`;
  });
}

// ── Neo4j ──
async function loadNeo4j() {
  const r = await fetch('/api/neo4j/preview');
  const d = await r.json();

  const statusEl = document.getElementById('neo4j-status-val');
  statusEl.textContent = d.neo4j_connected ? '● 연결됨' : '○ 오프라인';
  statusEl.className = d.neo4j_connected ? 'neo4j-connected' : 'neo4j-offline';
  setText('neo4j-uri', d.neo4j_uri);
  setText('neo4j-lines', d.script_lines);
  setText('neo4j-nodes', d.node_statements);
  setText('neo4j-rels',  d.relationship_statements);

  // 인덱스 제약
  document.getElementById('neo4j-constraints').textContent = (d.sample_queries||[]).map(q=>
    `// ${q.title}\n${q.cypher}`
  ).join('\n\n');

  // 스크립트 미리보기
  _vrCypherText = d.script_preview || '';
  document.getElementById('neo4j-script').textContent = _vrCypherText;

  // 샘플 쿼리 카드
  const qDiv = document.getElementById('neo4j-queries');
  (d.sample_queries||[]).forEach(q => {
    qDiv.innerHTML += `<div class="monitor-bar" style="flex-direction:column;align-items:flex-start;margin-bottom:6px;">
      <div style="font-weight:700;font-size:11px;color:var(--accent);margin-bottom:4px;">${q.title}</div>
      <code style="font-size:10px;color:#79c0ff;background:var(--bg);padding:4px 8px;border-radius:4px;width:100%;">${q.cypher}</code>
    </div>`;
  });

  // ── Neo4j 스타일 그래프 (KG 데이터 재활용, Neo4j 컬러 팔레트) ──
  const NEO4J_COLORS = {
    Material:'#4A90D9', SalesOrder:'#57B55D', ProductionOrder:'#D4A843',
    DeviationReport:'#E05A4F', CapaAction:'#E8812A', BillingDocument:'#7B68EE',
    Invoice:'#20B2AA', GlAccount:'#3CB371', GlPosting:'#228B22',
    CostCenter:'#6B8E23', InspectionLot:'#CD853F', AccountsReceivable:'#4682B4',
    PurchaseOrder:'#9370DB', default:'#708090',
  };
  const kgR = await fetch('/api/kg/graph');
  const kgD = await kgR.json();
  const neo4jNodes = new vis.DataSet((kgD.vis.nodes||[]).map(n => {
    const col = NEO4J_COLORS[n.group] || NEO4J_COLORS.default;
    return { ...n, color: { background: col, border: '#fff4', highlight: { background: col, border: '#fff' } },
      shape: 'ellipse', size: 18,
      font: { color: '#fff', size: 12, bold: true, strokeWidth: 2, strokeColor: '#00000088' },
      borderWidth: 2 };
  }));
  const neo4jEdges = new vis.DataSet((kgD.vis.edges||[]).map(e => ({
    ...e, color: { color: '#4A4A5A88', highlight: '#4A90D9' },
    font: { color: '#9aa3af', size: 10, strokeWidth: 2, strokeColor: '#0d1117' },
    arrows: { to: { scaleFactor: 0.6 } }, width: 1.5,
  })));
  const _neo4jC = document.getElementById('neo4j-canvas');
  const neo4jNet = new vis.Network(_neo4jC,
    { nodes: neo4jNodes, edges: neo4jEdges },
    { physics: { barnesHut: { gravitationalConstant: -3000, springLength: 80, springConstant: 0.08, damping: 0.3 }, stabilization: { iterations: 150 } },
      interaction: { hover: true, navigationButtons: true, zoomView: true },
      nodes: { borderWidth: 2 }, edges: { smooth: { type: 'continuous' }, width: 1.5 } });
  neo4jNet.once('stabilizationIterationsDone', () => setTimeout(() => {
    const c = document.getElementById('neo4j-canvas');
    neo4jNet.setSize(c.offsetWidth+'px', c.offsetHeight+'px'); neo4jNet.redraw();
    const pos = neo4jNet.getPositions(); const keys = Object.keys(pos);
    if (!keys.length) return;
    const xs = keys.map(k=>pos[k].x), ys = keys.map(k=>pos[k].y);
    const cx=(Math.min(...xs)+Math.max(...xs))/2, cy=(Math.min(...ys)+Math.max(...ys))/2;
    const scale = Math.min((c.offsetWidth-40)/(Math.max(...xs)-Math.min(...xs)+60), (c.offsetHeight-80)/(Math.max(...ys)-Math.min(...ys)+40), 2.5);
    neo4jNet.moveTo({ position:{x:cx,y:cy}, scale, animation:false });
  }, 500));
}

function downloadCypher() {
  fetch('/api/neo4j/cypher')
    .then(r => r.text())
    .then(txt => {
      const blob = new Blob([txt], {type:'text/plain'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'ckd_next_neo4j.cypher';
      a.click();
    });
}

// ── Vector RAG ──
async function loadVectorRAG() {
  const statsR = await fetch('/api/vectorrag/stats');
  const stats = await statsR.json();
  setText('vr-docs',  stats.total_documents);
  setText('vr-vocab', stats.vocabulary_size);
  setText('vr-shape', stats.matrix_shape ? stats.matrix_shape.join(' × ') : '-');

  // 분포 차트
  destroyChart('vrDistChart');
  const ctx = document.getElementById('vrDistChart');
  const dist = stats.entity_type_distribution || {};
  if (ctx && Object.keys(dist).length) {
    charts['vrDistChart'] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: Object.keys(dist),
        datasets: [{ data: Object.values(dist), backgroundColor: '#58a6ff88', borderColor: '#58a6ff', borderRadius: 4 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, indexAxis: 'y' }
    });
  }

  // 초기 검색
  runVectorSearch();
}

let _vrNetwork = null;
async function runVectorSearch() {
  const q = document.getElementById('vr-query').value;
  const r = await fetch(`/api/vectorrag/search?q=${encodeURIComponent(q)}&top_k=12`);
  const d = await r.json();
  const resDiv = document.getElementById('vr-results');
  resDiv.innerHTML = '';
  (d.results||[]).forEach(item => {
    resDiv.innerHTML += `<div class="vec-result">
      <span class="vec-score">cosine: ${item.score}</span>
      <div class="vec-type">${item.entity_type} | ${item.doc_id}</div>
      <div class="vec-text">${item.text}</div>
    </div>`;
  });

  // ── 유사도 네트워크 그래프 ──
  const VR_COLORS = {
    Material:'#58a6ff', DeviationReport:'#f85149', CapaAction:'#ffa657',
    GlPosting:'#3fb950', ProductionOrder:'#d2a8ff', SalesOrder:'#39d353',
    ProductComplaint:'#ff7b72', ChangeControl:'#e3b341', GlAccount:'#7ee787',
  };
  const results = d.results || [];
  const vrNodes = new vis.DataSet([
    { id: '__query__', label: q.substring(0,18)+'…', shape:'diamond',
      color: { background:'#f0883e', border:'#fff' }, size: 22,
      font: { color:'#fff', size: 12, bold: true } },
    ...results.map((item, i) => ({
      id: item.doc_id, label: item.doc_id,
      title: `[${item.entity_type}] score:${item.score}\n${item.text.substring(0,80)}`,
      shape: 'dot', size: 14 + Math.round(item.score * 40),
      color: { background: VR_COLORS[item.entity_type]||'#8b949e', border:'#fff4',
               highlight: { background: VR_COLORS[item.entity_type]||'#8b949e', border:'#fff' } },
      font: { color:'#e6edf3', size: 12, bold: true, strokeWidth: 2, strokeColor: '#0d1117' },
    }))
  ]);
  const vrEdges = new vis.DataSet(results.map((item, i) => ({
    id: i, from: '__query__', to: item.doc_id,
    label: String(item.score),
    width: 1 + item.score * 4,
    color: { color: VR_COLORS[item.entity_type]+'88' || '#58a6ff44', highlight: VR_COLORS[item.entity_type]||'#58a6ff' },
    font: { color:'#8b949e', size: 8 },
    arrows: { to: { enabled: false } },
    smooth: { type: 'curvedCW', roundness: 0.3 },
  })));
  if (_vrNetwork) _vrNetwork.destroy();
  _vrNetwork = new vis.Network(document.getElementById('vr-canvas'),
    { nodes: vrNodes, edges: vrEdges },
    { physics: { barnesHut: { gravitationalConstant: -4000, springLength: 130, damping: 0.2 }, stabilization: { iterations: 100 } },
      interaction: { hover: true, navigationButtons: true, tooltipDelay: 100, zoomView: true },
      nodes: { borderWidth: 2 }, edges: { smooth: { type: 'curvedCW', roundness: 0.3 }, width: 2 } });
  _vrNetwork.once('stabilizationIterationsDone', () => setTimeout(() => {
    const c = document.getElementById('vr-canvas');
    _vrNetwork.setSize(c.offsetWidth+'px', c.offsetHeight+'px'); _vrNetwork.redraw();
    const pos = _vrNetwork.getPositions(); const keys = Object.keys(pos);
    if (!keys.length) return;
    const xs = keys.map(k=>pos[k].x), ys = keys.map(k=>pos[k].y);
    const cx=(Math.min(...xs)+Math.max(...xs))/2, cy=(Math.min(...ys)+Math.max(...ys))/2;
    const scale = Math.min((c.offsetWidth-40)/(Math.max(...xs)-Math.min(...xs)+60), (c.offsetHeight-80)/(Math.max(...ys)-Math.min(...ys)+60), 3.0);
    _vrNetwork.moveTo({ position:{x:cx,y:cy}, scale, animation:false });
  }, 500));
}

function vrQuickSearch(q) {
  document.getElementById('vr-query').value = q;
  runVectorSearch();
}

// ── GraphRAG ──
async function runGraphRAG() {
  const q = document.getElementById('gr-query').value;
  document.getElementById('gr-results-wrap').style.display = 'none';
  document.getElementById('gr-stats-row').style.display = 'none';
  document.getElementById('gr-fused').innerHTML = '<div style="color:var(--text-dim);padding:10px;">검색 중...</div>';

  const r = await fetch(`/api/graphrag/query?q=${encodeURIComponent(q)}&top_k=10`);
  const d = await r.json();

  // 통계
  document.getElementById('gr-stats-row').style.display = 'grid';
  setText('gr-domain', d.domain);
  setText('gr-v-hits', d.stats?.vector_hits || 0);
  setText('gr-g-hits', d.stats?.graph_hits || 0);

  // 융합 결과
  const fusedDiv = document.getElementById('gr-fused');
  fusedDiv.innerHTML = '';
  (d.fused_results||[]).forEach(item => {
    const srcClass = item.source === 'vector+graph' ? 'src-both' : (item.source === 'vector' ? 'src-vector' : 'src-graph');
    fusedDiv.innerHTML += `<div class="fused-item">
      <div class="fused-rank" style="background:var(--accent);color:#000">${item.rank}</div>
      <div style="flex:1">
        <div style="font-weight:600;font-size:12px">${item.doc_id}</div>
        <div style="color:var(--text-dim);font-size:10px">${item.text||''}</div>
      </div>
      <span class="source-badge ${srcClass}">${item.source||''}</span>
      <span style="color:var(--text-dim);font-size:10px">${item.rrf_score||''}</span>
    </div>`;
  });

  // Graph 이웃
  const gDiv = document.getElementById('gr-graph-hits');
  gDiv.innerHTML = '';
  (d.graph_neighbors||[]).forEach(n => {
    gDiv.innerHTML += `<div class="monitor-bar">
      <span class="tag tag-inprog">${n.type}</span>
      <span class="m-title">${n.label}</span>
      <span class="m-time">hop:${n.hop}</span>
    </div>`;
  });

  // RAG Prompt
  document.getElementById('gr-prompt').textContent = d.rag_prompt || '';

  document.getElementById('gr-results-wrap').style.display = 'grid';

  // ── GraphRAG 융합 네트워크 그래프 ──
  const GR_SRC_COLOR = { vector:'#58a6ff', graph:'#3fb950', 'vector+graph':'#ffa657' };
  const GR_TYPE_COLOR = {
    Material:'#388bfd', SalesOrder:'#2ea043', ProductionOrder:'#e3b341',
    DeviationReport:'#f85149', CapaAction:'#ff6e40', GlPosting:'#56d364',
    GlAccount:'#7ee787', BillingDocument:'#bc8cff', InspectionLot:'#d2a8ff',
    AccountsReceivable:'#4682B4', PurchaseOrder:'#9370DB',
  };
  const grNodes = new vis.DataSet();
  const grEdges = new vis.DataSet();
  // 쿼리 노드
  grNodes.add({ id:'__q__', label: q.substring(0,16)+'…', shape:'star', size:28,
    color:{background:'#f0883e',border:'#fff'}, font:{color:'#fff',size:13,bold:true} });
  // 융합 결과 노드
  (d.fused_results||[]).forEach((item, i) => {
    const col = GR_SRC_COLOR[item.source] || '#8b949e';
    if (!grNodes.get(item.doc_id)) {
      grNodes.add({ id: item.doc_id, label: `#${item.rank} ${item.doc_id}`,
        title: `[${item.source}] RRF:${item.rrf_score||''}\n${(item.text||'').substring(0,80)}`,
        shape:'dot', size: 14 - i, color:{background:col,border:'#fff2',highlight:{background:col,border:'#fff'}},
        font:{color:'#e6edf3', size:10} });
    }
    grEdges.add({ id:'v'+i, from:'__q__', to: item.doc_id,
      color:{color:col+'88',highlight:col}, width:2-(i*0.1),
      arrows:{to:{enabled:false}}, smooth:{type:'dynamic'} });
  });
  // 그래프 이웃 노드 추가
  (d.graph_neighbors||[]).forEach((n, i) => {
    const nid = 'gn:'+n.label;
    const col = GR_TYPE_COLOR[n.type] || '#8b949e';
    if (!grNodes.get(nid)) {
      grNodes.add({ id:nid, label: n.label.substring(0,16),
        title: `[${n.type}] hop:${n.hop}`, shape:'square', size:9,
        color:{background:col+'cc',border:'#fff1',highlight:{background:col,border:'#fff'}},
        font:{color:'#c9d1d9',size:9} });
      // 가장 관련성 있는 융합 결과에 연결 시도
      const relFused = (d.fused_results||[]).find(f => f.doc_id && n.label && (f.doc_id.includes(n.label) || n.label.includes(f.doc_id.replace(/\D+/,''))));
      const linkTarget = relFused ? relFused.doc_id : '__q__';
      grEdges.add({ id:'gn'+i, from:linkTarget, to:nid,
        color:{color:col+'55'}, width:1, dashes:true,
        arrows:{to:{enabled:true,scaleFactor:0.4}}, smooth:{type:'curvedCW',roundness:0.4} });
    }
  });
  document.getElementById('gr-graph-wrap').style.display = 'block';
  const grNet = new vis.Network(document.getElementById('gr-canvas'),
    { nodes: grNodes, edges: grEdges },
    { physics: { barnesHut:{ gravitationalConstant:-4000, springLength:160, damping:0.15 },
        stabilization:{ iterations:120 } },
      interaction: { hover:true, navigationButtons:true, tooltipDelay:100 },
      nodes:{ borderWidth:1 }, edges:{ smooth:{ type:'dynamic' } } });
  grNet.once('stabilizationIterationsDone', () => setTimeout(() => {
    const c = document.getElementById('gr-canvas');
    grNet.setSize(c.offsetWidth+'px', c.offsetHeight+'px'); grNet.redraw();
    const pos = grNet.getPositions(); const keys = Object.keys(pos);
    if (!keys.length) return;
    const xs = keys.map(k=>pos[k].x), ys = keys.map(k=>pos[k].y);
    const cx=(Math.min(...xs)+Math.max(...xs))/2, cy=(Math.min(...ys)+Math.max(...ys))/2;
    const scale = Math.min((c.offsetWidth-40)/(Math.max(...xs)-Math.min(...xs)+60), (c.offsetHeight-80)/(Math.max(...ys)-Math.min(...ys)+60), 3.0);
    grNet.moveTo({ position:{x:cx,y:cy}, scale, animation:false });
  }, 500));
}

function grQuick(q) {
  document.getElementById('gr-query').value = q;
  runGraphRAG();
}

// ──────────────────────────────────────────
// 초기화
// ──────────────────────────────────────────
window.onload = () => {
  connectWS();
  // 30초 간격으로 인프라 상태 갱신
  setInterval(loadInfraStatus, 30000);
};
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8765, reload=False, log_level="info")
