"""Standalone tests for reading the Digital Service Book from API v2 or v1 - run with:
python3 tests/test_service_book_versions.py

api.py imports aiohttp, which this dependency-free suite does not have, so the
real get_service_records is extracted from its source and exec'd against
stand-ins, the same AST approach the coordinator tests use.

Bosch published v2 of the Digital Service Book API (spec 2.0.3, a superset of
v1). v1 still answered when v2 came out and nothing says for how long, so v2 is
tried first and v1 is the fallback. The point of these tests is that the
fallback can never cost data: any HTTP error of v2 falls back, a v1 verdict is
remembered (no failing v2 request on every poll) but re-checked, and what is
not a version problem (auth, network) is not turned into one.
"""
import ast
import asyncio
import logging
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_API = _ROOT / "custom_components" / "ha_bosch_ebike" / "api.py"
_TREE = ast.parse(_API.read_text(encoding="utf-8"))

_CLASS = next(
    n for n in _TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeAPI"
)


def _method(name):
    found = next(
        (
            n for n in _CLASS.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
        ),
        None,
    )
    assert found is not None, (
        f"BoschEBikeAPI no longer defines {name} - update this test alongside "
        "the rename/removal"
    )
    return found


def _module_const(name):
    found = next(
        (
            n for n in _TREE.body
            if isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == name
        ),
        None,
    )
    return found


# --- stand-ins ---------------------------------------------------------------------


class AuthError(Exception):
    pass


class FakeResponseError(Exception):
    """aiohttp.ClientResponseError as far as get_service_records sees it."""

    def __init__(self, status):
        super().__init__(f"{status}, message='x'")
        self.status = status


class _FakeAiohttp:
    ClientResponseError = FakeResponseError


class _Clock:
    now = 1000.0

    @classmethod
    def monotonic(cls):
        return cls.now


class _Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append((record.levelno, record.getMessage()))

    def infos(self):
        return [m for lvl, m in self.records if lvl == logging.INFO]


_LOG = _Records()
_logger = logging.getLogger("test_service_book_versions")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False
_logger.addHandler(_LOG)

V1 = "/service-book/smart-system/v1/service-records"
V2 = "/service-book/smart-system/v2/service-records"

_ns: dict[str, Any] = {
    "Any": Any,
    "AuthError": AuthError,
    "aiohttp": _FakeAiohttp,
    "time": _Clock,
    "_LOGGER": _logger,
    "SERVICE_RECORDS_ENDPOINT": V1,
    "SERVICE_RECORDS_V2_ENDPOINT": V2,
}
_node = _method("get_service_records")
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(
        ast.Module(body=[_node], type_ignores=[]),
        str(_API),
        "exec",
        flags=__import__("__future__").annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)

_interval_node = next(
    n for n in _CLASS.body
    if isinstance(n, ast.Assign)
    and isinstance(n.targets[0], ast.Name)
    and n.targets[0].id == "_SERVICE_BOOK_V2_RECHECK_INTERVAL_S"
)
_interval = ast.literal_eval(
    ast.Expression(body=_interval_node.value)
) if isinstance(_interval_node.value, ast.Constant) else eval(  # 24 * 60 * 60
    compile(ast.Expression(body=_interval_node.value), "<interval>", "eval")
)


class FakeApi:
    get_service_records = _ns["get_service_records"]
    _SERVICE_BOOK_V2_RECHECK_INTERVAL_S = _interval

    def __init__(self):
        self._service_book_version = None
        self._service_book_v2_failed_at = 0.0
        self.calls = []
        # path prefix -> payload, or an exception instance to raise
        self.answers = {V2: {"serviceRecords": ["v2"]}, V1: {"serviceRecords": ["v1"]}}

    async def _get(self, path):
        self.calls.append(path)
        answer = self.answers[path.split("?", 1)[0]]
        if isinstance(answer, BaseException):
            raise answer
        return answer


def _setup():
    _LOG.records.clear()
    _Clock.now = 1000.0
    return FakeApi()


def _fetch(api, bike="bike-1"):
    return asyncio.run(api.get_service_records(bike))


# --- the healthy case --------------------------------------------------------------


def test_v2_is_asked_first_and_used_when_it_answers():
    api = _setup()
    assert _fetch(api) == {"serviceRecords": ["v2"]}
    assert api.calls == [f"{V2}?bikeId=bike-1"]
    assert api._service_book_version == "v2"
    assert len(_LOG.infos()) == 1 and "API v2" in _LOG.infos()[0]


def test_a_working_v2_is_used_on_every_later_poll_without_more_log_lines():
    api = _setup()
    _fetch(api)
    api.calls.clear()
    for _ in range(3):
        _fetch(api)
    assert api.calls == [f"{V2}?bikeId=bike-1"] * 3
    assert len(_LOG.infos()) == 1


