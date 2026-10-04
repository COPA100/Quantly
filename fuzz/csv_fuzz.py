"""atheris fuzzer for the portfolio csv parser.

the upload endpoint turns CSVValidationError into a 422, so that is the only
exception parse_portfolio may raise. anything else would surface as a 500.

    pip install atheris pandas numpy
    cd backend && python ../fuzz/csv_fuzz.py ../fuzz/corpus -max_total_time=60

atheris does not run on windows, CI runs it on ubuntu (.github/workflows/fuzz.yml).
"""

import io
import sys
import warnings

import atheris

# only instrument our code, instrumenting pandas makes every run crawl
with atheris.instrument_imports(include=["common"]):
    from common.csv_reader import CSVValidationError, parse_portfolio

warnings.simplefilter("ignore")


def test_one_input(data: bytes) -> None:
    try:
        positions = parse_portfolio(io.BytesIO(data))
    except CSVValidationError:
        return
    assert isinstance(positions, list)
    for p in positions:
        assert set(p) == {"symbol", "quantity", "purchase_price"}


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
