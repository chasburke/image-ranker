DROP TABLE IF EXISTS rankings;

CREATE TABLE rankings (
    image_filename TEXT PRIMARY KEY,
    points INTEGER NOT NULL
);