# --- v2 not available ----------------------------------------------------------------


def test_a_404_on_v2_falls_back_to_v1_in_the_same_call():
    api = _setup()
    api.answers[V2] = FakeResponseError(404)
    assert _fetch(api) == {"serviceRecords": ["v1"]}
    assert api.calls == [f"{V2}?bikeId=bike-1", f"{V1}?bikeId=bike-1"]
    assert api._service_book_version == "v1"


def test_any_http_error_of_v2_falls_back_not_only_a_404():
    for status in (400, 401, 403, 429, 500, 502, 503):
        api = _setup()
        api.answers[V2] = FakeResponseError(status)
        assert _fetch(api) == {"serviceRecords": ["v1"]}, status


def test_an_unreadable_v2_body_falls_back_too():
    # aiohttp raises ValueError (JSONDecodeError) for a body that is not JSON.
    api = _setup()
    api.answers[V2] = ValueError("Expecting value")
    assert _fetch(api) == {"serviceRecords": ["v1"]}


def test_a_v1_verdict_is_remembered_so_polls_do_not_ask_v2_again():
    api = _setup()
    api.answers[V2] = FakeResponseError(404)
    _fetch(api)
    api.calls.clear()
    _Clock.now += 3600  # an hour later: the next polls
    for _ in range(3):
        _fetch(api)
    assert api.calls == [f"{V1}?bikeId=bike-1"] * 3
    assert len(_LOG.infos()) == 1, "the fallback is announced once"
    assert "using v1" in _LOG.infos()[0]


def test_a_second_bike_in_the_same_poll_does_not_ask_v2_again():
    api = _setup()
    api.answers[V2] = FakeResponseError(404)
    _fetch(api, "bike-1")
    api.calls.clear()
    _fetch(api, "bike-2")
    assert api.calls == [f"{V1}?bikeId=bike-2"]


# --- v2 answers, but with nothing in it ---------------------------------------------------

EMPTY = {"serviceRecords": []}


def test_a_v2_without_records_asks_v1_and_returns_its_records():
    # The spec says v2 answers with an empty list when it has no data for a
    # bike. A v2 that is not filled for this account yet looks exactly like
    # that, while v1 may still hold the records: caching v2 here would turn the
    # last service date, the dealer and the next service date into unknown.
    api = _setup()
    api.answers[V2] = EMPTY
    assert _fetch(api) == {"serviceRecords": ["v1"]}
    assert api.calls == [f"{V2}?bikeId=bike-1", f"{V1}?bikeId=bike-1"]
    assert api._service_book_version == "v1"
    api.calls.clear()
    _fetch(api)
    assert api.calls == [f"{V1}?bikeId=bike-1"], "and v1 is remembered"
    assert len(_LOG.infos()) == 1 and "no records" in _LOG.infos()[0]


def test_when_both_versions_are_empty_the_answer_is_empty_without_extra_requests():
    api = _setup()
    api.answers[V2] = EMPTY
    api.answers[V1] = EMPTY
    assert _fetch(api) == EMPTY
    api.calls.clear()
    _Clock.now += 3600
    for _ in range(3):
        assert _fetch(api) == EMPTY
    assert api.calls == [f"{V1}?bikeId=bike-1"] * 3, "one request per poll, as before v2"
    assert len(_LOG.infos()) == 1


def test_an_answer_without_the_records_key_counts_as_no_records():
    api = _setup()
    api.answers[V2] = {}
    assert _fetch(api) == {"serviceRecords": ["v1"]}
    api.answers[V2] = None
    api._service_book_version = None
    assert _fetch(api) == {"serviceRecords": ["v1"]}


def test_a_v2_that_turns_empty_later_does_not_replace_data_v1_still_has():
    api = _setup()
    _fetch(api)
    assert api._service_book_version == "v2"
    api.answers[V2] = EMPTY
    assert _fetch(api) == {"serviceRecords": ["v1"]}
    assert api._service_book_version == "v1"


def test_a_v2_with_records_never_asks_v1():
    api = _setup()
    _fetch(api)
    _fetch(api)
    assert all(call.startswith(V2) for call in api.calls), api.calls


def test_an_empty_v2_and_a_failing_v1_raise_so_the_last_known_data_stays():
    # Returning v2's empty answer here would overwrite what the coordinator
    # still holds from an earlier poll.
    api = _setup()
    api.answers[V2] = EMPTY
    api.answers[V1] = FakeResponseError(500)
    try:
        _fetch(api)
    except FakeResponseError:
        pass
    else:
        raise AssertionError("v1's error must reach the coordinator")


def test_an_empty_v2_is_asked_again_after_the_recheck_interval():
    api = _setup()
    api.answers[V2] = EMPTY
    _fetch(api)
    api.answers[V2] = {"serviceRecords": ["v2"]}
    _Clock.now += _interval + 1
    assert _fetch(api) == {"serviceRecords": ["v2"]}
    assert api._service_book_version == "v2"


