"""Standalone tests for surviving an outage of Bosch's activity list - run with:
python3 tests/test_activity_outage.py

coordinator.py imports Home Assistant, so it cannot be imported directly in
this dependency-free suite. The real _async_update_data and the helpers it
uses are extracted from its source and exec'd against stand-ins, the same AST
approach test_persisted_state.py and test_battery_consumption_topup.py use for
the same file. Unlike those, this one runs the whole poll, because what it
guards is the control flow of the poll itself.

Issue #95: on 2026-11-03 Bosch's activity endpoint began answering 404 for
every account. The request sat in the same try as the bike list, so every poll
failed: all cloud entities of a running instance went unavailable, and an
instance restarted during the outage stayed in "setup error, retrying" with
nothing loaded. The activity list is the one thing a poll fetches that nothing
else depends on, so its failure must not fail the poll.

The easy half is to catch the error. The half these tests pin down is what a
poll does when the very first import never happened: _all_activities is then
empty, which does not mean "no rides". Running the consumption tracker on it
would fold the empty id set into its baseline, and once the import finally
succeeded every ride would look new and the Wh used since the outage began would
be spread over the whole backlog.
"""
import __future__
import ast
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_COORD = _ROOT / "custom_components" / "ha_bosch_ebike" / "coordinator.py"
_TREE = ast.parse(_COORD.read_text(encoding="utf-8"))

_CLASS = next(
    n for n in _TREE.body
    if isinstance(n, ast.ClassDef) and n.name == "BoschEBikeCoordinator"
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
        f"BoschEBikeCoordinator no longer defines {name} - update this test "
        "alongside the rename/removal"
    )
    return found


# --- stand-ins for what coordinator.py imports ---------------------------------


class AuthError(Exception):
    pass


class ConfigEntryAuthFailed(Exception):
    pass


class UpdateFailed(Exception):
    pass


class FakeResponseError(Exception):
    """aiohttp.ClientResponseError as far as the coordinator sees it."""

    def __init__(self, status, message, url, body=None):
        super().__init__(f"{status}, message='{message}', url='{url}'")
        self.status = status
        if body is not None:
            self.body = body


class _Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append((record.levelno, record.getMessage()))

    def at(self, level):
        return [m for lvl, m in self.records if lvl == level]


_LOG = _Records()
_logger = logging.getLogger("test_activity_outage")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False
_logger.addHandler(_LOG)


class _FakeDtUtil:
    @staticmethod
    def utcnow():
        return datetime(2026, 11, 3, 9, 20, tzinfo=timezone.utc)


_ns: dict[str, Any] = {
    "Any": Any,
    "AuthError": AuthError,
    "ConfigEntryAuthFailed": ConfigEntryAuthFailed,
    "UpdateFailed": UpdateFailed,
    "SYSTEM_BES2": "bes2",
    "SYSTEM_SMART": "smart",
    "_LOGGER": _logger,
    "dt_util": _FakeDtUtil,
    "compute_range_estimate": lambda *a, **k: {"wh_per_km": None},
    "range_estimate_log_key": lambda est: "key",
    "describe_range_estimate": lambda est: "none",
    "compute_energy_windows": lambda *a, **k: {},
    "compute_unassigned_activities": lambda *a, **k: [],
    "merge_manual_overrides": lambda heuristic, manual: {**heuristic, **manual},
    "timedelta": timedelta,
    "parse_iso_utc": lambda text: (
        datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None
    ),
    "track_distance_m": lambda details: None,
    "corrected_track_distance": lambda summary, track: None,
}

_STATIC = {
    "_describe_fetch_error",
    "_activity_sort_key",
    "_newest_by_start_time",
    "_preserve_derived_distance",
}
_WANTED = _STATIC | {
    "_async_update_data",
    "_fetch_activities_isolated",
    "_recheck_recent_activity_distances",
    "activities_unknown",
}
_nodes = [_method(name) for name in sorted(_WANTED)]
for _node in _nodes:
    # Static methods are exec'd as plain functions and re-wrapped below.
    _node.decorator_list = []
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(
        ast.Module(body=_nodes, type_ignores=[]),
        str(_COORD),
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    ),
    _ns,
)


# --- a fake Bosch API and a coordinator around the real methods -----------------


def act(activity_id, start):
    return {
        "id": activity_id,
        "startTime": start,
        "distance": 5000,
        "title": f"Ride {activity_id}",
    }


