from datetime import timedelta
from decimal import Decimal
from django.contrib import admin
from django.utils import timezone
from .models import Author, Book, Member, CirculationRecord, DAILY_FINE_RATE


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
    list_display = ('id', 'book', 'member', 'status', 'issue_date', 'due_date', 'return_date', 'fine_amount', 'returned', 'overdue_status')
    list_filter = ('status', 'returned', 'issue_date', 'due_date')
    search_fields = ('book__title', 'member__name', 'member__member_id')
    ordering = ('-id',)
    readonly_fields = ('fine_amount',)
    actions = ['approve_requests', 'reject_requests', 'process_returns']

    def overdue_status(self, obj):
        if obj.returned:
            return "Returned"
        return "OVERDUE" if obj.is_overdue else "On Track"
    overdue_status.short_description = "Circulation Status"

    @admin.action(description="Approve selected pending borrowing requests")
    def approve_requests(self, request, queryset):
        approved = 0
        skipped = 0
        today = timezone.now().date()
        for record in queryset:
            if record.status == 'PENDING':
                if record.book.available_copies > 0:
                    record.book.available_copies -= 1
                    record.book.save(update_fields=['available_copies'])
                    record.status = 'APPROVED'
                    record.issue_date = today
                    record.due_date = today + timedelta(days=14)
                    record.approved_by = request.user
                    record.returned = False
                    record.save(update_fields=['status', 'issue_date', 'due_date', 'approved_by', 'returned'])
                    approved += 1
                else:
                    skipped += 1
        if approved:
            self.message_user(request, f"Successfully approved {approved} borrowing request(s).")
        if skipped:
            self.message_user(request, f"{skipped} request(s) could not be approved due to zero available stock.", level='warning')

    @admin.action(description="Reject selected pending borrowing requests")
    def reject_requests(self, request, queryset):
        rejected = 0
        for record in queryset:
            if record.status == 'PENDING':
                record.status = 'REJECTED'
                record.approved_by = request.user
                record.rejection_reason = "Request declined via administration interface."
                record.save(update_fields=['status', 'approved_by', 'rejection_reason'])
                rejected += 1
        if rejected:
            self.message_user(request, f"Successfully marked {rejected} request(s) as Rejected.")

    @admin.action(description="Process return for selected active loans")
    def process_returns(self, request, queryset):
        returned_count = 0
        for record in queryset:
            if not record.returned:
                record.complete_return(fine_rate=DAILY_FINE_RATE)
                returned_count += 1
        if returned_count:
            self.message_user(request, f"Successfully processed returns for {returned_count} loan(s).")


admin.site.site_header = "Digital Library Administration"
admin.site.site_title = "Library Admin Portal"
admin.site.index_title = "Library Management System"
