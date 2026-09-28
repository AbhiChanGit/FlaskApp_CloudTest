# FlaskApp_CloudTest

A small user-registration web app built with **Flask** and **SQLite**, deployed on an **AWS EC2** Ubuntu instance behind **Apache + mod_wsgi**.

**Live site:** http://ec2-13-58-36-250.us-east-2.compute.amazonaws.com

> Use `http://`, not `https://`. The instance serves port 80 only.

## Features

| Feature | Where |
|---|---|
| Register with a username and password (password stored as a salted scrypt hash) | `/register` |
| Collect and store first name, last name, email, and address | `/register` |
| Redirect after registration to a page that displays the stored details | `/register` → `/profile` |
| Log back in later and retrieve the same details from the database | `/login` → `/profile` |
| Upload a `.txt` file (e.g. `Limerick_1.txt`), store it, and show its word count | `/register`, `/upload` |
| Download the uploaded file | `/download` |
| Log out | `/logout` |

## How it works

```
Browser ──HTTP :80──> AWS Security Group ──> EC2 (Ubuntu 24.04)
                                              └─ Apache
                                                  └─ mod_wsgi (daemon mode, runs as ubuntu)
                                                      └─ Flask app (app.py)
                                                          ├─ users.db   (SQLite)
                                                          └─ uploads/   (stored .txt files)
```

* **Apache** listens on port 80 and hands every request to **mod_wsgi**, which calls the Flask app through `flaskapp.wsgi`.
* **SQLite** stores all user data in a single file, `users.db`, which the app creates on first start.
* After a successful form POST the app redirects to a GET page (Post/Redirect/Get), so refreshing never resubmits a form.
* A signed session cookie keeps the user logged in between requests.
* **Word count** is `len(text.split())`: words separated by any whitespace. Blank lines and double spaces don't inflate the count.

## Project structure

```
FlaskApp_CloudTest/
├── app.py              # Flask app: routes, database, uploads
├── flaskapp.wsgi       # entry point loaded by Apache/mod_wsgi
├── requirements.txt
├── templates/
│   ├── base.html       # shared layout, nav bar, styles, flash messages
│   ├── index.html      # landing page
│   ├── register.html   # registration form + file upload
│   ├── login.html      # login form
│   └── profile.html    # user details, word count, download button
└── (created at runtime, not committed)
    ├── users.db
    └── uploads/
```

## Database schema

```sql
CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    username          TEXT NOT NULL UNIQUE,
    password_hash     TEXT NOT NULL,
    firstname         TEXT NOT NULL,
    lastname          TEXT NOT NULL,
    email             TEXT NOT NULL,
    address           TEXT NOT NULL,
    filename          TEXT,        -- stored name on disk: <username>_<file>.txt
    original_filename TEXT,        -- name shown to the user / used for download
    word_count        INTEGER
);
```

The file columns can be empty because a user may register first and upload a file later from the profile page.

## Security notes

* Passwords are hashed with `werkzeug.security` (scrypt + random salt); plaintext passwords are never stored.
* All SQL uses `?` placeholders, which prevents SQL injection.
* Uploaded file names pass through `secure_filename()`, and only `.txt` files up to 1 MB are accepted.
* Jinja2 auto-escapes every value it renders into a page.
* `users.db`, `uploads/`, and any `.pem` key are excluded by `.gitignore`.

## Run locally

```powershell
py -m pip install -r requirements.txt
py app.py
```

Open http://127.0.0.1:5000.

## Deploy on EC2 (Ubuntu 24.04)

1. Install the server packages:

   ```bash
   sudo apt update
   sudo apt install -y apache2 libapache2-mod-wsgi-py3 python3-pip python3-flask sqlite3
   ```

2. Clone the repo and let Apache traverse the home folder:

   ```bash
   cd ~
   git clone https://github.com/AbhiChanGit/FlaskApp_CloudTest.git
   chmod 755 /home/ubuntu
   ```

3. In `/etc/apache2/sites-enabled/000-default.conf`, below `DocumentRoot /var/www/html`, add:

   ```apache
   WSGIDaemonProcess flaskapp user=ubuntu group=ubuntu threads=5 python-path=/home/ubuntu/FlaskApp_CloudTest
   WSGIScriptAlias / /home/ubuntu/FlaskApp_CloudTest/flaskapp.wsgi

   <Directory /home/ubuntu/FlaskApp_CloudTest>
       WSGIProcessGroup flaskapp
       WSGIApplicationGroup %{GLOBAL}
       Require all granted
   </Directory>
   ```

4. If the Apache error log shows `OSError: [Errno 30] Read-only file system`, the apache2 systemd unit is mounting `/home` read-only. Allow writes to the app folder only:

   ```bash
   sudo mkdir -p /etc/systemd/system/apache2.service.d
   printf '[Service]\nReadWritePaths=/home/ubuntu/FlaskApp_CloudTest\n' | sudo tee /etc/systemd/system/apache2.service.d/flaskapp.conf
   sudo systemctl daemon-reload
   ```

5. Test the config and restart:

   ```bash
   sudo apache2ctl configtest
   sudo systemctl restart apache2
   ```

To deploy later changes: `cd ~/FlaskApp_CloudTest && git pull && sudo systemctl restart apache2`.

Errors show up in `sudo tail -n 30 /var/log/apache2/error.log`.

## Tech stack

AWS EC2 (Ubuntu 24.04, us-east-2) · Apache 2.4 · mod_wsgi · Python 3 · Flask · SQLite 3 · Jinja2
