import logging
import time
import os

from logging.handlers import TimedRotatingFileHandler
# from datetime import date
from threading import Lock, Timer
import datetime

kibi = 1024


def init_logger(when='d', maxKB=200, backups=4, path="/peaq/simulator/etc/logs/log", storeFor=5):
    maxBytes = kibi * maxKB
    file_handler = TimeSizeRotatingFileHandler(filename=path, when=when, maxBytes=maxBytes, backupCount=backups, storeFor=storeFor)
    console_handler = logging.StreamHandler()

    formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s : %(message)s')

    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger = logging.getLogger('simulator-logger')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


class TimeSizeRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename,
                 when='d', interval=1, backupCount=4, encoding=None,
                 delay=0, utc=0, maxBytes=1000, storeFor=5):
        """ This is just a combination of TimeSizeRotatingFileHandler and RotatingFileHandler (adds maxBytes to TimeSizeRotatingFileHandler)  """
        super().__init__(
            self, filename, when, interval, backupCount, encoding, delay, utc)

        self.maxBytes = maxBytes
        self.storeFor = storeFor
        self.mutex = Lock()
        self.deleteOldFiles()

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.

        we are also comparing times
        """
        with self.mutex:
            if self.stream is None:                 # delay was set...
                self.stream = self._open()
            if self.maxBytes > 0:                   # are we rolling over?
                msg = "%s\n" % self.format(record)
                if self.stream.tell() + len(msg) >= self.maxBytes:
                    return 1
            t = int(time.time())
            if t >= self.rolloverAt:
                return 1
        return 0

    def doRollover(self):
        """
        do a rollover; in this case, a date/time stamp is appended to the filename
        when the rollover happens.  However, you want the file to be named for the
        start of the interval, not the current time.  If there is a backup count,
        then we have to get a list of matching filenames, sort them and remove
        the one with the oldest suffix.
        """
        with self.mutex:
            if self.stream:
                self.stream.close()
            # get the time that this sequence started at and make it a TimeTuple
            currentTime = int(time.time())
            dstNow = time.localtime(currentTime)[-1]
            t = self.rolloverAt - self.interval
            if self.utc:
                timeTuple = time.gmtime(t)
            else:
                timeTuple = time.localtime(t)
                dstThen = timeTuple[-1]
                if dstNow != dstThen:
                    if dstNow:
                        addend = 3600
                    else:
                        addend = -3600
                    timeTuple = time.localtime(t + addend)
            timeSuffix = time.strftime(self.suffix, timeTuple)
            dfn = self.baseFilename + "." + timeSuffix
            if self.backupCount > 0:
                cnt = 1
                dfn2 = "%s.%03d" % (dfn, cnt)
                present = self.isDateLogFilesPresent(timeSuffix)
                if present:
                    while not os.path.exists(dfn2):
                        dfn2 = "%s.%03d" % (dfn, cnt)
                        cnt += 1
                while os.path.exists(dfn2):
                    dfn2 = "%s.%03d" % (dfn, cnt)
                    cnt += 1
                os.rename(self.baseFilename, dfn2)
                for s in self.getFilesToDelete():
                    if (s == self.baseFilename):
                        continue
                    os.remove(s)
            else:
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(self.baseFilename, dfn)
            self.mode = 'w'
            self.stream = self._open()
            newRolloverAt = self.computeRollover(currentTime)
            while newRolloverAt <= currentTime:
                newRolloverAt = newRolloverAt + self.interval
            # If DST changes and midnight or weekly rollover, adjust for this.
            if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
                dstAtRollover = time.localtime(newRolloverAt)[-1]
                if dstNow != dstAtRollover:
                    if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                        addend = -3600
                    else:           # DST bows out before next rollover, so we need to add an hour
                        addend = 3600
                    newRolloverAt += addend
            self.rolloverAt = newRolloverAt

    def getFilesToDelete(self):
        """
        Determine the files to delete when rolling over.
        """
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        prefix = baseName + "."
        plen = len(prefix)
        for fileName in fileNames:
            if fileName[:plen] == prefix:
                suffix = fileName[plen:-4]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dirName, fileName))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[:len(result) - self.backupCount]

        return result

    def isDateLogFilesPresent(self, timeSuffix: str) -> bool:
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        prefix = baseName + "." + timeSuffix
        plen = len(prefix)
        for fileName in fileNames:
            if fileName[:plen] == prefix:
                return True
        return False

    def deleteOldFiles(self) -> None:
        """
        Determine if the filenames in the logging directory exceed storage period and if so delete the file.
        """
        with self.mutex:
            dirName, baseName = os.path.split(self.baseFilename)
            fileNames = os.listdir(dirName)
            prefix = baseName + "."
            plen = len(prefix)
            for fileName in fileNames:
                if (fileName[:plen] == prefix and self.isOld(fileName)):
                    os.remove(os.path.join(dirName, fileName))
            Timer(10, self.deleteOldFiles).start()

    def isOld(self, fileName: str) -> bool:
        """
        Determine if the filename exceeds storage period and if so returns True.
        Else returns False
        """
        dirName, baseName = os.path.split(self.baseFilename)
        if (baseName == fileName):
            return False
        filePath = os.path.join(dirName, fileName)
        if not os.path.exists(filePath):
            return False

        # [TODO] ???
        # today = date.today()
        fileCreationYear = int(fileName[4:8])
        fileCreationMonth = int(fileName[9:11])
        fileCreationDay = int(fileName[12:14])

        start = datetime.datetime(fileCreationYear, fileCreationMonth, fileCreationDay,
                                  0, 0, 0, 0)
        end = datetime.datetime.now()
        delta = end - start

        if (delta.days > self.storeFor):
            return True
        return False
