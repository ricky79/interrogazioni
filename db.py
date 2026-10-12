import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS materie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    creata_il TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS date_interrogazione (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    materia_id INTEGER NOT NULL REFERENCES materie(id) ON DELETE CASCADE,
    giorno TEXT NOT NULL,
    UNIQUE (materia_id, giorno)
);
CREATE TABLE IF NOT EXISTS studenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    materia_id INTEGER NOT NULL REFERENCES materie(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    data_id INTEGER REFERENCES date_interrogazione(id) ON DELETE SET NULL,
    ordine INTEGER
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        get_db().executescript(SCHEMA)
    app.teardown_appcontext(close_db)
