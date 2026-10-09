import os
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Author, Book, Member, CirculationRecord, DAILY_FINE_RATE


def populate_sample_data():
    User = get_user_model()
    today = timezone.now().date()

    # 1. Authors
    authors_data = [
        {
            "name": "George Orwell",
            "biography": "English novelist, essayist, and critic known for acute social commentary and dystopian fiction including 1984 and Animal Farm."
        },
        {
            "name": "Jane Austen",
            "biography": "English novelist known for her realism, biting irony, and social commentary in works like Pride and Prejudice and Sense and Sensibility."
        },
        {
            "name": "Isaac Asimov",
            "biography": "Master of science fiction and biochemistry professor, famous for the Foundation series and Robot series."
        },
        {
            "name": "Gabriel García Márquez",
            "biography": "Colombian novelist, Nobel laureate, and pioneer of magical realism, renowned for One Hundred Years of Solitude."
        },
        {
            "name": "F. Scott Fitzgerald",
            "biography": "American author regarded as one of the greatest writers of the 20th century, capturing the Jazz Age in The Great Gatsby."
        },
        {
            "name": "Arthur Conan Doyle",
            "biography": "British author and physician who created the legendary detective Sherlock Holmes and Dr. John Watson."
        },
        {
            "name": "J.K. Rowling",
            "biography": "British author best known for writing the acclaimed Harry Potter fantasy series."
        },
    ]

    author_objs = {}
    for a in authors_data:
        author, _ = Author.objects.get_or_create(name=a["name"], defaults={"biography": a["biography"]})
        author_objs[a["name"]] = author

    # 2. Books with rich descriptions
    books_data = [
        {
            "title": "1984",
            "author": author_objs["George Orwell"],
            "isbn": "978-0451524935",
            "genre": "Dystopian Fiction",
            "description": "Winston Smith lives in a dystopian Oceania where the Party and its omnipresent leader Big Brother maintain surveillance, historical revisionism, and psychological control. A profound exploration of totalitarianism, truth, and individuality.",
            "total_copies": 5,
            "available_copies": 3,
            "cover_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=600&q=80"
        },
        {
            "title": "Animal Farm",
            "author": author_objs["George Orwell"],
            "isbn": "978-0451526342",
            "genre": "Political Satire",
            "description": "An allegorical fable charting the rebellion of farm animals against human dominion, exploring how ideals of equality can devolve into totalitarian rule through manipulation and deceit.",
            "total_copies": 4,
            "available_copies": 4,
            "cover_url": "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?auto=format&fit=crop&w=600&q=80"
        },
        {
            "title": "Pride and Prejudice",
            "author": author_objs["Jane Austen"],
            "isbn": "978-0141439518",
            "genre": "Classic Romance",
            "description": "The witty and independent Elizabeth Bennet navigates social status, family expectations, and tumultuous courtship alongside the aristocratic, enigmatic Mr. Darcy in Regency-era England.",
            "total_copies": 6,
            "available_copies": 5,
            "cover_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=600&q=80"
        },
        {
            "title": "Foundation",
            "author": author_objs["Isaac Asimov"],
            "isbn": "978-0553293357",
            "genre": "Science Fiction",
            "description": "Mathematician Hari Seldon develops psychohistory, predicting the collapse of the Galactic Empire. He establishes a colony of scholars at the edge of the galaxy to preserve human civilization through the dark age.",
            "total_copies": 3,
            "available_copies": 2,
            "cover_url": "https://images.unsplash.com/photo-1532012164546-f432f2e3777a?auto=format&fit=crop&w=600&q=80"
        },
        {
            "title": "One Hundred Years of Solitude",
            "author": author_objs["Gabriel García Márquez"],
            "isbn": "978-0060883287",
            "genre": "Magical Realism",
            "description": "The multi-generational saga of the Buendía family in the mythical town of Macondo, weaving miraculous phenomena, personal obsessions, and cyclical Latin American history into unforgettable literature.",
            "total_copies": 4,
            "available_copies": 3,
            "cover_url": "https://images.unsplash.com/photo-1516979187457-637abb4f9353?auto=format&fit=crop&w=600&q=80"
        },
        {
            "title": "The Great Gatsby",
            "author": author_objs["F. Scott Fitzgerald"],
            "isbn": "978-0743273565",
            "genre": "Classic Literature",
            "description": "Set during the roaring twenties on Long Island, narrator Nick Carraway observes the enigmatic millionaire Jay Gatsby's obsessive quest to reunite with Daisy Buchanan, revealing the disillusionment behind the American Dream.",
            "total_copies": 2,
            "available_copies": 0,  # Fully checked-out inventory demonstration
            "cover_url": "https://images.unsplash.com/photo-1495446815901-a7297e633e8d?auto=format&fit=crop&w=600&q=80"
        },
        {
            "title": "The Adventures of Sherlock Holmes",
            "author": author_objs["Arthur Conan Doyle"],
            "isbn": "978-0140437713",
            "genre": "Mystery",
            "description": "A classic collection of twelve short stories recounting the ingenious deductions and forensic investigations of Sherlock Holmes and Dr. John Watson across Victorian London.",
            "total_copies": 5,
            "available_copies": 4,
            "cover_url": "https://images.unsplash.com/photo-1476275466078-4007374efbbe?auto=format&fit=crop&w=600&q=80"
        },
        {
            "title": "Harry Potter and the Sorcerer's Stone",
            "author": author_objs["J.K. Rowling"],
            "isbn": "978-0590353427",
            "genre": "Fantasy",
            "description": "An orphaned eleven-year-old boy discovers his magical lineage and enrolls at Hogwarts School of Witchcraft and Wizardry, uncovering mysteries about his parents and facing dark forces.",
            "total_copies": 8,
            "available_copies": 7,
            "cover_url": "https://images.unsplash.com/photo-1507842229458-57754b2b3f11?auto=format&fit=crop&w=600&q=80"
        },
    ]

    book_objs = {}
    for b in books_data:
        book, created = Book.objects.get_or_create(
            isbn=b["isbn"],
            defaults={
                "title": b["title"],
                "author": b["author"],
                "genre": b["genre"],
                "description": b["description"],
                "total_copies": b["total_copies"],
                "available_copies": b["available_copies"],
                "cover_url": b["cover_url"]
            }
        )
        if not created and not book.description:
            book.description = b["description"]
            book.save(update_fields=["description"])
        book_objs[b["title"]] = book

    # 3. Create or get Demo Student user
    student_user, user_created = User.objects.get_or_create(
        username="student",
        defaults={
            "email": "alex.rivera@example.com",
            "first_name": "Alex",
            "last_name": "Rivera",
            "is_staff": False,
        }
    )
    if user_created:
        student_pwd = os.environ.get("DEMO_STUDENT_PASSWORD")
        if student_pwd:
            student_user.set_password(student_pwd)
        else:
            student_user.set_unusable_password()
        student_user.save()

    # 4. Members
    members_data = [
        {"name": "Alex Rivera", "member_id": "MEM-1001", "email": "alex.rivera@example.com", "phone": "+1 (555) 234-5678", "joined_date": today - timedelta(days=90), "user": student_user},
        {"name": "Sophia Chen", "member_id": "MEM-1002", "email": "sophia.chen@example.com", "phone": "+1 (555) 345-6789", "joined_date": today - timedelta(days=60), "user": None},
        {"name": "Marcus Johnson", "member_id": "MEM-1003", "email": "marcus.j@example.com", "phone": "+1 (555) 456-7890", "joined_date": today - timedelta(days=45), "user": None},
        {"name": "Emily Watson", "member_id": "MEM-1004", "email": "emily.watson@example.com", "phone": "+1 (555) 567-8901", "joined_date": today - timedelta(days=20), "user": None},
    ]

    member_objs = {}
    for m in members_data:
        member, created = Member.objects.get_or_create(
            member_id=m["member_id"],
            defaults={
                "name": m["name"],
                "email": m["email"],
                "phone": m["phone"],
                "joined_date": m["joined_date"],
                "user": m["user"]
            }
        )
        if m["user"] and member.user != m["user"]:
            member.user = m["user"]
            member.save(update_fields=["user"])
        member_objs[m["member_id"]] = member

    # 5. Circulation Records (Clean slate and populate rich records)
    CirculationRecord.objects.all().delete()

    # Record 1: Alex Rivera has "1984" - Active, On-Time (issued 4 days ago, due in 10 days)
    CirculationRecord.objects.create(
        book=book_objs["1984"],
        member=member_objs["MEM-1001"],
        status='APPROVED',
        issue_date=today - timedelta(days=4),
        due_date=today + timedelta(days=10),
        returned=False
    )

    # Record 2: Alex Rivera has "The Great Gatsby" - Active, OVERDUE! (issued 21 days ago, due 7 days ago -> 7 days overdue, 7 * ₹5 = ₹35 fine)
    CirculationRecord.objects.create(
        book=book_objs["The Great Gatsby"],
        member=member_objs["MEM-1001"],
        status='APPROVED',
        issue_date=today - timedelta(days=21),
        due_date=today - timedelta(days=7),
        returned=False
    )

    # Record 3: Sophia Chen has "Pride and Prejudice" - Active, Due Soon (issued 12 days ago, due in 2 days)
    CirculationRecord.objects.create(
        book=book_objs["Pride and Prejudice"],
        member=member_objs["MEM-1002"],
        status='APPROVED',
        issue_date=today - timedelta(days=12),
        due_date=today + timedelta(days=2),
        returned=False
    )

    # Record 4: Sophia Chen has "The Great Gatsby" - Active, OVERDUE! (issued 18 days ago, due 4 days ago)
    CirculationRecord.objects.create(
        book=book_objs["The Great Gatsby"],
        member=member_objs["MEM-1002"],
        status='APPROVED',
        issue_date=today - timedelta(days=18),
        due_date=today - timedelta(days=4),
        returned=False
    )

    # Record 5: Marcus Johnson has "Foundation" - Active, On-time (issued 2 days ago, due in 12 days)
    CirculationRecord.objects.create(
        book=book_objs["Foundation"],
        member=member_objs["MEM-1003"],
        status='APPROVED',
        issue_date=today - timedelta(days=2),
        due_date=today + timedelta(days=12),
        returned=False
    )

    # Record 6: Marcus Johnson returned "1984" past due (issued 30 days ago, due 16 days ago, returned 11 days ago -> 5 days overdue -> 5 * ₹5 = ₹25.00 fine paid)
    CirculationRecord.objects.create(
        book=book_objs["1984"],
        member=member_objs["MEM-1003"],
        status='RETURNED',
        issue_date=today - timedelta(days=30),
        due_date=today - timedelta(days=16),
        return_date=today - timedelta(days=11),
        fine_amount=Decimal('25.00'),
        returned=True
    )

    # Record 7: Emily Watson returned "One Hundred Years of Solitude" on-time
    CirculationRecord.objects.create(
        book=book_objs["One Hundred Years of Solitude"],
        member=member_objs["MEM-1004"],
        status='RETURNED',
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=6),
        return_date=today - timedelta(days=8),
        fine_amount=Decimal('0.00'),
        returned=True
    )

    # Record 8: Emily Watson has "Harry Potter and the Sorcerer's Stone" - Active
    CirculationRecord.objects.create(
        book=book_objs["Harry Potter and the Sorcerer's Stone"],
        member=member_objs["MEM-1004"],
        status='APPROVED',
        issue_date=today - timedelta(days=5),
        due_date=today + timedelta(days=9),
        returned=False
    )

    # Record 9: Alex Rivera has a PENDING borrowing request for "Animal Farm"
    CirculationRecord.objects.create(
        book=book_objs["Animal Farm"],
        member=member_objs["MEM-1001"],
        status='PENDING',
        request_date=timezone.now() - timedelta(hours=3),
        returned=False
    )

    # Record 10: Alex Rivera has a REJECTED borrowing request for "The Adventures of Sherlock Holmes"
    CirculationRecord.objects.create(
        book=book_objs["The Adventures of Sherlock Holmes"],
        member=member_objs["MEM-1001"],
        status='REJECTED',
        request_date=timezone.now() - timedelta(days=2),
        rejection_reason="Reserved for English Literature curriculum reference collection.",
        returned=False
    )

    # Re-synchronize available_copies for books based on active circulation (status='APPROVED', returned=False)
    for book in Book.objects.all():
        active_borrowed = book.circulation_records.filter(status='APPROVED', returned=False).count()
        book.available_copies = max(0, book.total_copies - active_borrowed)
        book.save()

    return len(books_data)
