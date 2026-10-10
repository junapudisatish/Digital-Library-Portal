from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core import mail
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
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


class NewFeaturesAndSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = Author.objects.create(name="Virginia Woolf", biography="Pioneering modernist author.")
        self.book = Book.objects.create(
            title="To the Lighthouse",
            author=self.author,
            isbn="978-0156907392",
            genre="Fiction",
            total_copies=3,
            available_copies=3
        )

        # Student user A and member profile
        self.user_a = User.objects.create_user(
            username="student_alice",
            email="alice@college.edu",
            password="PasswordAlice123!",
            first_name="Alice",
            last_name="Smith"
        )
        self.member_a = Member.objects.create(
            user=self.user_a,
            name="Alice Smith",
            email="alice@college.edu",
            member_id="STU-001"
        )

        # Student user B and member profile
        self.user_b = User.objects.create_user(
            username="student_bob",
            email="bob@college.edu",
            password="PasswordBob123!",
            first_name="Bob",
            last_name="Jones"
        )
        self.member_b = Member.objects.create(
            user=self.user_b,
            name="Bob Jones",
            email="bob@college.edu",
            member_id="STU-002"
        )

        # Librarian / Staff user
        self.staff_user = User.objects.create_user(
            username="librarian_carol",
            email="carol@library.edu",
            password="PasswordCarol123!",
            is_staff=True
        )

    def test_home_page_loads_and_displays_hero_and_stats(self):
        """Landing page renders successfully with editorial hero and real ORM statistics."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your Next Great Read Starts Here")
        self.assertContains(response, "To the Lighthouse")
        self.assertIn('total_titles', response.context)
        self.assertIn('total_inventory', response.context)
        self.assertEqual(response.context['total_titles'], 1)
        self.assertEqual(response.context['total_inventory'], 3)

    def test_librarian_dashboard_access_control(self):
        """Librarian dashboard requires staff privileges; anonymous and student users are blocked."""
        # 1. Anonymous user redirected to login
        anon_res = self.client.get(reverse('librarian_dashboard'))
        self.assertEqual(anon_res.status_code, 302)
        self.assertIn(reverse('login'), anon_res.url)

        # 2. Student user redirected away to student_dashboard
        self.client.login(username="student_alice", password="PasswordAlice123!")
        student_res = self.client.get(reverse('librarian_dashboard'))
        self.assertEqual(student_res.status_code, 302)
        self.assertIn(reverse('student_dashboard'), student_res.url)
        self.client.logout()

        # 3. Staff user receives 200 OK with analytics KPIs
        self.client.login(username="librarian_carol", password="PasswordCarol123!")
        staff_res = self.client.get(reverse('librarian_dashboard'))
        self.assertEqual(staff_res.status_code, 200)
        self.assertContains(staff_res, "Library Operations &amp; Circulation Analytics")
        self.assertIn('total_titles', staff_res.context)
        self.assertIn('active_loans_count', staff_res.context)
        self.assertIn('genre_labels', staff_res.context)

    def test_student_return_privacy_and_authorization(self):
        """A student cannot return another member's borrowed book."""
        # Alice borrows the book
        record_alice = CirculationRecord.objects.create(
            book=self.book,
            member=self.member_a,
            status='APPROVED',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=14)
        )
        self.book.issue_copy()
        self.assertEqual(self.book.available_copies, 2)

        # Bob logs in and attempts to return Alice's record
        self.client.login(username="student_bob", password="PasswordBob123!")

        # Attempt to return Alice's book via POST
        post_data = {
            'circulation_record': record_alice.id,
            'return_date': timezone.now().date().isoformat()
        }
        res = self.client.post(reverse('return_book'), post_data)
        record_alice.refresh_from_db()
        self.assertFalse(record_alice.returned)
        self.assertEqual(record_alice.status, 'APPROVED')
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)  # Copies unchanged

        # Now Alice logs in and returns her own book
        self.client.logout()
        self.client.login(username="student_alice", password="PasswordAlice123!")
        alice_post_res = self.client.post(reverse('return_book'), post_data, follow=True)
        self.assertEqual(alice_post_res.status_code, 200)
        record_alice.refresh_from_db()
        self.assertTrue(record_alice.returned)
        self.assertEqual(record_alice.status, 'RETURNED')
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 3)  # Copy replenished

    def test_seed_data_security(self):
        """Public visitors and students cannot trigger database seed/reset."""
        # Anonymous blocked
        res_anon = self.client.get(reverse('seed_data'))
        self.assertEqual(res_anon.status_code, 302)

        # Student member redirected away to catalog
        self.client.login(username="student_alice", password="PasswordAlice123!")
        res_student = self.client.get(reverse('seed_data'))
        self.assertEqual(res_student.status_code, 302)
        self.assertIn(reverse('catalog'), res_student.url)
        self.client.logout()

        # Staff user permitted via POST
        self.client.login(username="librarian_carol", password="PasswordCarol123!")
        res_staff = self.client.post(reverse('seed_data'), {'force_reset': '0'}, follow=True)
        self.assertEqual(res_staff.status_code, 200)
        self.assertContains(res_staff, "Sample library dataset successfully updated")

    def test_author_directory_and_crud_permissions(self):
        """Author directory is publicly searchable, but creation is restricted to staff."""
        # Public search
        res = self.client.get(reverse('author_list') + '?q=Virginia')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Virginia Woolf")

        # Student cannot create author (redirects to author_list)
        self.client.login(username="student_alice", password="PasswordAlice123!")
        res_student = self.client.post(reverse('author_create'), {'name': 'New Author', 'biography': 'Bio'})
        self.assertEqual(res_student.status_code, 302)
        self.assertIn(reverse('author_list'), res_student.url)
        self.client.logout()

        # Staff can create author
        self.client.login(username="librarian_carol", password="PasswordCarol123!")
        res_staff = self.client.post(reverse('author_create'), {'name': 'Chinua Achebe', 'biography': 'Author of Things Fall Apart'}, follow=True)
        self.assertEqual(res_staff.status_code, 200)
        self.assertTrue(Author.objects.filter(name='Chinua Achebe').exists())

    def test_institutional_pages(self):
        """About, policies, help, and due calculator load with 200 OK."""
        for url_name in ['about', 'policies', 'help', 'calculator', 'due_calculator']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)


