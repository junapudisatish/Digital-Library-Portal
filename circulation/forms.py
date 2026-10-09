from datetime import date, timedelta
from django import forms
from django.utils import timezone
from .models import Book, Member, CirculationRecord, Author


class BookIssueForm(forms.ModelForm):
    """Form to issue a book to a member."""
    class Meta:
        model = CirculationRecord
        fields = ['book', 'member', 'issue_date', 'due_date']
        widgets = {
            'book': forms.Select(attrs={'class': 'form-select', 'id': 'id_book'}),
            'member': forms.Select(attrs={'class': 'form-select', 'id': 'id_member'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_issue_date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_due_date'}),
        }

    def __init__(self, *args, **kwargs):
        initial_book = kwargs.pop('initial_book', None)
        super().__init__(*args, **kwargs)
        # Only show books that have available copies > 0
        self.fields['book'].queryset = Book.objects.filter(available_copies__gt=0)
        
        today = timezone.now().date()
        self.fields['issue_date'].initial = today
        self.fields['due_date'].initial = today + timedelta(days=14)
        
        if initial_book:
            self.fields['book'].initial = initial_book

    def clean(self):
        cleaned_data = super().clean()
        book = cleaned_data.get('book')
        member = cleaned_data.get('member')
        issue_date = cleaned_data.get('issue_date')
        due_date = cleaned_data.get('due_date')

        if book and book.available_copies <= 0:
            self.add_error('book', f"Sorry, '{book.title}' has 0 available copies left in stock.")

        if issue_date and due_date:
            if due_date < issue_date:
                self.add_error('due_date', "Due date cannot be earlier than the issue date.")

        # Check if member already has an active copy of this exact book
        if book and member:
            already_borrowed = CirculationRecord.objects.filter(
                book=book, member=member, returned=False
            ).exists()
            if already_borrowed:
                self.add_error(None, f"Member {member.name} already has an active copy of '{book.title}' on loan.")

        return cleaned_data


class BookReturnForm(forms.Form):
    """Form to return an active circulation record and calculate overdue fines."""
    circulation_record = forms.ModelChoiceField(
        queryset=CirculationRecord.objects.filter(returned=False).select_related('book', 'member'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_circulation_record'}),
        label="Select Active Loan"
    )
    return_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_return_date'}),
        initial=date.today,
        label="Return Date"
    )

    def clean(self):
        cleaned_data = super().clean()
        record = cleaned_data.get('circulation_record')
        return_date = cleaned_data.get('return_date')

        if record and return_date:
            if return_date < record.issue_date:
                self.add_error('return_date', f"Return date cannot be earlier than the issue date ({record.issue_date}).")
        return cleaned_data


class BookForm(forms.ModelForm):
    """Form to add or edit book catalog records."""
    class Meta:
        model = Book
        fields = ['title', 'author', 'isbn', 'genre', 'total_copies', 'available_copies', 'cover_url']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1984'}),
            'author': forms.Select(attrs={'class': 'form-select'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '978-0-452-28423-4'}),
            'genre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dystopian, Sci-Fi'}),
            'total_copies': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'available_copies': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'cover_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com/cover.jpg'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('total_copies')
        available = cleaned_data.get('available_copies')
        if total is not None and available is not None:
            if available > total:
                self.add_error('available_copies', "Available copies cannot exceed total copies.")
        return cleaned_data


class MemberForm(forms.ModelForm):
    """Form to register or edit library members."""
    class Meta:
        model = Member
        fields = ['name', 'member_id', 'email', 'phone', 'joined_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'member_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MEM-1005'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 000-0000'}),
            'joined_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
