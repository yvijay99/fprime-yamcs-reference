"""test_basic.py:

Simple proof-of-concept integration test for YamcsDeployment.
"""

from fprime_gds.common.testing_fw.api import IntegrationTestAPI
import time
from pathlib import Path


def test_is_streaming1(fprime_test_api: IntegrationTestAPI):
    """Test that flight software is streaming telemetry"""
    results = fprime_test_api.assert_telemetry_count(5, timeout=10)
    print(f"Received {len(results)} telemetry items")


def test_send_no_op(fprime_test_api: IntegrationTestAPI):
    """Test sending a simple NO-OP command"""
    fprime_test_api.send_command("CdhCore.cmdDisp.CMD_NO_OP")
    time.sleep(1.5)

    # Verify command was sent
    assert fprime_test_api.get_command_test_history().size() == 1
    print("Command sent successfully")

    # Verify event was generated
    events = fprime_test_api.get_event_test_history()
    assert events.size() > 0
    print(f"Retrieved {events.size()} events from history")


def test_await_event_after_no_op(fprime_test_api: IntegrationTestAPI):
    """send_command then await_event resolves the F Prime ack for the NO-OP"""
    fprime_test_api.send_command("CdhCore.cmdDisp.CMD_NO_OP")
    result = fprime_test_api.await_event(
        "CdhCore.cmdDisp.OpCodeCompleted", timeout=10
    )
    assert result is not None, "Did not receive OpCodeCompleted within 10s"


def test_send_and_assert_event_no_op(fprime_test_api: IntegrationTestAPI):
    """send_and_assert_event bundles send + await for the dispatch ack"""
    fprime_test_api.send_and_assert_event(
        "CdhCore.cmdDisp.CMD_NO_OP",
        events=["CdhCore.cmdDisp.OpCodeDispatched"],
        timeout=10,
    )


def test_event_subhistory_filters(fprime_test_api: IntegrationTestAPI):
    """Subhistories registered via the API only collect matching events"""
    pred = fprime_test_api.get_event_pred(event="CdhCore.cmdDisp.OpCodeCompleted")
    subhistory = fprime_test_api.get_event_subhistory(event_filter=pred)
    try:
        fprime_test_api.send_command("CdhCore.cmdDisp.CMD_NO_OP")
        fprime_test_api.await_event_count(
            1, events="CdhCore.cmdDisp.OpCodeCompleted", history=subhistory, timeout=10
        )
        for item in subhistory.retrieve():
            assert pred(item), "Subhistory contained an event the filter should have rejected"
    finally:
        fprime_test_api.remove_event_subhistory(subhistory)


def test_telemetry_count_with_specific_channel(fprime_test_api: IntegrationTestAPI):
    """Counting telemetry filtered to a single channel still returns updates within the window"""
    results = fprime_test_api.assert_telemetry_count(
        1, channels="CdhCore.cmdDisp.CommandsDispatched", timeout=10
    )
    assert all(
        r.template.get_full_name() == "CdhCore.cmdDisp.CommandsDispatched" for r in results
    )

def test_uplink_file(fprime_test_api: IntegrationTestAPI): 
    """Test that we can uplink a file and receive an event acknowledging it"""
    file_path = Path(__file__).parent / "test_file.txt"
    fprime_test_api.uplink_file(str(file_path), "CdhCore.fileUplink")
    result = fprime_test_api.await_event(
        "FileHandling.fileUplink.FileReceived", timeout=10
    )
    assert result is not None, "Did not receive FileReceived event within 10s"


"""ref_integration_test.py:

A set of integration tests to apply to the Ref app. This is intended to be a reference of integration testing.
"""

import subprocess
import time
from enum import Enum

from fprime_gds.common.testing_fw import predicates
from fprime_gds.common.utils.event_severity import EventSeverity


"""
This enum is includes the values of EventSeverity that can be filtered by the EventManager Component
"""
FilterSeverity = Enum(
    "FilterSeverity",
    "WARNING_HI WARNING_LO COMMAND ACTIVITY_HI ACTIVITY_LO DIAGNOSTIC",
)


def test_is_streaming(fprime_test_api):
    """Test flight software is streaming

    Tests that the flight software is streaming by looking for 5 telemetry items in 10 seconds. Additionally,
    FileHandling.fileUplink.PacketsReceived is verified to be present.
    """
    results = fprime_test_api.assert_telemetry_count(5, timeout=10)
    for result in results:
        msg = "received channel {} update: {}".format(result.get_id(), result.get_str())
        print(msg)
    fprime_test_api.assert_telemetry_count(
        1, channels="FileHandling.fileUplink.PacketsReceived", timeout=3
    )


