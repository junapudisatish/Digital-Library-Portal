from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

DAILY_FINE_RATE = getattr(settings, 'DAILY_FINE_RATE', Decimal('5.00'))  # Configurable daily overdue fine rate (Default: ₹5.00)

STATUS_PENDING = 'PENDING'
STATUS_APPROVED = 'APPROVED'
STATUS_REJECTED = 'REJECTED'
STATUS_RETURNED = 'RETURNED'

STATUS_CHOICES = [
    (STATUS_PENDING, 'Pending Approval'),
    (STATUS_APPROVED, 'Approved / Active Loan'),
    (STATUS_REJECTED, 'Rejected'),
    (STATUS_RETURNED, 'Returned'),
]


class Author(models.Model):
    """Author of books in the library."""
    name = models.CharField(max_length=200, help_text="Full name of the author")
    biography = models.TextField(blank=True, help_text="Biographical details of the author")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def book_count(self):
        return self.books.count()


class Book(models.Model):
    """Book inventory record with catalog metadata and copy tracking."""
    title = models.CharField(max_length=255)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')
    isbn = models.CharField(max_length=20, unique=True, help_text="ISBN-10 or ISBN-13 identifier")
    genre = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='', help_text="Detailed summary of the book")
    total_copies = models.PositiveIntegerField(default=1)
    available_copies = models.PositiveIntegerField(default=1)
    cover_url = models.URLField(max_length=500, blank=True, help_text="Direct URL to book cover image")

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} by {self.author.name} (ISBN: {self.isbn})"

    def clean(self):
        super().clean()
        if self.available_copies > self.total_copies:
            raise ValidationError({'available_copies': "Available copies cannot exceed total copies."})

    @property
    def is_available(self):
        return self.available_copies > 0

    @property
    def issued_copies(self):
        return max(0, self.total_copies - self.available_copies)

    def issue_copy(self):
        """Reduce available copies by 1 when issuing."""
        if self.available_copies <= 0:
            raise ValidationError(f"No copies of '{self.title}' are currently available for issue.")
        self.available_copies -= 1
        self.save(update_fields=['available_copies'])

    def return_copy(self):
        """Increase available copies by 1 when returning."""
        if self.available_copies < self.total_copies:
            self.available_copies += 1
            self.save(update_fields=['available_copies'])


class Member(models.Model):
    """Library member profile and membership tracking."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='member_profile',
        help_text="Associated student or member user account"
    )
    name = models.CharField(max_length=200)
    member_id = models.CharField(max_length=50, unique=True, help_text="Unique Member ID, e.g. MEM-1001")
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    joined_date = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.member_id})"

    @property
    def pending_requests(self):
        return self.circulation_records.filter(status=STATUS_PENDING).order_by('-request_date', '-id')

    @property
    def active_records(self):
        return self.circulation_records.filter(status=STATUS_APPROVED, returned=False).order_by('due_date')

    @property
    def past_records(self):
        return self.circulation_records.filter(models.Q(status=STATUS_RETURNED) | models.Q(returned=True)).order_by('-return_date', '-id')

    @property
    def due_soon_records(self):
        today = timezone.now().date()
        cutoff = today + timedelta(days=3)
        return self.active_records.filter(due_date__gte=today, due_date__lte=cutoff)

    @property
    def overdue_records(self):
        today = timezone.now().date()
        return self.active_records.filter(due_date__lt=today)

    @property
    def rejected_requests(self):
        return self.circulation_records.filter(status=STATUS_REJECTED).order_by('-request_date', '-id')

    @property
    def pending_requests_count(self):
        return self.pending_requests.count()

    @property
    def active_loans_count(self):
        return self.active_records.count()

    @property
    def due_soon_count(self):
        return self.due_soon_records.count()

    @property
    def overdue_loans_count(self):
        return self.overdue_records.count()

    @property
    def total_fines_accrued(self):
        return sum(record.fine_amount for record in self.circulation_records.filter(returned=True))


class CirculationRecord(models.Model):
    """Tracks book borrowing requests, active loans, due dates, returns, and overdue fines."""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='circulation_records')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='circulation_records')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_APPROVED,
        help_text="Current state of borrowing request or loan"
    )
    request_date = models.DateField(default=timezone.now, help_text="Date when borrowing was requested by student")
    issue_date = models.DateField(null=True, blank=True, help_text="Date approved and issued by librarian")
    due_date = models.DateField(null=True, blank=True, help_text="14-day loan expiration date")
    return_date = models.DateField(null=True, blank=True)
    fine_amount = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    returned = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_circulations',
        help_text="Librarian or staff who approved or rejected this request"
    )
    rejection_reason = models.TextField(blank=True, default='', help_text="Optional reason if request was rejected")

    class Meta:
        ordering = ['-request_date', '-id']

    def __str__(self):
        return f"{self.book.title} -> {self.member.name} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        # Auto-compute due date if approved/issued and due_date not explicitly set
        if self.status in [STATUS_APPROVED, STATUS_RETURNED] and self.issue_date and not self.due_date:
            if isinstance(self.issue_date, timezone.datetime):
                issue_d = self.issue_date.date()
            else:
                issue_d = self.issue_date
            self.due_date = issue_d + timedelta(days=14)
        super().save(*args, **kwargs)

    @property
    def is_pending(self):
        return self.status == STATUS_PENDING

    @property
    def is_approved(self):
        return self.status == STATUS_APPROVED and not self.returned

    @property
    def is_rejected(self):
        return self.status == STATUS_REJECTED

    @property
    def is_due_soon(self):
        """Due within next 3 days and not yet overdue."""
        if not self.is_approved or not self.due_date:
            return False
        today = timezone.now().date()
        return today <= self.due_date <= today + timedelta(days=3)

    @property
    def is_overdue(self):
        """Check if record is overdue (only applies to approved active loans or late returns)."""
        if self.status == STATUS_PENDING or self.status == STATUS_REJECTED:
            return False
        if self.returned:
            return bool(self.due_date and self.return_date and self.return_date > self.due_date)
        if not self.due_date:
            return False
        return timezone.now().date() > self.due_date

    @property
    def days_overdue(self):
        """Calculate overdue days."""
        if self.status == STATUS_PENDING or self.status == STATUS_REJECTED or not self.due_date:
            return 0
        if self.returned:
            if self.return_date and self.due_date and self.return_date > self.due_date:
                return (self.return_date - self.due_date).days
            return 0
        today = timezone.now().date()
        if today > self.due_date:
            return (today - self.due_date).days
        return 0

    @property
    def current_estimated_fine(self):
        """Calculate fine estimate for active loans."""
        if self.returned:
            return self.fine_amount
        return Decimal(self.days_overdue) * DAILY_FINE_RATE

    def complete_return(self, return_date=None, fine_rate=DAILY_FINE_RATE):
        """
        Executes the return business logic:
        1. Set return_date (defaults to today)
        2. Calculate final overdue fine: overdue_days * fine_rate (₹5/day)
        3. Mark returned = True and status = STATUS_RETURNED
        4. Increment book available_copies by 1
        """
        if self.returned:
            return self.fine_amount

        if return_date is None:
            return_date = timezone.now().date()

        self.return_date = return_date
        overdue_days = 0
        if self.due_date and self.return_date > self.due_date:
            overdue_days = (self.return_date - self.due_date).days
        self.fine_amount = Decimal(overdue_days) * fine_rate
        self.returned = True
        self.status = STATUS_RETURNED
        self.save(update_fields=['return_date', 'fine_amount', 'returned', 'status'])

        # Increment available copies
        self.book.return_copy()
        return self.fine_amount
