-- Idempotent: applied at every start.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE IF NOT EXISTS contracts (
    id TEXT PRIMARY KEY,
    assureur TEXT NOT NULL, produit TEXT NOT NULL, pays TEXT NOT NULL, cadre_legal TEXT NOT NULL,
    langue TEXT NOT NULL, version TEXT NOT NULL, date_effet DATE,
    source_url TEXT NOT NULL, sha256 TEXT NOT NULL, nb_pages INT NOT NULL,
    extracted_sha256 TEXT, -- set when structured extraction finished for this sha256
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS clauses (
    id TEXT PRIMARY KEY, -- "<contract_id>:<n>"
    contract_id TEXT NOT NULL REFERENCES contracts ON DELETE CASCADE,
    ordre INT NOT NULL,
    numero TEXT, titre TEXT NOT NULL, chemin TEXT NOT NULL, texte TEXT NOT NULL,
    page_debut INT NOT NULL, page_fin INT NOT NULL,
    bboxes JSONB NOT NULL, -- [[page, x0, y0, x1, y1], ...] for highlighting
    type TEXT NOT NULL DEFAULT 'autre',
    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('french', coalesce(titre, '') || ' ' || texte)) STORED,
    embedding vector(1024)
);
CREATE INDEX IF NOT EXISTS clauses_contract ON clauses (contract_id, ordre);
CREATE INDEX IF NOT EXISTS clauses_tsv ON clauses USING gin (tsv);
CREATE INDEX IF NOT EXISTS clauses_embedding ON clauses USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS garanties (
    id SERIAL PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts ON DELETE CASCADE,
    nom TEXT NOT NULL, categorie TEXT NOT NULL, description TEXT NOT NULL,
    optionnelle BOOL NOT NULL, clause_ids TEXT[] NOT NULL, citation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exclusions (
    id SERIAL PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts ON DELETE CASCADE,
    categorie TEXT, -- NULL = general exclusion
    description TEXT NOT NULL, clause_ids TEXT[] NOT NULL, citation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS definitions (
    id SERIAL PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts ON DELETE CASCADE,
    terme TEXT NOT NULL, terme_normalise TEXT NOT NULL, definition TEXT NOT NULL,
    clause_ids TEXT[] NOT NULL, citation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conditions (
    id SERIAL PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts ON DELETE CASCADE,
    categorie TEXT NOT NULL, description TEXT NOT NULL,
    clause_ids TEXT[] NOT NULL, citation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plafonds (
    id SERIAL PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts ON DELETE CASCADE,
    categorie TEXT NOT NULL, libelle TEXT NOT NULL, montant TEXT, franchise TEXT,
    clause_ids TEXT[] NOT NULL, citation TEXT NOT NULL
);

-- Analyses and qualifications, keyed by a hash of their inputs + prompt version.
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
