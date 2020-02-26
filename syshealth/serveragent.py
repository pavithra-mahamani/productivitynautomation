import socket, select

port = 12345
socket_list = []
users = {}

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(('',port))
server_socket.listen(5)
socket_list.append(server_socket)

is_exit = False
print("ServerAgent: Waiting for clients...")
while not is_exit:
    ready_to_read,ready_to_write,in_error = select.select(socket_list,[],[],0)
    for sock in ready_to_read:
        if sock == server_socket:
            connect, addr = server_socket.accept()
            socket_list.append(connect)
            connect.send("You are connected from:" + str(addr))
        else:
            try:
                data = sock.recv(2048)
                print("Received data: "+data)
                is_exit = True
                break
            except:
                continue
