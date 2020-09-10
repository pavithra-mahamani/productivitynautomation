CREATE TABLE test (c0);
CREATE PRIMARY INDEX ON test;
CREATE INDEX index_0 ON test(c0);
PRAGMA case_sensitive_like=false;
VACUUM;
SELECT * from test; -- Error: malformed database schema (index_0) - non-deterministic functions prohibited in index expressions;
