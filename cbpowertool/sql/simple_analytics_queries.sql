select "hello" as greeting;
SELECT VALUE 1;
SELECT DISTINCT * FROM [1, 2, 2, 3] AS foo;
SELECT DISTINCT VALUE foo FROM [1, 2, 2, 3] AS foo;
SELECT VALUE foo FROM [1, 2, 2, 3] AS foo 
  WHERE foo > 2;
SELECT ARRAY_SUM(DISTINCT [1, 1, 2, 2, 3]);
SELECT * FROM Metadata.`Dataverse`;
SELECT VALUE d.DataverseName || '.' || d.DatasetName FROM Metadata.`Dataset` d 
  WHERE d.DataverseName <> "Metadata";
