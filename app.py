"""
Personal Fashion Stylist - Flask Application
Auth flow: Registration (hashed passwords) → Login (sessions) → Dashboard.
Profile: body info + photo analysis (OpenCV/MediaPipe) + occasion selection.
"""

import os
import re
from functools import wraps

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    flash,
)
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from db_config import DB_CONFIG
from analysis import analyze_photo
from recommender import get_recommendations, COLOUR_HEX
from seed_data import seed_outfits

app = Flask(__name__)
app.secret_key = "fashion-stylist-secret-key-change-in-production"

# --------------- upload & analysis config ---------------
UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static", "uploads"
)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

BODY_TYPES = ["Hourglass", "Pear", "Apple", "Rectangle", "Inverted Triangle"]
SKIN_TONES = ["Fair", "Light", "Medium", "Olive", "Tan", "Deep"]
OCCASIONS = [
    {"value": "Casual",         "icon": "👕", "label": "Casual"},
    {"value": "Formal",         "icon": "👔", "label": "Formal / Business"},
    {"value": "Party",          "icon": "🎉", "label": "Party / Nightlife"},
    {"value": "Ethnic",         "icon": "👘", "label": "Ethnic / Traditional"},
    {"value": "Streetwear",     "icon": "🏙️", "label": "Streetwear"},
    {"value": "Sports",         "icon": "🏃", "label": "Sports / Active"},
    {"value": "Date Night",     "icon": "💕", "label": "Date Night"},
    {"value": "Wedding",        "icon": "💒", "label": "Wedding / Reception"},
    {"value": "Travel",         "icon": "✈️", "label": "Travel"},
    {"value": "Work From Home", "icon": "🏠", "label": "Work From Home"},
]


# --------------- database helper ---------------
def get_db():
    """Return a new MySQL connection using the shared config."""
    return mysql.connector.connect(**DB_CONFIG)


# --------------- auto-migration ---------------
def _run_migrations():
    """Silently add any missing columns/tables."""
    alter_stmts = [
        "ALTER TABLE profiles ADD COLUMN favourite_colour VARCHAR(50) AFTER skin_tone",
        "ALTER TABLE profiles ADD COLUMN occasion VARCHAR(255) AFTER style_pref",
        "ALTER TABLE outfits ADD COLUMN suitable_body_types VARCHAR(255) AFTER gender_target",
        "ALTER TABLE outfits ADD COLUMN suitable_skin_tones VARCHAR(255) AFTER suitable_body_types",
        "ALTER TABLE outfits ADD COLUMN colour VARCHAR(50) AFTER suitable_skin_tones",
        "ALTER TABLE feedback ADD COLUMN outfit_id INT AFTER user_id",
        "ALTER TABLE feedback MODIFY COLUMN rec_id INT DEFAULT NULL",
    ]
    try:
        conn = get_db()
        cur = conn.cursor()
        for sql in alter_stmts:
            try:
                cur.execute(sql)
            except mysql.connector.Error:
                pass  # column already exists

        # Create admins table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                admin_id      INT AUTO_INCREMENT PRIMARY KEY,
                username      VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)

        # Seed default admin account (admin / admin123)
        cur.execute("SELECT admin_id FROM admins LIMIT 1")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                ("admin", generate_password_hash("admin123")),
            )

        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass  # DB might not be reachable at import time


_run_migrations()
seed_outfits(get_db)  # populate outfits table on first run


# --------------- auth decorators ---------------
def login_required(f):
    """Redirect to login page if the user is not authenticated."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access that page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """Redirect to admin login if the admin is not authenticated."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            flash("Please log in as admin.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return decorated


# --------------- validation helpers ---------------
def validate_registration(username, email, password, confirm):
    """Return a list of error strings (empty = valid)."""
    errors = []
    if not username or len(username.strip()) < 3:
        errors.append("Username must be at least 3 characters.")
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("Please enter a valid email address.")
    if not password or len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if password != confirm:
        errors.append("Passwords do not match.")
    return errors


