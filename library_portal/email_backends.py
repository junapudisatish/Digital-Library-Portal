
import os
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class BrevoEmailBackend(BaseEmailBackend):
    """Send Django emails through Brevo's HTTPS API."""

    API_URL = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = os.environ.get("BREVO_API_KEY", "").strip()

    @staticmethod
    def address_list(addresses):
        result = []
        for address in addresses or []:
            name, email = parseaddr(address)
            if email:
                item = {"email": email}
                if name:
                    item["name"] = name
                result.append(item)
        return result

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        if not self.api_key:
            raise ValueError("BREVO_API_KEY is not configured.")

        sent = 0

        for message in email_messages:
            sender_name, sender_email = parseaddr(
                message.from_email or settings.DEFAULT_FROM_EMAIL
            )
            recipients = self.address_list(message.to)

            if not recipients:
                continue

            if not sender_email:
                raise ValueError("A valid sender email is required.")

            payload = {
                "sender": {
                    "name": sender_name or "LIBRA Digital Library",
                    "email": sender_email,
                },
                "to": recipients,
                "subject": message.subject or "Library notification",
            }

            cc = self.address_list(getattr(message, "cc", []))
            bcc = self.address_list(getattr(message, "bcc", []))

            if cc:
                payload["cc"] = cc
            if bcc:
                payload["bcc"] = bcc

            alternatives = getattr(message, "alternatives", None) or []
            html_content = next(
                (
                    content
                    for content, mimetype in reversed(alternatives)
                    if mimetype == "text/html"
                ),
                None,
            )

            if html_content is not None:
                payload["htmlContent"] = html_content
            elif getattr(message, "content_subtype", "plain") == "html":
                payload["htmlContent"] = message.body
            else:
                payload["textContent"] = message.body

            response = requests.post(
                self.API_URL,
                headers={
                    "accept": "application/json",
                    "api-key": self.api_key,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=15,
            )

            if not response.ok:
                raise RuntimeError(
                    f"Brevo API returned HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                )

            sent += 1

        return sent
