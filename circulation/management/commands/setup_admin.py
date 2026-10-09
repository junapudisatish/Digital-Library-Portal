import os
import sys
import getpass
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Safely create or update the superuser administrator account with active permissions."

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default=os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin'),
            help="Superuser username (default: env DJANGO_SUPERUSER_USERNAME or 'admin')"
        )
        parser.add_argument(
            '--email',
            type=str,
            default=os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com'),
            help="Superuser email (default: env DJANGO_SUPERUSER_EMAIL or 'admin@example.com')"
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help="Superuser password (optional; reads from DJANGO_SUPERUSER_PASSWORD or prompts if omitted)"
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        email = options['email']
        password = options['password'] or os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        # If interactive and password is not provided, prompt securely
        if not password and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
            try:
                password = getpass.getpass(f"Enter password for superuser '{username}': ")
            except (EOFError, KeyboardInterrupt):
                self.stderr.write("\nOperation cancelled.")
                return

        user = User.objects.filter(username=username).first()
        if user:
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            if password:
                user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated administrator '{username}' with staff and superuser permissions."
                )
            )
        else:
            if not password:
                self.stderr.write(
                    self.style.ERROR(
                        f"Error: Password is required to create new superuser '{username}'. Provide --password or set DJANGO_SUPERUSER_PASSWORD."
                    )
                )
                return
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created superuser '{username}' ({email})."
                )
            )
