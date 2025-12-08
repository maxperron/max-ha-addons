#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Family Expenses Tracker..."
exec python3 /app/run.py
