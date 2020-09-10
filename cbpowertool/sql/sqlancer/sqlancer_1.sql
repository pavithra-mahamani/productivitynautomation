CREATE TABLE test (c1 TEXT PRIMARY KEY) WITHOUT ROWID;
CREATE PRIMARY INDEX ON test;
CREATE INDEX index_0 ON test(c1);
INSERT INTO test (KEY, VALUE) VALUES ("A", {"c1":'A'});
INSERT INTO test (KEY, VALUE) VALUES ("a", {"c1":'a'});
SELECT * FROM test; -- only one row is fetched;