class FakeApi:
    access_token = "access"
    access_token_scope = None
    refresh_token = "refresh"

    def __init__(self):
        self.bikes = [{"id": "bike-1", "driveUnit": {"odometer": 1000}, "batteries": []}]
        self.all_activities = [act("a1", "2026-11-02T06:00:00Z"), act("a2", "2026-11-03T06:00:00Z")]
        self.recent = list(self.all_activities)
        self.bikes_error = None
        self.activities_error = None
        self.calls = []

    async def get_bikes(self):
        self.calls.append("bikes")
        if self.bikes_error:
            raise self.bikes_error
        return self.bikes

    async def get_all_activities(self):
        self.calls.append("all_activities")
        if self.activities_error:
            raise self.activities_error
        return [dict(a) for a in self.all_activities]

    async def get_recent_activities(self):
        self.calls.append("recent")
        if self.activities_error:
            raise self.activities_error
        return [dict(a) for a in self.recent]

    async def get_activity_detail(self, activity_id):
        # Same route family as the list (both sit behind the same gateway
        # policy), so it fails together with it.
        self.calls.append("detail")
        if self.activities_error:
            raise self.activities_error
        return {}

    async def get_bike_pass(self, bike_id):
        self.calls.append("bike_pass")
        return {"bikeId": bike_id}

    async def get_service_records(self, bike_id):
        self.calls.append("service_records")
        return []


class _Entries:
    def __init__(self):
        self.updated = []

    def async_update_entry(self, entry, data):
        self.updated.append(data)


class _Hass:
    def __init__(self):
        self.config_entries = _Entries()


class _Entry:
    data = {"access_token": "access", "refresh_token": "refresh"}


class FakeCoordinator:
    _async_update_data = _ns["_async_update_data"]
    _fetch_activities_isolated = _ns["_fetch_activities_isolated"]
    _recheck_recent_activity_distances = _ns["_recheck_recent_activity_distances"]
    activities_unknown = property(_ns["activities_unknown"])
    _describe_fetch_error = staticmethod(_ns["_describe_fetch_error"])
    _activity_sort_key = staticmethod(_ns["_activity_sort_key"])
    _newest_by_start_time = staticmethod(_ns["_newest_by_start_time"])
    _preserve_derived_distance = staticmethod(_ns["_preserve_derived_distance"])

    def __init__(self, api):
        self.api = api
        self.hass = _Hass()
        self.config_entry = _Entry()
        self._system = "smart"
        self._initial_import_done = False
        self._activities_error = None
        self._activities_error_since = None
        self._pending_new_activities = []
        self._all_activities = []
        self._latest_activity_details = None
        self._latest_activity_id = None
        self._latest_activity_details_by_bike = {}
        self._latest_activity_id_by_bike = {}
        self._activity_bike = {}
        self._activity_consumption = {}
        self._manual_activity_bike = {}
        self._maintenance = {}
        self._service_overrides = {}
        self._battery_capacity_wh = {}
        self._battery_field_data = {}
        self._drive_unit_field_data = {}
        self._bike_pass = {}
        self._service_records = {}
        self._capacity_testers = {}
        self._unassigned_activities = []
        self._range_log_keys = {}
        # What the steps the poll hands off to were asked to do.
        self.attribution_calls = []
        self.tracker_calls = []
        self.enrichment_calls = 0
        self.persisted_state_loads = 0
        self.saves = 0
        self.fired = []

    # The hand-offs that derive or persist state from the activity list.
    def attribute_activities_to_bikes(self, bikes, activities):
        self.attribution_calls.append(len(activities))
        return {a["id"]: "bike-1" for a in activities if a.get("id")}

    def _track_battery_consumption(self, bikes):
        self.tracker_calls.append(len(self._all_activities))
        return False

    async def _enrich_activities_with_live_data(self):
        self.enrichment_calls += 1
        return False

    async def async_load_persisted_state(self):
        self.persisted_state_loads += 1

    async def _async_save_state(self):
        self.saves += 1

    # Everything else the poll touches, reduced to the minimum.
    async def _fetch_capacity_testers(self, bikes, system):
        return None

    def _check_service_and_maintenance(self, bikes):
        return False

    def _apply_trick_check(self, activities):
        return None

    def _bike_latest_activity(self, bike_id, fallback_all=False):
        return self._all_activities[0] if self._all_activities else None

    def _fire_new_activity(self, activity, bike_id):
        self.fired.append((activity.get("id"), bike_id))


_ns["BoschEBikeCoordinator"] = FakeCoordinator

NOT_FOUND = FakeResponseError(
    404,
    "Not Found",
    "https://api.bosch-ebike.com/activity/smart-system/v1/activities?limit=20&sort=-startTime",
    body='{"title": "Not Found"}',
)


