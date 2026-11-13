import html
import re
from datetime import date
from functools import wraps

import requests
from flask import redirect, session

API_URL = "https://api.tvmaze.com"


def login_required(f):
    """Decorate routes to require login."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def tvmaze(path, params=None):
    """Ask the TVmaze API, return the JSON answer or None on error."""
    try:
        response = requests.get(API_URL + path, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def channel(show):
    """TV network or streaming service of a show."""
    if show.get("network"):
        return show["network"]["name"]
    if show.get("webChannel"):
        return show["webChannel"]["name"]
    return None


def search_series(name):
    """Return a list of series that match name, or None if TVmaze can't be reached."""
    results = tvmaze("/search/shows", {"q": name})
    if results is None:
        return None

    series = []
    for result in results:
        show = result["show"]
        series.append({
            "id": show["id"],
            "name": show["name"],
            "year": (show.get("premiered") or "")[:4],
            "status": show.get("status"),
            "network": channel(show),
            "image": (show.get("image") or {}).get("medium"),
        })
    return series


def get_series(show_id):
    """Return one series with all its seasons, or None."""
    show = tvmaze(f"/shows/{show_id}", {"embed": "seasons"})
    if show is None:
        return None

    seasons = []
    for season in show["_embedded"]["seasons"]:
        seasons.append({
            "number": season["number"],
            "premiere": season.get("premiereDate"),
            "finale": season.get("endDate"),
            "episodes": season.get("episodeOrder"),
        })

    # TVmaze sends the summary as HTML, we only want the text
    summary = html.unescape(re.sub("<[^>]*>", "", show.get("summary") or ""))

    return {
        "id": show["id"],
        "name": show["name"],
        "status": show.get("status"),
        "network": channel(show),
        "image": (show.get("image") or {}).get("medium"),
        "summary": summary,
        "premiered": show.get("premiered"),
        "ended": show.get("ended"),
        "seasons": seasons,
    }


def season_info(seasons):
    """Count the seasons that already started and find the next one.

    Dates look like "2026-11-07", so they can be compared as strings.
    """
    today = date.today().isoformat()
    info = {"total": len(seasons), "aired": 0, "latest": None,
            "next_season": None, "next_date": None}

    for season in sorted(seasons, key=lambda s: s["number"]):
        if season["premiere"] and season["premiere"] <= today:
            info["aired"] += 1
            info["latest"] = season["number"]
        elif info["next_season"] is None:
            # first season that hasn't started yet (date can be unknown)
            info["next_season"] = season["number"]
            info["next_date"] = season["premiere"]

    return info


def nice_date(value):
    """Format "2027-03-14" as "14 Mar 2027"."""
    if not value:
        return "TBA"
    return date.fromisoformat(value).strftime("%d %b %Y")


def days_until(value):
    """Number of days from today until a date."""
    if not value:
        return None
    return (date.fromisoformat(value) - date.today()).days
