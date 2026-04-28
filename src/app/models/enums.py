"""열거형 정의."""
from __future__ import annotations

from enum import Enum, IntEnum


class NRBand(str, Enum):
    """지원하는 NR band."""

    N1 = "n1"
    N3 = "n3"
    N5 = "n5"
    N7 = "n7"
    N8 = "n8"
    N20 = "n20"
    N26 = "n26"
    N28 = "n28"
    N38 = "n38"
    N40 = "n40"
    N41 = "n41"
    N71 = "n71"
    N77 = "n77"
    N78 = "n78"
    N79 = "n79"


class TestType(Enum):
    """시험 종류."""

    HARMONIC = "harmonic"
    INBAND = "inband"
    BILOG = "bilog"


class AntennaPol(Enum):
    """안테나 편파."""

    H = "H"
    V = "V"


class DUTAxis(Enum):
    """DUT 회전축."""

    X = "X"
    Y = "Y"
    Z = "Z"


class DUTAntPosition(Enum):
    """DUT Ant 위치."""

    UPPER = "Upper"
    LOWER = "Lower"


class Modulation(Enum):
    """지원하는 NR modulation 방식."""

    QPSK = "QPSK"
    PI_OVER_2_BPSK = "pi/2 BPSK"


class RBAllocation(Enum):
    """DFT-s 기반 RB allocation 프리셋."""

    INNER_FULL = "Inner_Full"
    INNER_1RB_LEFT = "Inner_1RB_Left"
    INNER_1RB_RIGHT = "Inner_1RB_Right"


class TestChannel(Enum):
    """시험 채널 위치."""

    LOW = "low"
    MID = "mid"
    HIGH = "high"


class InputPath(IntEnum):
    """Switch Box 입력 경로."""

    INPUT1 = 1
    INPUT2 = 2
    INPUT3 = 3


class FilterPath(IntEnum):
    """Switch Box 실제 필터 경로."""

    THRU = 1
    DIRECT_AMP = 2
    HPF_1G = 3
    HPF_3G = 4
    HPF_7G = 5
    HPF_6G = 6
    PORT_1 = 7
    PORT_2 = 8
    PORT_3 = 9
    PORT_4 = 10
    PORT_5 = 11
    PORT_6 = 12
    PORT_7 = 13
    PORT_8 = 14
    PORT_9 = 15
    PORT_10 = 16
    PORT_11 = 17
    PORT_12 = 18
    PORT_13 = 19
    PORT_14 = 20
    PORT_15 = 21
    PORT_16 = 22
    PORT_17 = 23
    PORT_18 = 24


class FilterMode(IntEnum):
    """Range 정의에서 사용하는 필터 선택 모드."""

    BRF = 1
    HPF_1G = 2
    HPF_3G = 3
    HPF_6G = 4
