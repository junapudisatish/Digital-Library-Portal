from datetime import date, datetime, timedelta
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from .models import Book, Author, Member, CirculationRecord, DAILY_FINE_RATE
from .forms import (
    BookIssueForm, BookReturnForm, BookForm, MemberForm,
    StudentRegistrationForm, StyledAuthenticationForm,
    StyledPasswordChangeForm, StyledPasswordResetForm, StyledSetPasswordForm
)


def get_or_create_member_for_user(user):
    """Ensure every student user has an associated Member profile."""
    if hasattr(user, 'member_profile') and user.member_profile:
        return user.member_profile
    member = Member.objects.filter(email=user.email).first()
    if not member:
        full_name = f"{user.first_name} {user.last_name}".strip() or user.username
        member_id = f"STU-{user.id:04d}"
        member = Member.objects.create(
            user=user,
            name=full_name,
            member_id=member_id,
            email=user.email or f"{user.username}@student.demo",
            joined_date=timezone.now().date()
        )
    else:
        if not member.user:
            member.user = user
            member.save(update_fields=['user'])
    return member


def catalog_view(request):
    """Book catalog view with live search, filtering, multi-criteria sorting, and pagination."""
    query = request.GET.get('q', '').strip()
    genre_filter = request.GET.get('genre', '').strip()
    availability_filter = request.GET.get('availability', '').strip()
    sort_option = request.GET.get('sort', 'title_asc').strip()

    books = Book.objects.select_related('author').all()

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__name__icontains=query) |
            Q(isbn__icontains=query) |
            Q(genre__icontains=query) |
            Q(description__icontains=query)
        )

    if genre_filter:
        books = books.filter(genre__iexact=genre_filter)

    if availability_filter == 'available':
        books = books.filter(available_copies__gt=0)
    elif availability_filter == 'unavailable':
        books = books.filter(available_copies=0)

    # Sorting options
    if sort_option == 'title_desc':
        books = books.order_by('-title')
    elif sort_option == 'author':
        books = books.order_by('author__name', 'title')
    elif sort_option == 'available':
        books = books.order_by('-available_copies', 'title')
    elif sort_option == 'newest':
        books = books.order_by('-id')
    else:
        books = books.order_by('title')

    # Overall library metrics for the hero banner
    total_titles = Book.objects.count()
    total_inventory = Book.objects.aggregate(total=Sum('total_copies'))['total'] or 0
    available_inventory = Book.objects.aggregate(total=Sum('available_copies'))['total'] or 0
    active_loans = CirculationRecord.objects.filter(returned=False).count()
    overdue_loans = CirculationRecord.objects.filter(returned=False, due_date__lt=timezone.now().date()).count()
    total_students = Member.objects.count()

    # Distinct genres for filter dropdown
    genres = Book.objects.values_list('genre', flat=True).distinct().order_by('genre')

    # Pagination: 8 books per page
    paginator = Paginator(books, 8)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.get_page(1)

    context = {
        'page_obj': page_obj,
        'books': page_obj.object_list,
        'total_filtered': paginator.count,
        'query': query,
        'genre_filter': genre_filter,
        'availability_filter': availability_filter,
        'sort_option': sort_option,
        'genres': genres,
        'total_titles': total_titles,
        'total_inventory': total_inventory,
        'available_inventory': available_inventory,
        'active_loans': active_loans,
        'overdue_loans': overdue_loans,
        'total_students': total_students,
    }
    return render(request, 'circulation/catalog.html', context)


def book_detail_view(request, book_id):
    """Detailed view for a single book with complete synopsis, metadata, and circulation history."""
    book = get_object_or_404(Book.objects.select_related('author'), id=book_id)
    active_loans = book.circulation_records.filter(status='APPROVED', returned=False).select_related('member')
    past_loans = book.circulation_records.filter(returned=True).select_related('member')[:10]

    user_active_loan = None
    user_pending_request = None
    if request.user.is_authenticated:
        member = getattr(request.user, 'member_profile', None)
        if member:
            user_active_loan = active_loans.filter(member=member).first()
            user_pending_request = book.circulation_records.filter(member=member, status='PENDING').first()

    context = {
        'book': book,
        'active_loans': active_loans,
        'past_loans': past_loans,
        'user_active_loan': user_active_loan,
        'user_pending_request': user_pending_request,
        'daily_fine_rate': DAILY_FINE_RATE,
    }
    return render(request, 'circulation/book_detail.html', context)