def _setup():
    _LOG.records.clear()
    api = FakeApi()
    return api, FakeCoordinator(api)


def _poll(coord):
    return asyncio.run(coord._async_update_data())


# --- a running instance: the poll after the import ---------------------------


def test_a_404_on_the_activity_list_does_not_fail_a_running_instance():
    api, coord = _setup()
    _poll(coord)  # healthy first poll: the import
    assert coord._initial_import_done and len(coord._all_activities) == 2

    api.activities_error = NOT_FOUND
    api.calls.clear()
    data = _poll(coord)  # must not raise UpdateFailed

    assert [b["id"] for b in data["bikes"]] == ["bike-1"]
    assert len(data["all_activities"]) == 2, "what was already known is kept"
    assert "detail" in api.calls, (
        "the GPS detail calls run during the outage too, and fail with it"
    )
    assert "bike_pass" in api.calls and "service_records" in api.calls, (
        "the other cloud data is still fetched during the outage"
    )
    assert coord._activities_error and "404" in coord._activities_error


def test_the_log_carries_the_status_and_what_bosch_replied():
    api, coord = _setup()
    _poll(coord)
    api.activities_error = NOT_FOUND
    _poll(coord)
    warnings = _LOG.at(logging.WARNING)
    assert len(warnings) == 1, warnings
    assert "404" in warnings[0] and "Not Found" in warnings[0]
    assert '{"title": "Not Found"}' in warnings[0], "Bosch's own reply is in the log"


def test_the_warning_names_the_scope_of_the_access_token():
    # Whether the token carries the activity scopes is the first thing to ask
    # when Bosch refuses a request that used to work.
    api, coord = _setup()
    api.access_token_scope = "openid activity:summaries:read"
    _poll(coord)
    api.activities_error = NOT_FOUND
    _poll(coord)
    warning = _LOG.at(logging.WARNING)[0]
    assert "[access token scope: openid activity:summaries:read]" in warning
    assert "access token scope" in coord._activities_error, "and in the diagnostics text"


def test_the_warning_has_no_scope_text_when_the_token_has_no_scope():
    api, coord = _setup()
    _poll(coord)
    api.activities_error = NOT_FOUND
    _poll(coord)
    assert "access token scope" not in _LOG.at(logging.WARNING)[0]


def test_a_long_outage_warns_once_and_recovery_is_reported_once():
    api, coord = _setup()
    _poll(coord)
    api.activities_error = NOT_FOUND
    for _ in range(4):
        _poll(coord)
    assert len(_LOG.at(logging.WARNING)) == 1, "one warning per outage, not per poll"
    assert coord._activities_error_since is not None

    api.activities_error = None
    _poll(coord)
    infos = [m for m in _LOG.at(logging.INFO) if "available again" in m]
    assert len(infos) == 1, infos
    assert coord._activities_error is None and coord._activities_error_since is None

    _poll(coord)
    assert len([m for m in _LOG.at(logging.INFO) if "available again" in m]) == 1


def test_a_ride_that_finished_during_the_outage_is_picked_up_afterwards():
    api, coord = _setup()
    _poll(coord)
    api.activities_error = NOT_FOUND
    _poll(coord)
    assert coord.fired == []

    api.activities_error = None
    api.recent = [act("a3", "2026-11-03T08:00:00Z")] + api.all_activities
    _poll(coord)
    assert [a["id"] for a in coord._all_activities] == ["a3", "a2", "a1"]
    assert coord.fired == [("a3", "bike-1")]


def test_a_new_ride_in_a_healthy_poll_is_still_merged_and_announced():
    # The same merge, with no outage involved: routing the request through the
    # helper must not have changed what a healthy poll does.
    api, coord = _setup()
    _poll(coord)
    api.recent = [act("a3", "2026-11-03T08:00:00Z")] + api.all_activities
    _poll(coord)
    assert [a["id"] for a in coord._all_activities] == ["a3", "a2", "a1"]
    assert coord.fired == [("a3", "bike-1")]
    assert _LOG.at(logging.WARNING) == []


