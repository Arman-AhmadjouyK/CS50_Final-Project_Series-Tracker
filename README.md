# Series Tracker

#### Video Demo: https://youtu.be/bR01piy0bEg

#### Description:

Series Tracker is a web application for people who follow many TV series at the same time and lose track of them. I had this problem myself: I often forgot which season of a series I had stopped at, whether the series had already ended, and whether a new season was coming. Series Tracker answers these questions in one place. A user creates an account, searches for a series, adds it to a personal list and records how many seasons they have watched. For each series, the app shows the status (running or ended), the total number of seasons, how many seasons are still left to watch and, if a new season has been announced, its premiere date and how many days are left until then. When a followed series gets a premiere date for its next season or a new season starts, the user receives a notification inside the app.

The application is written in Python with Flask, uses SQLite as its database and Bootstrap for the basic styling. All information about series comes from the free TVmaze API (https://www.tvmaze.com/api), which is licensed under CC BY-SA 4.0 and credited in the footer of every page.

## How it works

After logging in, the user lands on the dashboard ("My series"). At the top there is a search field. When the user searches for a title, for example "Dark", the app asks TVmaze for matching series and shows the results with poster, year, status and network. Each result has an "Add" button. Below the search field, the user's series are shown as cards. Each card has a coloured border that shows its state at a glance: yellow if there are seasons left to watch, blue if the user is waiting for an announced season, green if the series has ended and everything has been watched. The cards are sorted so that the series that need attention come first. On each card the user can choose how many seasons they have watched and save it. Clicking on a series opens a detail page with a summary and a table of all seasons with their premiere and finale dates.

## Files

**app.py** contains the Flask application and all routes. `register`, `login` and `logout` handle accounts in the same way as in CS50 Finance, with passwords stored as hashes. `index` shows the dashboard, `search` shows the search results, `add` adds a series to the list, `show` displays the detail page, `watched` saves the progress, `remove` deletes a series from the list and `notifications` shows the notifications and marks them as seen. The file also contains `query()`, a small helper that runs one SQL command and returns the rows as a list of dictionaries, similar to `db.execute` from the CS50 library. The most important function is `update_show()`. It downloads a series from TVmaze, saves it in the database and compares the new data with the data that was saved before. If a new season has started or a new premiere date has appeared, it creates a notification for every user who follows that series. The function `describe()` decides which message is shown on each card, for example "2 seasons left to watch" or "Season 3 starts on 09 Dec 2026".

**helpers.py** contains the `login_required` decorator and all communication with TVmaze. All requests go through one function, `tvmaze()`, which returns `None` if TVmaze cannot be reached, so error handling is in one place. `search_series()` and `get_series()` keep only the fields the app needs. `season_info()` counts the seasons that have already started and finds the next season. Because dates are stored as text in the format YYYY-MM-DD, they can be compared as strings.

**schema.sql** creates five tables: `users`, `shows`, `seasons`, `user_shows` and `notifications`.

**templates/** contains the HTML pages: `layout.html` (navigation bar, flash messages and footer), `login.html`, `register.html`, `index.html` (dashboard), `search.html`, `show.html` (detail page) and `notifications.html`.

**static/styles.css** contains my own styles on top of Bootstrap: the dark theme, the coloured borders of the cards and the poster sizes.

**requirements.txt** lists the two packages the app needs: Flask and requests.

## Design decisions

**Only real series can be added.** I did not want users to add titles that do not exist or contain typos. Therefore there is no free text field for adding a series. A series can only be added from the search results, and the server checks the TVmaze id again before saving it.

**No JavaScript.** At first I considered live search suggestions while typing. I decided against it and solved everything with HTML forms and CSS, because I wanted to keep the app simple and fast. Even the confirmation before removing a series works without JavaScript, using the HTML `<details>` element.

**Separate tables for shows and user progress.** The data of a series is the same for every user, but the progress is personal. So `shows` stores each series only once, and `user_shows` connects users with series and stores how many seasons each user has watched. If two users add the same series, there is one row in `shows` and two rows in `user_shows`.

**Caching.** Asking TVmaze on every page load would be slow and could hit its rate limit. Series are saved in the database and refreshed only when the saved data is older than 12 hours, with at most eight series per page load.

**Notifications by comparison.** Notifications are created only when the new data differs from the saved data. This is also why the first user who adds a series does not get a notification: there is nothing to compare yet.

**TVmaze as the only source.** I chose TVmaze because it is free and needs no API key. Its data is entered by users and is sometimes behind official announcements. I decided to show only the data that TVmaze provides instead of letting users enter dates manually, so that the information in the app always comes from one source.

## Limitations and ideas

Series are only refreshed when a user opens the dashboard, so notifications appear the next time the user visits the app. In the future, a scheduled job could refresh all series regularly and send notifications by email. Tracking progress per episode instead of per season would be another useful extension.

## How to run

```
pip install -r requirements.txt
flask run
```

The database `series.db` is created automatically the first time the app starts.

## Acknowledgements

Parts of this project were written with the help of Claude (Anthropic), an AI assistant, which I used for planning, writing and reviewing code, and editing the video. Series data is provided by TVmaze.