@login_required
def book_borrow_request_view(request, book_id):
    """
    Student submits a borrowing request from catalog or book detail.
    Validates availability, prevents duplicate pending/active loans,
    and creates a PENDING CirculationRecord without reducing stock.
    Stock is reduced ONLY when an authorized librarian approves.
    """
    if request.method != 'POST':
        return redirect('book_detail', book_id=book_id)

    book = get_object_or_404(Book, id=book_id)
    member = get_or_create_member_for_user(request.user)

    with transaction.atomic():
        book_obj = Book.objects.select_for_update().get(id=book.id)
        if book_obj.available_copies <= 0:
            messages.error(request, f"Sorry, '{book_obj.title}' currently has 0 copies available in stock.")
            return redirect('book_detail', book_id=book_obj.id)

        # Check duplicate pending request
        has_pending = CirculationRecord.objects.filter(
            book=book_obj, member=member, status='PENDING'
        ).exists()
        if has_pending:
            messages.warning(
                request,
                f"You already have a pending borrowing request for '{book_obj.title}'. Please wait for librarian review."
            )
            return redirect('student_dashboard')

        # Check duplicate active loan
        has_active = CirculationRecord.objects.filter(
            book=book_obj, member=member, status='APPROVED', returned=False
        ).exists()
        if has_active:
            messages.warning(
                request,
                f"You already have an active loan for '{book_obj.title}'. Duplicate loans of the same title are not permitted."
            )
            return redirect('student_dashboard')

        CirculationRecord.objects.create(
            book=book_obj,
            member=member,
            status='PENDING',
            request_date=timezone.now().date(),
            returned=False
        )

    messages.success(
        request,
        f"Borrowing request for '{book_obj.title}' submitted successfully! A librarian must review and approve your request before the book is issued."
    )
    return redirect('student_dashboard')


@login_required
def request_approve_view(request, record_id):
    """
    Librarian approves a pending borrowing request:
    1. Rechecks stock inside atomic transaction.
    2. Decrements available copies by 1.
    3. Sets status='APPROVED', issue_date=today, due_date=today+14 days.
    4. Records approving librarian.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access restricted to authorized librarians and staff.")
        return redirect('student_dashboard')

    if request.method == 'POST':
        with transaction.atomic():
            record = get_object_or_404(CirculationRecord.objects.select_for_update(), id=record_id)
            if record.status != 'PENDING':
                messages.warning(request, f"Request #{record.id} is already {record.get_status_display()}.")
                return redirect('staff_dashboard')

            book = Book.objects.select_for_update().get(id=record.book_id)
            if book.available_copies <= 0:
                messages.error(
                    request,
                    f"Cannot approve request: '{book.title}' currently has 0 copies available in stock."
                )
                return redirect('staff_dashboard')

            # Decrement stock by exactly 1
            book.available_copies -= 1
            book.save(update_fields=['available_copies'])

            today = timezone.now().date()
            record.status = 'APPROVED'
            record.approved_by = request.user
            record.issue_date = today
            record.due_date = today + timedelta(days=14)
            record.returned = False
            record.save(update_fields=['status', 'approved_by', 'issue_date', 'due_date', 'returned'])

            messages.success(
                request,
                f"Request approved! '{book.title}' issued to {record.member.name} ({record.member.member_id}). "
                f"Due date: {record.due_date.strftime('%b %d, %Y')}."
            )
    return redirect('staff_dashboard')


@login_required
def request_reject_view(request, record_id):
    """
    Librarian rejects a pending borrowing request:
    Marks request as REJECTED, records librarian & rejection reason without altering stock.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access restricted to authorized librarians and staff.")
        return redirect('student_dashboard')

    if request.method == 'POST':
        with transaction.atomic():
            record = get_object_or_404(CirculationRecord.objects.select_for_update(), id=record_id)
            if record.status != 'PENDING':
                messages.warning(request, f"Request #{record.id} is already {record.get_status_display()}.")
                return redirect('staff_dashboard')

            reason = request.POST.get('reason', '').strip() or request.POST.get('rejection_reason', '').strip() or 'Request declined by librarian.'
            record.status = 'REJECTED'
            record.approved_by = request.user
            record.rejection_reason = reason
            record.save(update_fields=['status', 'approved_by', 'rejection_reason'])

            messages.info(
                request,
                f"Request for '{record.book.title}' by {record.member.name} has been rejected."
            )
    return redirect('staff_dashboard')


