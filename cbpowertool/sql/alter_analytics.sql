
ALTER COLLECTION MyBucket.MyScope.MyCollection ENABLE ANALYTICS;
SELECT * FROM MyBucket.MyScope.MyCollection;

SELECT * FROM Metadata.`Dataverse`;
SELECT VALUE d.DataverseName || '.' || d.DatasetName FROM Metadata.`Dataset` d 
  WHERE d.DataverseName <> "Metadata";





