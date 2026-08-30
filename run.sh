#!/bin/sh
# Lancer le site (production légère) : http://localhost:8000
cd "$(dirname "$0")"
exec python3 app.py
