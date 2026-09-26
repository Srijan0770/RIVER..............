#!/usr/bin/env bash
# Render build script

pip install -r requirements.txt
python manage.py collectstatic --noinput