def set_event_filter(fprime_test_api, severity, enabled):
    """Send command to set event filter

    This helper will send a command that updates the given severity filter on the EventManager
    Component in the Ref App.

    Args:
        fprime_test_api: test api to use
        severity: A valid FilterSeverity Enum utilityValue (str) or an instance of FilterSeverity
        enabled: a boolean of whether or not to enable the given severity

    Return:
        boolean of whether the report filter was set successfully.
    """
    enabled = "ENABLED" if enabled else "DISABLED"
    if isinstance(severity, FilterSeverity):
        severity = severity.name
    else:
        severity = FilterSeverity[severity].name
    try:
        fprime_test_api.send_command(
            "CdhCore.events.SET_EVENT_FILTER",
            [severity, enabled],
        )
        return True
    except AssertionError:
        return False


def set_default_filters(fprime_test_api):
    """Set the default (initial) event filters"""
    set_event_filter(fprime_test_api, "COMMAND", True)
    set_event_filter(fprime_test_api, "ACTIVITY_LO", True)
    set_event_filter(fprime_test_api, "ACTIVITY_HI", True)
    set_event_filter(fprime_test_api, "WARNING_LO", True)
    set_event_filter(fprime_test_api, "WARNING_HI", True)
    set_event_filter(fprime_test_api, "DIAGNOSTIC", False)


def test_send_command(fprime_test_api):
    """Test that commands may be sent

    Tests command send, dispatch, and receipt using send_and_assert command with a pair of NO-OP commands.
    """
    fprime_test_api.send_and_assert_command("CdhCore.cmdDisp.CMD_NO_OP", max_delay=0.1)
    assert fprime_test_api.get_command_test_history().size() == 1
    fprime_test_api.send_and_assert_command("CdhCore.cmdDisp.CMD_NO_OP", max_delay=0.1)
    assert fprime_test_api.get_command_test_history().size() == 2


def test_send_command_args(fprime_test_api):
    """Test that commands may be sent with arguments

    Tests command send, dispatch, and receipt using send_and_assert command with a pair of NO-OP string commands.
    """
    for count, value in enumerate(["Test String 1", "Some other string"], 1):
        events = [
            fprime_test_api.get_event_pred(
                "CdhCore.cmdDisp.NoOpStringReceived", [value]
            )
        ]
        fprime_test_api.send_and_assert_command(
            "CdhCore.cmdDisp.CMD_NO_OP_STRING",
            [
                value,
            ],
            max_delay=0.1,
            events=events,
        )
        assert fprime_test_api.get_command_test_history().size() == count


def test_send_and_assert_no_op(fprime_test_api):
    """Test that commands may be sent in-order

    Tests command send, dispatch, and receipt using send_and_assert command with NO-OP commands. Repeats the series of
    commands 100 times and looks for no re-ordering nor drops.
    """
    length = 100
    failed = 0
    evr_seq = [
        "CdhCore.cmdDisp.OpCodeDispatched",
        "CdhCore.cmdDisp.NoOpReceived",
        "CdhCore.cmdDisp.OpCodeCompleted",
    ]
    any_reordered = False
    dropped = False
    for i in range(0, length):
        results = fprime_test_api.send_and_await_event(
            "CdhCore.cmdDisp.CMD_NO_OP", events=evr_seq, timeout=25
        )
        msg = "Send and assert NO_OP Trial #{}".format(i)
        if not fprime_test_api.test_assert(len(results) == 3, msg, True):
            items = fprime_test_api.get_event_test_history().retrieve()
            last = None
            reordered = False
            for item in items:
                if last is not None:
                    if item.get_time() < last.get_time():
                        fprime_test_api.log(
                            "during iteration #{}, a reordered event was detected: {}".format(
                                i, item
                            )
                        )
                        any_reordered = True
                        reordered = True
                        break
                last = item
            if not reordered:
                fprime_test_api.log(
                    "during iteration #{}, a dropped event was detected".format(i)
                )
                dropped = True
            failed += 1
        fprime_test_api.clear_histories()

    case = True
    case &= fprime_test_api.test_assert(
        not any_reordered, "Expected no events to be reordered.", True
    )
    case &= fprime_test_api.test_assert(
        not dropped, "Expected no events to be dropped.", True
    )
    msg = "{} sequences failed out of {}".format(failed, length)
    case &= fprime_test_api.test_assert(failed == 0, msg, True)

    assert (
        case
    ), "Expected all checks to pass (reordering, dropped events, all passed). See log."


