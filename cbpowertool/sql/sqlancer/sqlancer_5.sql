CREATE TABLE test (c0 REAL);
CREATE INDEX index_0 ON test(c0);
INSERT INTO test(KEY,VALUE) VALUES (UUID(),{"c0":'+/'});
SELECT * FROM test WHERE (c0 LIKE '+/');
