import sys
sys.path.insert(0, r'C:\Users\user\Desktop\ckd-next-dashboard')
try:
    from kg_ontology import get_ontology_summary
    s = get_ontology_summary()
    print(f"Ontology OK: {s['class_count']} classes, {s['obj_prop_count']} obj props")

    from kg_builder import get_graph_cache
    G, vis, metrics = get_graph_cache()
    print(f"KG Builder OK: {metrics['node_count']} nodes, {metrics['edge_count']} edges")
    print("Types:", list(metrics['type_counts'].keys()))

    from kg_vectorrag import get_vector_index
    idx = get_vector_index()
    st = idx.get_stats()
    print(f"VectorRAG OK: {st['total_documents']} docs, vocab={st['vocabulary_size']}")

    from kg_neo4j import get_neo4j_preview
    neo = get_neo4j_preview()
    print(f"Neo4j OK: {neo['script_lines']} lines, nodes:{neo['node_statements']}, rels:{neo['relationship_statements']}")

    from kg_graphrag import graphrag_query
    r = graphrag_query("Critical 일탈 CAPA 현황", top_k=5)
    print(f"GraphRAG OK: domain={r['domain']}, vec={r['stats']['vector_hits']}, graph={r['stats']['graph_hits']}")
    print("ALL KG MODULES OK")
except Exception as e:
    import traceback; traceback.print_exc()
