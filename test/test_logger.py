import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import time
import unittest
from unittest import mock

from src.logger import TimeSizeRotatingFileHandler
import logging

TEST_LOG_FOLDER = 'test/tmp'
TEST_LOG_NAME = 'log'
TEST_LOG_PATH = os.path.join(TEST_LOG_FOLDER, TEST_LOG_NAME)


class TestLog(unittest.TestCase):
    def setUp(self):
        try:
            os.system(f'rm -rf {TEST_LOG_FOLDER}')
        except Exception:
            pass
        os.mkdir(TEST_LOG_FOLDER)

    def tearDown(self):
        try:
            os.system(f'rm -rf {TEST_LOG_FOLDER}')
        except Exception:
            pass

    @mock.patch('threading.Timer.start')
    def test_remove_old_file(self, mock_thread_timer):
        mock_thread_timer.return_value = None

        filename = f'{TEST_LOG_FOLDER}/log.1999-12-12_12-12-12.001'
        open(filename, 'w').close()
        with TimeSizeRotatingFileHandler(TEST_LOG_PATH, storeFor=1):
            self.assertFalse(os.path.isfile(filename))

    @mock.patch('threading.Timer.start')
    def test_shouldRolloverSize(self, mock_thread_timer):
        mock_thread_timer.return_value = None

        with TimeSizeRotatingFileHandler(TEST_LOG_PATH, storeFor=1, maxBytes=10) as logger:
            record = logging.makeLogRecord({'msg': '1234567890' * 20})
            self.assertTrue(logger.shouldRollover(record))

    @mock.patch('threading.Timer.start')
    def test_shouldRolloverTime(self, mock_thread_timer):
        mock_thread_timer.return_value = None

        with TimeSizeRotatingFileHandler(TEST_LOG_PATH, storeFor=1, maxBytes=10, when='s') as logger:
            time.sleep(2)
            record = logging.makeLogRecord({'msg': '1'})
            self.assertTrue(logger.shouldRollover(record))

    @mock.patch('threading.Timer.start')
    def test_doRolloverOne(self, mock_thread_timer):
        mock_thread_timer.return_value = None

        open(TEST_LOG_PATH, 'w').close()
        with TimeSizeRotatingFileHandler(TEST_LOG_PATH, storeFor=1, maxBytes=10, when='s') as logger:
            logger.doRollover()
            self.assertEqual(len([_ for _ in os.listdir(TEST_LOG_FOLDER) if _.endswith('.001')]), 1)

    @mock.patch('threading.Timer.start')
    def test_doRolloverNonOverlap(self, mock_thread_timer):
        mock_thread_timer.return_value = None
        log_times = 2

        with TimeSizeRotatingFileHandler(TEST_LOG_PATH, storeFor=1, maxBytes=10, backupCount=4, when='d') as logger:
            for i in range(1, log_times + 1):
                logger.doRollover()
            self.assertEqual(len([_ for _ in os.listdir(TEST_LOG_FOLDER) if _.startswith(TEST_LOG_NAME)]),
                             log_times + 1)

    @mock.patch('threading.Timer.start')
    def test_doRolloverOverlap(self, mock_thread_timer):
        mock_thread_timer.return_value = None
        backup_count = 3

        with TimeSizeRotatingFileHandler(
                TEST_LOG_PATH, storeFor=1, maxBytes=10,
                backupCount=backup_count, when='d') as logger:
            for i in range(1, 20):
                logger.doRollover()
            self.assertEqual(len([_ for _ in os.listdir(TEST_LOG_FOLDER) if _.startswith(TEST_LOG_NAME)]), backup_count + 1)


if __name__ == '__main__':
    unittest.main()