def validate_profile(gender, age, height_cm, weight_kg):
    """Return a list of error strings for the profile form."""
    errors = []
    valid_genders = {"Male", "Female", "Non-Binary", "Other"}
    if gender and gender not in valid_genders:
        errors.append("Please select a valid gender.")
    if age:
        try:
            a = int(age)
            if a < 1 or a > 120:
                errors.append("Age must be between 1 and 120.")
        except (ValueError, TypeError):
            errors.append("Age must be a valid number.")
    if height_cm:
        try:
            h = float(height_cm)
            if h < 50 or h > 300:
                errors.append("Height must be between 50 and 300 cm.")
        except (ValueError, TypeError):
            errors.append("Height must be a valid number.")
    if weight_kg:
        try:
            w = float(weight_kg)
            if w < 10 or w > 500:
                errors.append("Weight must be between 10 and 500 kg.")
        except (ValueError, TypeError):
            errors.append("Weight must be a valid number.")
    return errors


def allowed_file(filename):
    """Check whether a filename has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ===================== ROUTES =====================

# --------------- home ---------------
@app.route("/")
def home():
    """Public landing page."""
    return render_template("home.html")


# --------------- register ---------------
@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration with hashing + validation."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        # Validate
        errors = validate_registration(username, email, password, confirm)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", username=username, email=email)

        # Check for duplicate username / email
        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT user_id FROM users WHERE username = %s OR email = %s",
                (username, email),
            )
            if cursor.fetchone():
                flash("Username or email already exists.", "danger")
                cursor.close()
                conn.close()
                return render_template("register.html", username=username, email=email)

            # Insert new user
            hashed = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email, hashed),
            )
            conn.commit()
            cursor.close()
            conn.close()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
            return render_template("register.html", username=username, email=email)

    return render_template("register.html")


# --------------- login ---------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """Session-based login."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please fill in all fields.", "danger")
            return render_template("login.html", email=email)

        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and check_password_hash(user["password_hash"], password):
                session["user_id"] = user["user_id"]
                session["username"] = user["username"]
                flash(f"Welcome back, {user['username']}!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password.", "danger")
                return render_template("login.html", email=email)

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
            return render_template("login.html", email=email)

    return render_template("login.html")


# --------------- logout ---------------
@app.route("/logout")
def logout():
    """Clear the session and redirect to home."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# --------------- dashboard (protected) ---------------
@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard shell — only accessible when logged in."""
    profile = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM profiles WHERE user_id = %s", (session["user_id"],)
        )
        profile = cursor.fetchone()
        cursor.close()
        conn.close()
    except mysql.connector.Error:
        pass

    profile_complete = bool(
        profile
        and profile.get("gender")
        and profile.get("body_type")
        and profile.get("occasion")
    )

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        profile=profile,
        profile_complete=profile_complete,
    )