@login_required
def book_issue_view(request, book_id=None):
    """Direct circulation desk issue workflow for authorized librarians."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access restricted to authorized librarians.")
        return redirect('catalog')

    initial_book = None
    if book_id:
        initial_book = get_object_or_404(Book, id=book_id)

    if request.method == 'POST':
        form = BookIssueForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                circulation = form.save(commit=False)
                book = Book.objects.select_for_update().get(id=circulation.book_id)

                if book.available_copies <= 0:
                    messages.error(request, f"Cannot issue '{book.title}': No available copies left in stock!")
                    return redirect('catalog')

                # Prevent duplicate active checkouts
                already_borrowed = CirculationRecord.objects.filter(
                    book=book, member=circulation.member, status='APPROVED', returned=False
                ).exists()
                if already_borrowed:
                    messages.error(request, f"Member '{circulation.member.name}' already has an active copy of '{book.title}' on loan!")
                    return redirect('book_detail', book_id=book.id)

                # Reduce available copies
                book.issue_copy()
                circulation.status = 'APPROVED'
                circulation.approved_by = request.user
                circulation.save()

            messages.success(
                request,
                f"Successfully issued '{book.title}' to {circulation.member.name}! "
                f"Due date: {circulation.due_date.strftime('%b %d, %Y')}."
            )
            return redirect('member_dashboard', member_id=circulation.member.id)
        else:
            messages.error(request, "Please correct the form errors below to issue the book.")
    else:
        form = BookIssueForm(initial_book=initial_book)

    context = {
        'form': form,
        'initial_book': initial_book,
        'daily_fine_rate': DAILY_FINE_RATE,
    }
    return render(request, 'circulation/issue_book.html', context)


@login_required
def book_return_view(request, record_id=None):
    """Workflow to return a borrowed book and compute overdue fines safely at ₹5/day."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access restricted to authorized librarians.")
        return redirect('student_dashboard')

    selected_record = None
    if record_id:
        selected_record = get_object_or_404(CirculationRecord.objects.select_related('book', 'member'), id=record_id)
        if selected_record.returned:
            messages.info(request, f"Book '{selected_record.book.title}' is already returned.")
            return redirect('member_dashboard', member_id=selected_record.member.id)

    if request.method == 'POST':
        form = BookReturnForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                rec_obj = form.cleaned_data['circulation_record']
                record = CirculationRecord.objects.select_for_update().get(id=rec_obj.id)
                if record.returned:
                    messages.warning(request, f"Book '{record.book.title}' is already marked as returned.")
                    return redirect('member_dashboard', member_id=record.member.id)

                return_date = form.cleaned_data['return_date']
                fine = record.complete_return(return_date=return_date, fine_rate=DAILY_FINE_RATE)

            if fine > 0:
                messages.warning(
                    request,
                    f"Book '{record.book.title}' returned by {record.member.name}. "
                    f"OVERDUE by {record.days_overdue} day(s)! Overdue Fine: ₹{fine:.2f}."
                )
            else:
                messages.success(
                    request,
                    f"Book '{record.book.title}' returned on time by {record.member.name}! No overdue fine."
                )
            return redirect('member_dashboard', member_id=record.member.id)
        else:
            messages.error(request, "Please check the form inputs.")
    else:
        initial = {}
        if selected_record:
            initial['circulation_record'] = selected_record
            initial['return_date'] = timezone.now().date()
        form = BookReturnForm(initial=initial)

    active_records = CirculationRecord.objects.filter(status='APPROVED', returned=False).select_related('book', 'member').order_by('due_date')

    context = {
        'form': form,
        'selected_record': selected_record,
        'active_records': active_records,
        'daily_fine_rate': DAILY_FINE_RATE,
        'today': timezone.now().date(),
    }
    return render(request, 'circulation/return_book.html', context)



