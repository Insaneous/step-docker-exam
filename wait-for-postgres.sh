#!/bin/bash

host="$1"
shift
until nc -z "$host" 5432; do
  echo "Waiting for PostgreSQL at $host:5432..."
  sleep 2
done
echo "PostgreSQL is up and running!"
exec "$@"