# --------------- profile (protected) ---------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Create / edit body-info profile."""
    if request.method == "POST":
        gender = request.form.get("gender", "").strip()
        age = request.form.get("age", "").strip()
        height_cm = request.form.get("height_cm", "").strip()
        weight_kg = request.form.get("weight_kg", "").strip()
        body_type = request.form.get("body_type", "").strip()
        skin_tone = request.form.get("skin_tone", "").strip()
        favourite_colour = request.form.get("favourite_colour", "").strip()

        errors = validate_profile(gender, age, height_cm, weight_kg)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "profile.html",
                profile={
                    "gender": gender,
                    "age": age,
                    "height_cm": height_cm,
                    "weight_kg": weight_kg,
                    "body_type": body_type,
                    "skin_tone": skin_tone,
                    "favourite_colour": favourite_colour,
                },
            )

        age_val = int(age) if age else None
        height_val = float(height_cm) if height_cm else None
        weight_val = float(weight_kg) if weight_kg else None

        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT profile_id FROM profiles WHERE user_id = %s",
                (session["user_id"],),
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """UPDATE profiles
                       SET gender=%s, age=%s, height_cm=%s, weight_kg=%s,
                           body_type=%s, skin_tone=%s, favourite_colour=%s
                     WHERE user_id=%s""",
                    (
                        gender or None,
                        age_val,
                        height_val,
                        weight_val,
                        body_type or None,
                        skin_tone or None,
                        favourite_colour or None,
                        session["user_id"],
                    ),
                )
            else:
                cursor.execute(
                    """INSERT INTO profiles
                       (user_id, gender, age, height_cm, weight_kg,
                        body_type, skin_tone, favourite_colour)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        session["user_id"],
                        gender or None,
                        age_val,
                        height_val,
                        weight_val,
                        body_type or None,
                        skin_tone or None,
                        favourite_colour or None,
                    ),
                )

            conn.commit()
            cursor.close()
            conn.close()

            flash("Profile saved!", "success")
            return redirect(url_for("upload_photo"))

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
            return render_template(
                "profile.html",
                profile={
                    "gender": gender,
                    "age": age,
                    "height_cm": height_cm,
                    "weight_kg": weight_kg,
                    "body_type": body_type,
                    "skin_tone": skin_tone,
                    "favourite_colour": favourite_colour,
                },
            )

    # GET — load existing profile
    prof = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM profiles WHERE user_id = %s", (session["user_id"],)
        )
        prof = cursor.fetchone()
        cursor.close()
        conn.close()
    except mysql.connector.Error:
        pass

    return render_template("profile.html", profile=prof)


# --------------- upload photo (protected) ---------------
@app.route("/upload-photo", methods=["GET", "POST"])
@login_required
def upload_photo():
    """Photo upload with OpenCV / MediaPipe analysis (fallback to manual)."""
    if request.method == "POST":
        step = request.form.get("step", "upload")

        # ── Step 1: upload & analyse ──
        if step == "upload":
            file = request.files.get("photo")
            if not file or file.filename == "":
                flash("Please select a photo to upload.", "danger")
                return render_template("upload_photo.html")

            if not allowed_file(file.filename):
                flash("Unsupported file type. Use JPEG, PNG, or WebP.", "danger")
                return render_template("upload_photo.html")

            filename = secure_filename(f"{session['user_id']}_{file.filename}")
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            try:
                file.save(filepath)
            except Exception as exc:
                flash(f"Could not save file: {exc}", "danger")
                return render_template("upload_photo.html")

            # Run CV analysis (never crashes — errors returned in dict)
            analysis = analyze_photo(filepath)

            # Stash filename in session for the save step
            session["_photo_filename"] = filename

            return render_template(
                "upload_photo.html",
                show_results=True,
                analysis=analysis,
                photo_url=url_for("static", filename=f"uploads/{filename}"),
                body_types=BODY_TYPES,
                skin_tones=SKIN_TONES,
            )

        # ── Step 2: save confirmed / overridden values ──
        if step == "save":
            body_type = request.form.get("body_type", "").strip() or None
            skin_tone = request.form.get("skin_tone", "").strip() or None
            photo_filename = session.pop("_photo_filename", None)

            try:
                conn = get_db()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT profile_id FROM profiles WHERE user_id = %s",
                    (session["user_id"],),
                )
                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        """UPDATE profiles
                           SET body_type = %s, skin_tone = %s, profile_pic = %s
                         WHERE user_id = %s""",
                        (body_type, skin_tone, photo_filename, session["user_id"]),
                    )
                else:
                    cursor.execute(
                        """INSERT INTO profiles
                           (user_id, body_type, skin_tone, profile_pic)
                           VALUES (%s, %s, %s, %s)""",
                        (session["user_id"], body_type, skin_tone, photo_filename),
                    )

                conn.commit()
                cursor.close()
                conn.close()

                flash("Photo analysis saved!", "success")
                return redirect(url_for("occasion"))

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")
                return redirect(url_for("upload_photo"))

    return render_template("upload_photo.html")


# --------------- occasion selection (protected) ---------------
@app.route("/occasion", methods=["GET", "POST"])
@login_required
def occasion():
    """Select the occasions you dress for."""
    if request.method == "POST":
        selected = request.form.getlist("occasions")
        occasion_str = ", ".join(selected) if selected else None

        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT profile_id FROM profiles WHERE user_id = %s",
                (session["user_id"],),
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    "UPDATE profiles SET occasion = %s WHERE user_id = %s",
                    (occasion_str, session["user_id"]),
                )
            else:
                cursor.execute(
                    "INSERT INTO profiles (user_id, occasion) VALUES (%s, %s)",
                    (session["user_id"], occasion_str),
                )

            conn.commit()
            cursor.close()
            conn.close()

            flash(
                "Occasion preferences saved! Your profile setup is complete. 🎉",
                "success",
            )
            return redirect(url_for("dashboard"))

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")

    # GET — load saved occasions
    saved = []
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT occasion FROM profiles WHERE user_id = %s", (session["user_id"],)
        )
        row = cursor.fetchone()
        if row and row.get("occasion"):
            saved = [o.strip() for o in row["occasion"].split(",")]
        cursor.close()
        conn.close()
    except mysql.connector.Error:
        pass

    return render_template("occasion.html", occasions=OCCASIONS, saved=saved)


# --------------- recommendations (protected) ---------------
@app.route("/recommendations")
@login_required
def recommendations():
    """Show outfit recommendations scored against the user's profile."""
    profile = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM profiles WHERE user_id = %s", (session["user_id"],)
        )
        profile = cursor.fetchone()
        cursor.close()
        conn.close()
    except mysql.connector.Error:
        pass

    if not profile or not profile.get("body_type"):
        flash("Please complete your profile first to get recommendations.", "warning")
        return redirect(url_for("profile"))

    # Load all outfits and user's favourites
    outfits = []
    fav_ids = set()
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM outfits")
        outfits = cursor.fetchall()
        cursor.execute(
            "SELECT outfit_id FROM favourites WHERE user_id = %s",
            (session["user_id"],),
        )
        fav_ids = {row["outfit_id"] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    # Score and rank
    results = get_recommendations(outfits, profile)

    return render_template(
        "recommendations.html",
        profile=profile,
        results=results,
        colour_hex_map=COLOUR_HEX,
        fav_ids=fav_ids,
    )


# --------------- toggle favourite (protected) ---------------
@app.route("/toggle-favourite", methods=["POST"])
@login_required
def toggle_favourite():
    """Add or remove an outfit from favourites."""
    outfit_id = request.form.get("outfit_id", type=int)
    redirect_to = request.form.get("redirect_to", "favourites")

    if not outfit_id:
        flash("Invalid outfit.", "danger")
        return redirect(url_for("recommendations"))

    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT fav_id FROM favourites WHERE user_id = %s AND outfit_id = %s",
            (session["user_id"], outfit_id),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "DELETE FROM favourites WHERE user_id = %s AND outfit_id = %s",
                (session["user_id"], outfit_id),
            )
            flash("Removed from favourites.", "info")
        else:
            cursor.execute(
                "INSERT INTO favourites (user_id, outfit_id) VALUES (%s, %s)",
                (session["user_id"], outfit_id),
            )
            flash("Saved to favourites!", "success")

        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    if redirect_to == "recommendations":
        return redirect(url_for("recommendations"))
    return redirect(url_for("favourites_page"))


