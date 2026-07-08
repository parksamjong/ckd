"""
CKD-NEXT OWL/RDF 온톨로지 정의
rdflib 기반 — 제약 GxP 도메인 OWL 클래스·속성 정의
"""
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, URIRef, Literal

CKD = Namespace("http://ckd-next.co.kr/ontology/")
GxP = Namespace("http://ckd-next.co.kr/gxp/")

# 온톨로지 클래스 정의 목록
OWL_CLASSES = [
    # 자재·제품
    ("Material",         "원부자재 및 완제품 마스터"),
    ("RawMaterial",      "원료 (API, 부형제)"),
    ("PackagingMaterial","포장재"),
    ("FinishedGood",     "완제품"),
    # 영업
    ("Customer",         "고객사"),
    ("SalesOrder",       "판매 오더"),
    ("SalesOrderItem",   "판매 오더 라인"),
    ("BillingDocument",  "청구 문서"),
    ("Invoice",          "세금계산서"),
    # 구매·공급
    ("Vendor",           "공급업체"),
    ("PurchaseOrder",    "구매 오더"),
    ("GoodsReceipt",     "입고"),
    # 생산
    ("ProductionOrder",  "생산 오더"),
    ("Batch",            "배치 (로트)"),
    ("BOM",              "자재명세서"),
    ("Routing",          "작업 지시서"),
    # 품질·GxP
    ("DeviationReport",  "일탈 보고서"),
    ("OOS",              "규격 이탈 (OOS)"),
    ("ProductComplaint", "제품 민원"),
    ("CapaAction",       "CAPA 조치"),
    ("ChangeControl",    "변경 관리"),
    ("InspectionLot",    "QM 검사 로트"),
    ("QmCharacteristic", "검사 특성"),
    # 재무
    ("GlAccount",        "총계정원장 계정"),
    ("GlPosting",        "회계 전표"),
    ("CostCenter",       "코스트센터"),
    ("AccountsReceivable","매출채권"),
    ("AccountsPayable",  "매입채무"),
    ("AccrualEntry",     "발생전표"),
    # 인사
    ("Employee",         "임직원"),
    ("Department",       "부서"),
    ("LeaveRequest",     "휴가 신청"),
    # 공통
    ("Plant",            "공장/플랜트"),
    ("Company",          "회사 코드"),
    ("ControllingArea",  "관리 영역"),
]

# 객체 속성 (Object Properties)
OWL_OBJ_PROPS = [
    ("contains",         "SalesOrder",       "Material",        "수주에 포함된 자재"),
    ("bills",            "BillingDocument",  "SalesOrder",      "청구 문서가 대상으로 하는 수주"),
    ("invoices",         "Invoice",          "BillingDocument", "세금계산서 ↔ 청구"),
    ("produces",         "ProductionOrder",  "Material",        "생산 오더가 생산하는 자재"),
    ("hasDeviation",     "ProductionOrder",  "DeviationReport", "생산 오더에서 발생한 일탈"),
    ("hasCapa",          "DeviationReport",  "CapaAction",      "일탈에 연결된 CAPA"),
    ("hasOOS",           "InspectionLot",    "OOS",             "검사 로트에서 발생한 OOS"),
    ("inspects",         "InspectionLot",    "Material",        "검사 대상 자재"),
    ("placedBy",         "SalesOrder",       "Customer",        "수주를 발행한 고객"),
    ("suppliedBy",       "PurchaseOrder",    "Vendor",          "발주 공급업체"),
    ("postedTo",         "GlPosting",        "GlAccount",       "전표 계정 귀속"),
    ("belongsToCostCenter","GlPosting",      "CostCenter",      "전표 코스트센터"),
    ("receivableFor",    "AccountsReceivable","Invoice",        "채권 대상 세금계산서"),
    ("payableFor",       "AccountsPayable",  "PurchaseOrder",   "채무 대상 발주"),
    ("employedBy",       "Employee",         "Department",      "임직원 소속 부서"),
    ("locatedAt",        "ProductionOrder",  "Plant",           "생산 오더 플랜트"),
    ("managedBy",        "CapaAction",       "Employee",        "CAPA 담당자"),
    ("hasBatch",         "ProductionOrder",  "Batch",           "생산 오더의 배치"),
    ("usedIn",           "Material",         "BOM",             "자재가 사용된 BOM"),
    ("changeControlFor", "ChangeControl",    "Material",        "자재 변경 관리"),
]

