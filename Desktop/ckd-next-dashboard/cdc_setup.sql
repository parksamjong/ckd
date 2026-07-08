-- ============================================================
-- CKD-NEXT CDC (Change Data Capture) PostgreSQL 설정
-- PostgreSQL TRIGGER → pg_notify → Python CDC Listener → Kafka
-- ============================================================

-- 공통 CDC 알림 함수
CREATE OR REPLACE FUNCTION ckd_cdc_notify()
RETURNS TRIGGER AS $$
DECLARE
  payload JSONB;
  topic   TEXT;
BEGIN
  -- 테이블별 Kafka 토픽 매핑
  topic := TG_TABLE_NAME;

  IF (TG_OP = 'DELETE') THEN
    payload := jsonb_build_object(
      'op', 'DELETE', 'table', TG_TABLE_NAME,
      'before', to_jsonb(OLD), 'after', NULL,
      'ts', extract(epoch FROM now())::bigint
    );
  ELSIF (TG_OP = 'INSERT') THEN
    payload := jsonb_build_object(
      'op', 'INSERT', 'table', TG_TABLE_NAME,
      'before', NULL, 'after', to_jsonb(NEW),
      'ts', extract(epoch FROM now())::bigint
    );
  ELSE  -- UPDATE
    payload := jsonb_build_object(
      'op', 'UPDATE', 'table', TG_TABLE_NAME,
      'before', to_jsonb(OLD), 'after', to_jsonb(NEW),
      'ts', extract(epoch FROM now())::bigint
    );
  END IF;

  PERFORM pg_notify('ckd_cdc_' || TG_TABLE_NAME, payload::TEXT);
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- ── 수주 ──────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_cdc_sales_order ON sales_order;
CREATE TRIGGER trg_cdc_sales_order
AFTER INSERT OR UPDATE OR DELETE ON sales_order
FOR EACH ROW EXECUTE FUNCTION ckd_cdc_notify();

-- ── 일탈 보고서 ────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_cdc_deviation_report ON deviation_report;
CREATE TRIGGER trg_cdc_deviation_report
AFTER INSERT OR UPDATE OR DELETE ON deviation_report
FOR EACH ROW EXECUTE FUNCTION ckd_cdc_notify();

-- ── CAPA 조치 ──────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_cdc_capa_action ON capa_action;
CREATE TRIGGER trg_cdc_capa_action
AFTER INSERT OR UPDATE OR DELETE ON capa_action
FOR EACH ROW EXECUTE FUNCTION ckd_cdc_notify();

-- ── 생산 오더 ──────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_cdc_production_order ON production_order;
CREATE TRIGGER trg_cdc_production_order
AFTER INSERT OR UPDATE OR DELETE ON production_order
FOR EACH ROW EXECUTE FUNCTION ckd_cdc_notify();

-- ── 구매 오더 ──────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_cdc_purchase_order ON purchase_order;
CREATE TRIGGER trg_cdc_purchase_order
AFTER INSERT OR UPDATE OR DELETE ON purchase_order
FOR EACH ROW EXECUTE FUNCTION ckd_cdc_notify();

-- ── 매출채권 ───────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_cdc_accounts_receivable ON accounts_receivable;
CREATE TRIGGER trg_cdc_accounts_receivable
AFTER INSERT OR UPDATE OR DELETE ON accounts_receivable
FOR EACH ROW EXECUTE FUNCTION ckd_cdc_notify();

-- ── 검사 로트 ──────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_cdc_qm_inspection_lot ON qm_inspection_lot;
CREATE TRIGGER trg_cdc_qm_inspection_lot
AFTER INSERT OR UPDATE OR DELETE ON qm_inspection_lot
FOR EACH ROW EXECUTE FUNCTION ckd_cdc_notify();

-- ── GL 전표 ────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS trg_cdc_gl_posting ON gl_posting;
CREATE TRIGGER trg_cdc_gl_posting
AFTER INSERT OR UPDATE OR DELETE ON gl_posting
FOR EACH ROW EXECUTE FUNCTION ckd_cdc_notify();

-- 확인
SELECT
  trigger_name,
  event_object_table AS table_name,
  event_manipulation AS event
FROM information_schema.triggers
WHERE trigger_name LIKE 'trg_cdc_%'
ORDER BY event_object_table;