# --------------- favourites page (protected) ---------------
@app.route("/favourites")
@login_required
def favourites_page():
    """Show user's saved outfits with feedback forms."""
    favourites = []
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT o.*, f.saved_at,
                      fb.rating AS feedback_rating,
                      fb.comment AS feedback_comment
               FROM favourites f
               JOIN outfits o ON o.outfit_id = f.outfit_id
               LEFT JOIN feedback fb
                    ON fb.user_id = f.user_id AND fb.outfit_id = f.outfit_id
              WHERE f.user_id = %s
              ORDER BY f.saved_at DESC""",
            (session["user_id"],),
        )
        favourites = cursor.fetchall()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    return render_template(
        "favourites.html",
        favourites=favourites,
        colour_hex_map=COLOUR_HEX,
    )


# --------------- submit feedback (protected) ---------------
@app.route("/feedback", methods=["POST"])
@login_required
def submit_feedback():
    """Store a rating (1-5) and optional comment for an outfit."""
    outfit_id = request.form.get("outfit_id", type=int)
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip() or None

    if not outfit_id or not rating or rating < 1 or rating > 5:
        flash("Please provide a valid rating (1-5).", "danger")
        return redirect(url_for("favourites_page"))

    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Upsert: update if feedback already exists
        cursor.execute(
            "SELECT feedback_id FROM feedback WHERE user_id = %s AND outfit_id = %s",
            (session["user_id"], outfit_id),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "UPDATE feedback SET rating = %s, comment = %s WHERE feedback_id = %s",
                (rating, comment, existing["feedback_id"]),
            )
        else:
            cursor.execute(
                "INSERT INTO feedback (user_id, outfit_id, rating, comment) VALUES (%s, %s, %s, %s)",
                (session["user_id"], outfit_id, rating, comment),
            )

        conn.commit()
        cursor.close()
        conn.close()

        flash("Thanks for your feedback!", "success")
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    return redirect(url_for("favourites_page"))


# ===================== ADMIN PANEL =====================

# --------------- admin login ---------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Separate admin authentication."""
    if "admin_id" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please fill in all fields.", "danger")
            return render_template("admin_login.html", username=username)

        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
            admin = cursor.fetchone()
            cursor.close()
            conn.close()

            if admin and check_password_hash(admin["password_hash"], password):
                session["admin_id"] = admin["admin_id"]
                session["admin_username"] = admin["username"]
                flash(f"Welcome, {admin['username']}!", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid admin credentials.", "danger")
                return render_template("admin_login.html", username=username)

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
            return render_template("admin_login.html", username=username)

    return render_template("admin_login.html")


# --------------- admin logout ---------------
@app.route("/admin/logout")
def admin_logout():
    """Clear admin session keys and redirect to admin login."""
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("admin_login"))


