--
-- Simple queries
--
select "hello" as greeting;
SELECT VALUE 1;
SELECT DISTINCT * FROM [1, 2, 2, 3] AS foo;
SELECT DISTINCT VALUE foo FROM [1, 2, 2, 3] AS foo;
SELECT VALUE foo FROM [1, 2, 2, 3] AS foo 
-- condition
   WHERE foo > 2;
