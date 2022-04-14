import os
from substrateinterface import Keypair


def get_account_from_env(prefix: str) -> str:
    for key, func in [(f'{prefix}_URI', Keypair.create_from_uri),
                      (f'{prefix}_MNEMONIC', Keypair.create_from_mnemonic)]:
        data = os.environ.get(key)
        if not data:
            continue
        try:
            return func(data.replace('"', ''))
        except Exception as e:
            print(e)
            print(data)
            raise
    raise IOError('please setup the provider secret key')
