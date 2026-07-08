"""
CKD-NEXT GraphRAG — 하이브리드 검색
Vector RAG (TF-IDF cosine) + Graph Traversal (NetworkX BFS)
→ 두 결과를 RRF 융합 (Reciprocal Rank Fusion)
"""
from typing import List, Optional
import networkx as nx

from kg_vectorrag import VectorDocument, get_vector_index, vector_search
from kg_builder import get_graph_cache, NODE_STYLES


# ─────────────────────────────────────────────────────────────
# RRF (Reciprocal Rank Fusion)
# ─────────────────────────────────────────────────────────────
def rrf_fusion(ranked_lists: List[List[str]], k: int = 60) -> List[tuple]:
    scores = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ─────────────────────────────────────────────────────────────
# 그래프 이웃 탐색 (BFS, 최대 2홉)
# ─────────────────────────────────────────────────────────────
def graph_neighbors(G: nx.DiGraph, seed_ids: List[str], hops: int = 2) -> List[dict]:
    visited = set()
    frontier = set()

    # seed_ids와 매칭되는 노드 찾기 (doc_id prefix 방식)
    node_map = {attrs.get("data", {}).get("id", ""):nid for nid, attrs in G.nodes(data=True)}
    prefix_map = {}
    for nid, attrs in G.nodes(data=True):
        ntype = attrs.get("type", "")
        prefix_map[nid] = {"node_id": nid, "type": ntype, "label": attrs.get("label", nid),
                           "data": attrs.get("data", {}), "source": "graph_neighbor"}

    for seed in seed_ids:
        # doc_id 예: "DEV:DEV-2026-0001" → 노드 ID 매칭
        for nid in G.nodes():
            if seed.split(":")[-1] in nid or nid.startswith(seed.split(":")[0]):
                frontier.add(nid)
                break

    result_nodes = []
    for hop in range(hops):
        next_frontier = set()
        for nid in frontier:
            if nid in visited:
                continue
            visited.add(nid)
            if nid in prefix_map:
                info = prefix_map[nid].copy()
                info["hop"] = hop
                result_nodes.append(info)
            # 인접 노드 추가 (in + out)
            for neighbor in list(G.successors(nid)) + list(G.predecessors(nid)):
                if neighbor not in visited:
                    next_frontier.add(neighbor)
        frontier = next_frontier

    return result_nodes[:30]


# ─────────────────────────────────────────────────────────────
# GraphRAG 메인 함수
# ─────────────────────────────────────────────────────────────
def graphrag_query(query: str, top_k: int = 10) -> dict:
    """
    1단계: Vector 검색 → seed 문서
    2단계: Graph BFS → 이웃 컨텍스트
    3단계: RRF 융합
    4단계: 컨텍스트 조합 반환
    """
    G, vis_data, metrics = get_graph_cache()
    idx = get_vector_index()

    # ── 1. Vector 검색 ──
    vec_results = idx.search(query, top_k=top_k)
    vec_ids = [r.doc_id for r in vec_results]

    # ── 2. Graph 이웃 탐색 ──
    graph_nodes = graph_neighbors(G, vec_ids[:5], hops=2)
    graph_ids = [n["node_id"] for n in graph_nodes]

    # ── 3. RRF 융합 ──
    fused = rrf_fusion([vec_ids, graph_ids])

    # ── 4. 결과 조합 ──
    # Vector 결과
    vec_formatted = [
        {
            "rank": i + 1,
            "doc_id": r.doc_id,
            "entity_type": r.entity_type,
            "text": r.text[:200],
            "vector_score": round(r.score, 4),
            "source": "vector",
            "metadata": r.metadata,
        }
        for i, r in enumerate(vec_results)
    ]

    # Graph 이웃 결과
    graph_formatted = []
    for n in graph_nodes[:8]:
        graph_formatted.append({
            "node_id": n["node_id"],
            "type": n["type"],
            "label": n["label"],
            "hop": n.get("hop", 0),
            "data": n["data"],
            "source": "graph",
        })

    # RRF 최종 순위
    fused_formatted = []
    vec_map = {r.doc_id: r for r in vec_results}
    graph_map = {n["node_id"]: n for n in graph_nodes}

    for rank, (doc_id, rrf_score) in enumerate(fused[:top_k]):
        item = {"rank": rank + 1, "doc_id": doc_id, "rrf_score": round(rrf_score, 6)}
        if doc_id in vec_map:
            r = vec_map[doc_id]
            item.update({
                "entity_type": r.entity_type,
                "text": r.text[:150],
                "source": "vector+graph" if doc_id in graph_map else "vector",
            })
        elif doc_id in graph_map:
            n = graph_map[doc_id]
            item.update({
                "entity_type": n["type"],
                "text": n["label"],
                "source": "graph",
            })
        fused_formatted.append(item)

    # ── 5. LLM 컨텍스트 생성 (RAG prompt context) ──
    context_parts = []
    for i, r in enumerate(vec_results[:5]):
        context_parts.append(f"[{i+1}] {r.entity_type}: {r.text[:120]}")
    for n in graph_nodes[:5]:
        context_parts.append(f"[관련] {n['type']}({n['label']}): {json_safe(n['data'])}")

    context_text = "\n".join(context_parts)
    prompt = (
        f"당신은 종근당 CKD-NEXT 시스템 전문가입니다.\n"
        f"다음 컨텍스트를 기반으로 질문에 답하세요.\n\n"
        f"=== 검색 컨텍스트 ===\n{context_text}\n\n"
        f"=== 질문 ===\n{query}\n\n"
        f"=== 답변 ==="
    )

    # 도메인 분류 (간단한 키워드 기반)
    domain = classify_domain(query)

    return {
        "query": query,
        "domain": domain,
        "vector_results": vec_formatted,
        "graph_neighbors": graph_formatted,
        "fused_results": fused_formatted,
        "rag_prompt": prompt[:1500],
        "stats": {
            "vector_hits": len(vec_results),
            "graph_hits": len(graph_nodes),
            "fused_total": len(fused),
        },
    }


def classify_domain(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ["일탈","deviation","oos","capa","품질","gmp","검사","규격"]):
        return "품질·GMP"
    elif any(k in q for k in ["수주","매출","청구","고객","sales","billing","invoice"]):
        return "영업·재무"
    elif any(k in q for k in ["생산","production","제조","배치","batch","공정"]):
        return "생산·공정"
    elif any(k in q for k in ["전표","gl","계정","채권","채무","비용","원가","재무"]):
        return "재무·회계"
    elif any(k in q for k in ["원료","자재","material","구매","발주","공급"]):
        return "자재·구매"
    elif any(k in q for k in ["직원","인사","employee","휴가","급여"]):
        return "인사·HR"
    return "공통"


def json_safe(d: dict) -> str:
    try:
        parts = [f"{k}:{v}" for k, v in (d or {}).items() if v is not None]
        return " ".join(parts)[:80]
    except Exception:
        return str(d)[:80]


if __name__ == "__main__":
    result = graphrag_query("Critical 일탈 원료 품질 문제 CAPA 현황")
    print(f"Domain: {result['domain']}")
    print(f"Vector hits: {result['stats']['vector_hits']}, Graph hits: {result['stats']['graph_hits']}")
    print("\nFused Results:")
    for r in result['fused_results'][:5]:
        print(f"  [{r['rank']}] {r.get('entity_type','')} {r['doc_id']} (RRF:{r['rrf_score']}) [{r.get('source','')}]")
