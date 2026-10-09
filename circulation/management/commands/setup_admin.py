import os
import sys
import getpass
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Safely create the administrator superuser ('admin') if missing without overwriting existing credentials."

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
            default=os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@library.demo'),
            help="Superuser email (default: env DJANGO_SUPERUSER_EMAIL or 'admin@library.demo')"
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help="Superuser password (reads from DJANGO_SUPERUSER_PASSWORD or prompts securely if omitted)"
        )
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help="Explicitly reset the password for existing administrator account (requires confirmation)"
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        email = options['email']
        password = options['password'] or os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        reset_password = options.get('reset_password', False)

        user = User.objects.filter(username=username).first()
        if user:
            # Account exists. Check whether explicit password reset was requested
            if reset_password:
                if not password and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
                    try:
                        password = getpass.getpass(f"Enter new password for superuser '{username}': ")
                    except (EOFError, KeyboardInterrupt):
                        self.stderr.write("\nOperation cancelled.")
                        return
                if password:
                    user.set_password(password)
                user.email = email or user.email
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully updated credentials and permissions for administrator '{username}'."
                    )
                )
            else:
                # Do NOT overwrite existing credentials automatically!
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Administrator '{username}' already exists. Preserved existing password and verified active admin permissions."
                    )
                )
            return

        # Account does not exist - create a new superuser
        if not password and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
            try:
                password = getpass.getpass(f"Enter password for new superuser '{username}': ")
            except (EOFError, KeyboardInterrupt):
                self.stderr.write("\nOperation cancelled.")
                return

        if not password:
            self.stderr.write(
                self.style.ERROR(
                    f"Error: Password is required to create new administrator '{username}'. Provide --password, set DJANGO_SUPERUSER_PASSWORD, or run interactively."
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
                f"Successfully created administrator superuser '{username}' ({email})."
            )
        )
