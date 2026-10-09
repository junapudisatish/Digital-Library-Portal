# Digital Library & E-Book Circulation Portal

A modern, responsive full-stack **Digital Library & E-Book Circulation Portal** built with **Django**, **Bootstrap 5**, **JavaScript (ES6+)**, and **SQLite**. Deployed and production-ready for **Render** using **WhiteNoise** and **Gunicorn**.

---

## 1. Project Overview & Features

- **Dynamic Book Catalog**: Browse titles with high-definition book covers, author metadata, genre tags, and availability status pills.
- **Instant Client-Side Search & Filter**: Real-time JavaScript search filtering by title, author, genre, and ISBN without full-page reloads.
- **Book Issue Workflow**:
  - Automatically verifies available inventory
  - Decrements available stock upon checkout.
  - Automatically calculates and sets the standard **14-day loan term due date**.
- **Book Return Workflow & Fine Assessment**:
  - Replenishes available stock upon return
  - Interactive overdue calculation preview widget before submission.
  - Computes overdue fines based on daily penalty rates
- **Patron / Member Dashboard**:
  - Live loan status tracking 
  - Prominent overdue alert banners showing overdue durations and calculated fines.
  - One-click return processing buttons directly from active loan rows.
  - Complete borrowing history with fine assessment records.
- **Interactive Due-Date & Fine Calculator**:
  - Standalone simulation tool with configurable loan terms (7, 14, 21, 30 days) and date pickers.
  - Real-time client-side overdue day computation and fine evaluation.
- **Automated Sample Data Seeding**:
  - Populate 7 authors, 8 classic & modern books with cover images, 4 members, and realistic circulation records (including active on-time, active overdue, and past returned loans).

---

## 2. Technology Stack

- **Backend**: Python 3.11+, Django 6.x / 5.x, Django ORM
- **Database**: SQLite (`db.sqlite3` — default built-in Django database)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Bootstrap Icons, Google Fonts (*Plus Jakarta Sans*)
- **Static Assets & Serving**: WhiteNoise (`CompressedManifestStaticFilesStorage`)
- **WSGI Production Server**: Gunicorn
- **Deployment Platform**: Render (Infrastructure-as-code via `render.yaml` Blueprint)

---

## 3. Database Architecture & Relational Schema

Managed through Django ORM and ForeignKey relationships:

1. **`Author`**:
   - `name` (CharField)
   - `biography` (TextField)
2. **`Book`**:
   - `title` (CharField)
   - `author` (ForeignKey -> Author)
   - `isbn` (CharField, unique)
   - `genre` (CharField)
   - `total_copies` (PositiveIntegerField)
   - `available_copies` (PositiveIntegerField)
   - `cover_url` (URLField)
3. **`Member`**:
   - `name` (CharField)
   - `member_id` (CharField, unique)
   - `email` (EmailField, unique)
   - `phone` (CharField)
   - `joined_date` (DateField)
4. **`CirculationRecord`**:
   - `book` (ForeignKey -> Book)
   - `member` (ForeignKey -> Member)
   - `issue_date` (DateField)
   - `due_date` (DateField, auto-defaults to `issue_date + 14 days`)
   - `return_date` (DateField, nullable)
   - `fine_amount` (DecimalField, defaults to 0.00)
   - `returned` (BooleanField, default False)

---

## 4. Business Logic Rules

| Rule | Implementation Details |
|---|---|
| **Zero Available Copies Constraint** | Issue form disallows checkout when `available_copies == 0`. |
| **Inventory Decrement** | `book.issue_copy()` reduces `available_copies` by 1 on issue. |
| **Inventory Replenishment** | `book.return_copy()` increases `available_copies` by 1 on return. |
| **Loan Period Default** | Due date defaults to 14 days after issue date (`issue_date + timedelta(days=14)`). |
| **Overdue Fine Computation** | During return, fine = `max(0, (return_date - due_date).days) * DAILY_FINE_RATE`. |

---

## 5. Local Setup & Execution

### Step 1: Clone / Navigate to Directory
```bash
cd "Digital Library & E-Book Circulation Portal"
```

### Step 2: Activate Virtual Environment
```bash
# Windows
.\venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run Migrations & Create Superuser
```bash
python manage.py migrate
python create_superuser.py
```
### Step 5: Seed Demo Dataset (Optional)
```bash
python manage.py seed_library
```

### Step 6: Start Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Open **`http://127.0.0.1:8000/`** in your browser.

---
## 7. Automated Test Suite

Run the 12 automated unit and integration tests:
```bash
python manage.py test
```
**Results**:
```
Ran 12 tests in 0.422s
OK
```
Tests validate:
- Book inventory decrement & 0-copy validation
- Model constraints & relations
- Issue date to 14-day due date calculation
- On-time vs overdue fine calculations
- View response codes (HTTP 200)
- End-to-end checkout & return workflows
- JSON API calculation endpoint
