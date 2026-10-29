import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")

def db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQLHOST", "127.0.0.1"),
        port=int(os.getenv("MYSQLPORT", "3306")),
        user=os.getenv("MYSQLUSER", "root"),
        password=os.getenv("MYSQLPASSWORD", ""),
        database=os.getenv("MYSQLDATABASE", "library_system"),
        connection_timeout=10,
    )

def query_db(sql, params=(), fetch=True):
    conn = db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        result = cur.fetchall() if fetch else None
        if not fetch:
            conn.commit()
        return result
    finally:
        cur.close()
        conn.close()

def init_db():
    conn = db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            email VARCHAR(190) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('member','admin') NOT NULL DEFAULT 'member',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS books (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(220) NOT NULL,
            author VARCHAR(180) NOT NULL,
            category VARCHAR(100) DEFAULT 'General',
            isbn VARCHAR(40) DEFAULT '',
            description TEXT,
            total_copies INT NOT NULL DEFAULT 1,
            available_copies INT NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS borrowings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NOT NULL,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            due_date DATE NULL,
            status ENUM('Pending','Approved','Borrowed','Returned','Rejected') NOT NULL DEFAULT 'Pending',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
        )""")
        conn.commit()
        # Seed starter catalog only when the catalog is empty.
        cur.execute("SELECT COUNT(*) FROM books")
        if cur.fetchone()[0] == 0:
            cur.executemany("""INSERT INTO books
                (title, author, category, isbn, description, total_copies, available_copies)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""", [
                ("The Little Prince", "Antoine de Saint-Exupéry", "Fiction", "9780156012195",
                 "A poetic classic about friendship, love, and seeing with the heart.", 3, 3),
                ("Pride and Prejudice", "Jane Austen", "Classic", "9780141439518",
                 "A classic novel of manners, family, and first impressions.", 2, 2),
                ("Atomic Habits", "James Clear", "Self-help", "9780735211292",
                 "A practical guide to building good habits and breaking bad ones.", 2, 2),
                ("Noli Me Tangere", "José Rizal", "Filipino Literature", "9789710810735",
                 "José Rizal's landmark novel on colonial Philippine society.", 4, 4),
                ("Introduction to Python", "Community Edition", "Technology", "9780000000001",
                 "A beginner-friendly introduction to programming concepts.", 2, 2),
            ])
            conn.commit()
    finally:
        cur.close()
        conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access is required.", "danger")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_globals():
    return {"current_user": session.get("user_name"), "user_role": session.get("role")}

@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql = "SELECT * FROM books WHERE 1=1"
    params = []
    if search:
        sql += " AND (title LIKE %s OR author LIKE %s OR isbn LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like, like])
    if category:
        sql += " AND category = %s"
        params.append(category)
    sql += " ORDER BY title"
    books = query_db(sql, tuple(params))
    categories = query_db("SELECT DISTINCT category FROM books ORDER BY category")
    return render_template("index.html", books=books, categories=categories, q=search, selected_category=category)

@app.route("/book/<int:book_id>")
def book_detail(book_id):
    rows = query_db("SELECT * FROM books WHERE id=%s", (book_id,))
    if not rows:
        flash("Book not found.", "danger")
        return redirect(url_for("index"))
    return render_template("book_detail.html", book=rows[0])

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email, and use a password with at least 8 characters.", "warning")
            return render_template("register.html")
        try:
            query_db("INSERT INTO users (name,email,password_hash) VALUES (%s,%s,%s)",
                     (name, email, generate_password_hash(password)), fetch=False)
            flash("Account created. You can now sign in.", "success")
            return redirect(url_for("login"))
        except Error:
            flash("That email may already be registered, or the database is unavailable.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        rows = query_db("SELECT * FROM users WHERE email=%s", (email,))
        if rows and check_password_hash(rows[0]["password_hash"], password):
            user = rows[0]
            session.update(user_id=user["id"], user_name=user["name"], role=user["role"])
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "my_borrowings"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("index"))

@app.route("/borrow/<int:book_id>", methods=["POST"])
@login_required
def borrow_book(book_id):
    rows = query_db("SELECT * FROM books WHERE id=%s", (book_id,))
    if not rows:
        flash("Book not found.", "danger")
    elif rows[0]["available_copies"] < 1:
        flash("This book is currently unavailable.", "warning")
    else:
        existing = query_db("""SELECT id FROM borrowings
            WHERE user_id=%s AND book_id=%s AND status IN ('Pending','Approved','Borrowed')""",
            (session["user_id"], book_id))
        if existing:
            flash("You already have an active request for this book.", "warning")
        else:
            query_db("INSERT INTO borrowings (user_id,book_id) VALUES (%s,%s)",
                     (session["user_id"], book_id), fetch=False)
            flash("Borrow request submitted. The library admin will review it.", "success")
    return redirect(url_for("book_detail", book_id=book_id))

@app.route("/my-borrowings")
@login_required
def my_borrowings():
    borrowings = query_db("""SELECT br.*, b.title, b.author FROM borrowings br
        JOIN books b ON b.id=br.book_id WHERE br.user_id=%s
        ORDER BY br.requested_at DESC""", (session["user_id"],))
    return render_template("my_borrowings.html", borrowings=borrowings)

@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    stats = {
        "books": query_db("SELECT COUNT(*) AS n FROM books")[0]["n"],
        "members": query_db("SELECT COUNT(*) AS n FROM users WHERE role='member'")[0]["n"],
        "pending": query_db("SELECT COUNT(*) AS n FROM borrowings WHERE status='Pending'")[0]["n"],
        "borrowed": query_db("SELECT COUNT(*) AS n FROM borrowings WHERE status='Borrowed'")[0]["n"],
    }
    borrowings = query_db("""SELECT br.*, u.name AS member_name, b.title AS book_title
        FROM borrowings br JOIN users u ON u.id=br.user_id JOIN books b ON b.id=br.book_id
        ORDER BY br.requested_at DESC LIMIT 30""")
    return render_template("admin.html", stats=stats, borrowings=borrowings)

@app.route("/admin/books", methods=["GET", "POST"])
@login_required
@admin_required
def admin_books():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "General").strip() or "General"
        isbn = request.form.get("isbn", "").strip()
        description = request.form.get("description", "").strip()
        copies = max(1, int(request.form.get("copies", "1") or 1))
        if not title or not author:
            flash("Title and author are required.", "warning")
        else:
            query_db("""INSERT INTO books (title,author,category,isbn,description,total_copies,available_copies)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (title, author, category, isbn, description, copies, copies), fetch=False)
            flash("Book added to the catalog.", "success")
            return redirect(url_for("admin_books"))
    books = query_db("SELECT * FROM books ORDER BY title")
    return render_template("admin_books.html", books=books)

