# Digital Library & E-Book Circulation Portal

A comprehensive, production-ready full-stack **Digital Library & E-Book Circulation Portal** built with **Django**, **Bootstrap 5**, **JavaScript (ES6+)**, and **SQLite**. Featuring an elegant **Navy Blue, Crisp White, and Subtle Metallic Gold** design system, a two-stage **Student Borrow Request & Librarian Approval Lifecycle**, real-time **14-Day Loan Engine**, automated **₹5/day Overdue Fine Calculation**, full **Django Admin & Member Authentication**, and public deployment on **Render** using **WhiteNoise** and **Gunicorn**.

---

## 1. Key Features & Architectural Capabilities

### 🎨 Premium Navy Blue & Gold Design System
- **Curated Palette**: Deep Luxury Navy (`#0B192C`, `#102A45`), Crisp White (`#FFFFFF`), and Warm Metallic Gold accents (`#D4AF37`, `#C59B27`).
- **Modern Typography**: Google Fonts (*Outfit* for bold headings and *Plus Jakarta Sans* for clean body text).
- **Glassmorphic Navigation**: Sticky navy navbar with gold branding badge and role-based dropdown navigation.
- **Micro-Animations & Visual Hierarchy**: Smooth card lifting (`translateY`), cover image zoom on hover, overdue pulse indicators, and CSS skeleton loaders.
- **Full Responsiveness**: Seamless across mobile phones, tablets, and wide desktop displays.

### 📚 Book Catalog, Instant Search, Filtering & Pagination
- **Multi-Criteria Discovery**: Instant client-side ES6+ search alongside server-side keyword query across title, author, genre, and ISBN.
- **Category & Stock Filters**: Filter by genre or availability (In Stock vs. Checked Out).
- **Database-Optimized Sorting**: Sort by Title (A &rarr; Z), Title (Z &rarr; A), Author, Most Available Copies, or Newest Additions.
- **Django Pagination**: 8 books per page with preserved query parameters across pagination links.
- **Rich Book Detail Pages**: Book cover, author biography, ISBN, total/available copies, synopsis overview, student loan status alert, and complete checkout history.

### 🎓 Student Authentication & "My Library" Dashboard
- **Secure Registration (`/register/`)**: Student signup provisioning a Django user account and linking to an automated student library card (`Member` record).
- **Member & Staff Login (`/login/`)**: Standard secure Django authentication with password hashing and CSRF protection. Credentials are never exposed on login pages.
- **Password Management**: Built-in Password Change (`/password-change/`) with session preservation and Password Reset (`/password-reset/`) flows.
- **"My Library" Dashboard (`/student/dashboard/`)**:
  - **4 Executive Metric Cards**: Pending Requests, Currently Borrowed, Due Soon, and Overdue.
  - **6 Dedicated Sections**:
    1. Pending Requests (with live approval status badges)
    2. Active Loans (with 14-day due date countdowns)
    3. Due Soon (within 3 days)
    4. Overdue Loans (with live estimated overdue days and ₹5/day fines)
    5. Returned Books / Historical Circulation
    6. Rejected Requests (with librarian explanation note)

### 🛡️ Librarian-Approved Book Borrowing Workflow
1. **Student Request**: Authenticated student browses the catalog and clicks **Borrow Book**.
2. **Server Validation**: The server validates book availability, prevents duplicate pending/active loans, and records a `PENDING` request. Available copies are **NOT** decremented at request submission.
3. **Librarian Review**: Staff views pending requests in the **Librarian Operations Center** (`/staff/`).
4. **Librarian Approval**:
   - Atomic database transaction (`transaction.atomic`) rechecks availability.
   - Decrements `available_copies` by exactly 1.
   - Sets status to `APPROVED`, records issue date, and computes authoritative due date (`issue_date + 14 days`).
   - Records the approving librarian.
5. **Librarian Rejection**:
   - Marks request `REJECTED` and records optional rejection reason for the student.
   - Stock remains untouched.

### 💰 Book Returns & Overdue Fine Engine
- **Loan Period**: Standard 14 days.
- **Fine Rate**: ₹5.00 per calendar day overdue (`DAILY_FINE_RATE = Decimal('5.00')`). Grace period: None.
- **Fine Formula**: `Overdue Days × ₹5.00` (where `Overdue Days = max(0, return_date - due_date)`).
- **Return Processing (`/return/`)**: Authorized librarians process returns. Available copies increment by exactly 1, and the final fine amount is authoritatively recorded.