def student_register_view(request):
    """Student registration view creating user account and library member profile."""
    if request.user.is_authenticated:
        return redirect('student_dashboard')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user, member = form.save()
            login(request, user)
            messages.success(
                request,
                f"Welcome to Digital Library Portal, {member.name}! Your student card is active ({member.member_id})."
            )
            return redirect('student_dashboard')
        else:
            messages.error(request, "Registration could not be completed. Please review the errors below.")
    else:
        form = StudentRegistrationForm()

    return render(request, 'circulation/student_register.html', {'form': form})


def student_login_view(request):
    """Member & Staff Login view without exposed credentials."""
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('staff_dashboard')
        return redirect('student_dashboard')

    if request.method == 'POST':
        form = StyledAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            if user.is_staff:
                return redirect('staff_dashboard')
            return redirect('student_dashboard')
        else:
            messages.error(request, "Invalid username or password. Please verify your credentials.")
    else:
        form = StyledAuthenticationForm(request)

    return render(request, 'circulation/login.html', {'form': form})


class CustomPasswordChangeView(LoginRequiredMixin, auth_views.PasswordChangeView):
    """Password change view for authenticated users with session preservation."""
    form_class = StyledPasswordChangeForm
    template_name = 'circulation/password_change.html'
    success_url = reverse_lazy('password_change_done')

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed successfully!")
        return super().form_valid(form)


class CustomPasswordChangeDoneView(LoginRequiredMixin, auth_views.PasswordChangeDoneView):
    """Confirmation page following a successful password change."""
    template_name = 'circulation/password_change_done.html'


class CustomPasswordResetView(auth_views.PasswordResetView):
    """Password reset request view with graceful email error handling."""
    form_class = StyledPasswordResetForm
    template_name = 'circulation/password_reset.html'
    email_template_name = 'circulation/password_reset_email.html'
    subject_template_name = 'circulation/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except Exception as e:
            messages.error(
                self.request,
                f"Password reset email could not be sent: {str(e)}. "
                "Please ensure email settings (EMAIL_HOST, EMAIL_PORT, etc.) are configured in environment variables, "
                "or contact your library system administrator."
            )
            return self.form_invalid(form)


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """Confirmation page that password reset email instructions were dispatched."""
    template_name = 'circulation/password_reset_done.html'


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """Password reset token confirmation and set-new-password view."""
    form_class = StyledSetPasswordForm
    template_name = 'circulation/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')


class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """Final confirmation page after successful password reset via token."""
    template_name = 'circulation/password_reset_complete.html'



def student_logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('catalog')


