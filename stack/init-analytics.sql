-- The warehouse Nexus reads and dbt builds into, kept separate from Airflow's
-- metadata database so schema snapshots see only real analytics objects.
CREATE DATABASE analytics OWNER nexus;
\connect analytics
CREATE SCHEMA IF NOT EXISTS raw AUTHORIZATION nexus;
CREATE SCHEMA IF NOT EXISTS staging AUTHORIZATION nexus;
CREATE SCHEMA IF NOT EXISTS marts AUTHORIZATION nexus;

-- Source tables, standing in for what an ingestion tool would land.
CREATE TABLE raw.salesforce_account (
    id          integer PRIMARY KEY,
    name        text NOT NULL,
    _loaded_at  timestamp NOT NULL DEFAULT now()
);
CREATE TABLE raw.app_users (
    id          integer PRIMARY KEY,
    account_id  integer NOT NULL,
    email       text,
    _loaded_at  timestamp NOT NULL DEFAULT now()
);

INSERT INTO raw.salesforce_account (id, name) VALUES
    (1, 'Acme Corp'), (2, 'Globex'), (3, 'Initech');
INSERT INTO raw.app_users (id, account_id, email) VALUES
    (10, 1, 'a@acme.test'), (11, 1, 'b@acme.test'),
    (12, 2, 'c@globex.test'), (13, 3, 'd@initech.test');