def test_an_outage_poll_leaves_the_wh_baseline_and_the_attribution_alone():
    # On a running instance the activity list is only stale during an outage,
    # while the bike list (and its lifetime Wh counter) keeps moving. If the
    # tracker ran now it would move its baseline past a ride it has not seen
    # yet, and that ride would later get no energy at all.
    api, coord = _setup()
    _poll(coord)
    assert coord.tracker_calls == [2] and coord.attribution_calls == [2]
    assert coord.enrichment_calls == 1

    api.activities_error = NOT_FOUND
    _poll(coord)
    _poll(coord)
    assert coord.tracker_calls == [2], "the tracker sat the outage polls out"
    assert coord.attribution_calls == [2]
    assert coord.enrichment_calls == 1

    api.activities_error = None
    api.recent = [act("a3", "2026-11-03T08:00:00Z")] + api.all_activities
    _poll(coord)
    assert coord.tracker_calls == [2, 3], (
        "the first poll with a current list runs it, and sees the new ride"
    )
    assert coord.attribution_calls == [2, 3]
    assert coord.enrichment_calls == 2


def test_a_failing_detail_call_for_a_bikes_own_latest_ride_does_not_fail_the_poll():
    # The per-bike GPS details are only fetched when a bike's own latest ride is
    # not the account wide latest one, which the one bike fake never hits by
    # default. Point it at the older ride so that call site runs.
    api, coord = _setup()
    coord._bike_latest_activity = lambda bike_id, fallback_all=False: coord._all_activities[-1]
    _poll(coord)
    api.activities_error = NOT_FOUND
    api.calls.clear()
    data = _poll(coord)
    assert api.calls.count("detail") >= 2, api.calls
    assert [b["id"] for b in data["bikes"]] == ["bike-1"]


# --- an instance that never got its first import ---------------------------------


def test_a_failed_first_import_does_not_fail_the_setup_and_is_retried():
    api, coord = _setup()
    api.activities_error = NOT_FOUND
    data = _poll(coord)  # the first refresh of a restart during the outage

    assert [b["id"] for b in data["bikes"]] == ["bike-1"]
    assert data["all_activities"] == [] and data["latest_activity"] is None
    assert coord._initial_import_done is False
    assert "bike_pass" in api.calls

    api.activities_error = None
    api.calls.clear()
    data = _poll(coord)
    assert "all_activities" in api.calls, "the import is tried again on the next poll"
    assert coord._initial_import_done is True
    assert len(data["all_activities"]) == 2


def test_nothing_is_derived_from_the_empty_list_before_the_import_succeeded():
    api, coord = _setup()
    api.activities_error = NOT_FOUND
    _poll(coord)
    _poll(coord)

    assert coord.persisted_state_loads == 2, "the stored state is still restored"
    assert coord.tracker_calls == [], (
        "the consumption tracker must not see the empty list: it would store "
        "an empty id set and shift the Wh baseline"
    )
    assert coord.attribution_calls == []
    assert coord.enrichment_calls == 0
    assert coord.saves == 0, "nothing changed, so nothing is written back"

    api.activities_error = None
    _poll(coord)
    assert coord.tracker_calls == [2], "the first look at the real list sees all of it"
    assert coord.attribution_calls == [2]


def test_the_import_failing_is_logged_once_and_the_import_message_is_not_repeated():
    api, coord = _setup()
    api.activities_error = NOT_FOUND
    for _ in range(3):
        _poll(coord)
    assert len(_LOG.at(logging.WARNING)) == 1
    announcements = [m for m in _LOG.at(logging.INFO) if "Initial import" in m]
    assert len(announcements) == 1, announcements


# --- the ride counters during an outage ---------------------------------------------
#
# An empty list after a failed first import means "not loaded", not "no rides".
# Total Rides is a total_increasing sensor: reading 0 there makes the long term
# statistics add the whole history again as soon as Bosch answers, so
# activities_unknown tells the sensors to read unknown instead
# (tests/test_total_rides_outage.py covers the sensor side).


def test_before_the_first_poll_the_counters_are_not_unknown():
    # No outage is known yet, and eBike System 2 never sets one.
    _, coord = _setup()
    assert coord.activities_unknown is False


def test_a_failing_list_before_any_import_makes_the_counters_unknown():
    api, coord = _setup()
    api.activities_error = NOT_FOUND
    _poll(coord)
    assert coord.activities_unknown is True


def test_an_import_that_found_no_rides_is_not_unknown():
    # An account that really has no rides keeps reading 0.
    api, coord = _setup()
    api.all_activities = []
    api.recent = []
    _poll(coord)
    assert coord._initial_import_done is True
    assert coord.activities_unknown is False


def test_an_outage_after_the_import_keeps_the_counters():
    api, coord = _setup()
    _poll(coord)
    api.activities_error = NOT_FOUND
    _poll(coord)
    assert coord._activities_error is not None
    assert coord.activities_unknown is False, "the imported rides are still there to count"


