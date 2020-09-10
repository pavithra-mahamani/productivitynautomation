
-- ALTER COLLECTION MyBucket ENABLE ANALYTICS;
-- SELECT * FROM MyBucket;

ALTER COLLECTION MyBucket.MyScope.MyCollection ENABLE ANALYTICS;
SELECT * FROM MyBucket.MyScope.MyCollection;

CREATE DATAVERSE MyBucket_MyScope_MyCollection;

CREATE ANALYTICS COLLECTION MyBucket_MyScope_MyCollection.MyNewCollection ON MyBucket.MyScope.MyCollection WHERE `role` = "Manager";
SELECT * FROM MyBucket_MyScope_MyCollection.MyNewCollection;

SELECT * FROM Metadata.`Dataverse`;
SELECT VALUE d.DataverseName || '.' || d.DatasetName FROM Metadata.`Dataset` d WHERE d.DataverseName <> "Metadata";





