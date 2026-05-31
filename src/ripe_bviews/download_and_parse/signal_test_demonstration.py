



from signal import signal, SIGINT
from time import sleep
import io

class OpenInterruptable(io.FileIO):



    def __init__(self, name, mode='r+b', *args, **kwargs):
        super(OpenInterruptable, self).__init__(name, mode, *args, **kwargs)
        self.is_running = False

    def signal_handler(self, sig, frame):
        print("SIGINT received. Exiting gracefully.")
        self.is_running = False

        import os
        if os.path.exists(self.name):
            os.remove(self.name)
        exit(0)

    def __enter__(self):
        self.file = open("test.txt", "w")
        self.is_running = True

        signal(SIGINT, self.signal_handler)
        return self.file

    def __exit__(self, exc_type, exc_value, traceback):
        self.is_running = False
        self.file.close()


 
  