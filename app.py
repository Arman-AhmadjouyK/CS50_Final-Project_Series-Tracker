import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import (days_until, get_series, login_required, nice_date,
                     search_series, season_info)

app = Flask(__name__)

# Change this with an environment variable when the app runs anywhere public
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
app.jinja_env.filters["nice_date"] = nice_date

FOLDER = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(FOLDER, "series.db")


def query(sql, *args):
    """Run one SQL command and return the rows as a list of dicts."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    rows = db.execute(sql, args).fetchall()
    db.commit()
    db.close()
    return [dict(row) for row in rows]


# Create the tables the first time the app starts
with open(os.path.join(FOLDER, "schema.sql")) as file:
    db = sqlite3.connect(DATABASE)
    db.executescript(file.read())
    db.close()


@app.context_processor
def unread_notifications():
    """Number of unread notifications, used by the navbar in layout.html."""
    if session.get("user_id") is None:
        return {"unread": 0}
    rows = query("SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND seen = 0",
                 session["user_id"])
    return {"unread": rows[0]["n"]}


def update_show(show_id):
    """Download a series from TVmaze and save it in the database.

    If the series was already saved before, compare old and new data and
    notify everyone who follows it about a new season or a new date.
    Returns False if TVmaze doesn't know the series.
    """
    series = get_series(show_id)
    if series is None:
        return False

    info = season_info(series["seasons"])
    old = query("SELECT * FROM shows WHERE id = ?", show_id)

    query("""INSERT OR REPLACE INTO shows
             (id, name, status, network, image, summary, premiered, ended,
              total_seasons, aired_seasons, next_season, next_date, updated)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
          series["id"], series["name"], series["status"], series["network"],
          series["image"], series["summary"], series["premiered"], series["ended"],
          info["total"], info["aired"], info["next_season"], info["next_date"])

    query("DELETE FROM seasons WHERE show_id = ?", show_id)
    for season in series["seasons"]:
        query("INSERT INTO seasons (show_id, number, premiere, finale, episodes) VALUES (?, ?, ?, ?, ?)",
              show_id, season["number"], season["premiere"], season["finale"], season["episodes"])

    if old:
        old = old[0]
        messages = []
        if info["aired"] > old["aired_seasons"]:
            messages.append(f"Season {info['latest']} of {series['name']} is out now!")
        if info["next_date"] and info["next_date"] != old["next_date"]:
            messages.append(f"Season {info['next_season']} of {series['name']} "
                            f"starts on {nice_date(info['next_date'])}.")

        for follower in query("SELECT user_id FROM user_shows WHERE show_id = ?", show_id):
            for message in messages:
                query("INSERT INTO notifications (user_id, show_id, message) VALUES (?, ?, ?)",
                      follower["user_id"], show_id, message)

    return True


def describe(show):
    """Work out what the user should see for one of their series."""
    show["watched"] = min(show["watched"], show["aired_seasons"])
    left = show["aired_seasons"] - show["watched"]

    if left > 0:
        show["state"] = "watch"
        show["message"] = f"{left} season{'s' if left > 1 else ''} left to watch"
    elif show["next_season"] and show["next_date"]:
        show["state"] = "waiting"
        show["message"] = f"Season {show['next_season']} starts on {nice_date(show['next_date'])}"
    elif show["next_season"]:
        show["state"] = "waiting"
        show["message"] = f"Season {show['next_season']} is announced, no date yet"
    elif show["status"] == "Ended":
        show["state"] = "done"
        show["message"] = "Finished, the series has ended"
    else:
        show["state"] = "uptodate"
        show["message"] = "Up to date, no news about a new season"

    show["days_left"] = days_until(show["next_date"])
    if show["aired_seasons"] > 0:
        show["percent"] = round(show["watched"] / show["aired_seasons"] * 100)
    else:
        show["percent"] = 0
    return show


@app.route("/")
@login_required
def index():
    """Show the user's series"""
    user_id = session["user_id"]

    # Refresh series that were last updated more than 12 hours ago
    old_shows = query("""SELECT shows.id FROM shows
                         JOIN user_shows ON user_shows.show_id = shows.id
                         WHERE user_shows.user_id = ?
                         AND shows.updated < datetime('now', '-12 hours')
                         LIMIT 8""", user_id)
    for row in old_shows:
        update_show(row["id"])

    rows = query("""SELECT shows.*, user_shows.watched FROM shows
                    JOIN user_shows ON user_shows.show_id = shows.id
                    WHERE user_shows.user_id = ?""", user_id)
    shows = [describe(row) for row in rows]

    # Series with seasons left to watch first, then the ones with a date coming up
    order = {"watch": 0, "waiting": 1, "uptodate": 2, "done": 3}
    shows.sort(key=lambda s: (order[s["state"]], s["next_date"] or "9999", s["name"]))

    return render_template("index.html", shows=shows)


