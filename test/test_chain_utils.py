import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import unittest
from src import chain_utils as ChainUtils
from unittest import mock
from substrateinterface import Keypair


class TestChainUtils(unittest.TestCase):
    def test_publish_did_fail(self):
        mock_substrate_obj = mock.Mock()
        kp = Keypair.create_from_uri('//Moon')
        self.assertRaises(IOError, ChainUtils.publish_did, mock_substrate_obj, None, kp, 'etc/did_doc.json')

    def test_publish_did_succ(self):
        mock_substrate_obj = mock.Mock()
        kp = Keypair.create_from_uri('//Bob//stash')
        ChainUtils.publish_did(mock_substrate_obj, None, kp, 'etc/did_doc.json')

    def test_republish_did_fail(self):
        mock_substrate_obj = mock.Mock()
        kp = Keypair.create_from_uri('//Moon')
        self.assertRaises(IOError, ChainUtils.republish_did, mock_substrate_obj, None, kp, 'etc/did_doc.json')

    def test_republish_did_succ(self):
        mock_substrate_obj = mock.Mock()
        kp = Keypair.create_from_uri('//Bob//stash')
        ChainUtils.republish_did(mock_substrate_obj, None, kp, 'etc/did_doc.json')


if __name__ == '__main__':
    unittest.main()
