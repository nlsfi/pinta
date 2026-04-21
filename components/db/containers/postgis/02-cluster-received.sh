#!/bin/bash

# Applied from https://github.com/postgis/docker-postgis licensed under MIT license

set -e

# Perform all actions as $POSTGRES_USER
export PGUSER="$POSTGRES_USER"

# Create the main role with necessary permissions

echo "Creating ansible admin user"
psql <<-EOSQL
  CREATE ROLE "admin" LOGIN CREATEDB CREATEROLE PASSWORD 'admin';
EOSQL
