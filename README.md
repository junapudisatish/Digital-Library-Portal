# Digital Library & E-Book Circulation Portal

A comprehensive, production-grade full-stack **Digital Library & E-Book Circulation Portal** built with **Django 5.x**, **Bootstrap 5.3**, **JavaScript (ES6+)**, **Chart.js**, and **SQLite**. Designed and upgraded as an academic B.Tech Capstone Project.

Live Production URL: **[https://digital-library-portal.onrender.com/](https://digital-library-portal.onrender.com/)**

---

## 1. Key Features & Architectural Capabilities

### 🎨 Editorial Library Theme & Design System
- **Curated Color Tokens**: Deep Navy (`#071224`, `#0B192C`), Warm Ivory (`#FAFAF7`), and Subtle Gold accents (`#D4AF37`, `#C59B27`).
- **Modern Typography**: Google Fonts (*Outfit* for editorial headings, *Plus Jakarta Sans* for UI body text).
- **Responsive Navigation**: Sticky glassmorphic navbar with active link highlights, student "My Library" portal, librarian quick-actions, and mobile drawer.
- **Offline Reliability**: Local vector SVG book-cover fallback (`/static/images/book-cover-fallback.svg`) for missing or broken image URLs.

### 🏛️ Landing Page (`/`)
- **Brand Identity**: LIBRA Digital Library Portal with editorial hero heading: *"Your Next Great Read Starts Here."*
- **Live Database Metrics**: Real-time ORM counters for catalog titles, physical copies, available copies, registered members, and active loans.
- **Instant Search Bar**: Hero search bar routing directly to filtered catalog queries.
- **Showcases**: Featured volumes, recently added titles, popular genres, and a 3-step borrowing workflow explanation.

### 📚 Catalog Discovery & Management (`/catalog/`)
- **Instant Client-Side & Server-Side Search**: Title, author, ISBN, and genre keyword matching.
- **Availability & Genre Filters**: Filter by genre or stock level (Available, Limited Copies, Unavailable).
- **Inventory Badges**: Distinct visual status indicators (`Available`, `Limited Stock`, `Out of Stock`).
- **Book Details (`/book/<id>/`)**: Bibliographic overview, author biography, ISBN, copy stock counters, student loan status alert, and issue request trigger.
- **Author Directory (`/authors/`)**: Searchable directory of literary creators with biographical notes and book counts.

### 🔄 Book Circulation, 14-Day Lending & ₹5/day Overdue Fine Engine
- **Atomic Book Issue (`/issue/`)**: Authenticated members request or librarians issue available copies. Transactional locking (`select_for_update`) prevents negative inventory and race conditions.
- **Automated Due Date**: Automatically set to 14 days after the issue date.
- **Book Return Desk (`/return/`)**:
  - Student members can self-return their own active loans directly from their dashboard.
  - Librarians can return any active circulation record.
  - Returns increment available book inventory by exactly 1 in a database transaction.
  - Overdue fines are authoritatively calculated on the Django server: `Overdue Days × DAILY_FINE_RATE` (default ₹5.00/day).
  - Books returned on or before due date incur ₹0.00 fine.
- **Interactive Due Date & Fine Calculator (`/calculator/` & `/due-calculator/`)**: Interactive tool to preview 14-day due dates and calculate overdue fines based on custom dates and rates.

### 📊 Role-Segregated Dashboards

#### 🎓 Student Member Dashboard (`/student/dashboard/`)
- **Executive Metric Tiles**: Pending requests, active borrowed books, loans due soon, and overdue alerts.
- **Tabbed Management**:
  1. *Pending Requests* (with librarian approval status).
  2. *Active Loans* (with due countdown and direct return buttons).
  3. *Due Soon* (expiring within 3 days).
  4. *Overdue Notice* (with accrued ₹5/day fine warnings).
  5. *Borrowing History* (past returned books and assessed fines).
  6. *Rejected Requests* (with librarian feedback).

#### 🛡️ Librarian Analytics & Operations Dashboard (`/librarian/dashboard/`)
- **8 Live KPI Tiles**: Catalog titles, physical copies, in-stock inventory, registered members, active loans, overdue loans, pending requests, and collected fines.
- **Chart.js Visualizations**:
  - Category / Genre distribution doughnut chart.
  - Circulation lifecycle status breakdown bar chart.
- **Operational Action Queues**:
  - Pending borrowing requests review and approval table.
  - Overdue borrowings attention table with fine calculator.
  - Most borrowed books leaderboard.
  - Recent circulation activity log.

---

## 2. Security, Authentication & Password Reset

### Authentication System
- Built on Django's native authentication framework with PBKDF2 SHA-256 password hashing.
- Member registration (`/register/`) with validation, unique emails, and automated `Member` profile linkage.
- Session-preserving password change (`/password-change/`).

### Password Reset Workflow
- Cryptographic token generation via Django `PasswordResetForm`.
- Validates that the submitted email belongs to an active, registered account.
- Dispatches secure reset links to user email (`/password-reset/confirm/<uidb64>/<token>/`).
- Detailed, structured logging records dispatch events and catches email delivery errors without exposing passwords.

### Email Configuration

#### Development Mode (Console Backend)
By default, the application uses Django's console email backend. Reset links are printed directly to the terminal/console stdout:
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

#### Production Mode (SMTP Configuration)
To send real emails via SMTP (e.g. Gmail or SendGrid), configure the following environment variables:
```bash
EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST="smtp.gmail.com"
EMAIL_PORT="587"
EMAIL_USE_TLS="True"
EMAIL_HOST_USER="your-email@gmail.com"
EMAIL_HOST_PASSWORD="your-app-password"  # Use Google App Password, not main password
DEFAULT_FROM_EMAIL="LIBRA Digital Library <your-email@gmail.com>"
```

### Access Control & Demonstration Safety
- Sensitive librarian dashboards and author/book creation routes require `is_staff` privileges.
- Student members are strictly restricted to their own circulation records and profiles; unauthorized attempts to return other members' records are rejected.
- **Safe Demo Seeding (`/seed-demo-data/`)**: Restricted to authenticated staff. Only synchronizes missing books and demo members; does not destructively delete existing student loans unless `--reset` is explicitly requested.

---

## 3. Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.11+, Django 5.x / 6.x, Django ORM |
| **Database** | SQLite (`db.sqlite3`) - Mandatory per Capstone requirement |
| **Frontend** | HTML5, CSS3 (Custom Navy & Gold tokens), Vanilla JS (ES6+), Bootstrap 5.3, Bootstrap Icons |
| **Visualizations** | Chart.js 4.4+ (Librarian Operations Analytics) |
| **Static Files** | WhiteNoise (`CompressedManifestStaticFilesStorage` in production) |
| **WSGI Server** | Gunicorn |
| **Deployment** | Render Cloud (`render.yaml`) |

> [!IMPORTANT]
> **SQLite on Render Free Web Services**:
> Render's free tier web service filesystem is ephemeral. While local development uses persistent local `db.sqlite3`, instances on Render's free tier may reset database state if the container restarts or is redeployed. For evaluation and viva demonstrations, run `python manage.py seed_library` or use the staff `/seed-demo-data/` portal to repopulate demonstration records instantaneously.

---

## 4. Local Setup & Development Commands

### 1. Clone & Enter Repository
```bash
git clone https://github.com/junapudisatish/Digital-Library-Portal.git
cd "Digital Library & E-Book Circulation Portal"
```

### 2. Activate Virtual Environment
**Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```
**Linux / macOS:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply Migrations
```bash
python manage.py migrate
```

### 5. Seed Library Catalog & Demonstration Records
```bash
python manage.py seed_library
```
*(To perform a clean reset of sample data, run `python manage.py seed_library --reset`)*

### 6. Create / Verify Administrator Account
```bash
python manage.py setup_admin --username=admin
# Enter your secure password when prompted
```

### 7. Run Verification Checks & Test Suite
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

### 8. Start Local Development Server
```bash
python manage.py runserver
```
Visit **`http://127.0.0.1:8000/`** in your browser.

---

## 5. Render Production Deployment

The project is preconfigured with a declarative `render.yaml` specification:

```yaml
services:
  - type: web
    name: digital-library-portal
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
      - key: DAILY_FINE_RATE
        value: "5.00"
      - key: EMAIL_BACKEND
        value: "django.core.mail.backends.console.EmailBackend"
```

### Manual Environment Variables on Render
If configuring the service manually in the Render dashboard:
- `SECRET_KEY`: A cryptographically secure random string.
- `DEBUG`: `False`
- `ALLOWED_HOSTS`: `digital-library-portal.onrender.com,localhost,127.0.0.1`
- `DAILY_FINE_RATE`: `5.00`
- `EMAIL_BACKEND`: `django.core.mail.backends.console.EmailBackend` (or SMTP credentials).
- `PYTHON_VERSION`: `3.11.0`

### Build & Start Commands
- **Build Command**:
  `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`
- **Start Command**:
  `gunicorn library_portal.wsgi:application`

---

## 6. Verification & Automated Test Coverage

The platform includes **39 automated unit tests** verifying:
- **Model Integrity**: Copy increment/decrement, zero copy issue prevention, 14-day default due date, and fine calculation.
- **Workflow & Atomicity**: Issue transactions, return inventory updates, and prevention of duplicate submissions.
- **Security & Authorization**: Student profile privacy, prevention of cross-member return submissions, and staff-only catalog/seed routes.
- **Authentication**: Registration, login, logout, password change, and password reset token delivery.
- **Institutional Pages**: Landing page, catalog search, librarian analytics, author directory, and error handlers.

All tests execute cleanly:
```bash
Ran 39 tests in 92.8s
OK
```