@app.route("/admin/books/<int:book_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_book(book_id):
    try:
        query_db("DELETE FROM books WHERE id=%s", (book_id,), fetch=False)
        flash("Book removed.", "success")
    except Error:
        flash("Could not remove this book because it has borrowing history.", "danger")
    return redirect(url_for("admin_books"))

@app.route("/admin/borrowings/<int:borrowing_id>", methods=["POST"])
@login_required
@admin_required
def update_borrowing(borrowing_id):
    new_status = request.form.get("status")
    allowed = {"Approved", "Borrowed", "Returned", "Rejected"}
    if new_status not in allowed:
        flash("Invalid borrowing status.", "danger")
        return redirect(url_for("admin_dashboard"))
    rows = query_db("SELECT * FROM borrowings WHERE id=%s", (borrowing_id,))
    if not rows:
        flash("Borrowing request not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    old_status = rows[0]["status"]
    book_id = rows[0]["book_id"]
    if new_status == "Borrowed" and old_status != "Borrowed":
        book = query_db("SELECT available_copies FROM books WHERE id=%s", (book_id,))
        if not book or book[0]["available_copies"] < 1:
            flash("No available copies remain.", "warning")
            return redirect(url_for("admin_dashboard"))
        query_db("UPDATE books SET available_copies=available_copies-1 WHERE id=%s", (book_id,), fetch=False)
    if old_status == "Borrowed" and new_status == "Returned":
        query_db("UPDATE books SET available_copies=LEAST(total_copies, available_copies+1) WHERE id=%s",
                 (book_id,), fetch=False)
    query_db("UPDATE borrowings SET status=%s WHERE id=%s", (new_status, borrowing_id), fetch=False)
    flash("Borrowing status updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    try:
        init_db()
    except Error as exc:
        print("Database initialization failed:", exc)
        print("Check MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, and MYSQLDATABASE.")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
