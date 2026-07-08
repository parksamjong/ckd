"""
CKD-NEXT Vector RAG
PostgreSQL 텍스트 필드 → TF-IDF 임베딩 → 코사인 유사도 검색
(sentence-transformers 없이 scikit-learn TF-IDF로 구현)
"""
import re
import json
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
import psycopg2
import psycopg2.extras
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DB_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "database": "ckd_next", "user": "postgres", "password": "1234",
}


@dataclass
class VectorDocument:
    doc_id: str
    entity_type: str
    text: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0


# ─────────────────────────────────────────────────────────────
# 문서 수집 (PostgreSQL → VectorDocument 리스트)
# ─────────────────────────────────────────────────────────────
def collect_documents() -> List[VectorDocument]:
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    docs = []

    # 자재
    cur.execute("""
        SELECT mm.material_id, mm.material_no, mm.material_type_code,
               mm.material_group_code, mm.base_uom,
               md.material_desc, md.short_desc
        FROM material_master mm
        LEFT JOIN material_description md
          ON md.material_id = mm.material_id AND md.language_code = 'KO'
        LIMIT 50
    """)
    for r in cur.fetchall():
        text = (f"자재 {r['material_no']} {r['material_desc'] or r['short_desc'] or ''} "
                f"유형:{r['material_type_code'] or ''} 그룹:{r['material_group_code'] or ''} 단위:{r['base_uom'] or ''}")
        docs.append(VectorDocument(
            doc_id=f"MAT:{r['material_id']}", entity_type="Material",
            text=text, metadata={"id": str(r['material_id']), "no": r['material_no'], "desc": r['material_desc']}
        ))

    # 일탈 보고서
    cur.execute("SELECT deviation_id, severity, description, immediate_action, root_cause, status FROM deviation_report LIMIT 20")
    for r in cur.fetchall():
        text = (f"일탈보고서 {r['deviation_id']} 심각도:{r['severity']} 상태:{r['status']} "
                f"내용:{r['description'] or ''} "
                f"즉각조치:{r['immediate_action'] or ''} 근본원인:{r['root_cause'] or ''}")
        docs.append(VectorDocument(
            doc_id=f"DEV:{r['deviation_id']}", entity_type="DeviationReport",
            text=text, metadata={"id": r['deviation_id'], "severity": r['severity'], "status": r['status']}
        ))

    # CAPA 조치
    cur.execute("SELECT action_id, action_type, description, status, target_date::text FROM capa_action LIMIT 20")
    for r in cur.fetchall():
        text = (f"CAPA조치 {r['action_id']} 유형:{r['action_type'] or ''} "
                f"내용:{r['description'] or ''} 상태:{r['status']} 목표일:{r['target_date'] or ''}")
        docs.append(VectorDocument(
            doc_id=f"CAPA:{r['action_id']}", entity_type="CapaAction",
            text=text, metadata={"id": str(r['action_id']), "status": r['status']}
        ))

    # GL 전표 (전표 번호 단위)
    cur.execute("""
        SELECT document_number, document_type, header_text,
               SUM(COALESCE(debit_amount,0)) AS total_debit
        FROM gl_posting
        GROUP BY document_number, document_type, header_text
        LIMIT 25
    """)
    for r in cur.fetchall():
        type_label = {"RV":"매출전표","KR":"매입전표","SA":"일반전표","AF":"감가상각전표","WA":"출고전표","DZ":"수금전표"}
        tl = type_label.get(r['document_type'], r['document_type'])
        text = (f"회계전표 {r['document_number']} 유형:{tl} "
                f"내용:{r['header_text'] or ''} 차변합계:{r['total_debit']}")
        docs.append(VectorDocument(
            doc_id=f"JV:{r['document_number']}", entity_type="GlPosting",
            text=text, metadata={"id": r['document_number'], "type": r['document_type'], "amount": float(r['total_debit'] or 0)}
        ))

    # 생산 오더
    cur.execute("SELECT prod_order_id, material_id, status, order_qty FROM production_order LIMIT 20")
    for r in cur.fetchall():
        text = f"생산오더 {r['prod_order_id']} 자재:{r['material_id']} 상태:{r['status']} 수량:{r['order_qty']}"
        docs.append(VectorDocument(
            doc_id=f"PO:{r['prod_order_id']}", entity_type="ProductionOrder",
            text=text, metadata={"id": str(r['prod_order_id']), "status": r['status']}
        ))

    # 수주
    cur.execute("SELECT order_id, order_no, overall_status, total_net_amount FROM sales_order LIMIT 15")
    for r in cur.fetchall():
        text = f"수주 {r['order_no'] or r['order_id']} 상태:{r['overall_status']} 금액:{r['total_net_amount']}"
        docs.append(VectorDocument(
            doc_id=f"SO:{r['order_id']}", entity_type="SalesOrder",
            text=text, metadata={"id": str(r['order_id']), "status": r['overall_status']}
        ))

    # 제품 민원
    cur.execute("SELECT complaint_id, complaint_type, description, status FROM product_complaint LIMIT 10")
    for r in cur.fetchall():
        text = f"제품민원 {r['complaint_id']} 유형:{r['complaint_type'] or ''} 내용:{r['description'] or ''} 상태:{r['status']}"
        docs.append(VectorDocument(
            doc_id=f"COMP:{r['complaint_id']}", entity_type="ProductComplaint",
            text=text, metadata={"id": r['complaint_id'], "status": r['status']}
        ))

    # 변경 관리
    cur.execute("SELECT change_id, change_type, category, description FROM change_control LIMIT 10")
    for r in cur.fetchall():
        text = f"변경관리 {r['change_id']} 유형:{r['change_type'] or ''} 카테고리:{r['category'] or ''} 내용:{(r['description'] or '')[:60]}"
        docs.append(VectorDocument(
            doc_id=f"CC:{r['change_id']}", entity_type="ChangeControl",
            text=text, metadata={"id": r['change_id'], "type": r['change_type']}
        ))

    # 계정 마스터
    cur.execute("SELECT account_id, account_name_short, account_name_long, account_type FROM gl_account_master LIMIT 18")
    for r in cur.fetchall():
        text = f"GL계정 {r['account_id']} {r['account_name_short'] or ''} {r['account_name_long'] or ''} 유형:{r['account_type']}"
        docs.append(VectorDocument(
            doc_id=f"ACC:{r['account_id']}", entity_type="GlAccount",
            text=text, metadata={"id": r['account_id'], "type": r['account_type']}
        ))

    conn.close()
    return docs


