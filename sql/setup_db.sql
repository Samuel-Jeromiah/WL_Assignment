-- Run as postgres superuser to create DB and app user
CREATE USER pubmed_user WITH PASSWORD 'pubmed_pass';
CREATE DATABASE pubmed_db OWNER pubmed_user;
GRANT ALL PRIVILEGES ON DATABASE pubmed_db TO pubmed_user;

-- Read-only role for LLM-generated queries (safety layer)
CREATE USER pubmed_readonly WITH PASSWORD 'readonly_pass';
GRANT CONNECT ON DATABASE pubmed_db TO pubmed_readonly;