class PasswordResetWorkflowTests(TestCase):
    """
    Comprehensive test suite for the upgraded password-reset workflow:
    - Request page and email dispatch
    - Valid and invalid/expired token verification
    - Server-side password strength validation (Django AUTH_PASSWORD_VALIDATORS)
    - Successful password change, token single-use invalidation, and login authentication.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="student_reader",
            email="reader@library.demo",
            password="InitialPassword123!",
            first_name="Reader",
            last_name="Student"
        )
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.valid_token = default_token_generator.make_token(self.user)

    def test_password_reset_page_loads_with_brand_and_form(self):
        """Password reset request page renders properly with LIBRA branding."""
        res = self.client.get(reverse('password_reset'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "LIBRA")
        self.assertContains(res, "Reset Account Password")
        self.assertContains(res, "Send Reset Link")

    def test_password_reset_email_dispatch_flow(self):
        """Requesting a reset email dispatches an email with valid token link."""
        mail.outbox = []
        res = self.client.post(reverse('password_reset'), {'email': 'reader@library.demo'}, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Check Your Email")
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn("/password-reset/confirm/", email_body)

    def test_password_reset_confirm_with_valid_token_displays_form(self):
        """Opening a valid reset link renders the modern password form with strength meter."""
        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': self.valid_token})
        res = self.client.get(confirm_url, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Create a New Password")
        self.assertContains(res, "Password Strength:")
        self.assertContains(res, "Password Requirements:")
        self.assertContains(res, "toggle-password-btn")
        self.assertContains(res, "id_new_password1")
        self.assertContains(res, "id_new_password2")
        self.assertContains(res, "Reset Password")

    def test_password_reset_confirm_with_invalid_or_expired_token(self):
        """Invalid or expired reset links display friendly error and no form."""
        bad_confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': 'invalid-token-12345'})
        res = self.client.get(bad_confirm_url, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Invalid or Expired Link")
        self.assertContains(res, "Request a New Reset Link")
        self.assertNotContains(res, 'id="passwordResetConfirmForm"')

    def test_password_reset_mismatched_passwords_rejected(self):
        """Submitting mismatched passwords is rejected by Django."""
        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': self.valid_token})
        self.client.get(confirm_url, follow=True)
        set_pwd_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': 'set-password'})
        res = self.client.post(set_pwd_url, {
            'new_password1': 'StrongPass2026#Valid',
            'new_password2': 'DifferentPassword2026#Mismatch',
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['form'].errors)

    def test_password_reset_violating_validators_rejected(self):
        """Submitting weak passwords violating Django validators is rejected by server."""
        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': self.valid_token})
        self.client.get(confirm_url, follow=True)
        set_pwd_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': 'set-password'})
        res = self.client.post(set_pwd_url, {
            'new_password1': '12345',
            'new_password2': '12345',
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['form'].errors)

    def test_password_reset_success_updates_password_and_authenticates(self):
        """Submitting a valid password updates user password hash, renders success page, and enables login."""
        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': self.valid_token})
        self.client.get(confirm_url, follow=True)
        set_pwd_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': 'set-password'})
        new_strong_pass = 'NovelBookworm@2026#Libra'
        res = self.client.post(set_pwd_url, {
            'new_password1': new_strong_pass,
            'new_password2': new_strong_pass,
        }, follow=True)

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Password Reset Successful!")
        self.assertContains(res, "Continue to Login")
        self.assertContains(res, "countdownSeconds")

        # Refresh user from DB
        self.user.refresh_from_db()

        # Old password must NO LONGER authenticate
        old_auth_success = self.client.login(username="student_reader", password="InitialPassword123!")
        self.assertFalse(old_auth_success)

        # New password MUST authenticate successfully
        new_auth_success = self.client.login(username="student_reader", password=new_strong_pass)
        self.assertTrue(new_auth_success)

    def test_token_cannot_be_reused_after_successful_reset(self):
        """A reset token cannot be reused once the password has been changed (single-use protection)."""
        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': self.valid_token})
        self.client.get(confirm_url, follow=True)
        set_pwd_url = reverse('password_reset_confirm', kwargs={'uidb64': self.uidb64, 'token': 'set-password'})
        new_strong_pass = 'NovelBookworm@2026#Libra'
        self.client.post(set_pwd_url, {
            'new_password1': new_strong_pass,
            'new_password2': new_strong_pass,
        })

        # Clear session to simulate reopening or another device
        self.client.session.flush()

        # Try accessing confirm URL again with the same token
        res_reused = self.client.get(confirm_url, follow=True)
        self.assertEqual(res_reused.status_code, 200)
        self.assertContains(res_reused, "Invalid or Expired Link")


