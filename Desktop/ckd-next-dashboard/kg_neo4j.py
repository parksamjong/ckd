"""
CKD-NEXT Neo4j Cypher 스크립트 생성기
PostgreSQL → Neo4j CREATE/MERGE Cypher
(Neo4j 연결 없이도 Cypher 스크립트 생성 가능)
"""
import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "database": "ckd_next", "user": "postgres", "password": "1234",
}

NEO4J_CONFIG = {
    "uri": "bolt://localhost:7687",
    "user": "neo4j",
    "password": "ckdnext2026",
}

# Neo4j 인덱스·제약 정의
CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Material) REQUIRE m.material_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:SalesOrder) REQUIRE s.order_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:ProductionOrder) REQUIRE p.prod_order_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:DeviationReport) REQUIRE d.deviation_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:CapaAction) REQUIRE c.action_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (b:BillingDocument) REQUIRE b.billing_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Invoice) REQUIRE i.invoice_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (g:GlPosting) REQUIRE g.document_number IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (a:GlAccount) REQUIRE a.account_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (l:InspectionLot) REQUIRE l.lot_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Employee) REQUIRE e.employee_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (o:PurchaseOrder) REQUIRE o.po_id IS UNIQUE",
    "CREATE INDEX IF NOT EXISTS FOR (d:DeviationReport) ON (d.severity)",
    "CREATE INDEX IF NOT EXISTS FOR (d:DeviationReport) ON (d.status)",
    "CREATE INDEX IF NOT EXISTS FOR (p:ProductionOrder) ON (p.status)",
    "CREATE INDEX IF NOT EXISTS FOR (s:SalesOrder) ON (s.overall_status)",
]


def _esc(v) -> str:
    """Cypher 문자열 이스케이프"""
    if v is None:
        return "null"
    v = str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", "")
    return f"'{v}'"


def _num(v) -> str:
    if v is None:
        return "null"
    try:
        return str(float(v))
    except (TypeError, ValueError):
        return "null"


