--Creating a new user account and password for the PubMed database and creating the database itself, assigning ownership to the new user. Additionally, 
--a read-only role is created for LLM-generated queries to enhance security.
CREATE USER pubmed_user WITH PASSWORD 'pubmed_pass';
CREATE DATABASE pubmed_db OWNER pubmed_user;
GRANT ALL PRIVILEGES ON DATABASE pubmed_db TO pubmed_user;

-- Creating a read-only user for LLM-generated queries to enhance security
CREATE USER pubmed_readonly WITH PASSWORD 'readonly_pass';
GRANT CONNECT ON DATABASE pubmed_db TO pubmed_readonly;
