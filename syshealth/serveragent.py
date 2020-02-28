import socket, select

class ServerAgent:

    def __init__(self, server_port=12345):
        self.port = server_port
        self.socket_list = []
        self.users = {}

    def get_ip(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('',self.port))
        server_socket.listen(5)
        self.socket_list.append(server_socket)

        is_exit = False
        print("ServerAgent: Waiting for clients...")
        while not is_exit:
            ready_to_read,ready_to_write,in_error = select.select(self.socket_list,[],[],0)
            for sock in ready_to_read:
                if sock == server_socket:
                    connect, addr = server_socket.accept()
                    self.socket_list.append(connect)
                else:
                    try:
                        data = sock.recv(2048)
                        #print("Received data: "+data)
                        server_socket.close()
                        return data
                    except:
                        continue


def main():
    print(ServerAgent().get_ip())

if __name__ == "__main__":
    main()