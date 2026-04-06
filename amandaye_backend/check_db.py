import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amandaye_backend.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DESCRIBE socios_cambios;")
    for row in cursor.fetchall():
        print(row)
