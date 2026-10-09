from django.urls import path
from . import views

urlpatterns = [
    # Catalog & Discovery
    path('', views.catalog_view, name='catalog'),
    path('book/<int:book_id>/', views.book_detail_view, name='book_detail'),
    path('book/add/', views.book_create_view, name='book_create'),
    path('book/<int:book_id>/edit/', views.book_edit_view, name='book_edit'),

    # Circulation Desk & Request Lifecycle
    path('book/<int:book_id>/borrow/', views.book_borrow_request_view, name='borrow_book'),
    path('requests/<int:record_id>/approve/', views.request_approve_view, name='approve_request'),
    path('requests/<int:record_id>/reject/', views.request_reject_view, name='reject_request'),
    path('issue/', views.book_issue_view, name='issue_book'),
    path('issue/<int:book_id>/', views.book_issue_view, name='issue_specific_book'),
    path('return/', views.book_return_view, name='return_book'),
    path('return/<int:record_id>/', views.book_return_view, name='return_specific_record'),

    # Authentication & Profile Security
    path('register/', views.student_register_view, name='register'),
    path('login/', views.student_login_view, name='login'),
    path('logout/', views.student_logout_view, name='logout'),
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', views.CustomPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('student/dashboard/', views.student_dashboard_view, name='student_dashboard'),

    # Staff / Librarian Management Hub
    path('staff/', views.staff_dashboard_view, name='staff_dashboard'),

    # Members Directory (Librarian/Staff overview)
    path('members/', views.member_list_view, name='member_list'),
    path('members/<int:member_id>/', views.member_dashboard_view, name='member_dashboard'),
    path('members/add/', views.member_create_view, name='member_create'),

    # Calculation Tool & API
    path('calculator/', views.calculator_view, name='calculator'),
    path('seed-demo-data/', views.seed_data_view, name='seed_data'),
    path('api/calculate-fine/', views.api_calculate_fine, name='api_calculate_fine'),
]
