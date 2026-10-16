-- The API and worker connect as nexus_app, which does not own the tables, so
-- row-level security applies to it. Migrations run as nexus_owner.
CREATE ROLE nexus_app LOGIN PASSWORD 'nexus_app_dev';
GRANT CONNECT ON DATABASE nexus TO nexus_app;
GRANT USAGE ON SCHEMA public TO nexus_app;
