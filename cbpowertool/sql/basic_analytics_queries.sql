
SELECT * FROM Metadata.`Dataverse`;
SELECT VALUE d.DataverseName || '.' || d.DatasetName FROM Metadata.`Dataset` d WHERE d.DataverseName <> "Metadata";
ALTER COLLECTION MyBucket ENABLE ANALYTICS;
SELECT * FROM MyBucket;


ALTER COLLECTION MyBucket.MyScope.MyCollection ENABLE ANALYTICS;
SELECT * FROM MyBucket.MyScope.MyCollection;
DROP Dataverse MyBucket.MyScope;

CREATE ANALYTICS COLLECTION MyDataverse.MyNewCollection ON MyBucket.MyScope.MyCollection;
CREATE LINK Local;
SELECT * FROM MyDataverse.MyNewCollection;


-- CREATE / DROP DATAVERSE ns_part_1.ns_part_2;
CREATE DATASET MyDS ON MyBucket;
CREATE DATASET MyDSC ON MyBucket.MyScope.MyCollection;
SELECT * FROM Metadata.`Dataverse`;
-- CREATE / DROP ANALYTICS SCOPE ns_part_1.ns_part_2;
-- CREATE / DROP ANALYTICS COLLECTION analytics_name ON kv_name;
-- REATE / DROP LINK;
-- CREATE ANALYTICS FUNCTION;





