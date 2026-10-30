# NoteFlow Backend - Secure Note-Taking & Social Platform API

A robust, production-ready Django REST API built for technical evaluation. It implements secure email-based authentication with 6-digit expiring OTP verification, strict Role-Based Access Control (RBAC), database query indexing optimizations, and data aggregation pipelines.

---

## 📌 Tech Stack

- **Framework**: Django 5.2 & Django REST Framework (DRF)
- **Database**: SQLite (ORM parameterized queries)
- **Authentication**: JWT (JSON Web Tokens) via `djangorestframework-simplejwt`
- **Security**: Cryptographic password hashing (PBKDF2 SHA-256), DRF rate limiting/throttling, security headers
- **API Documentation**: OpenAPI 3.0 / Swagger UI & ReDoc via `drf-spectacular`

---

## 🚀 Key Features & Architectural Highlights

### 1. Authentication & Security
- **Email-First Authentication**: Email is the primary unique identifier (`USERNAME_FIELD = "email"`).
- **6-Digit OTP Lifecycle**:
  - Secure random 6-digit numeric OTP generated for account registration and password reset.
  - Configurable expiration time (default: 5 minutes via `.env`).
  - **Auto-Cleanup**: OTPs are permanently purged (`.delete()`) from the database once verified or expired.
- **Minimalistic HTML Email Template**: Clean dark-theme responsive email with monospace code display and security alerts.
- **Rate Limiting**: Built-in throttling (`100/min` for anonymous, `500/min` for authenticated users) protecting against brute force.

### 2. Role-Based Access Control (RBAC)
- **`User` Role**:
  - Can create, read, update, and delete their own notes.
  - Can manage their own posts and react to community posts.
  - Strictly isolated: cannot view, modify, or delete another user's notes.
- **`Admin` Role**:
  - Inherits all `User` capabilities.
  - Can view all notes across all users, with optional filtering by `?user_id=`.
  - Full user management: list all users, create users with designated roles, update user status, and delete users.

### 3. Database Indexing Strategy (Zero-Waste Indexing)
In compliance with the optimization constraints, indexes are strictly defined to support query patterns without redundant overhead:
- **`User` Model**:
  - `models.Index(fields=["role", "created_at"])`: Optimizes administrative user listing and role filtering.
  - Unique index on `email` and primary key index on `id` support instant profile lookups.
- **`Note` Model**:
  - `models.Index(fields=["owner", "-created_at"])`: Powers user note list views ordered chronologically.
  - `models.Index(fields=["-created_at"])`: Powers global admin note feed ordered chronologically.
  - Indexed `status` and `priority` for query filtering.
- **`Post` Model**:
  - `models.Index(fields=["author", "-created_at"])`: Directly accelerates **Scenario 2** lookup of posts by author.
  - `models.Index(fields=["privacy", "-created_at"])`: Supports public vs. in-app feed retrieval.

### 4. Aggregation Scenarios
- **Scenario 1: Group Users by Interests** (`GET /api/v1/posts/aggregations/group-by-interests/`):
  - Aggregates user profiles by their registered interests array (e.g., `chess`, `reading`).
  - Returns grouped interest objects containing count and user details in an optimized pipeline.
- **Scenario 2: User Posts ($lookup Join)** (`GET /api/v1/posts/user/<int:user_id>/`):
  - Fetches all posts belonging to a specific user with joined author details using a single optimized query (`select_related("author")`), backed by composite index `(author, -created_at)`.

---

## 📡 API Endpoints Overview

### Authentication & Profile (`/auth/`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/auth/register/` | Register unverified account & send 6-digit OTP | Public |
| `POST` | `/auth/verify-otp/` | Verify 6-digit OTP & activate account | Public |
| `POST` | `/auth/resend-otp/` | Regenerate and resend 6-digit OTP | Public |
| `POST` | `/auth/login/` | Obtain JWT token pair (Access + Refresh) | Verified Users |
| `POST` | `/auth/token/refresh/` | Refresh JWT access token | Public |
| `POST` | `/auth/password-reset/request/` | Send 6-digit OTP for password recovery | Public |
| `POST` | `/auth/password-reset/confirm/` | Verify OTP & set new password | Public |
| `GET/PUT` | `/auth/profile/` | Retrieve or update current user profile | Authenticated |
| `GET/POST`| `/auth/admin/users/` | List (paginated) or create users | Admin Only |
| `GET/PUT/DELETE` | `/auth/admin/users/<id>/` | View, update, or remove a specific user | Admin Only |

### Notes Management (`/api/v1/notes/`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/v1/notes/` | List notes (Own notes for users, all for admins) | Authenticated |
| `POST` | `/api/v1/notes/` | Create a note with priority, dates, and status | Authenticated |
| `GET` | `/api/v1/notes/<id>/` | Retrieve specific note details | Owner / Admin |
| `PUT/PATCH` | `/api/v1/notes/<id>/` | Update own note | Owner / Admin |
| `DELETE` | `/api/v1/notes/<id>/` | Delete own note | Owner / Admin |

### Posts & Aggregations (`/api/v1/posts/`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/v1/posts/` | List posts (Public for visitors, in-app for logged-in) | Public / Auth |
| `POST` | `/api/v1/posts/` | Create a post with caption & privacy level | Authenticated |
| `GET` | `/api/v1/posts/<id>/` | Retrieve specific post details | Public / Auth |
| `PUT/PATCH/DELETE` | `/api/v1/posts/<id>/` | Edit or delete a post | Author / Admin |
| `POST` | `/api/v1/posts/<id>/react/` | Toggle reaction on post (`like`, etc.) | Authenticated |
| `GET` | `/api/v1/posts/user/<user_id>/` | **Scenario 2**: Retrieve all posts of a user | Public / Auth |
| `GET` | `/api/v1/posts/aggregations/group-by-interests/` | **Scenario 1**: Group users by interests | Public |

### Documentation & Diagnostics
- **Interactive Swagger UI**: `GET /api/v1/docs/`
- **ReDoc UI**: `GET /api/v1/redoc/`

---

## 🛠️ Local Development Setup

1. **Activate Virtual Environment**:
   ```bash
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and adjust settings as needed:
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   EMAIL_HOST_USER=
   EMAIL_HOST_PASSWORD=
   OTP_EXPIRY_MINUTES=5
   ```

4. **Apply Migrations**:
   ```bash
   python manage.py migrate
   ```

5. **Run Automated Tests**:
   ```bash
   python manage.py test
   ```

6. **Start Development Server**:
   ```bash
   python manage.py runserver
   ```
   Navigate to `http://127.0.0.1:8000/` to view the interactive Swagger documentation.

---

Built with passion by [Arif](https://www.linkedin.com/in/aru01/) 🖤💻


