from dataclasses import dataclass
from typing import List

from melati.types.blockchain_format.coin import Coin
from melati.types.blockchain_format.program import SerializedProgram, INFINITE_COST
from melati.util.chain_utils import additions_for_solution
from melati.util.streamable import Streamable, streamable


@dataclass(frozen=True)
@streamable
class CoinSolution(Streamable):
    """
    This is a rather disparate data structure that validates coin transfers. It's generally populated
    with data from different sources, since burned coins are identified by name, so it is built up
    more often that it is streamed.
    """

    coin: Coin
    puzzle_reveal: SerializedProgram
    solution: SerializedProgram

    def additions(self) -> List[Coin]:
        return additions_for_solution(self.coin.name(), self.puzzle_reveal, self.solution, INFINITE_COST)
