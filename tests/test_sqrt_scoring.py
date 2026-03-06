from math import sqrt


def parse_fractional_to_decimal(odds: str) -> float:
    num, den = odds.split("/", 1)
    return 1 + (float(num) / float(den))


def _round2(v: float) -> float:
    return round(v + 1e-12, 2)


def test_fractional_200_1_win_points() -> None:
    dec = parse_fractional_to_decimal("200/1")
    assert dec == 201.0
    points = 5 * sqrt(dec)
    assert _round2(points) == 70.89


def test_fractional_even_money() -> None:
    dec = parse_fractional_to_decimal("1/1")
    assert dec == 2.0
    points = 5 * sqrt(dec)
    assert _round2(points) == 7.07


def test_place_points_example() -> None:
    decimal_win = 201.0
    place_divisor = 5
    place_decimal = 1 + (decimal_win - 1) / place_divisor
    points = 3 * sqrt(place_decimal)
    assert _round2(place_decimal) == 41.0
    assert _round2(points) == 19.21


if __name__ == "__main__":
    test_fractional_200_1_win_points()
    test_fractional_even_money()
    test_place_points_example()
    print("sqrt scoring sanity checks passed")