# 데이터 속성 (Data Properties)
OWL_DATA_PROPS = [
    ("materialId",       "Material",         XSD.string,  "자재 ID"),
    ("severity",         "DeviationReport",  XSD.string,  "일탈 심각도 (CRITICAL/MAJOR/MINOR)"),
    ("status",           "DeviationReport",  XSD.string,  "일탈 상태 (OPEN/CLOSED/IN_INVESTIGATION)"),
    ("totalAmount",      "SalesOrder",       XSD.decimal, "수주 총액"),
    ("postingDate",      "GlPosting",        XSD.date,    "전표 전기일"),
    ("debitAmount",      "GlPosting",        XSD.decimal, "전표 차변 금액"),
    ("creditAmount",     "GlPosting",        XSD.decimal, "전표 대변 금액"),
    ("lotQty",           "InspectionLot",    XSD.decimal, "검사 로트 수량"),
    ("capaStatus",       "CapaAction",       XSD.string,  "CAPA 상태"),
    ("targetDate",       "CapaAction",       XSD.date,    "CAPA 목표일"),
    ("batchId",          "Batch",            XSD.string,  "배치 번호"),
    ("plantId",          "Plant",            XSD.string,  "플랜트 ID"),
    ("orderQty",         "ProductionOrder",  XSD.decimal, "생산 수량"),
    ("grossAmount",      "AccountsPayable",  XSD.decimal, "매입채무 총액"),
    ("openAmount",       "AccountsReceivable",XSD.decimal,"매출채권 미수금"),
]


def build_ontology() -> Graph:
    g = Graph()
    g.bind("ckd", CKD)
    g.bind("gxp", GxP)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    # 온톨로지 선언
    onto = CKD["CKDNextOntology"]
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.label, Literal("CKD-NEXT 종근당 AI·SAP 통합 플랫폼 온톨로지", lang="ko")))
    g.add((onto, OWL.versionInfo, Literal("1.0")))

    # 클래스 정의
    for cls, label in OWL_CLASSES:
        uri = CKD[cls]
        g.add((uri, RDF.type, OWL.Class))
        g.add((uri, RDFS.label, Literal(label, lang="ko")))
        g.add((uri, RDFS.isDefinedBy, onto))
        # 서브클래스 계층
        if cls in ("RawMaterial", "PackagingMaterial", "FinishedGood"):
            g.add((uri, RDFS.subClassOf, CKD["Material"]))

    # 객체 속성
    for prop, dom, rng, label in OWL_OBJ_PROPS:
        uri = CKD[prop]
        g.add((uri, RDF.type, OWL.ObjectProperty))
        g.add((uri, RDFS.label, Literal(label, lang="ko")))
        g.add((uri, RDFS.domain, CKD[dom]))
        g.add((uri, RDFS.range, CKD[rng]))

    # 데이터 속성
    for prop, dom, dtype, label in OWL_DATA_PROPS:
        uri = CKD[prop]
        g.add((uri, RDF.type, OWL.DatatypeProperty))
        g.add((uri, RDFS.label, Literal(label, lang="ko")))
        g.add((uri, RDFS.domain, CKD[dom]))
        g.add((uri, RDFS.range, dtype))

    return g


def get_ontology_summary() -> dict:
    g = build_ontology()
    classes = [(str(s), str(g.value(s, RDFS.label))) for s, p, o in g.triples((None, RDF.type, OWL.Class))]
    obj_props = [(str(s), str(g.value(s, RDFS.label))) for s, p, o in g.triples((None, RDF.type, OWL.ObjectProperty))]
    data_props = [(str(s), str(g.value(s, RDFS.label))) for s, p, o in g.triples((None, RDF.type, OWL.DatatypeProperty))]

    # Turtle 직렬화
    turtle_str = g.serialize(format="turtle")

    return {
        "class_count": len(classes),
        "obj_prop_count": len(obj_props),
        "data_prop_count": len(data_props),
        "classes": [{"uri": u.split("/")[-1], "label": l} for u, l in classes],
        "object_properties": [{"uri": u.split("/")[-1], "label": l} for u, l in obj_props],
        "data_properties": [{"uri": u.split("/")[-1], "label": l} for u, l in data_props],
        "turtle_snippet": turtle_str[:3000],
    }


if __name__ == "__main__":
    s = get_ontology_summary()
    print(f"Classes: {s['class_count']}, ObjProps: {s['obj_prop_count']}, DataProps: {s['data_prop_count']}")
