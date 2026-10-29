# PageTurn Library System

A Flask + MySQL library management system, styled as a responsive library catalog and ready to deploy as a Render web service.

## Features
- Search the catalog by title, author, or ISBN and filter by category.
- Book detail pages and member registration/login.
- Members can request to borrow books and track request status.
- Admin dashboard with summary counts and borrowing status management.
- Add/remove catalog entries.
- MySQL tables are initialized automatically when `app.py` is run locally.
- Starter books are seeded automatically when the `books` table is empty.

## Run locally
1. Install Python 3.10+ and make sure MySQL is running.
2. Create a database, for example:
   ```sql
   CREATE DATABASE library_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. Create and activate a virtual environment, then install dependencies:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Set database environment variables to your MySQL credentials:
   ```bash
   # Windows PowerShell example
   $env:MYSQLHOST="127.0.0.1"
   $env:MYSQLPORT="3306"
   $env:MYSQLUSER="root"
   $env:MYSQLPASSWORD="your-password"
   $env:MYSQLDATABASE="library_system"
   $env:SECRET_KEY="use-a-long-random-secret"
   python app.py
   ```
5. Visit `http://127.0.0.1:5000`.

## Deploy to Render
1. Push this project to a GitHub repository.
2. In Render, create a **Web Service** from the repository. The included `render.yaml` can configure the service.
3. Add the environment variables below in Render. Use credentials from your MySQL provider (such as Aiven, Railway, or another managed MySQL service).
   - `MYSQLHOST`
   - `MYSQLPORT` (usually `3306`, unless your provider specifies otherwise)
   - `MYSQLUSER`
   - `MYSQLPASSWORD`
   - `MYSQLDATABASE`
   - `SECRET_KEY` (Render can generate one)
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`
6. Deploy. `/health` is the health check endpoint.

**Important:** Render's standard web service does not provide a persistent MySQL database automatically. Use an external MySQL provider and ensure its network/firewall settings allow connections from Render. If your provider requires TLS, configure its connection settings accordingly before deploying.

## Create the first admin
Register an account through the website, then run this SQL on your database, replacing the email:
```sql
UPDATE users SET role='admin' WHERE email='your-admin-email@example.com';
```
Sign out and sign back in; the Admin link will appear in the navigation.

## Notes
- Passwords are stored as hashes.
- Change the `SECRET_KEY` before production use.
- The borrowing flow is a simple MVP: admins update requests to Approved, Borrowed, Returned, or Rejected.
- This project is a fresh library-system implementation and does not reuse the original stray-animal rescue app's domain data.
