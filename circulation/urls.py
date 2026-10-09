from django.urls import path
from . import views

urlpatterns = [
    path('', views.catalog_view, name='catalog'),
    path('book/<int:book_id>/', views.book_detail_view, name='book_detail'),
    path('book/add/', views.book_create_view, name='book_create'),
    path('issue/', views.book_issue_view, name='issue_book'),
    path('issue/<int:book_id>/', views.book_issue_view, name='issue_specific_book'),
    path('return/', views.book_return_view, name='return_book'),
    path('return/<int:record_id>/', views.book_return_view, name='return_specific_record'),
    path('members/', views.member_list_view, name='member_list'),
    path('members/<int:member_id>/', views.member_dashboard_view, name='member_dashboard'),
    path('members/add/', views.member_create_view, name='member_create'),
    path('calculator/', views.calculator_view, name='calculator'),
    path('seed-demo-data/', views.seed_data_view, name='seed_data'),
    path('api/calculate-fine/', views.api_calculate_fine, name='api_calculate_fine'),
]
