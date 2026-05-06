-- Enable pgvector on the default database so all subsequently created
-- Odoo databases (which inherit from template1) also have it available.
\connect template1
CREATE EXTENSION IF NOT EXISTS vector;

-- Also enable on the postgres database for bootstrap verification.
\connect postgres
CREATE EXTENSION IF NOT EXISTS vector;

-- LiteLLM virtual key persistence (ADR 0011)
CREATE DATABASE litellm OWNER odoo;
