-- Run once as a role allowed to create databases and warehouses.
USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS GOVERNAI
  COMMENT = 'GovernAI simulated-banking governance platform';

CREATE SCHEMA IF NOT EXISTS GOVERNAI.RAW
  COMMENT = 'Accepted source-shaped records with immutable batch evidence';
CREATE SCHEMA IF NOT EXISTS GOVERNAI.STAGING
  COMMENT = 'dbt normalization views';
CREATE SCHEMA IF NOT EXISTS GOVERNAI.CURATED
  COMMENT = 'Conformed dimensions, facts, and governed features';
CREATE SCHEMA IF NOT EXISTS GOVERNAI.ANALYTICS
  COMMENT = 'Approved business marts and dashboard-facing products';
CREATE SCHEMA IF NOT EXISTS GOVERNAI.GOVERNANCE
  COMMENT = 'Pipeline, reconciliation, lineage, policy, and audit evidence';

CREATE WAREHOUSE IF NOT EXISTS GOVAI_INGEST_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Small warehouse for GovernAI ingestion and verification';

CREATE WAREHOUSE IF NOT EXISTS GOVAI_TRANSFORM_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Small warehouse for GovernAI dbt transformations';
