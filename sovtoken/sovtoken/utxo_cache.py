from typing import List

from plenum.common.util import updateNamedTuple
from sovtoken.types import Output
from storage.kv_store import KeyValueStorage
from storage.optimistic_kv_store import OptimisticKVStore


class UTXOCache(OptimisticKVStore):
    # TODO: Extract storing in-memory`level`s like functionality from IdrCache
    """
    Used to answer 2 questions:
        1. Given​ ​an​ ​output,​ ​check​ ​if​ ​it's​ ​spent​ ​or​ ​not​ ​and​ ​return​ ​the​ ​amount​ ​
        held​ ​by​ ​it​ ​if​ ​not spent
        2. Given​ ​an​ ​address,​ ​return​ ​all​ ​valid​ ​UTXOs

    Stores 2 kinds of keys.
        Type1 key is an output prepended with "0"
        Type2 key is an address prepended with "1"

    An unspent output is combination of an address and a reference (seq no)
    to a txn in which this address was transferred some tokens
    """
    def __init__(self, kv_store: KeyValueStorage):
        super().__init__(kv_store)

    # Adds an output to the batch of uncommitted outputs
    def add_output(self, output: Output, is_committed=False):
        type1_key = self._create_type1_key(output)
        type2_key = self._create_type2_key(output.address)
        type1_val = str(output.value)
        try:
            seq_nos = self.get(type2_key, is_committed)
            if isinstance(seq_nos, (bytes, bytearray)):
                seq_nos = seq_nos.decode()
            seq_nos = self._parse_type2_val(seq_nos)
        except KeyError:
            seq_nos = []
        seq_no_str = str(output.seq_no)
        if seq_no_str not in seq_nos:
            seq_nos.append(seq_no_str)
        type2_val = self._create_type2_val(seq_nos)
        batch = [(type1_key, type1_val), (type2_key, type2_val)]
        self.setBatch(batch, is_committed=is_committed)

    # Returns the full output object in the key value store, when given an
    # incomplete output object (with seq_no set to None)
    def get_output(self, output: Output, is_committed=False) -> Output:
        type1_key = self._create_type1_key(output)
        val = self.get(type1_key, is_committed)
        if not val:
            raise KeyError(type1_key)
        return Output(output.address, output.seq_no, int(val))

    # Spends the provided output by fetching it from the key value store
    # (it must have been previously added) and then doing batch ops
    def spend_output(self, output: Output, is_committed=False):
        type1_key = self._create_type1_key(output)
        type2_key = self._create_type2_key(output.address)
        seq_nos = self.get(type2_key, is_committed)
        if isinstance(seq_nos, (bytes, bytearray)):
            seq_nos = seq_nos.decode()
        seq_nos = self._parse_type2_val(seq_nos)
        seq_no_str = str(output.seq_no)
        if seq_no_str not in seq_nos:
            raise KeyError('{} not in {}'.format(seq_no_str, seq_nos))
        seq_nos.remove(seq_no_str)
        batch = [(self._store.WRITE_OP, type1_key, '')]
        type2_val = self._create_type2_val(seq_nos)
        batch.append((self._store.WRITE_OP, type2_key, type2_val))
        self.do_ops_in_batch(batch, is_committed=is_committed)


    # Retrieves a list of the unspent outputs from the key value storage that
    # are associated with the provided address
    def get_unspent_outputs(self, address: str,
                            is_committed=False) -> List[Output]:
        seq_nos = self.get_unspent_seq_nos(address, is_committed)
        return [
            self.get_output(Output(address, seq_no, None), is_committed)
            for seq_no in seq_nos
        ]

    # Retrieves a list of the sequence numbers from the key value storage that
    # are associated with the provided address
    def get_unspent_seq_nos(self, address: str, is_committed) -> List[int]:
        try:
            type2_key = self._create_type2_key(address)
            seq_nos = self.get(type2_key, is_committed)
            if isinstance(seq_nos, (bytes, bytearray)):
                seq_nos = seq_nos.decode()

            return [int(seq_no) for seq_no in self._parse_type2_val(seq_nos)]
        except KeyError:
            return []

    # Creates a type1 key with this format: '0:address:sequence_number'
    # example: '0:2d4daf5d9247997d59ba430567e0c3a4:5354'
    @staticmethod
    def _create_type1_key(output: Output) -> str:
        return '0:{}:{}'.format(output.address, output.seq_no)

    # Creates a type2 key with this format: '1:address'
    # example: '1:2d4daf5d9247997d59ba430567e0c3a4'
    @staticmethod
    def _create_type2_key(address: str) -> str:
        return '1:{}'.format(address)

    # Creates a type2 value from a list of sequence numbers
    @staticmethod
    def _create_type2_val(seq_nos: List) -> str:
        return ':'.join(seq_nos)

    # Retrieves the type2 value from the sequence numbers
    @staticmethod
    def _parse_type2_val(seq_nos: str) -> List:
        return [] if not seq_nos else seq_nos.split(':')
