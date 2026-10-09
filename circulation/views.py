from datetime import date, datetime, timedelta
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone
from .models import Book, Author, Member, CirculationRecord, DAILY_FINE_RATE
from .forms import BookIssueForm, BookReturnForm, BookForm, MemberForm


def catalog_view(request):
    """Book catalog view with search, filtering, and stats."""
    query = request.GET.get('q', '').strip()
    genre_filter = request.GET.get('genre', '').strip()
    availability_filter = request.GET.get('availability', '').strip()

    books = Book.objects.select_related('author').all()

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__name__icontains=query) |
            Q(isbn__icontains=query) |
            Q(genre__icontains=query)
        )

    if genre_filter:
        books = books.filter(genre__iexact=genre_filter)

    if availability_filter == 'available':
        books = books.filter(available_copies__gt=0)
    elif availability_filter == 'unavailable':
        books = books.filter(available_copies=0)

    # Distinct genres for filter dropdown
    genres = Book.objects.values_list('genre', flat=True).distinct().order_by('genre')

    # Overall library metrics for the header
    total_titles = Book.objects.count()
    total_inventory = Book.objects.aggregate(total=Sum('total_copies'))['total'] or 0
    available_inventory = Book.objects.aggregate(total=Sum('available_copies'))['total'] or 0
    active_loans = CirculationRecord.objects.filter(returned=False).count()
    overdue_loans = CirculationRecord.objects.filter(returned=False, due_date__lt=timezone.now().date()).count()

    context = {
        'books': books,
        'query': query,
        'genre_filter': genre_filter,
        'availability_filter': availability_filter,
        'genres': genres,
        'total_titles': total_titles,
        'total_inventory': total_inventory,
        'available_inventory': available_inventory,
        'active_loans': active_loans,
        'overdue_loans': overdue_loans,
    }
    return render(request, 'circulation/catalog.html', context)


def book_detail_view(request, book_id):
    """Detailed view for a single book with circulation history."""
    book = get_object_or_404(Book.objects.select_related('author'), id=book_id)
    active_loans = book.circulation_records.filter(returned=False).select_related('member')
    past_loans = book.circulation_records.filter(returned=True).select_related('member')[:10]

    context = {
        'book': book,
        'active_loans': active_loans,
        'past_loans': past_loans,
        'daily_fine_rate': DAILY_FINE_RATE,
    }
    return render(request, 'circulation/book_detail.html', context)


def book_issue_view(request, book_id=None):
    """Workflow to issue a book to a member."""
    initial_book = None
    if book_id:
        initial_book = get_object_or_404(Book, id=book_id)

    if request.method == 'POST':
        form = BookIssueForm(request.POST)
        if form.is_valid():
            circulation = form.save(commit=False)
            book = circulation.book

            if book.available_copies <= 0:
                messages.error(request, f"Cannot issue '{book.title}': No available copies left in stock!")
                return redirect('catalog')

            # Reduce available copies
            book.issue_copy()
            circulation.save()

            messages.success(
                request,
                f"Successfully issued '{book.title}' to {circulation.member.name}! "
                f"Due date: {circulation.due_date.strftime('%b %d, %Y')}."
            )
            return redirect('member_dashboard', member_id=circulation.member.id)
        else:
            messages.error(request, "Please correct the errors below to issue the book.")
    else:
        form = BookIssueForm(initial_book=initial_book)

    context = {
        'form': form,
        'initial_book': initial_book,
        'daily_fine_rate': DAILY_FINE_RATE,
    }
    return render(request, 'circulation/issue_book.html', context)


def book_return_view(request, record_id=None):
    """Workflow to return a borrowed book and compute overdue fines."""
    selected_record = None
    if record_id:
        selected_record = get_object_or_404(CirculationRecord.objects.select_related('book', 'member'), id=record_id)
        if selected_record.returned:
            messages.info(request, f"Book '{selected_record.book.title}' is already returned.")
            return redirect('member_dashboard', member_id=selected_record.member.id)

    if request.method == 'POST':
        form = BookReturnForm(request.POST)
        if form.is_valid():
            record = form.cleaned_data['circulation_record']
            return_date = form.cleaned_data['return_date']

            fine = record.complete_return(return_date=return_date, fine_rate=DAILY_FINE_RATE)

            if fine > 0:
                messages.warning(
                    request,
                    f"Book '{record.book.title}' returned by {record.member.name}. "
                    f"OVERDUE by {record.days_overdue} days! Overdue Fine: ${fine:.2f}."
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

    # Active loans for selection
    active_records = CirculationRecord.objects.filter(returned=False).select_related('book', 'member').order_by('due_date')

    context = {
        'form': form,
        'selected_record': selected_record,
        'active_records': active_records,
        'daily_fine_rate': DAILY_FINE_RATE,
        'today': timezone.now().date(),
    }
    return render(request, 'circulation/return_book.html', context)


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

    # Compute live overdue and accrued fines for active records
    for record in active_records:
        if record.due_date < today:
            overdue_count += 1
            total_accrued_fines += record.current_estimated_fine

    # Sum of past assessed fines
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


def calculator_view(request):
    """Interactive client-side & server-backed due-date and fine calculator."""
    return render(request, 'circulation/calculator.html', {
        'daily_fine_rate': DAILY_FINE_RATE,
        'today': timezone.now().date(),
    })


def book_create_view(request):
    """Add a new book to the library catalog."""
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save()
            messages.success(request, f"Book '{book.title}' added to catalog successfully!")
            return redirect('catalog')
    else:
        form = BookForm()
    return render(request, 'circulation/book_form.html', {'form': form, 'title': 'Add New Book'})


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


def seed_data_view(request):
    """One-click seed demo dataset to showcase all functionality."""
    if request.method == 'POST':
        from .seed_data import populate_sample_data
        count = populate_sample_data()
        messages.success(request, f"Sample library dataset successfully loaded ({count} books & active loans seeded)!")
        return redirect('catalog')
    return render(request, 'circulation/seed_confirm.html')


# AJAX / API endpoints for interactive calculator & live lookups
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
            'formatted_fine': f"${fine:.2f}",
            'is_overdue': overdue_days > 0,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