@app.route("/search")
@login_required
def search():
    """Search TVmaze and show the results with an add button"""
    q = request.args.get("q", "").strip()
    if not q:
        return redirect("/")

    results = search_series(q)
    if results is None:
        flash("Could not reach TVmaze, please try again.", "danger")
        return redirect("/")

    rows = query("SELECT show_id FROM user_shows WHERE user_id = ?", session["user_id"])
    following = [row["show_id"] for row in rows]

    return render_template("search.html", q=q, results=results, following=following)


@app.route("/add", methods=["POST"])
@login_required
def add():
    """Add a series to the user's list"""
    show_id = request.form.get("show_id", "")
    if not show_id.isdigit():
        flash("Please choose a series from the search results.", "warning")
        return redirect("/")
    show_id = int(show_id)

    # The id has to belong to a real series on TVmaze
    if not query("SELECT id FROM shows WHERE id = ?", show_id):
        if not update_show(show_id):
            flash("This series could not be found on TVmaze.", "danger")
            return redirect("/")

    name = query("SELECT name FROM shows WHERE id = ?", show_id)[0]["name"]
    if query("SELECT * FROM user_shows WHERE user_id = ? AND show_id = ?", session["user_id"], show_id):
        flash(f"{name} is already in your list.", "info")
    else:
        query("INSERT INTO user_shows (user_id, show_id) VALUES (?, ?)", session["user_id"], show_id)
        flash(f"{name} was added to your list.", "success")
    return redirect("/")


@app.route("/show/<int:show_id>")
@login_required
def show(show_id):
    """Details and all seasons of one series"""
    rows = query("""SELECT shows.*, user_shows.watched FROM shows
                    JOIN user_shows ON user_shows.show_id = shows.id
                    WHERE user_shows.user_id = ? AND shows.id = ?""",
                 session["user_id"], show_id)
    if not rows:
        flash("This series is not in your list.", "warning")
        return redirect("/")

    series = describe(rows[0])
    seasons = query("SELECT * FROM seasons WHERE show_id = ? ORDER BY number", show_id)

    # The first `watched` seasons are the ones the user has seen
    for i, season in enumerate(seasons):
        if i < series["watched"]:
            season["label"], season["color"] = "Watched", "success"
        elif i < series["aired_seasons"]:
            season["label"], season["color"] = "Not watched yet", "warning"
        elif season["premiere"]:
            season["label"], season["color"] = "Coming soon", "info"
        else:
            season["label"], season["color"] = "Date TBA", "secondary"

    return render_template("show.html", show=series, seasons=seasons)


@app.route("/watched", methods=["POST"])
@login_required
def watched():
    """Save how many seasons the user has watched"""
    show_id = request.form.get("show_id", "")
    seasons = request.form.get("seasons", "")
    if not show_id.isdigit() or not seasons.isdigit():
        flash("Invalid input.", "danger")
        return redirect("/")

    # Nobody can watch more seasons than have aired
    rows = query("SELECT aired_seasons FROM shows WHERE id = ?", int(show_id))
    if rows:
        seasons = min(int(seasons), rows[0]["aired_seasons"])
        query("UPDATE user_shows SET watched = ? WHERE user_id = ? AND show_id = ?",
              seasons, session["user_id"], int(show_id))
        flash("Progress saved.", "success")

    # Go back to the detail page if the form was sent from there
    if request.form.get("back") == "show":
        return redirect(f"/show/{show_id}")
    return redirect("/")


@app.route("/remove", methods=["POST"])
@login_required
def remove():
    """Remove a series from the user's list"""
    show_id = request.form.get("show_id")
    query("DELETE FROM user_shows WHERE user_id = ? AND show_id = ?", session["user_id"], show_id)
    query("DELETE FROM notifications WHERE user_id = ? AND show_id = ?", session["user_id"], show_id)
    flash("Series removed from your list.", "info")
    return redirect("/")


@app.route("/notifications")
@login_required
def notifications():
    """Show all notifications, then mark them as seen"""
    items = query("SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 50",
                  session["user_id"])
    query("UPDATE notifications SET seen = 1 WHERE user_id = ?", session["user_id"])
    return render_template("notifications.html", items=items)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username:
        flash("Please enter a username.", "danger")
    elif len(password) < 8:
        flash("The password needs at least 8 characters.", "danger")
    elif password != request.form.get("confirmation"):
        flash("The passwords don't match.", "danger")
    elif query("SELECT id FROM users WHERE username = ?", username):
        flash("This username is already taken.", "danger")
    else:
        query("INSERT INTO users (username, hash) VALUES (?, ?)",
              username, generate_password_hash(password))
        session.clear()
        session["user_id"] = query("SELECT id FROM users WHERE username = ?", username)[0]["id"]
        session["username"] = username
        flash("Welcome! Search for a series to get started.", "success")
        return redirect("/")

    return render_template("register.html", username=username), 400


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    rows = query("SELECT * FROM users WHERE username = ?", username)

    if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password", "")):
        flash("Wrong username or password.", "danger")
        return render_template("login.html", username=username), 400

    session["user_id"] = rows[0]["id"]
    session["username"] = rows[0]["username"]
    return redirect("/")


@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/login")
