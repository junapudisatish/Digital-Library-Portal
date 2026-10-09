from django.contrib import admin
from .models import Author, Book, Member, CirculationRecord


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'biography_snippet', 'book_count')
    search_fields = ('name',)

    def biography_snippet(self, obj):
        return (obj.biography[:75] + '...') if len(obj.biography) > 75 else obj.biography
    biography_snippet.short_description = "Biography"

    def book_count(self, obj):
        return obj.books.count()
    book_count.short_description = "Total Books"


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'isbn', 'genre', 'available_copies', 'total_copies', 'availability_badge')
    list_filter = ('genre', 'author')
    search_fields = ('title', 'isbn', 'author__name')
    ordering = ('title',)

    def availability_badge(self, obj):
        return f"{obj.available_copies}/{obj.total_copies} Available"
    availability_badge.short_description = "Status"


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('member_id', 'name', 'email', 'phone', 'joined_date', 'active_loans')
    search_fields = ('member_id', 'name', 'email', 'phone')
    ordering = ('member_id',)

    def active_loans(self, obj):
        return obj.active_loans_count
    active_loans.short_description = "Active Loans"


@admin.register(CirculationRecord)
class CirculationRecordAdmin(admin.ModelAdmin):
    list_display = ('book', 'member', 'issue_date', 'due_date', 'return_date', 'fine_amount', 'returned', 'overdue_status')
    list_filter = ('returned', 'issue_date', 'due_date')
    search_fields = ('book__title', 'member__name', 'member__member_id')
    ordering = ('-issue_date',)
    readonly_fields = ('fine_amount',)

    def overdue_status(self, obj):
        if obj.returned:
            return "Returned"
        return "OVERDUE" if obj.is_overdue else "On Track"
    overdue_status.short_description = "Circulation Status"
