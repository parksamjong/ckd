"""
CKD-NEXT 지식 그래프 빌더
PostgreSQL → NetworkX DiGraph + RDF 인스턴스 트리플
"""
import json
from typing import Any
import networkx as nx
import psycopg2
import psycopg2.extras
from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef, XSD

CKD = Namespace("http://ckd-next.co.kr/ontology/")
INST = Namespace("http://ckd-next.co.kr/instance/")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "database": "ckd_next", "user": "postgres", "password": "1234",
}

# ─────────────────────────────────────────────────────────────
# 노드 타입별 색상·아이콘 (vis.js 시각화용)
# ─────────────────────────────────────────────────────────────
NODE_STYLES = {
    "Material":        {"color": "#58a6ff", "shape": "dot",     "group": "material"},
    "SalesOrder":      {"color": "#3fb950", "shape": "square",  "group": "sales"},
    "ProductionOrder": {"color": "#bc8cff", "shape": "diamond", "group": "production"},
    "DeviationReport": {"color": "#f85149", "shape": "star",    "group": "quality"},
    "Employee":        {"color": "#e3b341", "shape": "dot",     "group": "hr"},
    "Customer":        {"color": "#79c0ff", "shape": "triangle","group": "sales"},
    "Vendor":          {"color": "#ffa657", "shape": "triangle","group": "procurement"},
    "PurchaseOrder":   {"color": "#d2a8ff", "shape": "square",  "group": "procurement"},
    "GlPosting":       {"color": "#56d364", "shape": "box",     "group": "finance"},
    "GlAccount":       {"color": "#7ee787", "shape": "ellipse", "group": "finance"},
    "Invoice":         {"color": "#39d353", "shape": "box",     "group": "finance"},
    "BillingDocument": {"color": "#26a641", "shape": "square",  "group": "finance"},
    "InspectionLot":   {"color": "#ff7b72", "shape": "diamond", "group": "quality"},
    "CapaAction":      {"color": "#ffa198", "shape": "star",    "group": "quality"},
    "CostCenter":      {"color": "#cae8ff", "shape": "dot",     "group": "finance"},
    "AccountsReceivable":{"color": "#1f6feb","shape":"box",     "group": "finance"},
    "AccountsPayable": {"color": "#388bfd", "shape": "box",     "group": "finance"},
}

