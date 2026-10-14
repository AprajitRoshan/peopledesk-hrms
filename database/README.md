# MySQL database files

- `hrms_schema.sql` is the complete schema reference for a clean `hrms_db` database, including Day 1–3 tables and columns.
- The app creates missing tables and adds required Day 3 columns to existing tables on startup without dropping rows. For a production system, replace this lightweight compatibility layer with Alembic migrations.
- `export_database.ps1` dumps your existing local database to a SQL file when you run it; the resulting user-data dump is intentionally not included in the source ZIP.
