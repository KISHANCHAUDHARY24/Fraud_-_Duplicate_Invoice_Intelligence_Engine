-- Creates (or updates) the application database user and database.
-- Run through scripts\setup_database.ps1, which passes these psql variables:
--   :db_name  :db_user  :db_password
-- Safe to run more than once.

-- 1. Application login role (least privilege: not a superuser).
--    CREATEDB lets Django create its temporary test database.
SELECT format('CREATE ROLE %I LOGIN', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user') \gexec

SELECT format('ALTER ROLE %I WITH LOGIN CREATEDB PASSWORD %L', :'db_user', :'db_password') \gexec

-- 2. Database owned by the application role.
--    template0 + UTF8 avoids "encoding incompatible with template" errors on Windows.
SELECT format('CREATE DATABASE %I OWNER %I ENCODING ''UTF8'' TEMPLATE template0', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', :'db_name', :'db_user') \gexec

\echo 'Database setup complete.'
