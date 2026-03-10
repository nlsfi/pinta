#!/bin/sh

# When requesting a new cluster, these items need to be asked for:
#   - a superuser account
#   - a template database with postgis extension

# Applied from https://github.com/postgis/docker-postgis licensed under MIT license

set -e

# Perform all actions as $POSTGRES_USER
export PGUSER="$POSTGRES_USER"

# Create the template db

echo "Creating template db"
psql <<-'EOSQL'
  CREATE DATABASE template_postgis IS_TEMPLATE true;
EOSQL

# Load postgis into the template database

echo "Loading postgis into the template db"
psql --dbname=template_postgis <<-'EOSQL'
  CREATE EXTENSION IF NOT EXISTS postgis;
EOSQL