EDGE_COLORS = {
    "CONTAINS":    "#3fb950",
    "PRODUCES":    "#bc8cff",
    "HAS_DEVIATION":"#f85149",
    "HAS_CAPA":    "#ffa657",
    "PLACED_BY":   "#79c0ff",
    "BILLS":       "#26a641",
    "INVOICES":    "#39d353",
    "POSTED_TO":   "#56d364",
    "INSPECTS":    "#ff7b72",
    "SUPPLIED_BY": "#ffa657",
    "HAS_AR":      "#1f6feb",
    "HAS_AP":      "#388bfd",
    "BELONGS_TO_CC":"#cae8ff",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


# ─────────────────────────────────────────────────────────────
# NetworkX 그래프 빌더
# ─────────────────────────────────────────────────────────────
def build_networkx_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    conn = get_conn()
    cur = conn.cursor()

    # ── 자재 노드 ──
    cur.execute("""
        SELECT mm.material_id, mm.material_no, mm.material_type_code,
               mm.material_group_code, mm.base_uom,
               md.material_desc, md.short_desc
        FROM material_master mm
        LEFT JOIN material_description md
          ON md.material_id = mm.material_id AND md.language_code = 'KO'
        LIMIT 30
    """)
    for r in cur.fetchall():
        nid = f"MAT:{r['material_id']}"
        label = r['short_desc'] or r['material_desc'] or r['material_no'] or str(r['material_id'])
        G.add_node(nid, type="Material", label=label[:22],
                   data={"material_id": str(r['material_id']), "no": r['material_no'],
                         "type": r['material_type_code'], "group": r['material_group_code']},
                   **NODE_STYLES.get("Material", {}))

    # ── 수주 노드 ──
    cur.execute("SELECT order_id, order_no, overall_status, total_net_amount FROM sales_order LIMIT 20")
    for r in cur.fetchall():
        nid = f"SO:{r['order_id']}"
        G.add_node(nid, type="SalesOrder", label=f"SO {r['order_no'][-4:] if r['order_no'] else r['order_id']}",
                   data={"order_id": str(r['order_id']), "status": r['overall_status'], "amount": float(r['total_net_amount'] or 0)},
                   **NODE_STYLES.get("SalesOrder", {}))

    # material_no → node_id 역매핑 (material_no 기반 FK 연결용)
    matno_to_nid = {}
    for nid, attrs in list(G.nodes(data=True)):
        if attrs.get("type") == "Material":
            matno_to_nid[attrs["data"].get("no", "")] = nid

    # ── 수주 라인 → 자재 연결 ──
    cur.execute("""
        SELECT soi.order_id, soi.material_id AS mat_no
        FROM sales_order_item soi
        JOIN material_master mm ON mm.material_id = soi.material_id
        LIMIT 30
    """)
    for r in cur.fetchall():
        src = f"SO:{r['order_id']}"
        tgt = f"MAT:{r['mat_no']}"  # mat_no here is actually material_master.material_id (bigint)
        # Try lookup by material_master.material_id (bigint)
        tgt2 = f"MAT:{r['mat_no']}"
        if G.has_node(src) and G.has_node(tgt2):
            G.add_edge(src, tgt2, rel="CONTAINS", color=EDGE_COLORS["CONTAINS"], label="포함")

    # ── 생산 오더 노드 ──
    cur.execute("""
        SELECT po.prod_order_id, po.material_id AS mat_no, po.status, po.order_qty,
               mm.material_id AS mm_id
        FROM production_order po
        LEFT JOIN material_master mm ON mm.material_no = po.material_id
        LIMIT 20
    """)
    for r in cur.fetchall():
        nid = f"PO:{r['prod_order_id']}"
        G.add_node(nid, type="ProductionOrder", label=f"PO {str(r['prod_order_id'])[-6:]}",
                   data={"order_id": str(r['prod_order_id']), "status": r['status'],
                         "qty": float(r['order_qty'] or 0), "mat_no": r['mat_no']},
                   **NODE_STYLES.get("ProductionOrder", {}))
        # 생산 오더 → 자재 (material_no 기반)
        mat_nid = matno_to_nid.get(r['mat_no'])
        if not mat_nid and r['mm_id']:
            mat_nid = f"MAT:{r['mm_id']}"
        if mat_nid and G.has_node(mat_nid):
            G.add_edge(nid, mat_nid, rel="PRODUCES", color=EDGE_COLORS["PRODUCES"], label="생산")

    # ── 일탈 보고서 노드 ──
    cur.execute("""
        SELECT dr.deviation_id, dr.severity, dr.status,
               dr.production_order_id, dr.material_id AS mat_no, dr.description,
               mm.material_id AS mm_id
        FROM deviation_report dr
        LEFT JOIN material_master mm ON mm.material_no = dr.material_id
        LIMIT 20
    """)
    for r in cur.fetchall():
        nid = f"DEV:{r['deviation_id']}"
        desc = (r['description'] or '')[:20]
        G.add_node(nid, type="DeviationReport", label=f"DEV {r['deviation_id'][-4:]}",
                   data={"id": r['deviation_id'], "severity": r['severity'], "status": r['status'], "desc": desc},
                   **NODE_STYLES.get("DeviationReport", {}))
        if r['production_order_id']:
            po_nid = f"PO:{r['production_order_id']}"
            if G.has_node(po_nid):
                G.add_edge(po_nid, nid, rel="HAS_DEVIATION", color=EDGE_COLORS["HAS_DEVIATION"], label="일탈")
        mat_nid = matno_to_nid.get(r['mat_no'])
        if not mat_nid and r['mm_id']:
            mat_nid = f"MAT:{r['mm_id']}"
        if mat_nid and G.has_node(mat_nid):
            G.add_edge(nid, mat_nid, rel="RELATES_TO", color="#8b949e", label="관련자재")

    # ── CAPA 노드 ──
    cur.execute("SELECT action_id, capa_id, status, action_type, target_date::text FROM capa_action LIMIT 15")
    for r in cur.fetchall():
        nid = f"CAPA:{r['action_id']}"
        G.add_node(nid, type="CapaAction", label=f"CAPA {str(r['action_id'])[-3:]}",
                   data={"id": str(r['action_id']), "status": r['status'], "type": r['action_type']},
                   **NODE_STYLES.get("CapaAction", {}))
        # CAPA → DeviationReport
        dev_nid = f"DEV:{r['capa_id']}"
        if G.has_node(dev_nid):
            G.add_edge(dev_nid, nid, rel="HAS_CAPA", color=EDGE_COLORS["HAS_CAPA"], label="CAPA")

    # ── 청구 문서 노드 ──
    cur.execute("SELECT billing_id, billing_type, total_value, billing_status FROM billing_document LIMIT 10")
    for r in cur.fetchall():
        nid = f"BL:{r['billing_id']}"
        G.add_node(nid, type="BillingDocument", label=f"BL {r['billing_id'][-4:]}",
                   data={"id": r['billing_id'], "status": r['billing_status'], "amount": float(r['total_value'] or 0)},
                   **NODE_STYLES.get("BillingDocument", {}))

    # ── 세금계산서 노드 + 청구 연결 ──
    cur.execute("SELECT invoice_id, billing_id, total_amount, invoice_status FROM invoice LIMIT 10")
    for r in cur.fetchall():
        nid = f"INV:{r['invoice_id']}"
        G.add_node(nid, type="Invoice", label=f"INV {r['invoice_id'][-4:]}",
                   data={"id": r['invoice_id'], "status": r['invoice_status'], "amount": float(r['total_amount'] or 0)},
                   **NODE_STYLES.get("Invoice", {}))
        bl_nid = f"BL:{r['billing_id']}"
        if G.has_node(bl_nid):
            G.add_edge(bl_nid, nid, rel="INVOICES", color=EDGE_COLORS["INVOICES"], label="계산서")

    # ── GL 계정 노드 ──
    cur.execute("SELECT account_id, account_name_short, account_type FROM gl_account_master LIMIT 18")
    for r in cur.fetchall():
        nid = f"ACC:{r['account_id']}"
        G.add_node(nid, type="GlAccount", label=f"{r['account_id']} {(r['account_name_short'] or '')[:10]}",
                   data={"id": r['account_id'], "name": r['account_name_short'], "type": r['account_type']},
                   **NODE_STYLES.get("GlAccount", {}))

    # ── GL 전표 노드 (document 단위, 라인 아님) ──
    cur.execute("""
        SELECT DISTINCT document_number, document_type, posting_date::text,
               SUM(COALESCE(debit_amount,0)) AS total_debit,
               MIN(account_id) AS primary_account
        FROM gl_posting
        GROUP BY document_number, document_type, posting_date
        LIMIT 15
    """)
    for r in cur.fetchall():
        nid = f"JV:{r['document_number']}"
        G.add_node(nid, type="GlPosting", label=f"JV {r['document_number'][-4:]}",
                   data={"id": r['document_number'], "type": r['document_type'],
                         "date": r['posting_date'], "amount": float(r['total_debit'] or 0)},
                   **NODE_STYLES.get("GlPosting", {}))
        acc_nid = f"ACC:{r['primary_account']}"
        if G.has_node(acc_nid):
            G.add_edge(nid, acc_nid, rel="POSTED_TO", color=EDGE_COLORS["POSTED_TO"], label="계정귀속")

    # ── 코스트센터 노드 ──
    cur.execute("SELECT cost_center_id, cost_center_name FROM cost_center LIMIT 10")
    for r in cur.fetchall():
        nid = f"CC:{r['cost_center_id']}"
        G.add_node(nid, type="CostCenter", label=f"CC {r['cost_center_id']}",
                   data={"id": r['cost_center_id'], "name": r['cost_center_name']},
                   **NODE_STYLES.get("CostCenter", {}))

    # 전표 → 코스트센터
    cur.execute("""
        SELECT DISTINCT document_number, cost_center_id
        FROM gl_posting WHERE cost_center_id IS NOT NULL LIMIT 15
    """)
    for r in cur.fetchall():
        jv_nid = f"JV:{r['document_number']}"
        cc_nid = f"CC:{r['cost_center_id']}"
        if G.has_node(jv_nid) and G.has_node(cc_nid):
            G.add_edge(jv_nid, cc_nid, rel="BELONGS_TO_CC", color=EDGE_COLORS["BELONGS_TO_CC"], label="코센터")

    # ── 검사 로트 노드 ──
    cur.execute("""
        SELECT ql.lot_id, ql.material_id AS mat_no, ql.plant_id, ql.usage_decision,
               mm.material_id AS mm_id
        FROM qm_inspection_lot ql
        LEFT JOIN material_master mm ON mm.material_no = ql.material_id
        LIMIT 8
    """)
    for r in cur.fetchall():
        nid = f"LOT:{r['lot_id']}"
        G.add_node(nid, type="InspectionLot", label=f"LOT {r['lot_id'][-4:] if len(r['lot_id']) > 4 else r['lot_id']}",
                   data={"id": r['lot_id'], "plant": r['plant_id'], "decision": r['usage_decision']},
                   **NODE_STYLES.get("InspectionLot", {}))
        mat_nid = matno_to_nid.get(r['mat_no'])
        if not mat_nid and r['mm_id']:
            mat_nid = f"MAT:{r['mm_id']}"
        if mat_nid and G.has_node(mat_nid):
            G.add_edge(nid, mat_nid, rel="INSPECTS", color=EDGE_COLORS["INSPECTS"], label="검사")

    # ── 매출채권 노드 ──
    cur.execute("SELECT ar_id, invoice_id, open_amount, ar_status FROM accounts_receivable WHERE open_amount > 0 LIMIT 8")
    for r in cur.fetchall():
        nid = f"AR:{r['ar_id']}"
        G.add_node(nid, type="AccountsReceivable", label=f"AR {str(r['ar_id'])[-3:]}",
                   data={"id": str(r['ar_id']), "status": r['ar_status'], "amount": float(r['open_amount'] or 0)},
                   **NODE_STYLES.get("AccountsReceivable", {}))
        inv_nid = f"INV:{r['invoice_id']}"
        if G.has_node(inv_nid):
            G.add_edge(nid, inv_nid, rel="HAS_AR", color=EDGE_COLORS["HAS_AR"], label="채권")

    # ── 구매 오더 노드 ──
    cur.execute("SELECT po_id, vendor_id, po_status, total_value FROM purchase_order LIMIT 8")
    for r in cur.fetchall():
        nid = f"PORD:{r['po_id']}"
        G.add_node(nid, type="PurchaseOrder", label=f"PO {r['po_id'][-4:]}",
                   data={"id": r['po_id'], "vendor": r['vendor_id'], "status": r['po_status'],
                         "amount": float(r['total_value'] or 0)},
                   **NODE_STYLES.get("PurchaseOrder", {}))

    conn.close()
    return G


def graph_to_visjs(G: nx.DiGraph) -> dict:
    """NetworkX → vis.js Network JSON 변환"""
    nodes = []
    edges = []
    node_ids = {}

    for i, (nid, attrs) in enumerate(G.nodes(data=True)):
        node_ids[nid] = i
        style = NODE_STYLES.get(attrs.get("type", ""), {"color": "#8b949e", "shape": "dot"})
        nodes.append({
            "id": i,
            "label": attrs.get("label", nid)[:20],
            "title": json.dumps(attrs.get("data", {}), ensure_ascii=False, default=str),
            "color": {"background": style.get("color", "#8b949e"),
                      "border": "#30363d",
                      "highlight": {"background": "#fff", "border": style.get("color", "#8b949e")}},
            "shape": style.get("shape", "dot"),
            "group": style.get("group", "default"),
            "type": attrs.get("type", "Unknown"),
        })

    for i, (src, tgt, attrs) in enumerate(G.edges(data=True)):
        if src in node_ids and tgt in node_ids:
            edges.append({
                "id": i,
                "from": node_ids[src],
                "to": node_ids[tgt],
                "label": attrs.get("label", ""),
                "color": {"color": attrs.get("color", "#8b949e"), "opacity": 0.8},
                "arrows": "to",
                "rel": attrs.get("rel", ""),
            })

    return {"nodes": nodes, "edges": edges}


def graph_metrics(G: nx.DiGraph) -> dict:
    """그래프 분석 지표"""
    try:
        # 중심성 계산
        in_deg = dict(G.in_degree())
        out_deg = dict(G.out_degree())
        # PageRank
        pr = nx.pagerank(G, alpha=0.85, max_iter=100)
        top_pr = sorted(pr.items(), key=lambda x: x[1], reverse=True)[:10]

        # 노드 타입별 집계
        type_counts = {}
        for _, attrs in G.nodes(data=True):
            t = attrs.get("type", "Unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        # 엣지 관계 타입별 집계
        rel_counts = {}
        for _, _, attrs in G.edges(data=True):
            r = attrs.get("rel", "Unknown")
            rel_counts[r] = rel_counts.get(r, 0) + 1

        # 최고 연결 노드
        top_nodes = []
        for nid, attrs in G.nodes(data=True):
            top_nodes.append({
                "id": nid,
                "label": attrs.get("label", nid),
                "type": attrs.get("type", ""),
                "in_degree": in_deg.get(nid, 0),
                "out_degree": out_deg.get(nid, 0),
                "pagerank": round(pr.get(nid, 0), 6),
            })
        top_nodes.sort(key=lambda x: x["pagerank"], reverse=True)

        return {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "density": round(nx.density(G), 4),
            "is_dag": nx.is_directed_acyclic_graph(G),
            "weakly_connected_components": nx.number_weakly_connected_components(G),
            "type_counts": type_counts,
            "rel_counts": rel_counts,
            "top_pagerank_nodes": top_nodes[:10],
            "top_in_degree": sorted(top_nodes, key=lambda x: x["in_degree"], reverse=True)[:5],
        }
    except Exception as e:
        return {"error": str(e), "node_count": G.number_of_nodes(), "edge_count": G.number_of_edges()}


# 캐시
_cached_graph = None
_cached_visjs = None
_cached_metrics = None


def get_graph_cache():
    global _cached_graph, _cached_visjs, _cached_metrics
    if _cached_graph is None:
        _cached_graph = build_networkx_graph()
        _cached_visjs = graph_to_visjs(_cached_graph)
        _cached_metrics = graph_metrics(_cached_graph)
    return _cached_graph, _cached_visjs, _cached_metrics


if __name__ == "__main__":
    G, vis, metrics = get_graph_cache()
    print(f"Nodes: {metrics['node_count']}, Edges: {metrics['edge_count']}")
    print(f"Density: {metrics['density']}, DAG: {metrics['is_dag']}")
    print("Type counts:", metrics['type_counts'])
