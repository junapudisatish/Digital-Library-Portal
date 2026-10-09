from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

DAILY_FINE_RATE = Decimal('1.00')  # $1.00 fine per day overdue


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
    def active_records(self):
        return self.circulation_records.filter(returned=False).order_by('due_date')

    @property
    def past_records(self):
        return self.circulation_records.filter(returned=True).order_by('-return_date')

    @property
    def active_loans_count(self):
        return self.active_records.count()

    @property
    def overdue_loans_count(self):
        today = timezone.now().date()
        return self.active_records.filter(due_date__lt=today).count()

    @property
    def total_fines_accrued(self):
        return sum(record.fine_amount for record in self.circulation_records.all())


class CirculationRecord(models.Model):
    """Tracks book borrowing, due dates, returns, and overdue fines."""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='circulation_records')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='circulation_records')
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    fine_amount = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    returned = models.BooleanField(default=False)

    class Meta:
        ordering = ['-issue_date']

    def __str__(self):
        status = "Returned" if self.returned else "Active"
        return f"{self.book.title} -> {self.member.name} [{status}]"

    def save(self, *args, **kwargs):
        # Default due date to 14 days after issue_date if not set
        if not self.due_date:
            if isinstance(self.issue_date, timezone.datetime):
                issue_d = self.issue_date.date()
            else:
                issue_d = self.issue_date
            self.due_date = issue_d + timedelta(days=14)
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Check if record is overdue."""
        if self.returned:
            return bool(self.return_date and self.return_date > self.due_date)
        return timezone.now().date() > self.due_date

    @property
    def days_overdue(self):
        """Calculate overdue days."""
        if self.returned:
            if self.return_date and self.return_date > self.due_date:
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
        2. Calculate final overdue fine
        3. Mark returned = True
        4. Increment book available_copies
        """
        if self.returned:
            return self.fine_amount

        if return_date is None:
            return_date = timezone.now().date()

        self.return_date = return_date
        overdue_days = max(0, (self.return_date - self.due_date).days)
        self.fine_amount = Decimal(overdue_days) * fine_rate
        self.returned = True
        self.save(update_fields=['return_date', 'fine_amount', 'returned'])

        # Increment available copies
        self.book.return_copy()
        return self.fine_amount