# --------------- admin dashboard ---------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    """Admin overview with counts."""
    counts = {"users": 0, "outfits": 0, "feedback": 0}
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        counts["users"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM outfits")
        counts["outfits"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM feedback")
        counts["feedback"] = cursor.fetchone()[0]
        cursor.close()
        conn.close()
    except mysql.connector.Error:
        pass

    return render_template("admin_dashboard.html", counts=counts)


# --------------- admin: manage users ---------------
@app.route("/admin/users")
@admin_required
def admin_users():
    """List all registered users."""
    users = []
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.user_id, u.username, u.email, u.created_at,
                   p.gender, p.body_type, p.skin_tone, p.occasion
              FROM users u
              LEFT JOIN profiles p ON p.user_id = u.user_id
             ORDER BY u.created_at DESC
        """)
        users = cursor.fetchall()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    return render_template("admin_users.html", users=users)


# --------------- admin: manage outfits ---------------
@app.route("/admin/outfits")
@admin_required
def admin_outfits():
    """List all outfits."""
    outfits = []
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM outfits ORDER BY outfit_id DESC")
        outfits = cursor.fetchall()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    return render_template("admin_outfits.html", outfits=outfits, colour_hex_map=COLOUR_HEX)


# --------------- admin: add outfit ---------------
@app.route("/admin/outfits/add", methods=["GET", "POST"])
@admin_required
def admin_outfit_add():
    """Create a new outfit."""
    if request.method == "POST":
        data = {
            "outfit_name": request.form.get("outfit_name", "").strip(),
            "category": request.form.get("category", "").strip(),
            "season": request.form.get("season", "").strip(),
            "gender_target": request.form.get("gender_target", "").strip(),
            "suitable_body_types": request.form.get("suitable_body_types", "").strip(),
            "suitable_skin_tones": request.form.get("suitable_skin_tones", "").strip(),
            "colour": request.form.get("colour", "").strip(),
            "description": request.form.get("description", "").strip(),
        }

        if not data["outfit_name"]:
            flash("Outfit name is required.", "danger")
            return render_template("admin_outfit_form.html", outfit=data, is_edit=False)

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO outfits
                   (outfit_name, category, season, gender_target,
                    suitable_body_types, suitable_skin_tones, colour, description)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    data["outfit_name"], data["category"] or None,
                    data["season"] or None, data["gender_target"] or None,
                    data["suitable_body_types"] or None,
                    data["suitable_skin_tones"] or None,
                    data["colour"] or None, data["description"] or None,
                ),
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Outfit added successfully!", "success")
            return redirect(url_for("admin_outfits"))
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
            return render_template("admin_outfit_form.html", outfit=data, is_edit=False)

    return render_template("admin_outfit_form.html", outfit={}, is_edit=False)


# --------------- admin: edit outfit ---------------
@app.route("/admin/outfits/edit/<int:outfit_id>", methods=["GET", "POST"])
@admin_required
def admin_outfit_edit(outfit_id):
    """Edit an existing outfit."""
    if request.method == "POST":
        data = {
            "outfit_name": request.form.get("outfit_name", "").strip(),
            "category": request.form.get("category", "").strip(),
            "season": request.form.get("season", "").strip(),
            "gender_target": request.form.get("gender_target", "").strip(),
            "suitable_body_types": request.form.get("suitable_body_types", "").strip(),
            "suitable_skin_tones": request.form.get("suitable_skin_tones", "").strip(),
            "colour": request.form.get("colour", "").strip(),
            "description": request.form.get("description", "").strip(),
        }

        if not data["outfit_name"]:
            flash("Outfit name is required.", "danger")
            data["outfit_id"] = outfit_id
            return render_template("admin_outfit_form.html", outfit=data, is_edit=True)

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE outfits
                   SET outfit_name=%s, category=%s, season=%s, gender_target=%s,
                       suitable_body_types=%s, suitable_skin_tones=%s,
                       colour=%s, description=%s
                 WHERE outfit_id=%s""",
                (
                    data["outfit_name"], data["category"] or None,
                    data["season"] or None, data["gender_target"] or None,
                    data["suitable_body_types"] or None,
                    data["suitable_skin_tones"] or None,
                    data["colour"] or None, data["description"] or None,
                    outfit_id,
                ),
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Outfit updated successfully!", "success")
            return redirect(url_for("admin_outfits"))
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
            data["outfit_id"] = outfit_id
            return render_template("admin_outfit_form.html", outfit=data, is_edit=True)

    # GET — load outfit
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM outfits WHERE outfit_id = %s", (outfit_id,))
        outfit = cursor.fetchone()
        cursor.close()
        conn.close()
        if not outfit:
            flash("Outfit not found.", "danger")
            return redirect(url_for("admin_outfits"))
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        return redirect(url_for("admin_outfits"))

    return render_template("admin_outfit_form.html", outfit=outfit, is_edit=True)


# --------------- admin: delete outfit ---------------
@app.route("/admin/outfits/delete/<int:outfit_id>", methods=["POST"])
@admin_required
def admin_outfit_delete(outfit_id):
    """Delete an outfit."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM outfits WHERE outfit_id = %s", (outfit_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Outfit deleted.", "info")
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    return redirect(url_for("admin_outfits"))


# --------------- admin: view feedback ---------------
@app.route("/admin/feedback")
@admin_required
def admin_feedback():
    """View all feedback with user and outfit context."""
    feedbacks = []
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT fb.feedback_id, fb.rating, fb.comment, fb.created_at,
                   u.username, u.email,
                   o.outfit_name, o.category, o.colour
              FROM feedback fb
              JOIN users u   ON u.user_id = fb.user_id
              LEFT JOIN outfits o ON o.outfit_id = fb.outfit_id
             ORDER BY fb.created_at DESC
        """)
        feedbacks = cursor.fetchall()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    return render_template("admin_feedback.html", feedbacks=feedbacks)


# --------------- API endpoints (kept from before) ---------------
@app.route("/health")
def health():
    """Quick health-check endpoint."""
    return jsonify(status="ok", message="All systems operational")


@app.route("/db-check")
def db_check():
    """Verify MySQL connection and list all tables in fashion_db."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify(
            status="connected",
            database=DB_CONFIG["database"],
            tables=tables,
        )
    except mysql.connector.Error as err:
        return jsonify(status="error", message=str(err)), 500


# --------------- error handlers ---------------
@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file uploads that exceed the size limit."""
    flash("File is too large. Maximum upload size is 16 MB.", "danger")
    return redirect(url_for("upload_photo"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