def test_bd_cycles_ascending(fprime_test_api):
    """Test in-order block driver updates"""
    length = 60
    count_pred = predicates.greater_than(length - 1)
    results = fprime_test_api.await_telemetry_count(
        count_pred, "Ref.blockDrv.BD_Cycles", timeout=length
    )
    last = None
    reordered = False
    ascending = True
    for result in results:
        if last is not None:
            last_time = last.get_time()
            result_time = result.get_time()
            if result_time - last_time > 1.5:
                msg = "FSW didn't send an update between {} and {}".format(
                    last_time.to_readable(), result_time.to_readable()
                )
                fprime_test_api.log(msg)
            elif result_time < last_time:
                msg = "There is potential reorder error between {} and {}".format(
                    last_time, result_time
                )
                fprime_test_api.log(msg)
                reordered = True

            if not result.get_val() > last.get_val():
                msg = "Not all updates ascended: First ({}) Second ({})".format(
                    last.get_val(), result.get_val()
                )
                fprime_test_api.log(msg)
                ascending = False

        last = result

    case = True
    case &= fprime_test_api.test_assert(
        ascending, "Expected all updates to ascend.", True
    )
    case &= fprime_test_api.test_assert(
        not reordered, "Expected no updates to be dropped.", True
    )
    fprime_test_api.predicate_assert(
        count_pred,
        len(results) - 1,
        "Expected >= {} updates".format(length - 1),
        True,
    )
    fprime_test_api.assert_telemetry_count(0, "rateGroup1Comp.RgCycleSlips")
    assert case, "Expected all checks to pass (ascending, reordering). See log."


def test_active_logger_filter(fprime_test_api):
    """Test active logger event filtering"""
    set_default_filters(fprime_test_api)
    try:
        cmd_events = fprime_test_api.get_event_pred(severity=EventSeverity.COMMAND)
        actHI_events = fprime_test_api.get_event_pred(
            severity=EventSeverity.ACTIVITY_HI
        )
        pred = predicates.greater_than(0)
        zero = predicates.equal_to(0)
        # Drain time for dispatch events
        time.sleep(10)

        fprime_test_api.send_and_assert_command("CdhCore.cmdDisp.CMD_NO_OP")
        fprime_test_api.send_and_assert_command("CdhCore.cmdDisp.CMD_NO_OP")

        # Wait >1s for ComAggregator's 1Hz timeout to flush all downlink
        time.sleep(1.5)

        fprime_test_api.assert_event_count(pred, cmd_events)
        fprime_test_api.assert_event_count(pred, actHI_events)

        set_event_filter(fprime_test_api, FilterSeverity.COMMAND, False)
        # Drain time for dispatch events
        time.sleep(10)
        fprime_test_api.clear_histories()
        fprime_test_api.send_command("CdhCore.cmdDisp.CMD_NO_OP")
        fprime_test_api.send_command("CdhCore.cmdDisp.CMD_NO_OP")

        # Wait >1s for ComAggregator's 1Hz timeout to flush all downlink
        time.sleep(1.5)

        fprime_test_api.assert_event_count(zero, cmd_events)
        fprime_test_api.assert_event_count(pred, actHI_events)
    finally:
        set_default_filters(fprime_test_api)


def test_signal_generation(fprime_test_api):
    """Tests the behavior of signal gen component"""
    fprime_test_api.send_and_assert_command("Ref.SG4.Settings", [1, 5, 0, "SQUARE"])
    # First telemetry item should fill only the first slot of the history
    history = [0, 0, 0, 5]
    pair_history = [{"time": 0, "value": value} for value in history]
    info = {"type": "SQUARE", "history": history, "pairHistory": pair_history}
    fprime_test_api.send_and_assert_command("Ref.SG4.Toggle")
    fprime_test_api.assert_telemetry("Ref.SG4.History", history, timeout=6)
    fprime_test_api.assert_telemetry("Ref.SG4.PairHistory", pair_history, timeout=3)
    fprime_test_api.assert_telemetry("Ref.SG4.Info", info, timeout=3)
    fprime_test_api.send_and_assert_command("Ref.SG4.Toggle")


def test_seqgen(fprime_test_api):
    """Tests the seqgen can be dispatched (requires localhost testing)"""
    sequence = Path(__file__).parent / "test_seq.seq"
    assert (
        subprocess.run(
            [
                "fprime-seqgen",
                "--dictionary",
                str(fprime_test_api.dictionaries.dictionary_path),
                str(sequence),
                "/tmp/ref_test_int.bin",
            ]
        ).returncode
        == 0
    ), "Failed to run fprime-seqgen"
    fprime_test_api.send_and_assert_command(
        "Ref.cmdSeq.CS_RUN", args=["/tmp/ref_test_int.bin", "BLOCK"], max_delay=5
    )


def test_system_resources(fprime_test_api):
    """Test system resources telemetry meets minimum thresholds"""
    from fprime_gds.common.testing_fw import predicates

    # Test memory usage > 1KB using predicates
    pred_greater_than_1kb = predicates.greater_than(1)

    # Wait for telemetry and verify it meets thresholds
    fprime_test_api.await_telemetry_count(
        pred_greater_than_1kb, "Ref.systemResources.MEMORY_TOTAL", timeout=3
    )

    fprime_test_api.await_telemetry_count(
        pred_greater_than_1kb, "Ref.systemResources.MEMORY_USED", timeout=3
    )

    fprime_test_api.await_telemetry_count(
        pred_greater_than_1kb, "Ref.systemResources.NON_VOLATILE_TOTAL", timeout=3
    )

    fprime_test_api.await_telemetry_count(
        predicates.greater_than(1.0), "Ref.systemResources.CPU", timeout=3
    )