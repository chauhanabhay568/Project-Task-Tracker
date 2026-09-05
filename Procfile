web: uv run python manage.py migrate --noinput && uv run python manage.py seed && uv run python manage.py collectstatic --noinput && uv run gunicorn config.wsgi --workers 2
