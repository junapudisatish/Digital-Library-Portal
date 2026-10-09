from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core import mail
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Author, Book, Member, CirculationRecord, DAILY_FINE_RATE

User = get_user_model()


class LibraryCirculationModelTests(TestCase):
    def setUp(self):
        self.author = Author.objects.create(name="George Orwell", biography="Author of 1984")
        self.book = Book.objects.create(
            title="1984",
            author=self.author,
            isbn="978-0451524935",
            genre="Dystopian",
            description="Classic dystopian novel about Oceania and Big Brother.",
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

    def test_book_initial_state_and_description(self):
        self.assertTrue(self.book.is_available)
        self.assertEqual(self.book.issued_copies, 0)
        self.assertEqual(self.book.description, "Classic dystopian novel about Oceania and Big Brother.")

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
            issue_date=today,
            status='APPROVED'
        )
        self.assertEqual(record.due_date, today + timedelta(days=14))
        self.assertFalse(record.returned)

    def test_on_time_return_calculates_zero_fine(self):
        today = timezone.now().date()
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            issue_date=today - timedelta(days=10),
            due_date=today + timedelta(days=4),
            status='APPROVED'
        )
        fine = record.complete_return(return_date=today)
        self.assertEqual(fine, Decimal('0.00'))
        self.assertEqual(record.fine_amount, Decimal('0.00'))
        self.assertTrue(record.returned)
        self.assertEqual(record.status, 'RETURNED')

    def test_overdue_return_calculates_inr_fine(self):
        today = timezone.now().date()
        # Due 5 days ago, returned today -> 5 days overdue at ₹5/day = ₹25.00
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            issue_date=today - timedelta(days=19),
            due_date=today - timedelta(days=5),
            status='APPROVED'
        )
        self.assertTrue(record.is_overdue)
        self.assertEqual(record.days_overdue, 5)

        fine = record.complete_return(return_date=today)
        expected_fine = Decimal('5') * Decimal('5.00')  # ₹25.00
        self.assertEqual(fine, expected_fine)
        self.assertEqual(record.fine_amount, expected_fine)
        self.assertTrue(record.returned)
        self.assertEqual(record.status, 'RETURNED')


class LibraryWorkflowAndPermissionsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = Author.objects.create(name="Jane Austen")
        self.book = Book.objects.create(
            title="Pride and Prejudice",
            author=self.author,
            isbn="978-0141439518",
            genre="Romance",
            description="A masterpiece of manners and romantic friction.",
            total_copies=2,
            available_copies=2
        )
        self.student_user = User.objects.create_user(
            username="student_alice",
            email="alice@example.com",
            password="password123",
            first_name="Alice",
            last_name="Smith"
        )
        self.member = Member.objects.create(
            user=self.student_user,
            name="Alice Smith",
            member_id="MEM-1002",
            email="alice@example.com"
        )
        self.staff_librarian = User.objects.create_superuser(
            username="librarian_bob",
            email="librarian@library.demo",
            password="librarianpass123"
        )

    # 1. Catalog & Search
    def test_catalog_view_with_sorting_and_pagination(self):
        response = self.client.get(reverse('catalog'), {'sort': 'title_asc'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pride and Prejudice")
        self.assertContains(response, "Jane Austen")

    def test_catalog_search(self):
        response = self.client.get(reverse('catalog'), {'q': 'Prejudice'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pride and Prejudice")

    def test_book_detail_view(self):
        response = self.client.get(reverse('book_detail', args=[self.book.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pride and Prejudice")
        self.assertContains(response, "978-0141439518")

    # 2. Student Borrowing Workflow (Phase 8)
    def test_unauthenticated_borrow_request_redirects_to_login(self):
        borrow_url = reverse('borrow_book', args=[self.book.id])
        response = self.client.post(borrow_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_student_borrow_request_creates_pending_record_without_reducing_stock(self):
        self.client.force_login(self.student_user)
        borrow_url = reverse('borrow_book', args=[self.book.id])
        response = self.client.post(borrow_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('student_dashboard'))

        # Record should exist with PENDING status
        record = CirculationRecord.objects.get(book=self.book, member=self.member)
        self.assertEqual(record.status, 'PENDING')
        self.assertFalse(record.returned)
        self.assertIsNone(record.issue_date)
        self.assertIsNone(record.due_date)

        # IMPORTANT: Stock must NOT be reduced upon mere request submission (Phase 8 requirement)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

    def test_prevent_duplicate_borrow_requests(self):
        self.client.force_login(self.student_user)
        borrow_url = reverse('borrow_book', args=[self.book.id])

        # First request
        self.client.post(borrow_url)
        self.assertEqual(CirculationRecord.objects.filter(book=self.book, member=self.member).count(), 1)

        # Second request must be blocked
        response = self.client.post(borrow_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CirculationRecord.objects.filter(book=self.book, member=self.member).count(), 1)

    # 3. Librarian Approval Workflow (Phase 8)
    def test_librarian_approves_pending_request(self):
        # Create pending request
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            status='PENDING'
        )
        self.assertEqual(self.book.available_copies, 2)

        # Librarian approves
        self.client.force_login(self.staff_librarian)
        approve_url = reverse('approve_request', args=[record.id])
        response = self.client.post(approve_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin:circulation_circulationrecord_changelist'))

        # Check record updated
        record.refresh_from_db()
        self.assertEqual(record.status, 'APPROVED')
        today = timezone.now().date()
        self.assertEqual(record.issue_date, today)
        self.assertEqual(record.due_date, today + timedelta(days=14))
        self.assertEqual(record.approved_by, self.staff_librarian)

        # Stock must be decremented by exactly 1 upon approval
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_librarian_cannot_approve_when_out_of_stock(self):
        # Book with 0 copies
        self.book.available_copies = 0
        self.book.save()

        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            status='PENDING'
        )

        self.client.force_login(self.staff_librarian)
        approve_url = reverse('approve_request', args=[record.id])
        response = self.client.post(approve_url)
        self.assertEqual(response.status_code, 302)

        # Record must remain PENDING
        record.refresh_from_db()
        self.assertEqual(record.status, 'PENDING')
        self.assertIsNone(record.issue_date)

    def test_librarian_rejects_pending_request(self):
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            status='PENDING'
        )

        self.client.force_login(self.staff_librarian)
        reject_url = reverse('reject_request', args=[record.id])
        response = self.client.post(reject_url, {
            'reason': 'Reserved for examination period reference only.'
        })
        self.assertEqual(response.status_code, 302)

        record.refresh_from_db()
        self.assertEqual(record.status, 'REJECTED')
        self.assertEqual(record.rejection_reason, 'Reserved for examination period reference only.')
        self.assertEqual(record.approved_by, self.staff_librarian)

        # Stock remains untouched
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

    def test_student_cannot_approve_or_reject_requests(self):
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            status='PENDING'
        )

        self.client.force_login(self.student_user)
        approve_res = self.client.post(reverse('approve_request', args=[record.id]))
        self.assertEqual(approve_res.status_code, 302)

        # Must still be PENDING
        record.refresh_from_db()
        self.assertEqual(record.status, 'PENDING')

    # 4. Manual Issue and Return Desk (Staff)
    def test_staff_manual_issue_workflow(self):
        self.client.force_login(self.staff_librarian)
        issue_url = reverse('issue_book')
        response = self.client.post(issue_url, {
            'book': self.book.id,
            'member': self.member.id,
            'issue_date': str(timezone.now().date()),
            'due_date': str(timezone.now().date() + timedelta(days=14)),
        })
        self.assertEqual(response.status_code, 302)

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        self.assertEqual(CirculationRecord.objects.filter(book=self.book, returned=False).count(), 1)

    def test_staff_return_workflow_with_fine(self):
        today = timezone.now().date()
        record = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            issue_date=today - timedelta(days=16),
            due_date=today - timedelta(days=2),  # 2 days overdue
            status='APPROVED',
            returned=False
        )
        self.book.available_copies = 1
        self.book.save()

        self.client.force_login(self.staff_librarian)
        return_url = reverse('return_book')
        response = self.client.post(return_url, {
            'circulation_record': record.id,
            'return_date': str(today),
        })
        self.assertEqual(response.status_code, 302)

        record.refresh_from_db()
        self.assertTrue(record.returned)
        self.assertEqual(record.status, 'RETURNED')
        # 2 days * ₹5.00 = ₹10.00
        self.assertEqual(record.fine_amount, Decimal('10.00'))

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

    # 5. Member Dashboard & Profile Isolation (Phase 9 & 16)
    def test_student_dashboard_my_library_displays_sections(self):
        today = timezone.now().date()
        # Pending request
        CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            status='PENDING'
        )
        self.client.force_login(self.student_user)
        res = self.client.get(reverse('student_dashboard'))
        self.assertContains(res, "My Library")
        self.assertContains(res, "Pending Requests")
        self.assertContains(res, "Pride and Prejudice")

    def test_student_registration_workflow(self):
        register_url = reverse('register')
        response = self.client.post(register_url, {
            'username': 'bob_new',
            'first_name': 'Bob',
            'last_name': 'Marley',
            'email': 'bob@student.demo',
            'student_id': 'STU-9999',
            'phone': '555-987-6543',
            'password': 'safePassword123',
            'confirm_password': 'safePassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='bob_new').exists())
        self.assertTrue(Member.objects.filter(member_id='STU-9999').exists())

    # 6. Admin Authentication & Security (Phase 3 & 14)
    def test_login_page_does_not_reveal_credentials(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "1-Click Demonstration Shortcuts")
        self.assertNotContains(response, "admin123")
        self.assertNotContains(response, "student123")
        self.assertNotContains(response, "admini@123")
        self.assertContains(response, reverse('password_reset'))

    def test_admin_setup_command_and_login_validation(self):
        initial_test_pass = 'InitialAdminTestPass#2026'
        call_command('setup_admin', username='admin', password=initial_test_pass, email='admin@library.demo')
        admin_user = User.objects.get(username='admin')
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_active)

        # Invalid login rejected
        invalid_response = self.client.post(reverse('login'), {
            'username': 'admin',
            'password': 'wrongpassword'
        })
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "Invalid username or password")

        # Valid login accepted and redirects to admin interface
        valid_response = self.client.post(reverse('login'), {
            'username': 'admin',
            'password': initial_test_pass
        })
        self.assertEqual(valid_response.status_code, 302)
        self.assertEqual(valid_response.url, '/admin/')

    def test_password_change_workflow(self):
        initial_test_pass = 'InitialAdminTestPass#2026'
        call_command('setup_admin', username='admin', password=initial_test_pass)
        self.client.login(username='admin', password=initial_test_pass)

        get_res = self.client.get(reverse('password_change'))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, "Current Password")

        post_res = self.client.post(reverse('password_change'), {
            'old_password': initial_test_pass,
            'new_password1': 'NewAdminPass@2026!',
            'new_password2': 'NewAdminPass@2026!'
        })
        self.assertEqual(post_res.status_code, 302)
        self.assertEqual(post_res.url, reverse('password_change_done'))

        self.client.logout()
        self.assertFalse(self.client.login(username='admin', password=initial_test_pass))
        self.assertTrue(self.client.login(username='admin', password='NewAdminPass@2026!'))

    def test_password_reset_flow(self):
        call_command('setup_admin', username='admin', password='TemporaryResetPass#2026', email='admin@library.demo')

        res = self.client.get(reverse('password_reset'))
        self.assertEqual(res.status_code, 200)

        res = self.client.post(reverse('password_reset'), {
            'email': 'admin@library.demo'
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

    # 7. Member Terminology & Admin Access Control
    def test_member_terminology_in_admin_views(self):
        self.client.force_login(self.staff_librarian)
        members_res = self.client.get(reverse('member_list'))
        self.assertEqual(members_res.status_code, 200)
        self.assertContains(members_res, "Members Directory")
        self.assertContains(members_res, "Register New Member")
        self.assertNotContains(members_res, "Patrons Directory")
        self.assertNotContains(members_res, "Register New Patron")

    # 8. Django Admin URL & Access Tests
    def test_admin_portal_available_at_admin_route(self):
        """Visiting /admin/ opens Django's built-in admin login interface for unauthenticated users."""
        response = self.client.get('/admin/')
        # Django admin redirects unauthenticated users to /admin/login/?next=/admin/
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

        login_res = self.client.get('/admin/login/')
        self.assertEqual(login_res.status_code, 200)
        self.assertContains(login_res, "Digital Library Administration")
        self.assertContains(login_res, "login-form")

    def test_admin_login_and_access_admin_interface(self):
        """Superuser admin can log in and view Django Admin with customized branding."""
        admin_pass = 'SecureAdminAccess#2026'
        call_command('setup_admin', username='admin', password=admin_pass)
        self.client.login(username='admin', password=admin_pass)

        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Digital Library Administration")
        self.assertContains(response, reverse('admin:password_change'))

    def test_regular_student_cannot_access_django_admin(self):
        """Regular library students cannot access /admin/ or admin privileged views."""
        self.client.force_login(self.student_user)

        # GET /admin/ redirects non-staff users to admin login
        admin_res = self.client.get('/admin/')
        self.assertEqual(admin_res.status_code, 302)
        self.assertIn('/admin/login/', admin_res.url)

        # Regular user attempting admin book addition is blocked
        add_book_res = self.client.get('/admin/circulation/book/add/')
        self.assertEqual(add_book_res.status_code, 302)

        # Regular user cannot access members directory
        members_res = self.client.get(reverse('member_list'))
        self.assertEqual(members_res.status_code, 302)
        self.assertIn(reverse('login'), members_res.url)

    def test_staff_dashboard_is_removed(self):
        """The staff dashboard route /staff/ has been completely removed."""
        res = self.client.get('/staff/')
        self.assertEqual(res.status_code, 404)

    # 9. Built-in Admin Password Change Workflow
    def test_admin_built_in_password_change_flow(self):
        """Administrator changes password via Django's built-in /admin/password_change/ interface."""
        initial_pass = 'AdminOriginalPass#2026'
        new_pass = 'AdminBrandNewPass#2026'
        call_command('setup_admin', username='admin', password=initial_pass)
        self.client.login(username='admin', password=initial_pass)

        # 1. Access password change page in admin
        get_res = self.client.get('/admin/password_change/')
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, "old_password")
        self.assertContains(get_res, "new_password1")

        # 2. Reject wrong current password
        wrong_old_res = self.client.post('/admin/password_change/', {
            'old_password': 'IncorrectOldPassword',
            'new_password1': new_pass,
            'new_password2': new_pass,
        })
        self.assertEqual(wrong_old_res.status_code, 200)
        self.assertContains(wrong_old_res, "Your old password was entered incorrectly.")

        # 3. Successful password change
        post_res = self.client.post('/admin/password_change/', {
            'old_password': initial_pass,
            'new_password1': new_pass,
            'new_password2': new_pass,
        })
        self.assertEqual(post_res.status_code, 302)
        self.assertEqual(post_res.url, reverse('admin:password_change_done'))

        # 4. Confirmation page loads and confirms session
        done_res = self.client.get(reverse('admin:password_change_done'))
        self.assertEqual(done_res.status_code, 200)
        self.assertContains(done_res, "Password change successful")

        # 5. Verify new password authentication works and old password fails
        self.client.logout()
        self.assertFalse(self.client.login(username='admin', password=initial_pass))
        self.assertTrue(self.client.login(username='admin', password=new_pass))

    # 10. setup_admin Credentials Safety
    def test_setup_admin_preserves_existing_password(self):
        """setup_admin does not overwrite administrator credentials if user already exists."""
        first_pass = 'AdminFirstPassword#2026'
        second_pass = 'AdminSecondPassword#2026'

        # First run creates user
        call_command('setup_admin', username='admin', password=first_pass)
        self.assertTrue(self.client.login(username='admin', password=first_pass))
        self.client.logout()

        # Second run without --reset-password MUST preserve existing password
        call_command('setup_admin', username='admin', password=second_pass)
        self.assertTrue(self.client.login(username='admin', password=first_pass))
        self.client.logout()
        self.assertFalse(self.client.login(username='admin', password=second_pass))

        # Explicit reset with --reset-password updates password
        call_command('setup_admin', username='admin', password=second_pass, reset_password=True)
        self.assertTrue(self.client.login(username='admin', password=second_pass))

    # 11. Django Admin Bulk Actions for Circulation
    def test_circulation_admin_actions(self):
        """Admin actions approve, reject, and return records in Django Admin."""
        from circulation.admin import CirculationRecordAdmin
        from django.contrib.admin.sites import AdminSite

        admin_user = User.objects.create_superuser(username='super_mgr', email='mgr@library.demo', password='password123')
        site = AdminSite()
        model_admin = CirculationRecordAdmin(CirculationRecord, site)

        # Pending request
        record_pending = CirculationRecord.objects.create(
            book=self.book,
            member=self.member,
            status='PENDING'
        )
        self.assertEqual(self.book.available_copies, 2)

        # Test approve action
        class DummyMessages:
            def add(self, level, message, extra_tags=''):
                pass

        class MockRequest:
            user = admin_user
            def __init__(self):
                self._messages = DummyMessages()
            def message_user(self, *args, **kwargs):
                pass

        req = MockRequest()
        model_admin.approve_requests(req, CirculationRecord.objects.filter(id=record_pending.id))
        record_pending.refresh_from_db()
        self.assertEqual(record_pending.status, 'APPROVED')
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

        # Test return action
        model_admin.process_returns(req, CirculationRecord.objects.filter(id=record_pending.id))
        record_pending.refresh_from_db()
        self.assertTrue(record_pending.returned)
        self.assertEqual(record_pending.status, 'RETURNED')
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)
