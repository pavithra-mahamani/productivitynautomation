for i in {1..10}
do
    for j in {1..10}
    do
	curl -v http://172.23.107.87:8093/query/service -d 'statement=create index indx'$j' on default(rsx) with { "num_replica": 1}' -u Administrator:password
    done
    for j in {1..10}
    do
        curl -v http://172.23.107.87:8093/query/service -d 'statement=DROP INDEX default.indx'$j' USING GSI' -u Administrator:password
    done

    for j in {1..10}
    do
        curl -v http://172.23.107.87:8093/query/service -d 'statement=create index indx'$j' on default1(rsx) with { "num_replica": 1}' -u Administrator:password
    done
    for j in {1..10}
    do
        curl -v http://172.23.107.87:8093/query/service -d 'statement=DROP INDEX default1.indx'$j' USING GSI' -u Administrator:password
    done


    for j in {1..10}
    do
        curl -v http://172.23.107.87:8093/query/service -d 'statement=create index indx'$j' on default3(rsx) with { "num_replica": 1}' -u Administrator:password
    done
    for j in {1..10}
    do
        curl -v http://172.23.107.87:8093/query/service -d 'statement=DROP INDEX default3.indx'$j' USING GSI' -u Administrator:password
    done


    for j in {1..10}
    do
        curl -v http://172.23.107.87:8093/query/service -d 'statement=create index indx'$j' on default4(rsx) with { "num_replica": 1}' -u Administrator:password
    done
    for j in {1..10}
    do
        curl -v http://172.23.107.87:8093/query/service -d 'statement=DROP INDEX default4.indx'$j' USING GSI' -u Administrator:password
    done


done
