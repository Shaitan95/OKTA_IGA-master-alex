# Plan for a Modular IGA Data Pipeline Refactor

## Introduction
This document outlines a refactor of the existing Identity Governance & Administration (IGA) backup code into a modular and configurable data pipeline. The goal is to make it easy to fetch data from IGA APIs and route it either to S3-backed Delta Lake tables (for Databricks) or to a MySQL database with minimal code changes.

## Objectives
- **Modular design:** Separate resource definitions, API access, parsing, and sink logic so new object types can be added with configuration or a small module.
- **Local-first execution:** Validate end-to-end runs locally before deploying to Databricks or other environments.
- **Databricks & Delta Lake integration:** Support writing API data into Delta tables on S3 for Databricks workloads.
- **MySQL integration:** Provide an alternative sink that writes data into MySQL tables.
- **Configurable & parameterized:** Read domains, tokens, enabled object types, and output modes from configuration files or environment variables instead of hard-coding.
- **Documentation & maintainability:** Supply clear code comments and usage docs, plus guidance for adding new object types.

## Current Issues to Address
- **Monolithic flow:** API calls and storage are coupled, making it hard to extend to new object types.
- **Tight coupling of steps:** Fetching, parsing, and storing are intermixed instead of layered.
- **Limited configurability:** Some runtime details are still hard-coded instead of pulled from configuration or secrets.
- **Single destination:** Outputs are focused on local files; switching to Delta Lake or MySQL is not first-class.
- **Limited concurrency:** Potentially sequential fetching; the refactor should honor async/concurrency settings already present in configuration.

## Proposed Architecture
A layered approach keeps components independent:

1. **Resource definitions (blueprints):** For each object type, define how to extract external IDs and display names, plus default table/file naming and optional metadata extraction.
2. **API client layer:** Async-capable client that reads endpoint configuration, handles auth, rate limiting, pagination, and concurrency controls, and returns raw JSON objects.
3. **Parser/transform layer:** Normalizes raw JSON into a standard record shape (object type, external ID, display name, raw data, optional timestamps) using the resource definitions.
4. **Sink layer:** Pluggable writers for different destinations:
   - **File or logging sinks** for local testing.
   - **Delta Lake sink** to write Spark DataFrames to Delta tables on S3 (append or overwrite per run).
   - **MySQL sink** that converts records to DataFrames and writes via SQLAlchemy `to_sql`, with configurable table naming and write mode.

## Implementation Phases
### Phase 1: Local Modular Refactor
- Establish a clear package layout (configs, resource definitions, API client, parser, sinks, runner).
- Implement configuration loaders for endpoints, system settings, and credentials.
- Build resource definition mapping for ID/name extraction and target table hints.
- Implement API client with optional asyncio, pagination, rate limiting, and retry/backoff for 429s.
- Add parser to normalize records.
- Create file/logging sinks for local validation and a runner that orchestrates config → API → parse → sink.

### Phase 2: Databricks & Delta Lake
- Package or import the pipeline into a Databricks environment.
- Retrieve secrets (tokens, DB creds) via Databricks Secrets and pass them to the pipeline.
- Convert parsed records to Spark DataFrames and write to Delta tables on S3 using `format("delta")` with append/overwrite modes as needed.
- Validate writes with sample queries and adjust partitioning or modes based on volume.

### Phase 3: MySQL Integration
- Implement a MySQL sink using SQLAlchemy and pandas `to_sql`, with configurable connection strings and table names.
- Decide on snapshot (replace/truncate) vs. append/merge strategy per run; optionally add simple upsert or pre-delete logic for external IDs.
- Test locally against MySQL/SQLite, then validate connectivity and performance from Databricks if used there.

### Phase 4: Parameterization & Config Externalization
- Allow config loaders to pull from alternative sources (e.g., S3 or DB tables) in addition to JSON files.
- Accept runtime overrides for object types, output mode, and tenant/base URL via function args or CLI parameters.
- Keep the design flexible so future database-backed config can replace JSON without rewriting core logic.

### Phase 5: Documentation & Examples
- Add docstrings and comments for each module.
- Provide README instructions for local runs, Databricks runs (Delta sink), and MySQL runs (connection prerequisites and table behavior).
- Document how to add new object types by extending resource definitions and endpoint configs.

## Validation Strategy
- **Local tests:** Run with a minimal endpoint configuration to verify parsing and file/logging sinks, and exercise concurrency/rate limiting settings.
- **Databricks tests:** Write small batches to Delta tables and confirm counts/contents with Spark SQL.
- **MySQL tests:** Insert sample batches into test tables, confirm schema and data, and validate chosen write mode (append vs. replace/upsert).

## Expected Outcomes
- Clear separation of resource definitions, API fetching, parsing, and storage.
- Easily swappable sinks for Delta Lake and MySQL driven by configuration.
- Parameterized, environment-agnostic runs that minimize code changes between targets.
- Documentation that enables rapid onboarding and straightforward addition of new object types.