### 🛡️ Librarian / Staff Management Hub (`/staff/`)
- **8 Real-Time ORM Statistics**: Unique Titles, Total Stock, Available Copies, Registered Members, Pending Requests, Active Loans, Overdue Loans, and Returned Books.
- **Pending Request Decision Queue**: Review student requests with 1-click Approve or modal Reject.
- **Overdue Attention Center**: Live list of past-due checkouts with estimated fines requiring immediate return.
- **Inventory & Copy Management**: Add new titles (`/book/add/`), edit metadata (`/book/<id>/edit/`), and manage stock copy counts.
- **Members Directory (`/members/`)**: Inspect student borrowing records, contact info, and loan standings.

---

## 2. Administrator & Member Authentication Setup

### Secure Superuser / Admin Setup
Configure or update the administrator account using the custom Django management command. To protect credentials, passwords should be set via environment variables or entered securely via masked prompt:

```bash
# Option A: Interactive masked prompt (recommended for local development)
python manage.py setup_admin --username=admin

# Option B: Via environment variable (recommended for automated deployments & Render)
export DJANGO_SUPERUSER_PASSWORD="your-secure-password"
python manage.py setup_admin --username=admin
```
This command is safe and idempotent: if the administrator already exists, its permissions are safely verified without creating duplicate accounts or logging credentials.

| Role | Provisioning | Notes |
| :--- | :--- | :--- |
| **Librarian / Superuser** | Configured via `setup_admin` or environment variables | Access to Staff Hub (`/staff/`), Password Change (`/password-change/`), and Django Admin (`/admin/`). |
| **Student Member** | Self-registration (`/register/`) or administrative creation | Access to personal "My Library" hub (`/student/dashboard/`). |

---

## 3. Technology Stack

- **Backend**: Python 3.11+, Django 6.x / 5.x, Django ORM
- **Database**: SQLite (`db.sqlite3`) using Django's built-in backend
- **Frontend**: HTML5, Vanilla CSS3 (Custom Navy & Gold tokens), JavaScript (ES6+), Bootstrap 5, Bootstrap Icons
- **Static Asset Pipeline**: WhiteNoise (`CompressedManifestStaticFilesStorage` in production, `StaticFilesStorage` in development)
- **Production WSGI Server**: Gunicorn
- **Deployment Platform**: Render (`render.yaml`)

> [!NOTE]
> **SQLite on Render Free Tier**: Render's default free web service filesystem is ephemeral. While local development uses persistent `db.sqlite3`, data written to SQLite on a free Render web service may reset upon service redeployments or container restarts unless a Render Persistent Disk is attached.

---

## 4. Local Installation & Development Setup

### 1. Clone the repository and enter directory
```bash
git clone https://github.com/junapudisatish/Digital-Library-Portal.git
cd "Digital Library & E-Book Circulation Portal"
```

### 2. Activate virtual environment
**On Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```
**On macOS / Linux:**
```bash
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run migrations
```bash
python manage.py migrate
```

### 5. Seed sample books, demo members, and circulation records
```bash
python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_portal.settings'); django.setup(); from circulation.seed_data import populate_sample_data; populate_sample_data()"
```

### 6. Set up admin account
```bash
python manage.py setup_admin --username=admin
# Enter your secure administrator password when prompted
```

### 7. Run automated test suite
```bash
python manage.py test
```

### 8. Start the local development server
```bash
python manage.py runserver
```
Visit **`http://127.0.0.1:8000/`** in your browser.

---

## 5. Deployment on Render

This project includes a declarative `render.yaml` blueprint configured for Render:

```yaml
services:
  - type: web
    name: digital-library-demo
    runtime: python
    buildCommand: "pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate"
    startCommand: "gunicorn library_portal.wsgi:application"
    envVars:
      - key: PYTHON_VERSION
        value: "3.11.0"
      - key: SECRET_KEY
        generateValue: true
      - key: DEBUG
        value: "False"
      - key: WEB_CONCURRENCY
        value: "2"
```

### Required Environment Variables on Render
- `SECRET_KEY`: Auto-generated by Render or specified manually.
- `DEBUG`: Set to `False`.
- `PYTHON_VERSION`: `3.11.0` or later.
- `RENDER`: Set to `True` (automatically set by Render).

### Push Changes to GitHub
```bash
git status
git add .
git commit -m "Upgrade digital library portal"
git push origin main
```
Render automatically triggers the build command (installs dependencies, collects static assets via WhiteNoise, applies migrations) and starts the Gunicorn application server.
