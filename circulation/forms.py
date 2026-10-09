import uuid
from datetime import date, timedelta
from django import forms
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from .models import Book, Member, CirculationRecord, Author

User = get_user_model()


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
        self.fields['book'].queryset = Book.objects.filter(available_copies__gt=0).select_related('author')
        
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
        fields = ['title', 'author', 'isbn', 'genre', 'description', 'total_copies', 'available_copies', 'cover_url']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1984'}),
            'author': forms.Select(attrs={'class': 'form-select'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '978-0-452-28423-4'}),
            'genre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dystopian, Sci-Fi'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Comprehensive book summary, synopsis, or overview...'}),
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


class StudentRegistrationForm(forms.Form):
    """Student registration form creating User and linked Member profile."""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose username'})
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'student@university.edu'})
    )
    student_id = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. STU-2026-001 (Optional, auto-generated if blank)'})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 123-4567'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter secure password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken. Please choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists() or Member.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if password and confirm and password != confirm:
            self.add_error('confirm_password', "Passwords do not match.")
        if password and len(password) < 6:
            self.add_error('password', "Password must be at least 6 characters long.")
        return cleaned_data

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name']
        )
        # Determine student member ID
        member_id = data.get('student_id')
        if not member_id:
            member_id = f"STU-{uuid.uuid4().hex[:6].upper()}"

        full_name = f"{data['first_name']} {data['last_name']}".strip() or data['username']
        member = Member.objects.create(
            user=user,
            name=full_name,
            member_id=member_id,
            email=data['email'],
            phone=data.get('phone', ''),
            joined_date=timezone.now().date()
        )
        return user, member


class StyledAuthenticationForm(AuthenticationForm):
    """Styled Bootstrap 5 authentication form."""
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Username or Student ID'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Password'})
    )


class StyledPasswordChangeForm(PasswordChangeForm):
    """Bootstrap 5 styled Password Change Form."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        if 'old_password' in self.fields:
            self.fields['old_password'].widget.attrs.update({'placeholder': 'Enter your current password'})
        if 'new_password1' in self.fields:
            self.fields['new_password1'].widget.attrs.update({'placeholder': 'Enter your new password'})
        if 'new_password2' in self.fields:
            self.fields['new_password2'].widget.attrs.update({'placeholder': 'Confirm your new password'})


class StyledPasswordResetForm(PasswordResetForm):
    """Bootstrap 5 styled Password Reset Form."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.update({
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter your registered email address'
            })


class StyledSetPasswordForm(SetPasswordForm):
    """Bootstrap 5 styled Set Password Form for reset confirmation."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        if 'new_password1' in self.fields:
            self.fields['new_password1'].widget.attrs.update({'placeholder': 'Enter new password'})
        if 'new_password2' in self.fields:
            self.fields['new_password2'].widget.attrs.update({'placeholder': 'Confirm new password'})

