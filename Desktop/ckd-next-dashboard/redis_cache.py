"""
CKD-NEXT Redis 캐시 레이어
Redis Stack Cluster 6노드 (localhost:6379~6384)
address_remap으로 내부 Docker IP(172.20.0.x) → localhost 포트 변환
"""
import json
import logging
from typing import Optional

import redis
import redis.asyncio as aioredis
from redis.asyncio.cluster import RedisCluster

log = logging.getLogger("ckd.redis")

# 내부 Docker IP → localhost 포트 매핑 (클러스터 MOVED 리디렉션 처리)
_ADDR_REMAP = {
    ("172.20.0.11", 6379): ("localhost", 6379),
    ("172.20.0.12", 6379): ("localhost", 6380),
    ("172.20.0.13", 6379): ("localhost", 6381),
    # 추가 노드가 생기면 여기에 추가
}

def _addr_remap(addr: tuple) -> tuple:
    return _ADDR_REMAP.get(addr, addr)

KPI_CACHE_KEY = "ckd:kpi:cache"
KPI_CACHE_TTL = 15
ALERTS_KEY    = "ckd:alerts:critical"
STREAM_KEY    = "ckd:events:stream"
PUBSUB_CH     = "ckd:realtime"

_client: Optional[RedisCluster] = None
_available: bool = False


def _build_remap_dynamic() -> dict:
    """서버 시작 시 실제 클러스터 토폴로지로 remap 테이블 갱신."""
    remap = {}
    id_to_local: dict[str, tuple] = {}
    for port in range(6379, 6385):
        try:
            c = redis.Redis(host="localhost", port=port, socket_connect_timeout=1)
            nid = c.execute_command("CLUSTER MYID")
            if isinstance(nid, bytes):
                nid = nid.decode()
            id_to_local[nid] = ("localhost", port)
            c.close()
        except Exception:
            pass
    try:
        c = redis.Redis(host="localhost", port=6379, socket_connect_timeout=2)
        nodes = c.execute_command("CLUSTER NODES")
        c.close()
        for addr, info in nodes.items():
            nid = info.get("node_id", "")
            if nid in id_to_local and addr and addr != ":0":
                h, p = addr.rsplit(":", 1)
                remap[(h, int(p))] = id_to_local[nid]
    except Exception as e:
        log.warning(f"클러스터 토폴로지 자동 감지 실패 — 기본 remap 사용: {e}")
        return _ADDR_REMAP
    return remap or _ADDR_REMAP


async def init_redis() -> bool:
    global _client, _available, _ADDR_REMAP
    try:
        # 동적으로 remap 갱신
        _ADDR_REMAP = _build_remap_dynamic()
        log.info(f"Redis 주소 remap: {_ADDR_REMAP}")

        _client = RedisCluster(
            host="localhost", port=6379,
            decode_responses=True,
            address_remap=_addr_remap,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        await _client.ping()
        info = await _client.info("server")
        _available = True
        log.info(f"Redis Cluster 연결 OK (v{info.get('redis_version','?')}, nodes={len(_ADDR_REMAP)})")
    except Exception as e:
        _available = False
        log.warning(f"Redis 불가 — fallback 모드: {e}")
    return _available


async def close_redis():
    global _client
    if _client:
        try:
            await _client.aclose()
        except Exception:
            pass


# ── KPI 캐시 ────────────────────────────────────────────────────

async def get_kpi_cache() -> Optional[dict]:
    if not _available or not _client:
        return None
    try:
        raw = await _client.get(KPI_CACHE_KEY)
        if raw:
            return json.loads(raw)
    except Exception as e:
        log.debug(f"캐시 조회: {e}")
    return None


async def set_kpi_cache(data: dict):
    if not _available or not _client:
        return
    try:
        await _client.setex(
            KPI_CACHE_KEY, KPI_CACHE_TTL,
            json.dumps(data, ensure_ascii=False, default=str),
        )
    except Exception as e:
        log.debug(f"캐시 저장: {e}")


async def invalidate_kpi_cache():
    if not _available or not _client:
        return
    try:
        await _client.delete(KPI_CACHE_KEY)
    except Exception:
        pass


# ── 알람 ─────────────────────────────────────────────────────────

async def get_critical_alerts(limit: int = 20) -> list:
    if not _available or not _client:
        return []
    try:
        items = await _client.zrevrangebyscore(
            ALERTS_KEY, "+inf", "-inf", start=0, num=limit, withscores=True
        )
        result = []
        for raw, score in items:
            try:
                obj = json.loads(raw)
                obj["ts"] = int(score)
                result.append(obj)
            except Exception:
                pass
        return result
    except Exception:
        return []


# ── 이벤트 스트림 ─────────────────────────────────────────────────

async def get_recent_events(count: int = 50) -> list:
    if not _available or not _client:
        return []
    try:
        entries = await _client.xrevrange(STREAM_KEY, count=count)
        return [
            {"id": eid, "topic": f.get("topic",""), "op": f.get("op",""),
             "table": f.get("table",""), "ts": f.get("ts","")}
            for eid, f in entries
        ]
    except Exception:
        return []


# ── Pub/Sub → WebSocket 브릿지 ───────────────────────────────────

async def subscribe_realtime(callback):
    """Redis Pub/Sub 구독 — 단일 노드에 직접 연결."""
    if not _available:
        return
    r = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(PUBSUB_CH)
    log.info(f"Redis Pub/Sub 구독: {PUBSUB_CH}")
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await callback(msg["data"])
    except (asyncio.CancelledError, GeneratorExit, RuntimeError):
        pass
    finally:
        try:
            await pubsub.unsubscribe(PUBSUB_CH)
            await r.aclose()
        except Exception:
            pass


# ── 헬스체크 ─────────────────────────────────────────────────────

async def redis_info() -> dict:
    if not _available or not _client:
        return {"available": False}
    try:
        info   = await _client.info("server")
        ttl    = await _client.ttl(KPI_CACHE_KEY)
        slen   = await _client.xlen(STREAM_KEY)
        alerts = await _client.zcard(ALERTS_KEY)
        return {
            "available": True,
            "version": info.get("redis_version", "?"),
            "used_memory_human": info.get("used_memory_human", "?"),
            "kpi_cache_ttl": ttl,
            "stream_len": slen,
            "alerts_count": alerts,
            "cluster_nodes": len(_ADDR_REMAP),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
