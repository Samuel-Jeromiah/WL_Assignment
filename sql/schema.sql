-- PubMed assignment schema
-- Normalized: articles, journals, authors, mesh_terms + 2 junction tables

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS journals (
    id      SERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS authors (
    id          SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS mesh_terms (
    id      SERIAL PRIMARY KEY,
    term    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS articles (
    pmid        BIGINT PRIMARY KEY,
    title       TEXT NOT NULL,
    abstract    TEXT,
    year        INTEGER,
    journal_id  INTEGER REFERENCES journals(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS article_authors (
    article_id  BIGINT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    author_id   INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    PRIMARY KEY (article_id, author_id)
);

CREATE TABLE IF NOT EXISTS article_mesh (
    article_id  BIGINT NOT NULL REFERENCES articles(pmid) ON DELETE CASCADE,
    mesh_id     INTEGER NOT NULL REFERENCES mesh_terms(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, mesh_id)
);

CREATE INDEX IF NOT EXISTS idx_articles_year ON articles(year);
CREATE INDEX IF NOT EXISTS idx_articles_journal ON articles(journal_id);
CREATE INDEX IF NOT EXISTS idx_articles_title_trgm ON articles USING gin (title gin_trgm_ops);

-- Grants (run after tables exist; requires the two roles from setup_db.sql)
GRANT USAGE ON SCHEMA public TO pubmed_user, pubmed_readonly;
GRANT ALL ON ALL TABLES IN SCHEMA public TO pubmed_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO pubmed_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pubmed_readonly;