def test_the_counters_come_back_when_the_first_import_finally_works():
    api, coord = _setup()
    api.activities_error = NOT_FOUND
    _poll(coord)
    assert coord.activities_unknown is True
    api.activities_error = None
    _poll(coord)
    assert coord.activities_unknown is False


def test_ebike_system_2_can_never_reach_the_outage_flag():
    # The aggregate sensors exist for eBike System 2 too. Its poll
    # (_update_bes2) loads its trips on every run and neither uses the
    # isolating helper nor sets the flags; if it did, its ride totals would
    # turn unknown during an outage although the trips are loaded.
    touched = {
        node.attr
        for node in ast.walk(_method("_update_bes2"))
        if isinstance(node, ast.Attribute)
        and node.attr
        in {
            "_fetch_activities_isolated",
            "_activities_error",
            "_activities_error_since",
            "_initial_import_done",
        }
    }
    assert not touched, f"_update_bes2 now touches the Smart System outage state: {touched}"


# --- what must keep failing -------------------------------------------------------


def test_an_auth_error_on_the_activity_list_still_asks_for_reauthentication():
    api, coord = _setup()
    _poll(coord)
    api.activities_error = AuthError("token revoked")
    try:
        _poll(coord)
    except ConfigEntryAuthFailed:
        pass
    else:
        raise AssertionError("an auth error must not be mistaken for an outage")
    assert coord._activities_error is None
    assert _LOG.at(logging.WARNING) == []


def test_an_auth_error_during_the_first_import_asks_for_reauthentication_too():
    api, coord = _setup()
    api.activities_error = AuthError("token revoked")
    try:
        _poll(coord)
    except ConfigEntryAuthFailed:
        pass
    else:
        raise AssertionError("an auth error must not be mistaken for an outage")


def test_a_rejected_login_on_the_bike_list_asks_for_reauthentication():
    # Issue #98: refresh_access_token() now raises AuthError when Bosch rejects
    # the refresh token or the Client-ID. The poll has to turn that into the
    # request to sign in again, on a running instance and on the first poll
    # after a restart (which used to end in "setup error, will retry").
    for poll_before in (False, True):
        api, coord = _setup()
        if poll_before:
            _poll(coord)
        api.bikes_error = AuthError("Bosch rejected the refresh token (invalid_client)")
        try:
            _poll(coord)
        except ConfigEntryAuthFailed as err:
            assert "invalid_client" in str(err)
        else:
            raise AssertionError("a rejected login must ask for a new sign-in")


def test_a_failing_bike_list_still_fails_the_update():
    # Without bikes there is nothing to show; only the activity list is optional.
    api, coord = _setup()
    api.bikes_error = FakeResponseError(500, "Server Error", "https://example/bikes")
    try:
        _poll(coord)
    except UpdateFailed as err:
        assert "500" in str(err)
    else:
        raise AssertionError("a failing bike list must fail the update")


# --- the log line -----------------------------------------------------------------


def test_describe_fetch_error_names_the_class_the_message_and_the_reply():
    text = _ns["_describe_fetch_error"](NOT_FOUND)
    assert text.startswith("FakeResponseError: 404, message='Not Found'")
    assert text.endswith("(Bosch replied: {\"title\": \"Not Found\"})")


def test_describe_fetch_error_without_a_body_is_just_the_error():
    text = _ns["_describe_fetch_error"](TimeoutError("took too long"))
    assert text == "TimeoutError: took too long"


def test_describe_fetch_error_flattens_and_shortens_the_reply():
    err = FakeResponseError(502, "Bad Gateway", "https://example/x", body="line one\n\n  line two " + "x" * 400)
    text = _ns["_describe_fetch_error"](err)
    assert "\n" not in text
    reply = text.split("(Bosch replied: ", 1)[1].rstrip(")")
    assert reply.startswith("line one line two x")
    assert len(reply) == 200


# --- structure pin ----------------------------------------------------------------


def test_the_poll_reaches_the_activity_list_only_through_the_helper():
    # Calling the API directly again would put the request back into the try
    # that fails the whole poll.
    update = _method("_async_update_data")
    direct = []
    via_helper = []
    for node in ast.walk(update):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"get_all_activities", "get_recent_activities"}
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "api"
        ):
            direct.append(func.attr)
        if isinstance(func, ast.Attribute) and func.attr == "_fetch_activities_isolated":
            via_helper.extend(
                a.attr for a in node.args if isinstance(a, ast.Attribute)
            )
    assert direct == [], f"called directly: {direct}"
    assert sorted(via_helper) == ["get_all_activities", "get_recent_activities"], via_helper


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
