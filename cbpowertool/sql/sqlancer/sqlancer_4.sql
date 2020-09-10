CREATE TABLE test (c0, c1 TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS index_0 ON test(c1);
CREATE INDEX IF NOT EXISTS index_1 ON test(c0 || FALSE) WHERE c1;
INSERT OR IGNORE INTO test(c0, c1) VALUES (UUID(),{"c0":'a', "c1":TRUE});
INSERT OR IGNORE INTO test(c0, c1) VALUES (UUID(),{"c0":'a', "c1":FALSE});
PRAGMA legacy_file_format=true;
REINDEX; -- Error: UNIQUE constraint failed: index 'index_0';