# --- coming back to v2 -----------------------------------------------------------------


def test_v2_is_tried_again_after_the_recheck_interval_and_picked_up_when_it_works():
    api = _setup()
    api.answers[V2] = FakeResponseError(404)
    _fetch(api)
    api.answers[V2] = {"serviceRecords": ["v2"]}
    _Clock.now += _interval - 1
    assert _fetch(api) == {"serviceRecords": ["v1"]}, "not yet"
    _Clock.now += 2
    api.calls.clear()
    assert _fetch(api) == {"serviceRecords": ["v2"]}
    assert api.calls == [f"{V2}?bikeId=bike-1"]
    assert api._service_book_version == "v2"
    api.calls.clear()
    _fetch(api)
    assert api.calls == [f"{V2}?bikeId=bike-1"], "and then v2 stays"


def test_a_failed_recheck_keeps_v1_and_does_not_log_again():
    api = _setup()
    api.answers[V2] = FakeResponseError(404)
    _fetch(api)
    _Clock.now += _interval + 1
    api.calls.clear()
    assert _fetch(api) == {"serviceRecords": ["v1"]}
    assert api.calls == [f"{V2}?bikeId=bike-1", f"{V1}?bikeId=bike-1"]
    assert len(_LOG.infos()) == 1
    api.calls.clear()
    _fetch(api)
    assert api.calls == [f"{V1}?bikeId=bike-1"], "the interval restarted"


def test_v2_that_stops_answering_later_falls_back_to_v1():
    # The day Bosch retires or breaks v2 again: no data lost, back on v1.
    api = _setup()
    _fetch(api)
    api.answers[V2] = FakeResponseError(404)
    assert _fetch(api) == {"serviceRecords": ["v1"]}
    assert api._service_book_version == "v1"


# --- what is not a version problem -------------------------------------------------------


def test_an_auth_error_propagates_and_is_not_taken_for_a_missing_v2():
    api = _setup()
    api.answers[V2] = AuthError("not authenticated")
    try:
        _fetch(api)
    except AuthError:
        pass
    else:
        raise AssertionError("an auth error must not trigger the v1 fallback")
    assert api.calls == [f"{V2}?bikeId=bike-1"]
    assert api._service_book_version is None


def test_a_network_failure_propagates_instead_of_marking_v2_as_broken():
    # It would hit v1 just the same, and a blip must not move a working v2
    # account onto v1 for a day.
    for error in (TimeoutError("slow"), OSError("down")):
        api = _setup()
        _fetch(api)  # v2 works
        api.answers[V2] = error
        try:
            _fetch(api)
        except type(error):
            pass
        else:
            raise AssertionError("a network failure must propagate")
        assert api._service_book_version == "v2"


def test_when_v1_fails_too_its_error_propagates():
    api = _setup()
    api.answers[V2] = FakeResponseError(404)
    api.answers[V1] = FakeResponseError(500)
    try:
        _fetch(api)
    except FakeResponseError as err:
        assert err.status == 500
    else:
        raise AssertionError("the v1 error must reach the coordinator")


# --- structure pin ------------------------------------------------------------------------


def test_the_bike_id_goes_to_both_versions():
    api = _setup()
    api.answers[V2] = FakeResponseError(404)
    _fetch(api, "6c06707b-c489-4577-8c73-87120b7aaeee")
    assert api.calls == [
        f"{V2}?bikeId=6c06707b-c489-4577-8c73-87120b7aaeee",
        f"{V1}?bikeId=6c06707b-c489-4577-8c73-87120b7aaeee",
    ]


def test_the_version_in_use_is_readable_for_the_diagnostics():
    prop = next(
        (
            n for n in _CLASS.body
            if isinstance(n, ast.FunctionDef) and n.name == "service_book_version"
        ),
        None,
    )
    assert prop is not None and any(
        isinstance(d, ast.Name) and d.id == "property" for d in prop.decorator_list
    ), "BoschEBikeAPI must expose service_book_version as a property"
    returned = prop.body[-1]
    assert isinstance(returned, ast.Return) and ast.unparse(returned.value) == "self._service_book_version"


def test_the_endpoint_constants_name_v1_and_v2():
    # The stand-ins above use the literal paths; make sure const.py agrees.
    tree = ast.parse((_ROOT / "custom_components" / "ha_bosch_ebike" / "const.py").read_text(encoding="utf-8"))
    values = {
        n.targets[0].id: n.value.value
        for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
        and isinstance(n.targets[0], ast.Name)
    }
    assert values["SERVICE_RECORDS_ENDPOINT"] == V1
    assert values["SERVICE_RECORDS_V2_ENDPOINT"] == V2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
