#!/bin/bash

# When recieving a new cluster, these steps need to be done manually:
#   - create the main ansible user as the existing superuser
#   - add other necessary extensions to the template as the existing superuser
#   - possibly verify template is actually set as template

# Applied from https://github.com/postgis/docker-postgis licensed under MIT license

set -e

# Perform all actions as $POSTGRES_USER
export PGUSER="$POSTGRES_USER"

# Create the main role with necessary permissions

echo "Creating ansible admin user"
psql <<-EOSQL
  CREATE ROLE "admin" LOGIN CREATEDB CREATEROLE PASSWORD 'admin';
EOSQL