# ─────────────────────────────────────────────────────────────
# Vector Index (TF-IDF + cosine)
# ─────────────────────────────────────────────────────────────
class VectorIndex:
    def __init__(self):
        self.docs: List[VectorDocument] = []
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),   # 한국어 n-gram
            max_features=8000,
            sublinear_tf=True,
        )
        self.matrix = None

    def build(self, docs: Optional[List[VectorDocument]] = None):
        if docs is None:
            docs = collect_documents()
        self.docs = docs
        texts = [d.text for d in docs]
        self.matrix = self.vectorizer.fit_transform(texts)
        return self

    def search(self, query: str, top_k: int = 8,
               filter_type: Optional[str] = None) -> List[VectorDocument]:
        if self.matrix is None:
            raise RuntimeError("Index not built. Call build() first.")
        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.matrix).flatten()
        top_idx = np.argsort(scores)[::-1]

        results = []
        for idx in top_idx:
            if scores[idx] < 0.01:
                break
            doc = self.docs[idx]
            if filter_type and doc.entity_type != filter_type:
                continue
            doc.score = float(scores[idx])
            results.append(doc)
            if len(results) >= top_k:
                break
        return results

    def get_stats(self) -> dict:
        type_counts = {}
        for d in self.docs:
            type_counts[d.entity_type] = type_counts.get(d.entity_type, 0) + 1
        return {
            "total_documents": len(self.docs),
            "vocabulary_size": len(self.vectorizer.vocabulary_) if self.matrix is not None else 0,
            "matrix_shape": list(self.matrix.shape) if self.matrix is not None else [0, 0],
            "entity_type_distribution": type_counts,
        }


# 싱글턴
_vector_index: Optional[VectorIndex] = None


def get_vector_index() -> VectorIndex:
    global _vector_index
    if _vector_index is None:
        _vector_index = VectorIndex()
        _vector_index.build()
    return _vector_index


def vector_search(query: str, top_k: int = 8, filter_type: str = None) -> List[dict]:
    idx = get_vector_index()
    results = idx.search(query, top_k=top_k, filter_type=filter_type or None)
    return [
        {
            "doc_id": r.doc_id,
            "entity_type": r.entity_type,
            "text": r.text[:150],
            "score": round(r.score, 4),
            "metadata": r.metadata,
        }
        for r in results
    ]


if __name__ == "__main__":
    idx = get_vector_index()
    stats = idx.get_stats()
    print("Vector Index Stats:", stats)
    results = vector_search("Critical 일탈 원료 품질")
    for r in results:
        print(f"[{r['score']:.3f}] {r['doc_id']} - {r['text'][:60]}")