def generate_cypher_script() -> str:
    """PostgreSQL 데이터 → 완성된 Neo4j Cypher 스크립트"""
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    lines = []

    lines.append("// ==========================================================")
    lines.append("// CKD-NEXT Neo4j 지식 그래프 로더")
    lines.append("// 종근당 차세대 AI·SAP 통합 플랫폼")
    lines.append("// ==========================================================")
    lines.append("")
    lines.append("// ── 제약·인덱스 생성 ──")
    for c in CONSTRAINTS:
        lines.append(c + ";")
    lines.append("")

    # ── 자재 노드 ──
    lines.append("// ── Material 노드 ──")
    cur.execute("""
        SELECT mm.material_id, mm.material_no, mm.material_type_code,
               mm.material_group_code, mm.base_uom,
               md.material_desc
        FROM material_master mm
        LEFT JOIN material_description md ON md.material_id = mm.material_id AND md.language_code = 'KO'
        LIMIT 50
    """)
    for r in cur.fetchall():
        lines.append(
            f"MERGE (m:Material {{material_id:{_esc(r['material_id'])}}}) "
            f"SET m.material_no={_esc(r['material_no'])}, m.desc={_esc(r['material_desc'])}, "
            f"m.type={_esc(r['material_type_code'])}, m.group={_esc(r['material_group_code'])}, "
            f"m.uom={_esc(r['base_uom'])};"
        )

    # ── 수주 노드 ──
    lines.append("\n// ── SalesOrder 노드 ──")
    cur.execute("SELECT order_id, order_no, overall_status, total_net_amount FROM sales_order LIMIT 20")
    for r in cur.fetchall():
        lines.append(
            f"MERGE (s:SalesOrder {{order_id:{_esc(r['order_id'])}}}) "
            f"SET s.order_no={_esc(r['order_no'])}, s.status={_esc(r['overall_status'])}, "
            f"s.net_amount={_num(r['total_net_amount'])};"
        )

    # 수주 → 자재 관계
    lines.append("\n// ── SalesOrder -[CONTAINS]-> Material ──")
    cur.execute("SELECT order_id, material_id, order_qty, net_price FROM sales_order_item LIMIT 30")
    for r in cur.fetchall():
        lines.append(
            f"MATCH (s:SalesOrder {{order_id:{_esc(r['order_id'])}}}) "
            f"MATCH (m:Material {{material_id:{_esc(r['material_id'])}}}) "
            f"MERGE (s)-[:CONTAINS {{qty:{_num(r['order_qty'])}, price:{_num(r['net_price'])}}}]->(m);"
        )

    # ── 생산 오더 노드 ──
    lines.append("\n// ── ProductionOrder 노드 ──")
    cur.execute("""
        SELECT po.prod_order_id, po.material_id AS mat_no, po.status, po.order_qty,
               po.scheduled_start::text, po.scheduled_end::text,
               mm.material_id AS mm_id
        FROM production_order po
        LEFT JOIN material_master mm ON mm.material_no = po.material_id
        LIMIT 20
    """)
    for r in cur.fetchall():
        lines.append(
            f"MERGE (p:ProductionOrder {{prod_order_id:{_esc(r['prod_order_id'])}}}) "
            f"SET p.status={_esc(r['status'])}, p.qty={_num(r['order_qty'])}, "
            f"p.start={_esc(r['scheduled_start'])}, p.end={_esc(r['scheduled_end'])};"
        )
        if r['mm_id']:
            lines.append(
                f"MATCH (p:ProductionOrder {{prod_order_id:{_esc(r['prod_order_id'])}}}) "
                f"MATCH (m:Material {{material_id:{_esc(r['mm_id'])}}}) "
                f"MERGE (p)-[:PRODUCES]->(m);"
            )

    # ── 일탈 보고서 노드 ──
    lines.append("\n// ── DeviationReport 노드 ──")
    cur.execute("""
        SELECT deviation_id, severity, status, production_order_id,
               material_id, description, root_cause
        FROM deviation_report LIMIT 20
    """)
    for r in cur.fetchall():
        desc = (r['description'] or '')[:100]
        root = (r['root_cause'] or '')[:100]
        lines.append(
            f"MERGE (d:DeviationReport {{deviation_id:{_esc(r['deviation_id'])}}}) "
            f"SET d.severity={_esc(r['severity'])}, d.status={_esc(r['status'])}, "
            f"d.description={_esc(desc)}, d.root_cause={_esc(root)};"
        )
        if r['production_order_id']:
            lines.append(
                f"MATCH (p:ProductionOrder {{prod_order_id:{_esc(r['production_order_id'])}}}) "
                f"MATCH (d:DeviationReport {{deviation_id:{_esc(r['deviation_id'])}}}) "
                f"MERGE (p)-[:HAS_DEVIATION]->(d);"
            )
        if r['material_id']:
            lines.append(
                f"MATCH (d:DeviationReport {{deviation_id:{_esc(r['deviation_id'])}}}) "
                f"MATCH (m:Material {{material_id:{_esc(r['material_id'])}}}) "
                f"MERGE (d)-[:RELATES_TO_MATERIAL]->(m);"
            )

    # ── CAPA 노드 ──
    lines.append("\n// ── CapaAction 노드 ──")
    cur.execute("SELECT action_id, capa_id, action_type, description, status, target_date::text FROM capa_action LIMIT 20")
    for r in cur.fetchall():
        desc = (r['description'] or '')[:80]
        lines.append(
            f"MERGE (c:CapaAction {{action_id:{_esc(r['action_id'])}}}) "
            f"SET c.type={_esc(r['action_type'])}, c.status={_esc(r['status'])}, "
            f"c.description={_esc(desc)}, c.target_date={_esc(r['target_date'])};"
        )
        lines.append(
            f"MATCH (d:DeviationReport {{deviation_id:{_esc(r['capa_id'])}}}) "
            f"MATCH (c:CapaAction {{action_id:{_esc(r['action_id'])}}}) "
            f"MERGE (d)-[:HAS_CAPA]->(c);"
        )

    # ── GL 계정 노드 ──
    lines.append("\n// ── GlAccount 노드 ──")
    cur.execute("SELECT account_id, account_name_short, account_type FROM gl_account_master LIMIT 20")
    for r in cur.fetchall():
        lines.append(
            f"MERGE (a:GlAccount {{account_id:{_esc(r['account_id'])}}}) "
            f"SET a.name={_esc(r['account_name_short'])}, a.type={_esc(r['account_type'])};"
        )

    # ── GL 전표 노드 ──
    lines.append("\n// ── GlPosting 노드 ──")
    cur.execute("""
        SELECT DISTINCT document_number, document_type, posting_date::text,
               SUM(COALESCE(debit_amount,0)) AS total_debit,
               MIN(account_id) AS primary_account,
               MIN(cost_center_id) AS cost_center
        FROM gl_posting
        GROUP BY document_number, document_type, posting_date
        LIMIT 20
    """)
    for r in cur.fetchall():
        lines.append(
            f"MERGE (g:GlPosting {{document_number:{_esc(r['document_number'])}}}) "
            f"SET g.type={_esc(r['document_type'])}, g.date={_esc(r['posting_date'])}, "
            f"g.total_debit={_num(r['total_debit'])};"
        )
        if r['primary_account']:
            lines.append(
                f"MATCH (g:GlPosting {{document_number:{_esc(r['document_number'])}}}) "
                f"MATCH (a:GlAccount {{account_id:{_esc(r['primary_account'])}}}) "
                f"MERGE (g)-[:POSTED_TO]->(a);"
            )

    # ── 청구 문서 ──
    lines.append("\n// ── BillingDocument 노드 ──")
    cur.execute("SELECT billing_id, billing_type, total_value, billing_status FROM billing_document LIMIT 10")
    for r in cur.fetchall():
        lines.append(
            f"MERGE (b:BillingDocument {{billing_id:{_esc(r['billing_id'])}}}) "
            f"SET b.type={_esc(r['billing_type'])}, b.amount={_num(r['total_value'])}, "
            f"b.status={_esc(r['billing_status'])};"
        )

    # ── 세금계산서 ──
    lines.append("\n// ── Invoice 노드 ──")
    cur.execute("SELECT invoice_id, billing_id, total_amount, invoice_status FROM invoice LIMIT 10")
    for r in cur.fetchall():
        lines.append(
            f"MERGE (i:Invoice {{invoice_id:{_esc(r['invoice_id'])}}}) "
            f"SET i.amount={_num(r['total_amount'])}, i.status={_esc(r['invoice_status'])};"
        )
        lines.append(
            f"MATCH (b:BillingDocument {{billing_id:{_esc(r['billing_id'])}}}) "
            f"MATCH (i:Invoice {{invoice_id:{_esc(r['invoice_id'])}}}) "
            f"MERGE (b)-[:INVOICES]->(i);"
        )

    # ── 검사 로트 ──
    lines.append("\n// ── InspectionLot 노드 ──")
    cur.execute("SELECT lot_id, material_id, plant_id, usage_decision FROM qm_inspection_lot LIMIT 10")
    for r in cur.fetchall():
        lines.append(
            f"MERGE (l:InspectionLot {{lot_id:{_esc(r['lot_id'])}}}) "
            f"SET l.plant={_esc(r['plant_id'])}, l.decision={_esc(r['usage_decision'])};"
        )
        lines.append(
            f"MATCH (l:InspectionLot {{lot_id:{_esc(r['lot_id'])}}}) "
            f"MATCH (m:Material {{material_id:{_esc(r['material_id'])}}}) "
            f"MERGE (l)-[:INSPECTS]->(m);"
        )

    # ── 구매 오더 ──
    lines.append("\n// ── PurchaseOrder 노드 ──")
    cur.execute("SELECT po_id, vendor_id, po_status, total_value FROM purchase_order LIMIT 10")
    for r in cur.fetchall():
        lines.append(
            f"MERGE (o:PurchaseOrder {{po_id:{_esc(r['po_id'])}}}) "
            f"SET o.vendor={_esc(r['vendor_id'])}, o.status={_esc(r['po_status'])}, "
            f"o.amount={_num(r['total_value'])};"
        )

    conn.close()

    lines.append("\n// ── 그래프 통계 쿼리 (읽기 전용) ──")
    lines.append("// CALL apoc.meta.stats() YIELD labels, relTypesCount;")
    lines.append("// MATCH (n) RETURN labels(n) AS type, count(n) AS cnt ORDER BY cnt DESC;")
    lines.append("// MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC;")
    lines.append("// CALL gds.pageRank.stream('ckd-graph') YIELD nodeId, score RETURN nodeId, score ORDER BY score DESC LIMIT 10;")

    return "\n".join(lines)


