-- Database schema for the chat application

CREATE TABLE users (
    username TEXT PRIMARY KEY,
    connected_at DATETIME
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME,
    sender TEXT,
    receiver TEXT,
    content TEXT
);
