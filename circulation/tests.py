from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Author, Book, Member, CirculationRecord, DAILY_FINE_RATE


class LibraryCirculationModelTests(TestCase):
    def setUp(self):
        self.author = Author.objects.create(name="George Orwell", biography="Author of 1984")
        self.book = Book.objects.create(
            title="1984",
            author=self.author,
            isbn="978-0451524935",
            genre="Dystopian",
            total_copies=2,
            available_copies=2,
            cover_url="https://example.com/cover.jpg"
        )
        self.member = Member.objects.create(
            name="John Doe",
            member_id="MEM-9901",
            email="john@example.com",
            phone="1234567890"
        )

    def test_book_initial_state(self):
        self.assertTrue(self.book.is_available)
        self.assertEqual(self.book.issued_copies, 0)

    def test_book_issue_copy_decrements_available(self):
        self.book.issue_copy()
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        self.assertEqual(self.book.issued_copies, 1)

    def test_cannot_issue_when_zero_copies(self):
        self.book.available_copies = 0
        self.book.save()
        with self.assertRaises(ValidationError):
            self.book.issue_copy()

    def test_book_return_copy_increments_available(self):
        self.book.available_copies = 1
        self.book.save()
        self.book.return_copy()
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

    def test_circulation_record_default_due_date_14_days(self):
        today = timezone.now().date()
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            issue_date=today
        )
        self.assertEqual(record.due_date, today + timedelta(days=14))
        self.assertFalse(record.returned)

    def test_on_time_return_calculates_zero_fine(self):
        today = timezone.now().date()
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            issue_date=today - timedelta(days=10),
            due_date=today + timedelta(days=4)
        )
        fine = record.complete_return(return_date=today)
        self.assertEqual(fine, Decimal('0.00'))
        self.assertEqual(record.fine_amount, Decimal('0.00'))
        self.assertTrue(record.returned)

    def test_overdue_return_calculates_fine(self):
        today = timezone.now().date()
        # Due 5 days ago, returned today -> 5 days overdue
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            issue_date=today - timedelta(days=19),
            due_date=today - timedelta(days=5)
        )
        self.assertTrue(record.is_overdue)
        self.assertEqual(record.days_overdue, 5)

        fine = record.complete_return(return_date=today)
        expected_fine = Decimal('5') * DAILY_FINE_RATE
        self.assertEqual(fine, expected_fine)
        self.assertEqual(record.fine_amount, expected_fine)
        self.assertTrue(record.returned)


class LibraryViewWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = Author.objects.create(name="Jane Austen")
        self.book = Book.objects.create(
            title="Pride and Prejudice",
            author=self.author,
            isbn="978-0141439518",
            genre="Romance",
            total_copies=1,
            available_copies=1
        )
        self.member = Member.objects.create(
            name="Alice Smith",
            member_id="MEM-1002",
            email="alice@example.com"
        )

    def test_catalog_view(self):
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pride and Prejudice")
        self.assertContains(response, "Jane Austen")

    def test_issue_workflow(self):
        issue_url = reverse('issue_book')
        response = self.client.post(issue_url, {
            'book': self.book.id,
            'member': self.member.id,
            'issue_date': str(timezone.now().date()),
            'due_date': str(timezone.now().date() + timedelta(days=14)),
        })
        self.assertEqual(response.status_code, 302)
        
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 0)
        self.assertEqual(CirculationRecord.objects.filter(book=self.book, returned=False).count(), 1)

    def test_return_workflow(self):
        # Create active loan
        today = timezone.now().date()
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            issue_date=today - timedelta(days=16),
            due_date=today - timedelta(days=2),  # 2 days overdue
            returned=False
        )
        self.book.available_copies = 0
        self.book.save()

        return_url = reverse('return_book')
        response = self.client.post(return_url, {
            'circulation_record': record.id,
            'return_date': str(today),
        })
        self.assertEqual(response.status_code, 302)

        record.refresh_from_db()
        self.assertTrue(record.returned)
        self.assertEqual(record.fine_amount, Decimal('2.00'))  # 2 days * $1.00

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_member_dashboard(self):
        response = self.client.get(reverse('member_dashboard', args=[self.member.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")
        self.assertContains(response, "MEM-1002")

    def test_api_calculate_fine(self):
        url = reverse('api_calculate_fine')
        response = self.client.get(url, {
            'due_date': '2026-10-01',
            'return_date': '2026-10-05',
            'rate': '1.00'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['overdue_days'], 4)
        self.assertEqual(data['fine_amount'], 4.0)