def get_neo4j_preview() -> dict:
    """Neo4j Cypher 미리보기 + 연결 상태"""
    script = generate_cypher_script()
    line_count = len(script.split("\n"))
    node_lines = sum(1 for l in script.split("\n") if "MERGE" in l and "]->" not in l)
    rel_lines = sum(1 for l in script.split("\n") if "]->" in l or "-[:" in l)

    # Neo4j 연결 시도
    neo4j_connected = False
    neo4j_status = "연결 안됨 (Neo4j 서비스 미실행)"
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_CONFIG["uri"],
                                      auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"]))
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok")
            result.single()
        neo4j_connected = True
        neo4j_status = f"연결됨 - {NEO4J_CONFIG['uri']}"
        driver.close()
    except Exception as e:
        neo4j_status = f"오프라인 (스크립트만 생성): {str(e)[:60]}"

    # 샘플 Cypher 쿼리 예제
    sample_queries = [
        {
            "title": "일탈 심각도별 집계",
            "cypher": "MATCH (d:DeviationReport) RETURN d.severity AS severity, count(d) AS cnt ORDER BY cnt DESC"
        },
        {
            "title": "자재별 생산-일탈 경로",
            "cypher": "MATCH (p:ProductionOrder)-[:PRODUCES]->(m:Material)<-[:RELATES_TO_MATERIAL]-(d:DeviationReport) RETURN m.material_id, count(d) AS deviations ORDER BY deviations DESC"
        },
        {
            "title": "Critical 일탈 → CAPA 경로",
            "cypher": "MATCH (d:DeviationReport {severity:'CRITICAL'})-[:HAS_CAPA]->(c:CapaAction) RETURN d.deviation_id, d.description, c.status, c.target_date"
        },
        {
            "title": "GL전표 → 계정 집계",
            "cypher": "MATCH (g:GlPosting)-[:POSTED_TO]->(a:GlAccount) RETURN a.account_id, a.name, sum(g.total_debit) AS total ORDER BY total DESC"
        },
        {
            "title": "PageRank 상위 노드",
            "cypher": "CALL gds.pageRank.stream('ckd-graph') YIELD nodeId, score RETURN gds.util.asNode(nodeId).name AS name, score ORDER BY score DESC LIMIT 10"
        },
        {
            "title": "수주 → 자재 → 생산 오더 삼각관계",
            "cypher": "MATCH (s:SalesOrder)-[:CONTAINS]->(m:Material)<-[:PRODUCES]-(p:ProductionOrder) RETURN s.order_no, m.material_id, p.status LIMIT 20"
        },
    ]

    return {
        "neo4j_connected": neo4j_connected,
        "neo4j_status": neo4j_status,
        "neo4j_uri": NEO4J_CONFIG["uri"],
        "script_lines": line_count,
        "node_statements": node_lines,
        "relationship_statements": rel_lines,
        "constraints": len(CONSTRAINTS),
        "sample_queries": sample_queries,
        "script_preview": script[:4000],
    }


if __name__ == "__main__":
    info = get_neo4j_preview()
    print(f"Neo4j 상태: {info['neo4j_status']}")
    print(f"Cypher 스크립트: {info['script_lines']}줄, 노드:{info['node_statements']}, 관계:{info['relationship_statements']}")
    print("\n생성된 스크립트 앞부분:")
    print(info['script_preview'][:500])
