import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_portal.settings')
django.setup()

from django.contrib.auth import get_user_model
from circulation.models import Book
from circulation.seed_data import populate_sample_data

def create_admin():
    User = get_user_model()
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@library.demo')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admini!123')

    admin_user = User.objects.filter(username=username).first()
    if not admin_user:
        if password:
            print(f"Creating superuser: {username} ({email})")
            User.objects.create_superuser(username=username, email=email, password=password)
            print("Superuser created successfully.")
        else:
            print(f"Notice: Superuser '{username}' does not exist and DJANGO_SUPERUSER_PASSWORD is not set in environment.")
    else:
        # Safely preserve existing administrator credentials; verify active staff and superuser status
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.save(update_fields=['is_staff', 'is_superuser', 'is_active'])
        print(f"Verified administrator '{username}' exists with active staff and superuser permissions (credentials preserved).")

    # Automatically populate sample books and circulation records if database is empty
    if Book.objects.count() == 0:
        print("Seeding initial library catalog and sample circulation records...")
        count = populate_sample_data()
        print(f"Seeded {count} books with active and past circulation records.")

if __name__ == '__main__':
    create_admin()
