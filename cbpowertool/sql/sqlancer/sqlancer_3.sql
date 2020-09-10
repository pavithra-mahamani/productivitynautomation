CREATE TABLE test (c0, c1 REAL);
CREATE UNIQUE INDEX index_1 ON test(c0,c1);
INSERT INTO test(KEY, VALUE) VALUES (UUID(),{"c0":'1', "c1":'1'});
INSERT INTO test(key,value) VALUES (UUID(),{"c0":'0', "c1":'1'});
REINDEX; 
-- Error: UNIQUE constraint failed;
