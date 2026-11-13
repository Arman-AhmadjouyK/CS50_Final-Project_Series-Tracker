CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL
);

-- Copy of the TVmaze data, so we don't ask TVmaze on every page load.
-- id is the TVmaze id of the series.
CREATE TABLE IF NOT EXISTS shows (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT,
    network TEXT,
    image TEXT,
    summary TEXT,
    premiered TEXT,
    ended TEXT,
    total_seasons INTEGER NOT NULL DEFAULT 0,
    aired_seasons INTEGER NOT NULL DEFAULT 0,
    next_season INTEGER,
    next_date TEXT,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seasons (
    show_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    premiere TEXT,
    finale TEXT,
    episodes INTEGER,
    FOREIGN KEY (show_id) REFERENCES shows(id)
);

-- Which user follows which series and how many seasons they have watched
CREATE TABLE IF NOT EXISTS user_shows (
    user_id INTEGER NOT NULL,
    show_id INTEGER NOT NULL,
    watched INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, show_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (show_id) REFERENCES shows(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    show_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    seen INTEGER NOT NULL DEFAULT 0,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
