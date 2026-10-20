-- Apply explicitly after DBA review; no automatic schema changes.
CREATE TABLE IF NOT EXISTS eddy_vr_decisoes (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    chamado_id BIGINT NOT NULL,
    digest CHAR(64) NOT NULL,
    decisao_json JSON NOT NULL,
    snapshot_json JSON NOT NULL,
    criado_em DATETIME(6) NOT NULL,
    UNIQUE KEY uq_eddy_vr_decisao_digest (chamado_id, digest),
    KEY idx_eddy_vr_decisoes_chamado (chamado_id, criado_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