@login_required
def student_dashboard_view(request):
    """
    Dedicated Student Dashboard (My Library):
    Real database records showing:
    - Summary Cards: Pending Requests, Currently Borrowed, Due Soon, Overdue Books
    - Sections: Pending Requests, Approved / Currently Borrowed, Due Soon, Overdue, Returned Books / Borrowing History, Rejected Requests
    """
    member = get_or_create_member_for_user(request.user)

    today = timezone.now().date()
    pending_requests = member.circulation_records.filter(status='PENDING').select_related('book', 'book__author').order_by('-request_date', '-id')
    active_records = member.circulation_records.filter(status='APPROVED', returned=False).select_related('book', 'book__author').order_by('due_date')
    due_soon_records = active_records.filter(due_date__gte=today, due_date__lte=today + timedelta(days=3))
    overdue_records = active_records.filter(due_date__lt=today)
    past_records = member.circulation_records.filter(Q(status='RETURNED') | Q(returned=True)).select_related('book', 'book__author').order_by('-return_date', '-id')
    rejected_requests = member.circulation_records.filter(status='REJECTED').select_related('book', 'book__author').order_by('-request_date', '-id')

    overdue_count = overdue_records.count()
    total_accrued_fines = sum((rec.current_estimated_fine for rec in overdue_records), Decimal('0.00'))
    past_fines = member.circulation_records.filter(returned=True).aggregate(total=Sum('fine_amount'))['total'] or Decimal('0.00')
    grand_total_fines = total_accrued_fines + past_fines

    context = {
        'member': member,
        'pending_requests': pending_requests,
        'active_records': active_records,
        'due_soon_records': due_soon_records,
        'overdue_records': overdue_records,
        'past_records': past_records,
        'rejected_requests': rejected_requests,
        'pending_count': pending_requests.count(),
        'active_count': active_records.count(),
        'due_soon_count': due_soon_records.count(),
        'overdue_count': overdue_count,
        'returned_count': past_records.count(),
        'rejected_count': rejected_requests.count(),
        'today': today,
        'total_accrued_fines': total_accrued_fines,
        'past_fines': past_fines,
        'grand_total_fines': grand_total_fines,
        'daily_fine_rate': DAILY_FINE_RATE,
    }
    return render(request, 'circulation/student_dashboard.html', context)


