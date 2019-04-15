import sys
import os
import time
import threading
import cv2
import pyprind

import argparse


class CharFrame:
    ascii_char = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/|()1{}[]?-_+~<>i!lI;:,^`'. "

    # pixels map to characters
    def pixel_to_char(self, luminance):
        return self.ascii_char[int(luminance / 256 * len(self.ascii_char))]

    # converts a normal frame to an ASCII character frame
    def convert(self, img, limit_size=-1, fill=False, wrap=False):
        if limit_size != -1 and (img.shape[0] > limit_size[1] or img.shape[1] > limit_size[0]):
            img = cv2.resize(img, limit_size, interpolation=cv2.INTER_AREA)
        ascii_frame = ''
        blank = ''
        if fill:
            blank += ' ' * (limit_size[0] - img.shape[1])
        if wrap:
            blank += '\n'
        for i in range(img.shape[0]):
            for j in range(img.shape[1]):
                ascii_frame += self.pixel_to_char(img[i, j])
            ascii_frame += blank
        return ascii_frame


class V2Char(CharFrame):
    charVideo = []
    timeInterval = 0.033

    def __init__(self, path):

        if path.endswith('txt'):
            self.load(path)
        else:
            self.gen_char_video(path)

    def gen_char_video(self, filepath):
        self.charVideo = []
        # use opencv read video
        cap = cv2.VideoCapture(filepath)
        self.timeInterval = round(1 / cap.get(5), 3)
        nf = int(cap.get(7))
        print('Generate char video, please wait...')
        for _ in pyprind.prog_bar(range(nf)):
            # change color space, the second parameter is the type conversion, cv2. COLOR_BGR2GRAY said from BGR ↔ Gray
            raw_frame = cv2.cvtColor(cap.read()[1], cv2.COLOR_BGR2GRAY)
            frame = self.convert(raw_frame, os.get_terminal_size(), fill=True)
            self.charVideo.append(frame)
        cap.release()

    def export(self, filepath):
        if not self.charVideo:
            return
        with open(filepath, 'w') as f:
            for frame in self.charVideo:
                # add a newline character to separate each frame
                f.write(frame + '\n')

    def load(self, filepath):
        self.charVideo = []
        for i in open(filepath):
            self.charVideo.append(i[:-1])

    def play(self, stream=1):
        # cursor location escape codes are not compatible with Windows
        if not self.charVideo:
            return
        if stream == 1 and os.isatty(sys.stdout.fileno()):
            self.streamOut = sys.stdout.write
            self.streamFlush = sys.stdout.flush
        elif stream == 2 and os.isatty(sys.stderr.fileno()):
            self.streamOut = sys.stderr.write
            self.streamFlush = sys.stderr.flush
        elif hasattr(stream, 'write'):
            self.streamFlush = stream.flush
            self.streamOut = stream.write
        breakflag = False

        def get_char():
            nonlocal breakflag
            try:
                # if the system is Windows, directly call msvcrt.getch()
                import msvcrt
            except ImportError:
                import termios
                import tty
                # gets the file descriptor for standard input
                fd = sys.stdin.fileno()
                # save the properties of the standard input
                old_settings = termios.tcgetattr(fd)
                try:
                    # set standard input to raw mode
                    tty.setraw(sys.stdin.fileno())
                    # read a char
                    ch = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                if ch:
                    breakflag = True
            else:
                if msvcrt.getch():
                    breakflag = True

        # create thread
        getchar = threading.Thread(target=get_char)
        getchar.daemon = True
        getchar.start()
        # the number of lines drawn by the
        # character output
        rows = len(self.charVideo[0]) // os.get_terminal_size()[0]
        for frame in self.charVideo:
            # when input is received, the loop exits
            if breakflag:
                break
            self.streamOut(frame)
            self.streamFlush()
            time.sleep(self.timeInterval)
            # the cursor is moved up to rows-1 back to the beginning
            self.streamOut('\033[{}A\r'.format(rows - 1))
        # move the cursor down rows-1 to the last row and clear the last row
        self.streamOut('\033[{}B\033[K'.format(rows - 1))
        # empty all lines of the last frame (starting from the penultimate line)
        for i in range(rows - 1):
            # move the cursor up one line
            self.streamOut('\033[1A')
            # clear the cursor line
            self.streamOut('\r\033[K')
        if breakflag:
            self.streamOut('User interrupt!\n')
        else:
            self.streamOut('Finished!\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Video to Char!")
    parser.add_argument('--path', '-p', default='video.mp4', type=str, help='Video path.')
    opt = parser.parse_args()
    v2char = V2Char(opt.path)
    v2char.play()
