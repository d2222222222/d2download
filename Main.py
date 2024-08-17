import curses
import socket
import os
import json
import hashlib
import zlib
import threading

uploadsDir = "Uploads"
downloadsDir = "Downloads"
addressBookFile = "address_book.json"
chunkSize = 32 * 1024  # 32 KB chunk size
defaultPort = 5000

# Ensure directories exist
os.makedirs(uploadsDir, exist_ok=True)
os.makedirs(downloadsDir, exist_ok=True)

def calculateFileHash(filePath):
    """Calculate SHA-256 hash for a file."""
    sha256 = hashlib.sha256()
    try:
        with open(filePath, 'rb') as f:
            while chunk := f.read(chunkSize):
                sha256.update(chunk)
    except IOError:
        return None
    return sha256.hexdigest()

def startServer():
    """Start the server to listen for incoming connections."""
    serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSock.bind(('', defaultPort))
    serverSock.listen(5)
    print(f"Server listening on port {defaultPort}...")

    while True:
        clientSock, addr = serverSock.accept()
        print(f"Connection from {addr}")
        threading.Thread(target=handleClient, args=(clientSock, addr)).start()

def handleClient(clientSock, addr):
    """Handle an incoming client connection."""
    try:
        data = clientSock.recv(1024)
        request = json.loads(data.decode())

        if request["request"] == "download":
            filename = request["filename"]
            filePath = os.path.join(uploadsDir, filename)
            if os.path.exists(filePath):
                with open(filePath, 'rb') as f:
                    while chunk := f.read(chunkSize):
                        clientSock.sendall(chunk)
            else:
                clientSock.sendall(b'')
    except Exception as e:
        print(f"Error handling client {addr}: {e}")
    finally:
        clientSock.close()

def listFiles():
    """List files in the Uploads directory."""
    return [f for f in os.listdir(uploadsDir) if os.path.isfile(os.path.join(uploadsDir, f))]

def listFilesUi(stdscr):
    """Display the list of files available for download."""
    stdscr.clear()
    files = listFiles()
    if not files:
        stdscr.addstr(0, 0, "No files available for download.")
    else:
        stdscr.addstr(0, 0, "Files available for download:")
        for idx, file in enumerate(files, start=1):
            stdscr.addstr(idx, 0, f"{idx}. {file}")
    stdscr.refresh()
    stdscr.getch()

def loadAddressBook():
    """Load the address book from a JSON file."""
    try:
        with open(addressBookFile, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def saveAddressBook(addressBook):
    """Save the address book to a JSON file."""
    try:
        with open(addressBookFile, 'w') as f:
            json.dump(addressBook, f)
    except IOError as e:
        print(f"Error: Unable to save address book: {e}")

def listPeersUi(stdscr):
    """Display the list of saved peers."""
    stdscr.clear()
    addressBook = loadAddressBook()
    if not addressBook:
        stdscr.addstr(0, 0, "No peers added.")
    else:
        stdscr.addstr(0, 0, "Saved Peers:")
        for idx, (name, addr) in enumerate(addressBook.items(), start=1):
            stdscr.addstr(idx, 0, f"{idx}. {name} ({addr})")
    stdscr.refresh()
    stdscr.getch()

def addPeerUi(stdscr):
    """UI to add a new peer to the address book."""
    curses.echo()
    stdscr.clear()
    stdscr.addstr(0, 0, "Enter peer name: ")
    name = stdscr.getstr(1, 0).decode()
    stdscr.addstr(2, 0, "Enter IP address and port (e.g., 192.168.1.2:5000): ")
    addr = stdscr.getstr(3, 0).decode()
    
    addressBook = loadAddressBook()
    addressBook[name] = addr
    saveAddressBook(addressBook)
    
    stdscr.addstr(5, 0, f"Peer '{name}' added successfully.")
    stdscr.refresh()
    curses.noecho()
    stdscr.getch()

def downloadFileUi(stdscr):
    """UI to download a file from a peer."""
    curses.echo()
    stdscr.clear()
    stdscr.addstr(0, 0, "Enter peer name or IP address: ")
    peer = stdscr.getstr(1, 0).decode()
    stdscr.addstr(2, 0, "Enter the file name you want to download: ")
    filename = stdscr.getstr(3, 0).decode()

    # Load the peer's address from the address book if a name is given
    addressBook = loadAddressBook()
    if peer in addressBook:
        peer = addressBook[peer]

    stdscr.addstr(5, 0, f"Downloading '{filename}' from {peer}...")

    try:
        ipAddress, port = peer.split(":")
        port = int(port)

        # Connect to the peer and request the file
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((ipAddress, port))
            request = json.dumps({"request": "download", "filename": filename})
            sock.sendall(request.encode())

            # Receive the file in chunks
            filePath = os.path.join(downloadsDir, filename)
            with open(filePath, 'wb') as f:
                while chunk := sock.recv(chunkSize):
                    if not chunk:
                        break
                    f.write(chunk)

            # Verify file integrity
            downloadedFileHash = calculateFileHash(filePath)
            originalFileHash = calculateFileHash(os.path.join(uploadsDir, filename))
            if downloadedFileHash == originalFileHash:
                stdscr.addstr(6, 0, f"'{filename}' downloaded and verified successfully.")
            else:
                stdscr.addstr(6, 0, f"Error: File verification failed. Deleting corrupt file.")
                os.remove(filePath)

    except Exception as e:
        stdscr.addstr(6, 0, f"Error: {e}")

    stdscr.refresh()
    curses.noecho()
    stdscr.getch()

def getLocalIpAddress():
    """Get the local IP address of the machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('10.254.254.254', 1))  # Use any address, it will not actually connect
        ipAddress = s.getsockname()[0]
    except Exception as e:
        print(f"Error: Unable to determine IP address: {e}")
        ipAddress = 'Unknown'
    finally:
        s.close()
    return ipAddress

def displayUi(stdscr):
    """Display the main UI with curses."""
    # Get the local IP address
    ipAddress = getLocalIpAddress()

    # Initialize colors if supported
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Default theme

    # Define menu options
    options = [
        "List Files",
        "List Peers",
        "Add Peer",
        "Download File",
        "Quit"
    ]
    selectedIdx = 0

    # Main loop to keep the UI active
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # Display IP address in the bottom-right corner
        ipText = f"IP: {ipAddress}"
        stdscr.addstr(h - 1, w - len(ipText) - 1, ipText, curses.color_pair(1))

        # Display the menu options
        for idx, option in enumerate(options):
            x = w // 2 - len(option) // 2
            y = h // 2 - len(options) // 2 + idx
            if idx == selectedIdx:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(y, x, option)
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(y, x, option)

        stdscr.refresh()

        key = stdscr.getch()

        if key == curses.KEY_UP and selectedIdx > 0:
            selectedIdx -= 1
        elif key == curses.KEY_DOWN and selectedIdx < len(options) - 1:
            selectedIdx += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:
            if selectedIdx == len(options) - 1:  # Quit option
                break
            elif selectedIdx == 0:  # List Files
                listFilesUi(stdscr)
            elif selectedIdx == 1:  # List Peers
                listPeersUi(stdscr)
            elif selectedIdx == 2:  # Add Peer
                addPeerUi(stdscr)
            elif selectedIdx == 3:  # Download File
                downloadFileUi(stdscr)

curses.wrapper(displayUi)

# Automatically start the server when the program runs
if __name__ == "__main__":
    threading.Thread(target=startServer, daemon=True).start()