@login_required
def staff_dashboard_view(request):
    """
    Librarian / Staff Operations Hub:
    Central dashboard for managing pending borrowing requests, active loans,
    overdue loans, stock inventory, members, and return processing.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Access restricted to authorized library staff.")
        return redirect('student_dashboard')

    today = timezone.now().date()
    total_titles = Book.objects.count()
    total_copies = Book.objects.aggregate(total=Sum('total_copies'))['total'] or 0
    available_copies = Book.objects.aggregate(total=Sum('available_copies'))['total'] or 0
    issued_copies = max(0, total_copies - available_copies)

    pending_requests = CirculationRecord.objects.filter(status='PENDING').select_related('book', 'member').order_by('-request_date', '-id')
    active_loans = CirculationRecord.objects.filter(status='APPROVED', returned=False).select_related('book', 'member').order_by('due_date')
    overdue_loans = [loan for loan in active_loans if loan.is_overdue]
    recent_returns = CirculationRecord.objects.filter(returned=True).select_related('book', 'member').order_by('-return_date', '-id')[:6]
    total_fines_collected = CirculationRecord.objects.filter(returned=True).aggregate(total=Sum('fine_amount'))['total'] or Decimal('0.00')
    recent_books = Book.objects.select_related('author').order_by('-id')[:8]
    members = Member.objects.all().order_by('-joined_date')[:8]

    context = {
        'total_titles': total_titles,
        'total_copies': total_copies,
        'available_copies': available_copies,
        'issued_copies': issued_copies,
        'registered_members': Member.objects.count(),
        'pending_requests': pending_requests,
        'pending_requests_count': pending_requests.count(),
        'active_loans': active_loans,
        'active_loans_count': active_loans.count(),
        'overdue_loans': overdue_loans,
        'overdue_loans_count': len(overdue_loans),
        'returned_count': CirculationRecord.objects.filter(returned=True).count(),
        'recent_returns': recent_returns,
        'total_fines_collected': total_fines_collected,
        'recent_books': recent_books,
        'members': members,
        'daily_fine_rate': DAILY_FINE_RATE,
        'today': today,
    }
    return render(request, 'circulation/staff_dashboard.html', context)


def book_create_view(request):
    """Add a new book to the library catalog."""
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save()
            messages.success(request, f"Book '{book.title}' added to catalog successfully!")
            return redirect('book_detail', book_id=book.id)
    else:
        form = BookForm()
    return render(request, 'circulation/book_form.html', {'form': form, 'title': 'Add New Book'})


def book_edit_view(request, book_id):
    """Edit existing book details and copy inventory."""
    book = get_object_or_404(Book, id=book_id)
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, f"Book '{book.title}' updated successfully!")
            return redirect('book_detail', book_id=book.id)
    else:
        form = BookForm(instance=book)
    return render(request, 'circulation/book_form.html', {'form': form, 'title': f'Edit Book: {book.title}', 'book': book})


def member_list_view(request):
    """List all registered members with their borrowing summaries."""
    query = request.GET.get('q', '').strip()
    members = Member.objects.all()

    if query:
        members = members.filter(
            Q(name__icontains=query) |
            Q(member_id__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )

    context = {
        'members': members,
        'query': query,
    }
    return render(request, 'circulation/member_list.html', context)


def member_dashboard_view(request, member_id):
    """
    Member Dashboard showing active borrowed books, due dates, overdue alerts,
    and complete borrowing history with fines.
    """
    member = get_object_or_404(Member, id=member_id)
    active_records = member.circulation_records.filter(returned=False).select_related('book').order_by('due_date')
    past_records = member.circulation_records.filter(returned=True).select_related('book').order_by('-return_date')

    today = timezone.now().date()
    overdue_count = 0
    total_accrued_fines = Decimal('0.00')

    for record in active_records:
        if record.due_date < today:
            overdue_count += 1
            total_accrued_fines += record.current_estimated_fine

    past_fines = member.circulation_records.filter(returned=True).aggregate(total=Sum('fine_amount'))['total'] or Decimal('0.00')
    grand_total_fines = total_accrued_fines + past_fines

    context = {
        'member': member,
        'active_records': active_records,
        'past_records': past_records,
        'today': today,
        'overdue_count': overdue_count,
        'total_accrued_fines': total_accrued_fines,
        'past_fines': past_fines,
        'grand_total_fines': grand_total_fines,
        'daily_fine_rate': DAILY_FINE_RATE,
    }
    return render(request, 'circulation/member_dashboard.html', context)


def member_create_view(request):
    """Register a new library member."""
    if request.method == 'POST':
        form = MemberForm(request.POST)
        if form.is_valid():
            member = form.save()
            messages.success(request, f"Member '{member.name}' ({member.member_id}) registered successfully!")
            return redirect('member_dashboard', member_id=member.id)
    else:
        form = MemberForm()
    return render(request, 'circulation/member_form.html', {'form': form, 'title': 'Register New Member'})


def calculator_view(request):
    """Interactive client-side & server-backed due-date and fine calculator."""
    return render(request, 'circulation/calculator.html', {
        'daily_fine_rate': DAILY_FINE_RATE,
        'today': timezone.now().date(),
    })


def seed_data_view(request):
    """One-click seed demo dataset to showcase all functionality."""
    if request.method == 'POST':
        from .seed_data import populate_sample_data
        count = populate_sample_data()
        messages.success(request, f"Sample library dataset successfully loaded ({count} books, rich descriptions & demo student accounts seeded)!")
        return redirect('catalog')
    return render(request, 'circulation/seed_confirm.html')


def api_calculate_fine(request):
    """API endpoint to calculate overdue fine based on due date and return date."""
    due_date_str = request.GET.get('due_date')
    return_date_str = request.GET.get('return_date') or str(timezone.now().date())
    rate = Decimal(request.GET.get('rate', str(DAILY_FINE_RATE)))

    try:
        due_d = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        return_d = datetime.strptime(return_date_str, '%Y-%m-%d').date()
        overdue_days = max(0, (return_d - due_d).days)
        fine = Decimal(overdue_days) * rate
        return JsonResponse({
            'success': True,
            'overdue_days': overdue_days,
            'fine_amount': float(fine),
            'formatted_fine': f"₹{fine:.2f}",
            'is_overdue': overdue_days > 0,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
